"""Phase 8.6 Sprint 1 — G3 회로차단기 (1차→2차 통과율).

3거래일 연속 일별 통과율 < 임계 시 발동.
일별 통과율 = `screener:candidates:passed:{date}` / `screener:candidates:total:{date}`
(폴백 보강 종목은 분자에서 제외. realtime_screener가 분자/분모를 동시 적재.)

P0 보강 #1 (Daytrader Critical) — 분모(=total)=0인 날이 있으면 데이터 부족으로 보수 해석하여
회로차단기를 강제 ON(should_trigger=True)한다.

P0 보강 #3 (Daytrader Critical) — 회로차단기 활성 상태에서도 청산 계열 신호는 통과시켜
보유 포지션 청산을 막지 않는다(`signal.action in ("exit","stop_loss","take_profit")` 또는
backward-compat `signal_type=="sell"`).

발동 시 Redis override 2종을 동시 설정:
- `phase86:circuit_breaker:active=true` (TTL 24h) — Phase 8.6 변경 일괄 차단
- `settings:override:SECONDARY_POOL_FALLBACK_ENABLED=False` (TTL 24h) — Phase 8.5 폴백 동시 차단
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Protocol

logger = logging.getLogger(__name__)

CIRCUIT_BREAKER_KEY = "phase86:circuit_breaker:active"
PHASE85_FALLBACK_OVERRIDE_KEY = "settings:override:SECONDARY_POOL_FALLBACK_ENABLED"
CIRCUIT_BREAKER_TTL_SECONDS = 86400  # 24시간


class _SettingsLike(Protocol):
    CIRCUIT_BREAKER_ENABLED: bool
    CIRCUIT_BREAKER_PASS_RATE_THRESHOLD: float
    CIRCUIT_BREAKER_CONSECUTIVE_DAYS: int


@dataclass
class CircuitEvaluation:
    should_trigger: bool
    daily_rates: list[tuple[str, float | None]] = field(default_factory=list)
    reason: str = ""
    detail: dict = field(default_factory=dict)


def _is_exit_signal(signal) -> bool:
    """청산 계열 신호 판정 — action 우선, signal_type=="sell" backward-compat."""
    action = getattr(signal, "action", None)
    if action in ("exit", "stop_loss", "take_profit"):
        return True
    return getattr(signal, "signal_type", None) == "sell"


class CircuitBreaker:
    """G3 1차→2차 통과율 회로차단기.

    Phase 8.6 Sprint 1 Task 5 — Daytrader Critical 보강 적용 위치.
    """

    def __init__(
        self,
        *,
        redis_client,
        settings: _SettingsLike,
        notifier=None,
    ):
        self._redis = redis_client
        self._settings = settings
        self._notifier = notifier

    async def evaluate(self, today: date) -> CircuitEvaluation:
        if not self._settings.CIRCUIT_BREAKER_ENABLED:
            return CircuitEvaluation(should_trigger=False, reason="disabled")

        consec_days = self._settings.CIRCUIT_BREAKER_CONSECUTIVE_DAYS
        threshold = self._settings.CIRCUIT_BREAKER_PASS_RATE_THRESHOLD

        days = [today - timedelta(days=i) for i in range(consec_days)]
        daily_rates: list[tuple[str, float | None]] = []
        zero_denominator_day: str | None = None

        for d in days:
            total = await self._read_int(f"screener:candidates:total:{d.isoformat()}")
            passed = await self._read_int(f"screener:candidates:passed:{d.isoformat()}")
            if total == 0:
                daily_rates.append((d.isoformat(), None))
                if zero_denominator_day is None:
                    zero_denominator_day = d.isoformat()
                continue
            daily_rates.append((d.isoformat(), passed / total))

        detail = {
            "threshold": threshold,
            "consecutive_days": consec_days,
            "rates": daily_rates,
        }

        # P0 #1: 분모=0 fail-safe — 데이터 부족 → 강제 ON
        if zero_denominator_day is not None:
            return CircuitEvaluation(
                should_trigger=True,
                daily_rates=daily_rates,
                reason=f"zero_denominator:{zero_denominator_day}",
                detail=detail,
            )

        all_below = all(r is not None and r < threshold for _, r in daily_rates)
        return CircuitEvaluation(
            should_trigger=all_below,
            daily_rates=daily_rates,
            reason="all_below_threshold" if all_below else "above_threshold",
            detail=detail,
        )

    async def execute(self, evaluation: CircuitEvaluation) -> None:
        """회로차단기 발동 — Redis override 2종 + 텔레그램 알림.

        Phase 8.6 변경분(`phase86:circuit_breaker:active`) + Phase 8.5 폴백(`SECONDARY_POOL_FALLBACK_ENABLED`)
        을 동시 차단. DoR §3 G3 명시 사항.

        2026-05-12 hotfix — 미발동(should_trigger=False) 시 기존 활성 상태이면 자동 해제.
        자연 해제 메커니즘 부재로 TTL 24h까지 신호 차단 지속되던 문제 수정.
        """
        if not evaluation.should_trigger:
            existing = await self._redis.get(CIRCUIT_BREAKER_KEY)
            if existing is not None:
                await self._redis.delete(CIRCUIT_BREAKER_KEY)
                await self._redis.delete(PHASE85_FALLBACK_OVERRIDE_KEY)
                logger.warning(
                    "G3 회로차단기 해제: 트리거 조건 풀림 → "
                    "phase86:circuit_breaker:active + SECONDARY_POOL_FALLBACK_ENABLED DEL"
                )
                if self._notifier is not None:
                    msg = (
                        "✅ Phase 8.6 G3 회로차단기 해제 — 트리거 조건 해소. "
                        "phase86:circuit_breaker:active + SECONDARY_POOL_FALLBACK_ENABLED DEL."
                    )
                    try:
                        await self._notifier.send_system_alert(
                            "phase86_circuit_breaker", msg
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception("G3 해제 텔레그램 알림 실패")
            return

        await self._redis.set(
            CIRCUIT_BREAKER_KEY, "true", ttl=CIRCUIT_BREAKER_TTL_SECONDS
        )
        await self._redis.set(
            PHASE85_FALLBACK_OVERRIDE_KEY, "False", ttl=CIRCUIT_BREAKER_TTL_SECONDS
        )

        logger.warning(
            "G3 회로차단기 발동: reason=%s detail=%s",
            evaluation.reason, evaluation.detail,
        )
        if self._notifier is not None:
            msg = (
                f"🚨 Phase 8.6 G3 회로차단기 발동 — reason={evaluation.reason}. "
                f"phase86:circuit_breaker:active=true + SECONDARY_POOL_FALLBACK_ENABLED=False (TTL 24h). "
                "관리자 확인 필요."
            )
            try:
                await self._notifier.send_system_alert("phase86_circuit_breaker", msg)
            except Exception:  # noqa: BLE001
                logger.exception("회로차단기 텔레그램 알림 실패")

    async def is_active(self) -> bool:
        """Redis 플래그 확인 — 활성 상태면 True."""
        try:
            raw = await self._redis.get(CIRCUIT_BREAKER_KEY)
        except Exception:  # noqa: BLE001
            logger.exception("circuit_breaker is_active 조회 실패 (False 반환)")
            return False
        if raw is None:
            return False
        return str(raw).lower() in ("true", "1", "yes")

    async def allow_signal(self, signal) -> bool:
        """신호 허용 여부 — 청산 계열은 항상 통과, 신규 진입만 차단."""
        if _is_exit_signal(signal):
            return True
        if not await self.is_active():
            return True
        return False

    async def _read_int(self, key: str) -> int:
        try:
            raw = await self._redis.get(key)
        except Exception:  # noqa: BLE001
            logger.exception("circuit_breaker 카운터 조회 실패 key=%s (0 반환)", key)
            return 0
        return int(raw or 0)
