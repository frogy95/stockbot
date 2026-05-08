"""LIVE 토글 게이트 G-Bt1·G-Bt2·G-Bt3 자동 평가 잡 (Phase 8.6 Sprint 4 Task 5).

- G-Bt1: walk-forward 검증 R²(또는 pass_rate) 격차 ≤ 10%p (학습 대비)
  Task 3에서 BacktestSignalMetric에 학습/검증 split 라벨이 분리되어 있지 않으므로,
  본 평가는 가장 최근 BacktestRun 의 metric 들을 대상으로 simulated vs actual 격차로 근사한다.
  details["mode"]="proxy_simulated_vs_actual" 로 한계를 명시하고, Sprint 5에서 split 라벨
  도입 시 정밀 비교로 교체한다.
- G-Bt2: 직전 30거래일 일별 신호 수 → bootstrap CI 하한 ≥ 1.0
- G-Bt3: 직전 5거래일 일평균 ≥ 1.5 AND 0건 일수 ≤ 30%
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, func, select

from core.config import settings
from core.models.backtest import BacktestRun, BacktestSignalMetric, LiveGateStatus
from core.models.trading import TradeSignal
from core.redis import redis_client
from modules.backtest.bootstrap_ci import bootstrap_ci_lower
from modules.backtest.models import GateEvalResult

logger = logging.getLogger(__name__)


_GBT1_GAP_THRESHOLD = 0.10  # 격차 10%p
_GBT2_CI_THRESHOLD = 1.0
_GBT3_DAILY_MEAN_THRESHOLD = 1.5
_GBT3_ZERO_RATIO_THRESHOLD = 0.30  # 30%
_GBT3_LOOKBACK_DAYS = 5
_GBT2_LOOKBACK_DAYS = 30


class LiveGateEvaluator:
    """LIVE 진입 게이트 평가기 — DB+Redis 기반 G-Bt1/2/3 산출."""

    def __init__(self, session_factory, notifier=None) -> None:
        self.session_factory = session_factory
        self.notifier = notifier

    async def assess(self) -> GateEvalResult | None:
        """게이트 평가 + LiveGateStatus INSERT + 알림. 비활성 시 None."""
        if not settings.LIVE_GATE_AUTO_EVAL_ENABLED:
            logger.info("LIVE_GATE_AUTO_EVAL_ENABLED=false — 게이트 평가 스킵")
            return None

        async with self.session_factory() as session:
            g_bt1 = await self._eval_gbt1(session)
            g_bt2 = await self._eval_gbt2(session)
            g_bt3 = await self._eval_gbt3(session)

            all_passed = bool(g_bt1["passed"] and g_bt2["passed"] and g_bt3["passed"])

            row = LiveGateStatus(
                evaluated_at=datetime.now(timezone.utc),
                g_bt1_passed=bool(g_bt1["passed"]),
                g_bt2_passed=bool(g_bt2["passed"]),
                g_bt3_passed=bool(g_bt3["passed"]),
                all_passed=all_passed,
                details={"g_bt1": g_bt1, "g_bt2": g_bt2, "g_bt3": g_bt3},
            )
            session.add(row)
            try:
                await session.commit()
            except Exception:  # pragma: no cover — mock 호환
                logger.exception("LiveGateStatus commit 실패")

        if not all_passed:
            await self._alert(g_bt1, g_bt2, g_bt3)
            try:
                await redis_client.set(
                    "metrics:live_gate:dry_run_forced", "true", ttl=7 * 24 * 3600
                )
            except Exception:
                logger.warning("redis dry_run_forced set 실패", exc_info=True)

        logger.info(
            "live_gate_assess g_bt1=%s g_bt2=%s g_bt3=%s all=%s",
            g_bt1["passed"], g_bt2["passed"], g_bt3["passed"], all_passed,
            extra={
                "g_bt1": g_bt1,
                "g_bt2": g_bt2,
                "g_bt3": g_bt3,
                "all_passed": all_passed,
            },
        )

        return GateEvalResult(
            g_bt1_passed=bool(g_bt1["passed"]),
            g_bt2_passed=bool(g_bt2["passed"]),
            g_bt3_passed=bool(g_bt3["passed"]),
            details={"g_bt1": g_bt1, "g_bt2": g_bt2, "g_bt3": g_bt3},
        )

    # ---------- G-Bt1 ----------

    async def _eval_gbt1(self, session) -> dict:
        """G-Bt1: walk-forward 학습-검증 격차 ≤ 10%p.

        Task 3 BacktestSignalMetric에 학습/검증 split 라벨이 분리되어 있지 않으므로,
        가장 최근 BacktestRun(status=completed)의 tier별 simulated vs actual 격차로 근사.
        run/metric 부재 시 underspecified=True + passed=True (LIVE 게이트 통과로 간주, 차단 사유 없음).
        """
        stmt = (
            select(BacktestRun)
            .where(BacktestRun.status == "completed")
            .order_by(desc(BacktestRun.completed_at))
            .limit(1)
        )
        result = await session.execute(stmt)
        run = result.scalars().first()
        if run is None:
            return {
                "passed": True,
                "mode": "proxy_simulated_vs_actual",
                "underspecified": True,
                "reason": "no_completed_backtest_run",
                "max_gap": None,
                "threshold": _GBT1_GAP_THRESHOLD,
            }

        metrics_stmt = select(BacktestSignalMetric).where(
            BacktestSignalMetric.run_id == run.run_id
        )
        metrics_result = await session.execute(metrics_stmt)
        metrics = list(metrics_result.scalars().all())
        if not metrics:
            return {
                "passed": True,
                "mode": "proxy_simulated_vs_actual",
                "underspecified": True,
                "reason": "no_metrics",
                "run_id": run.run_id,
                "max_gap": None,
                "threshold": _GBT1_GAP_THRESHOLD,
            }

        gaps: dict[str, float] = {}
        for m in metrics:
            sim = float(m.pass_rate_simulated or 0.0)
            act = float(m.pass_rate_actual) if m.pass_rate_actual is not None else sim
            gaps[m.tier] = abs(sim - act)
        max_gap = max(gaps.values()) if gaps else 0.0
        passed = max_gap <= _GBT1_GAP_THRESHOLD

        return {
            "passed": bool(passed),
            "mode": "proxy_simulated_vs_actual",
            "underspecified": False,
            "run_id": run.run_id,
            "gaps": gaps,
            "max_gap": float(max_gap),
            "threshold": _GBT1_GAP_THRESHOLD,
        }

    # ---------- G-Bt2 ----------

    async def _eval_gbt2(self, session) -> dict:
        """G-Bt2: 직전 30거래일 일별 신호 수 → bootstrap CI 하한 ≥ 1.0."""
        counts = await self._daily_signal_counts(session, lookback_days=_GBT2_LOOKBACK_DAYS)
        ci_lower, ci_upper = bootstrap_ci_lower(counts) if counts else (0.0, 0.0)
        passed = ci_lower >= _GBT2_CI_THRESHOLD
        return {
            "passed": bool(passed),
            "ci_lower": float(ci_lower),
            "ci_upper": float(ci_upper),
            "threshold": _GBT2_CI_THRESHOLD,
            "n_days": len(counts),
        }

    # ---------- G-Bt3 ----------

    async def _eval_gbt3(self, session) -> dict:
        """G-Bt3: 직전 5거래일 일평균 ≥ 1.5 AND 0건 일수 ≤ 30%."""
        counts = await self._daily_signal_counts(session, lookback_days=_GBT3_LOOKBACK_DAYS)
        if not counts:
            return {
                "passed": False,
                "daily_mean": 0.0,
                "zero_ratio": 1.0,
                "n_days": 0,
                "threshold_mean": _GBT3_DAILY_MEAN_THRESHOLD,
                "threshold_zero_ratio": _GBT3_ZERO_RATIO_THRESHOLD,
            }
        daily_mean = sum(counts) / len(counts)
        zero_days = sum(1 for c in counts if c == 0)
        zero_ratio = zero_days / len(counts)
        passed = (
            daily_mean >= _GBT3_DAILY_MEAN_THRESHOLD
            and zero_ratio <= _GBT3_ZERO_RATIO_THRESHOLD
        )
        return {
            "passed": bool(passed),
            "daily_mean": float(daily_mean),
            "zero_ratio": float(zero_ratio),
            "n_days": len(counts),
            "threshold_mean": _GBT3_DAILY_MEAN_THRESHOLD,
            "threshold_zero_ratio": _GBT3_ZERO_RATIO_THRESHOLD,
        }

    # ---------- 공통: 일별 신호 수 산출 ----------

    async def _daily_signal_counts(self, session, *, lookback_days: int) -> list[int]:
        """직전 lookback_days 거래일 일별 TradeSignal 카운트.

        주말/휴일도 포함한 캘린더 일자 기준으로 단순화 — 게이트 평가는 KST 거래일 의도이지만
        SQL 단에서 거래일 캘린더 join은 Sprint 5+ 에서 정밀화한다.
        """
        end = date.today()
        start = end - timedelta(days=lookback_days - 1)
        stmt = (
            select(
                func.date(TradeSignal.created_at).label("d"),
                func.count(TradeSignal.id).label("cnt"),
            )
            .where(
                TradeSignal.created_at >= datetime.combine(start, datetime.min.time()),
                TradeSignal.created_at <= datetime.combine(end, datetime.max.time()),
            )
            .group_by("d")
        )
        result = await session.execute(stmt)
        rows = {r.d: int(r.cnt or 0) for r in result.all()}

        counts: list[int] = []
        for offset in range(lookback_days):
            d = start + timedelta(days=offset)
            counts.append(int(rows.get(d, 0)))
        return counts

    # ---------- 알림 ----------

    async def _alert(self, g_bt1: dict, g_bt2: dict, g_bt3: dict) -> None:
        msg = (
            "⚠️ LIVE 토글 게이트 미충족 — dry_run 강제 유지\n"
            f"G-Bt1: {'PASS' if g_bt1['passed'] else 'FAIL'} "
            f"(max_gap={g_bt1.get('max_gap')})\n"
            f"G-Bt2: {'PASS' if g_bt2['passed'] else 'FAIL'} "
            f"(CI 하한 {g_bt2.get('ci_lower')})\n"
            f"G-Bt3: {'PASS' if g_bt3['passed'] else 'FAIL'} "
            f"(일평균 {g_bt3.get('daily_mean')}, 0건 비율 {g_bt3.get('zero_ratio')})"
        )
        if self.notifier is None:
            return
        try:
            send = getattr(self.notifier, "send", None)
            if send is None:
                send = getattr(self.notifier, "send_system_alert", None)
                if send is not None:
                    await send("live_gate_block", msg)
                    return
            if send is not None:
                await send(msg)
        except Exception:
            logger.warning("telegram send failed", exc_info=True)


async def run_weekly_backtest_and_gate_assess(
    session_factory: Any,
    notifier: Any = None,
) -> None:
    """매주 월요일 00:00 KST 잡 — walk-forward 실행 + LIVE 게이트 평가.

    BACKTEST_ENABLED=False 시 walk-forward 스킵 후 게이트 평가만 수행.
    """
    if settings.BACKTEST_ENABLED:
        # walk-forward 실행 — 별도 세션, 실패해도 게이트 평가는 진행
        from modules.backtest.walkforward import WalkForwardRunner  # 지연 import (순환 회피)

        try:
            async with session_factory() as session:
                runner = WalkForwardRunner(session=session)
                await runner.run(
                    period_end=date.today(),
                    n_days=settings.BACKTEST_DEFAULT_N_DAYS,
                )
        except Exception:
            logger.exception("weekly walkforward 실패 — 게이트 평가는 계속 진행")
    else:
        logger.info("BACKTEST_ENABLED=false — walk-forward 스킵")

    evaluator = LiveGateEvaluator(session_factory=session_factory, notifier=notifier)
    await evaluator.assess()

    try:
        await redis_client.set(
            "scheduler:last_backtest_assess",
            datetime.now(timezone.utc).isoformat(),
            ttl=14 * 24 * 3600,
        )
    except Exception:
        logger.warning("scheduler:last_backtest_assess set 실패", exc_info=True)
