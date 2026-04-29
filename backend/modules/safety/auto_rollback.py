"""Phase 8.6 Sprint 1 — G2 자동 롤백 R1~R4 OR 트리거.

R1: 직전 3거래일 모두 신호 0건 → 발동
R2 (v0): 직전 3거래일 모두 폴백 발동 1건 이상 → 발동
        TODO(phase8.6-sprint2): R2 streak 정확화 v1 보강 (가중 streak / 분모 정확화)
R3: 직전 5거래일 모두 활성 tier 종류 ≤ 1 → 발동 (기본 비활성, Sprint 2 후 활성)
R4: 당일 폴백 비중 = fallback_signals / (fallback_signals + primary_candidates) ≥ 0.7 → 발동
        (분모=0 시 미발동 — fail-safe는 G3 회로차단기 책임)

OR 결합: 활성 트리거 중 하나라도 충족 시 should_rollback=True.
발동 시 Redis `phase86:rollback:active`=true(TTL 24h) + 텔레그램 알림.
Phase 8.5 폴백 키(`SECONDARY_POOL_FALLBACK_ENABLED`)는 G3 회로차단기 책임이며 본 모듈은 건드리지 않는다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Awaitable, Callable, Protocol

logger = logging.getLogger(__name__)

PHASE86_ROLLBACK_KEY = "phase86:rollback:active"
ROLLBACK_TTL_SECONDS = 86400  # 24시간

R1_CONSECUTIVE_DAYS = 3
R2_CONSECUTIVE_DAYS = 3
R3_CONSECUTIVE_DAYS = 5
R3_MAX_TIER_COUNT = 1
R4_FALLBACK_SHARE_THRESHOLD = 0.7


class _SettingsLike(Protocol):
    AUTO_ROLLBACK_ENABLED: bool
    AUTO_ROLLBACK_R1_ENABLED: bool
    AUTO_ROLLBACK_R2_ENABLED: bool
    AUTO_ROLLBACK_R3_ENABLED: bool
    AUTO_ROLLBACK_R4_ENABLED: bool


@dataclass
class RollbackEvaluation:
    should_rollback: bool
    triggered: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


def _prev_days(today: date, count: int) -> list[date]:
    """오늘 포함 직전 count일 리스트 (오늘이 첫 원소)."""
    return [today - timedelta(days=i) for i in range(count)]


class AutoRollbackEvaluator:
    """G2 자동 롤백 평가자.

    데이터 소스는 호출 측에서 주입된 loader 콜백을 통해 조회한다.
    프로덕션 사용 시 scheduler가 DB/Redis 어댑터를 주입.
    """

    def __init__(
        self,
        *,
        redis_client,
        session_factory,
        settings: _SettingsLike,
        signal_count_loader: Callable[[date], Awaitable[int]],
        fallback_triggered_loader: Callable[[date], Awaitable[int]],
        fallback_signal_count_loader: Callable[[date], Awaitable[int]],
        primary_candidate_count_loader: Callable[[date], Awaitable[int]],
        tier_count_loader: Callable[[date], Awaitable[int]],
        notifier=None,
    ):
        self._redis = redis_client
        self._session_factory = session_factory
        self._settings = settings
        self._signal_count = signal_count_loader
        self._fallback_triggered = fallback_triggered_loader
        self._fallback_signal_count = fallback_signal_count_loader
        self._primary_candidate_count = primary_candidate_count_loader
        self._tier_count = tier_count_loader
        self._notifier = notifier

    async def evaluate(self, today: date) -> RollbackEvaluation:
        if not self._settings.AUTO_ROLLBACK_ENABLED:
            return RollbackEvaluation(should_rollback=False)

        triggered: list[str] = []
        detail: dict = {}

        if self._settings.AUTO_ROLLBACK_R1_ENABLED and await self._check_r1(today, detail):
            triggered.append("R1")
        if self._settings.AUTO_ROLLBACK_R2_ENABLED and await self._check_r2(today, detail):
            triggered.append("R2")
        if self._settings.AUTO_ROLLBACK_R3_ENABLED and await self._check_r3(today, detail):
            triggered.append("R3")
        if self._settings.AUTO_ROLLBACK_R4_ENABLED and await self._check_r4(today, detail):
            triggered.append("R4")

        return RollbackEvaluation(
            should_rollback=bool(triggered),
            triggered=triggered,
            detail=detail,
        )

    async def _check_r1(self, today: date, detail: dict) -> bool:
        days = _prev_days(today, R1_CONSECUTIVE_DAYS)
        counts = [await self._signal_count(d) for d in days]
        detail["R1_signal_counts"] = {str(d): c for d, c in zip(days, counts)}
        return all(c == 0 for c in counts)

    async def _check_r2(self, today: date, detail: dict) -> bool:
        days = _prev_days(today, R2_CONSECUTIVE_DAYS)
        triggered_counts = [await self._fallback_triggered(d) for d in days]
        detail["R2_fallback_triggered"] = {
            str(d): c for d, c in zip(days, triggered_counts)
        }
        return all(c >= 1 for c in triggered_counts)

    async def _check_r3(self, today: date, detail: dict) -> bool:
        days = _prev_days(today, R3_CONSECUTIVE_DAYS)
        tier_counts = [await self._tier_count(d) for d in days]
        detail["R3_tier_counts"] = {str(d): c for d, c in zip(days, tier_counts)}
        return all(c <= R3_MAX_TIER_COUNT for c in tier_counts)

    async def _check_r4(self, today: date, detail: dict) -> bool:
        fallback_n = await self._fallback_signal_count(today)
        primary_n = await self._primary_candidate_count(today)
        denom = fallback_n + primary_n
        share = (fallback_n / denom) if denom > 0 else 0.0
        detail["R4_fallback_share"] = {
            "fallback_signals": fallback_n,
            "primary_candidates": primary_n,
            "share": share,
        }
        return denom > 0 and share >= R4_FALLBACK_SHARE_THRESHOLD

    async def execute_rollback(self, evaluation: RollbackEvaluation) -> None:
        """발동 시 Redis 일괄 비활성화 토글 + 텔레그램 알림."""
        if not evaluation.should_rollback:
            return

        await self._redis.set(
            PHASE86_ROLLBACK_KEY, "true", ttl=ROLLBACK_TTL_SECONDS
        )
        logger.warning(
            "G2 자동 롤백 발동: triggers=%s detail=%s",
            evaluation.triggered, evaluation.detail,
        )

        if self._notifier is not None:
            msg = (
                f"🚨 Phase 8.6 자동 롤백 발동 — triggers={evaluation.triggered}. "
                f"phase86:rollback:active=true (TTL 24h). 관리자 확인 필요."
            )
            try:
                await self._notifier.send_system_alert("phase86_auto_rollback", msg)
            except Exception:  # noqa: BLE001
                logger.exception("자동 롤백 텔레그램 알림 실패")
