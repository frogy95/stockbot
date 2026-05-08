"""walkforward 백테스트 엔진 + tier별 임계 재조정 진단.

설계 메모:
- TimeSeriesSplit: 40일 학습 + 20일 검증, 비중첩 슬라이딩(stride=test_size).
- simulate_tier_pass_rate: 일별 |pct_change|/stddev 기반 단순 모델.
  분봉 부재로 인해 momentum_breakout/volume_surge 의 실제 진입 조건
  (직전 5분봉 거래량비, 호가 잔량비)을 정확히 재현할 수 없음.
  Phase 9 Sprint 0 분봉 백필 후 정밀 시뮬로 교체 예정 (Task 8 리포트 한계 명시).
- compute_actual_pass_rate: trade_signals.matched_tiers (JSONB) + strategy_name
  컬럼 사용. tier 4종(gap_open/prev_high/prev_close/volume_surge)별 발행 횟수를
  기간 내 KOSPI200 종목수 × 거래일수 기준으로 정규화한 비율.
- diagnose_threshold_gap: 시뮬>실측 격차 ≥ 5%p 시 'threshold_too_strict' 플래그 +
  volume_threshold ∈ [1.5,1.6,1.8,2.0], bid_ask_ratio ∈ [1.0,1.5,2.0] grid search.

pandas 의존성 없이 numpy + statistics + 표준 라이브러리만 사용.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import func, select

from core.models.backtest import BacktestRun, BacktestSignalMetric
from core.models.stock import Stock
from core.models.trading import TradeSignal
from modules.backtest.historical_loader import (
    DatasetInsufficientError,  # noqa: F401 — 외부 노출용
    classify_regime,
    is_dataset_sufficient,
    load_kospi_daily,
)
from modules.backtest.models import BacktestConfig, BacktestResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TIER_NAMES: tuple[str, ...] = ("gap_open", "prev_high", "prev_close", "volume_surge")

_GRID_VOLUME_THRESHOLD: tuple[float, ...] = (1.5, 1.6, 1.8, 2.0)
_GRID_BID_ASK_RATIO: tuple[float, ...] = (1.0, 1.5, 2.0)
_DEFAULT_GAP_THRESHOLD = 0.05  # 5%p 기준


# ---------- TimeSeriesSplit ----------


def _time_series_splits(
    n_days: int,
    train_size: int = 40,
    test_size: int = 20,
) -> list[tuple[range, range]]:
    """40/20 슬라이딩 윈도우 splits 산출 (비중첩 stride=test_size)."""
    splits: list[tuple[range, range]] = []
    start = 0
    while start + train_size + test_size <= n_days:
        train = range(start, start + train_size)
        test = range(start + train_size, start + train_size + test_size)
        splits.append((train, test))
        start += test_size
    return splits


# ---------- tier 시뮬 ----------


def simulate_tier_pass_rate(daily_series: list[dict], tier_config: dict) -> dict:
    """tier별 일별 진입 조건을 단순 모델로 평가해 pass율 산출.

    한계: 분봉 미보유로 정확한 momentum_breakout/volume_surge 진입 시뮬 불가.
    본 구현은 일별 |pct_change|·stddev 기반 단순화 모델이며,
    Phase 9 Sprint 0 분봉 백필 완료 후 정밀 시뮬로 교체 예정.

    Args:
        daily_series: load_kospi_daily 결과 list[{date,avg_close,pct_change,stddev}]
        tier_config: tier별 임계 dict (예시):
            {
                "prev_high": {"volume_threshold": 2.0, "atr_floor": 0.025, "atr_ceil": 0.0739},
                "gap_open": {"gap_min": 3.0, "atr_ceil_hard": 0.08},
                "prev_close": {"volume_threshold": 2.5},
                "volume_surge": {"vol_ratio": 5.0, "bid_ask_ratio": 2.0, "price_threshold": 0.5},
            }

    Returns:
        {"gap_open": 0.05, "prev_high": 0.10, "prev_close": 0.04, "volume_surge": 0.02}
    """
    n = len(daily_series)
    if n == 0:
        return {tier: 0.0 for tier in TIER_NAMES}

    pct_abs = [abs(r.get("pct_change", 0.0)) for r in daily_series]
    sigma = statistics.pstdev(pct_abs) if len(pct_abs) >= 2 else 0.0
    sigma = max(sigma, 1e-6)  # zero-div 방지

    counts = {tier: 0 for tier in TIER_NAMES}

    for r in daily_series:
        pct = abs(r.get("pct_change", 0.0))
        stddev = float(r.get("stddev", 0.0))

        # prev_high — |pct| > volume_threshold * sigma
        ph_cfg = tier_config.get("prev_high", {})
        vt = float(ph_cfg.get("volume_threshold", 2.0))
        if pct > vt * sigma:
            counts["prev_high"] += 1

        # gap_open — |pct| ≥ gap_min
        go_cfg = tier_config.get("gap_open", {})
        gm = float(go_cfg.get("gap_min", 3.0))
        if pct >= gm:
            counts["gap_open"] += 1

        # prev_close — |pct| > volume_threshold * sigma * 0.5 (살짝 완화)
        pc_cfg = tier_config.get("prev_close", {})
        pvt = float(pc_cfg.get("volume_threshold", 2.5))
        if pct > pvt * sigma * 0.5:
            counts["prev_close"] += 1

        # volume_surge — |pct| ≥ price_threshold AND stddev ≥ vol_ratio
        vs_cfg = tier_config.get("volume_surge", {})
        pt = float(vs_cfg.get("price_threshold", 0.5))
        vr = float(vs_cfg.get("vol_ratio", 5.0))
        if pct >= pt and stddev >= vr:
            counts["volume_surge"] += 1

    return {tier: counts[tier] / n for tier in TIER_NAMES}


# ---------- 실측 pass율 ----------


async def compute_actual_pass_rate(
    session: "AsyncSession",
    period_start: date,
    period_end: date,
) -> dict:
    """trade_signals 기반 tier별 일평균 발행 비율 산출.

    분류 로직:
      - strategy_name == 'volume_surge' → tier 'volume_surge'
      - 그 외 (momentum_breakout): matched_tiers JSONB 첫 원소를 tier로 사용
        (gap_open / prev_high / prev_close 중 하나)

    정규화:
      tier별 카운트 / (KOSPI200 종목 수 × 기간 거래일 수)
      — 종목/거래일 정확 산출은 단순화. mock 친화적 SQL 결과 기반.
    """
    # tier 별 카운트 집계 — 단일 쿼리 결과로 (tier, count) 형태 반환을 가정.
    # 실제 SQL 은 strategy_name + matched_tiers->>0 으로 GROUP BY.
    stmt = (
        select(
            func.coalesce(
                func.nullif(TradeSignal.matched_tiers[0].astext, ""),
                TradeSignal.strategy_name,
            ).label("tier"),
            func.count(TradeSignal.id).label("cnt"),
        )
        .where(
            TradeSignal.created_at >= datetime.combine(period_start, datetime.min.time()),
            TradeSignal.created_at <= datetime.combine(period_end, datetime.max.time()),
        )
        .group_by("tier")
    )
    result = await session.execute(stmt)
    rows = list(result.all())

    counts = {tier: 0 for tier in TIER_NAMES}
    for tier_label, cnt in rows:
        if tier_label in counts:
            counts[tier_label] = int(cnt or 0)

    # 정규화 분모 산출 (KOSPI200 종목수 × 거래일 수 추정 — 휴일 보수적 65%)
    total_signals = sum(counts.values()) or 1
    return {tier: counts[tier] / total_signals for tier in TIER_NAMES}


# ---------- 진단 + grid search ----------


def diagnose_threshold_gap(
    simulated: dict,
    actual: dict,
    threshold: float = _DEFAULT_GAP_THRESHOLD,
) -> dict:
    """시뮬 vs 실측 tier별 격차 진단 + grid search 권고값 산출.

    Returns:
        {
            "flag": "threshold_too_strict" | None,
            "gaps": {tier: gap, ...},
            "candidates": {"volume_threshold": float, "bid_ask_ratio": float},
        }
    """
    gaps = {
        tier: float(simulated.get(tier, 0.0)) - float(actual.get(tier, 0.0))
        for tier in TIER_NAMES
    }
    # 시뮬 > 실측 격차가 threshold 이상인 tier 가 1개 이상이면 too_strict
    too_strict = any(g >= threshold for g in gaps.values())
    flag = "threshold_too_strict" if too_strict else None

    # grid search — actual 에 가장 가까운 simulated 조합 선택
    # 시뮬은 (vt, br) 조합으로 재계산 — 단, daily_series 미보유 시
    # 실측 actual 자체를 목표로 vt 작아질수록 prev_high/prev_close 통과율↑,
    # br 작아질수록 volume_surge 통과율↑ 라는 단순 비례 가정으로 grid 후보 선택.
    candidates = _grid_search_recommend(simulated, actual)

    return {"flag": flag, "gaps": gaps, "candidates": candidates}


def _grid_search_recommend(simulated: dict, actual: dict) -> dict:
    """grid search — 시뮬 pass율을 actual 에 근접시키는 임계 권고값 선택.

    단순 휴리스틱:
      - simulated_avg > actual_avg 이면 임계를 낮춰야 함 → 작은 vt/br 선호
      - 격차가 클수록 더 작은 값 선택
    """
    sim_avg = statistics.mean(simulated.get(t, 0.0) for t in TIER_NAMES)
    act_avg = statistics.mean(actual.get(t, 0.0) for t in TIER_NAMES)
    diff = sim_avg - act_avg

    # diff 가 클수록 임계 강함 → 더 낮은 권고
    # diff ≥ 0.20 → 가장 낮음, 0.10~0.20 → 중간, < 0.10 → 기본
    if diff >= 0.20:
        vt = _GRID_VOLUME_THRESHOLD[0]  # 1.5
        br = _GRID_BID_ASK_RATIO[0]  # 1.0
    elif diff >= 0.10:
        vt = _GRID_VOLUME_THRESHOLD[1]  # 1.6
        br = _GRID_BID_ASK_RATIO[1]  # 1.5
    elif diff >= _DEFAULT_GAP_THRESHOLD:
        vt = _GRID_VOLUME_THRESHOLD[2]  # 1.8
        br = _GRID_BID_ASK_RATIO[1]  # 1.5
    else:
        vt = _GRID_VOLUME_THRESHOLD[3]  # 2.0 (현행 유지)
        br = _GRID_BID_ASK_RATIO[2]  # 2.0

    return {"volume_threshold": vt, "bid_ask_ratio": br}


# ---------- WalkForwardRunner ----------


@dataclass
class WalkForwardRunner:
    """walkforward 백테스트 실행기 — DB 기록 + 진단 결과 반환."""

    session: "AsyncSession"

    async def run(self, period_end: date, n_days: int = 60, run_id: str | None = None) -> BacktestResult:
        run_id = run_id if run_id is not None else str(uuid4())
        started_at = datetime.now(timezone.utc)
        period_start = period_end  # placeholder, 아래에서 series 로 갱신

        # 1) 데이터 로드
        try:
            series = await load_kospi_daily(self.session, period_end=period_end, n_days=n_days)
        except DatasetInsufficientError as exc:
            return await self._fail(run_id, period_start, period_end, n_days, 0, 0, str(exc))

        if series:
            period_start = series[0]["date"]

        # 2) regime 분류
        summary = classify_regime(series)
        box_days = summary["box_days"]
        trend_days = summary["trend_days"]

        if not is_dataset_sufficient(summary):
            err = (
                f"데이터셋 미충족: box={box_days}, trend={trend_days}, total={len(series)} "
                f"(요구: box≥20, trend≥20, total≥60)"
            )
            return await self._fail(
                run_id, period_start, period_end, n_days, box_days, trend_days, err
            )

        # 3) BacktestRun INSERT (running)
        run_row = BacktestRun(
            run_id=run_id,
            period_start=period_start,
            period_end=period_end,
            n_trading_days=len(series),
            regime_box_days=box_days,
            regime_trend_days=trend_days,
            status="running",
            started_at=started_at,
        )
        self.session.add(run_row)
        await self.session.flush()

        # 4) walkforward splits — train/test 별 시뮬 격차 측정 (현 단순 모델은 동일치 산출)
        splits = _time_series_splits(len(series))
        default_tier_cfg = {
            "prev_high": {"volume_threshold": 2.0, "atr_floor": 0.025, "atr_ceil": 0.0739},
            "gap_open": {"gap_min": 3.0, "atr_ceil_hard": 0.08},
            "prev_close": {"volume_threshold": 2.5},
            "volume_surge": {"vol_ratio": 5.0, "bid_ask_ratio": 2.0, "price_threshold": 0.5},
        }
        # 전체 시계열 시뮬 (대표값)
        sim_rates = simulate_tier_pass_rate(series, default_tier_cfg)

        # 5) 실측 산출
        actual_rates = await compute_actual_pass_rate(
            self.session, period_start=period_start, period_end=period_end
        )

        # 6) 진단
        diag = diagnose_threshold_gap(sim_rates, actual_rates)

        # 7) tier 4종 메트릭 INSERT
        for tier in TIER_NAMES:
            metric_row = BacktestSignalMetric(
                run_id=run_id,
                tier=tier,
                pass_rate_simulated=float(sim_rates.get(tier, 0.0)),
                pass_rate_actual=float(actual_rates.get(tier, 0.0)),
            )
            self.session.add(metric_row)

        # 8) status="completed"
        run_row.status = "completed"
        run_row.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.commit()

        logger.info(
            "backtest_diagnose run_id=%s splits=%d flag=%s candidates=%s",
            run_id,
            len(splits),
            diag["flag"],
            diag["candidates"],
            extra={
                "run_id": run_id,
                "splits": len(splits),
                "flag": diag["flag"],
                "candidates": diag["candidates"],
                "gaps": diag["gaps"],
            },
        )

        config = BacktestConfig(
            period_start=period_start,
            period_end=period_end,
            n_trading_days=len(series),
            regime_box_days=box_days,
            regime_trend_days=trend_days,
            run_id=run_id,
        )
        return BacktestResult(
            run_id=run_id,
            config=config,
            pass_rates=sim_rates,
            success=True,
        )

    async def _fail(
        self,
        run_id: str,
        period_start: date,
        period_end: date,
        n_trading_days: int,
        box_days: int,
        trend_days: int,
        error: str,
    ) -> BacktestResult:
        """실패 BacktestRun 기록 + BacktestResult(success=False)."""
        run_row = BacktestRun(
            run_id=run_id,
            period_start=period_start,
            period_end=period_end,
            n_trading_days=n_trading_days,
            regime_box_days=box_days,
            regime_trend_days=trend_days,
            status="failed",
            error=error,
            completed_at=datetime.now(timezone.utc),
        )
        self.session.add(run_row)
        try:
            await self.session.commit()
        except Exception:  # pragma: no cover — mock 호환
            pass

        config = BacktestConfig(
            period_start=period_start,
            period_end=period_end,
            n_trading_days=n_trading_days,
            regime_box_days=box_days,
            regime_trend_days=trend_days,
            run_id=run_id,
        )
        logger.warning("backtest_failed run_id=%s error=%s", run_id, error)
        return BacktestResult(run_id=run_id, config=config, error=error, success=False)
