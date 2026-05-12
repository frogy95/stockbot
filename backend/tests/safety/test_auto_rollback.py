"""Phase 8.6 Sprint 1 — Task 4: G2 자동 롤백 R1~R4 OR 트리거 검증.

R1: 0건 3일 연속 → 발동
R2: 폴백 발동 일수 3일 연속 (v0 simplified) → 발동
R3: tier 종류 ≤1 5일 연속 → 발동 (기본 비활성)
R4: 폴백 신호 / (폴백 + 1차) ≥ 0.7 1일 → 발동
OR 결합: R1~R4 중 하나라도 발동 시 should_rollback=True
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from unittest.mock import AsyncMock

import pytest

from modules.safety.auto_rollback import (
    AutoRollbackEvaluator,
    RollbackEvaluation,
)


@dataclass
class _Cfg:
    AUTO_ROLLBACK_ENABLED: bool = True
    AUTO_ROLLBACK_R1_ENABLED: bool = True
    AUTO_ROLLBACK_R2_ENABLED: bool = True
    AUTO_ROLLBACK_R3_ENABLED: bool = False
    AUTO_ROLLBACK_R4_ENABLED: bool = True


def _make_evaluator(
    *,
    daily_signals: dict[date, int] | None = None,
    daily_fallback_triggered: dict[date, int] | None = None,
    daily_fallback_signals: dict[date, int] | None = None,
    daily_primary_candidates: dict[date, int] | None = None,
    daily_tier_count: dict[date, int] | None = None,
    settings: _Cfg | None = None,
) -> AutoRollbackEvaluator:
    return AutoRollbackEvaluator(
        redis_client=AsyncMock(),
        session_factory=AsyncMock(),
        settings=settings or _Cfg(),
        signal_count_loader=AsyncMock(side_effect=lambda d: (daily_signals or {}).get(d, 0)),
        fallback_triggered_loader=AsyncMock(
            side_effect=lambda d: (daily_fallback_triggered or {}).get(d, 0)
        ),
        fallback_signal_count_loader=AsyncMock(
            side_effect=lambda d: (daily_fallback_signals or {}).get(d, 0)
        ),
        primary_candidate_count_loader=AsyncMock(
            side_effect=lambda d: (daily_primary_candidates or {}).get(d, 0)
        ),
        tier_count_loader=AsyncMock(
            side_effect=lambda d: (daily_tier_count or {}).get(d, 0)
        ),
    )


def _days(today: date, n: int) -> list[date]:
    """오늘 포함 직전 n일."""
    from datetime import timedelta
    return [today - timedelta(days=i) for i in range(n)]


# ---------------------------------------------------------------------------
# R1: 0건 3일 연속
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r1_zero_signal_3days_consecutive():
    today = date(2026, 4, 29)
    d3, d2, d1 = _days(today, 3)
    daily = {d3: 0, d2: 0, d1: 0}
    ev = _make_evaluator(daily_signals=daily)
    result = await ev.evaluate(today)
    assert "R1" in result.triggered
    assert result.should_rollback is True


@pytest.mark.asyncio
async def test_r1_with_2days_zero_does_not_trigger():
    today = date(2026, 4, 29)
    d3, d2, d1 = _days(today, 3)
    daily = {d3: 0, d2: 0, d1: 5}
    ev = _make_evaluator(daily_signals=daily)
    result = await ev.evaluate(today)
    assert "R1" not in result.triggered


# ---------------------------------------------------------------------------
# R2 (v0): 폴백 발동 일수 3일 연속
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r2_fallback_streak_3days_triggers():
    today = date(2026, 4, 29)
    d3, d2, d1 = _days(today, 3)
    triggered = {d3: 5, d2: 12, d1: 8}
    ev = _make_evaluator(
        daily_signals={d1: 1, d2: 1, d3: 1},  # R1 회피
        daily_fallback_triggered=triggered,
    )
    result = await ev.evaluate(today)
    assert "R2" in result.triggered


@pytest.mark.asyncio
async def test_r2_fallback_with_2days_does_not_trigger():
    today = date(2026, 4, 29)
    d3, d2, d1 = _days(today, 3)
    triggered = {d3: 5, d2: 0, d1: 8}
    ev = _make_evaluator(
        daily_signals={d1: 1, d2: 1, d3: 1},
        daily_fallback_triggered=triggered,
    )
    result = await ev.evaluate(today)
    assert "R2" not in result.triggered


# ---------------------------------------------------------------------------
# R3: tier ≤1 5일 (기본 비활성)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_tier_diversity_one_5days_disabled_by_default():
    today = date(2026, 4, 29)
    days = _days(today, 5)
    tiers = {d: 1 for d in days}
    ev = _make_evaluator(
        daily_signals={d: 1 for d in days},
        daily_tier_count=tiers,
    )
    result = await ev.evaluate(today)
    assert "R3" not in result.triggered


@pytest.mark.asyncio
async def test_r3_enabled_5days_one_tier_triggers():
    today = date(2026, 4, 29)
    days = _days(today, 5)
    cfg = _Cfg(AUTO_ROLLBACK_R3_ENABLED=True)
    ev = _make_evaluator(
        daily_signals={d: 1 for d in days},
        daily_tier_count={d: 1 for d in days},
        settings=cfg,
    )
    result = await ev.evaluate(today)
    assert "R3" in result.triggered


# ---------------------------------------------------------------------------
# R4: 폴백 비중 ≥0.7 1일 (분모 baseline counter)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r4_fallback_share_above_70pct_triggers():
    today = date(2026, 4, 29)
    # 폴백 7, 1차 3 → 7/(7+3)=0.7
    ev = _make_evaluator(
        daily_signals={today: 10},
        daily_fallback_signals={today: 7},
        daily_primary_candidates={today: 3},
    )
    result = await ev.evaluate(today)
    assert "R4" in result.triggered


@pytest.mark.asyncio
async def test_r4_below_threshold_does_not_trigger():
    today = date(2026, 4, 29)
    ev = _make_evaluator(
        daily_signals={today: 10},
        daily_fallback_signals={today: 4},
        daily_primary_candidates={today: 6},  # 4/10 = 0.4
    )
    result = await ev.evaluate(today)
    assert "R4" not in result.triggered


@pytest.mark.asyncio
async def test_r4_zero_denominator_does_not_trigger():
    """분모 0 — fail-safe로 R4 미발동 (R4는 비율 의미 없음, 별도 fail-safe는 G3 회로차단기 책임)."""
    today = date(2026, 4, 29)
    ev = _make_evaluator(
        daily_signals={today: 1},
        daily_fallback_signals={today: 0},
        daily_primary_candidates={today: 0},
    )
    result = await ev.evaluate(today)
    assert "R4" not in result.triggered


# ---------------------------------------------------------------------------
# OR 결합 + env 토글 + 발동 시 액션
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_or_combination_any_one_triggers():
    today = date(2026, 4, 29)
    days = _days(today, 3)
    ev = _make_evaluator(
        daily_signals={d: 0 for d in days},  # R1만 발동
    )
    result = await ev.evaluate(today)
    assert result.should_rollback is True
    assert result.triggered == ["R1"]


@pytest.mark.asyncio
async def test_env_toggle_disables_individual_trigger():
    today = date(2026, 4, 29)
    days = _days(today, 3)
    cfg = _Cfg(AUTO_ROLLBACK_R1_ENABLED=False)
    ev = _make_evaluator(
        daily_signals={d: 0 for d in days},
        settings=cfg,
    )
    result = await ev.evaluate(today)
    assert "R1" not in result.triggered


@pytest.mark.asyncio
async def test_master_toggle_disables_all():
    today = date(2026, 4, 29)
    days = _days(today, 3)
    cfg = _Cfg(AUTO_ROLLBACK_ENABLED=False)
    ev = _make_evaluator(
        daily_signals={d: 0 for d in days},
        settings=cfg,
    )
    result = await ev.evaluate(today)
    assert result.should_rollback is False
    assert result.triggered == []


@pytest.mark.asyncio
async def test_execute_rollback_disables_phase86_only_not_phase85():
    """발동 시 phase86:rollback:active=true Redis override 설정. Phase 8.5 폴백은 영향 없음."""
    today = date(2026, 4, 29)
    days = _days(today, 3)
    redis = AsyncMock()
    ev = AutoRollbackEvaluator(
        redis_client=redis,
        session_factory=AsyncMock(),
        settings=_Cfg(),
        signal_count_loader=AsyncMock(side_effect=lambda d: 0),
        fallback_triggered_loader=AsyncMock(side_effect=lambda d: 0),
        fallback_signal_count_loader=AsyncMock(side_effect=lambda d: 0),
        primary_candidate_count_loader=AsyncMock(side_effect=lambda d: 0),
        tier_count_loader=AsyncMock(side_effect=lambda d: 0),
    )
    await ev.execute_rollback(RollbackEvaluation(should_rollback=True, triggered=["R1"]))
    redis.set.assert_any_await(
        "phase86:rollback:active", "true", ttl=86400
    )
    # Phase 8.5 폴백 키(SECONDARY_POOL_FALLBACK_ENABLED)는 G2 본 모듈에서 건드리지 않음
    for call in redis.set.await_args_list:
        args, _ = call
        assert "SECONDARY_POOL_FALLBACK_ENABLED" not in args[0]


@pytest.mark.asyncio
async def test_execute_rollback_self_clears_when_no_trigger():
    """2026-05-12 hotfix — should_rollback=False && 기존 활성 시 자동 DEL."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="true")  # 기존 활성
    redis.delete = AsyncMock()
    notifier = AsyncMock()
    notifier.send_system_alert = AsyncMock()
    ev = AutoRollbackEvaluator(
        redis_client=redis,
        session_factory=AsyncMock(),
        settings=_Cfg(),
        signal_count_loader=AsyncMock(),
        fallback_triggered_loader=AsyncMock(),
        fallback_signal_count_loader=AsyncMock(),
        primary_candidate_count_loader=AsyncMock(),
        tier_count_loader=AsyncMock(),
        notifier=notifier,
    )
    await ev.execute_rollback(RollbackEvaluation(should_rollback=False))
    redis.delete.assert_any_await("phase86:rollback:active")
    notifier.send_system_alert.assert_awaited_once()
    args = notifier.send_system_alert.call_args[0]
    assert args[0] == "phase86_auto_rollback"
    assert "해제" in args[1]


@pytest.mark.asyncio
async def test_execute_rollback_no_clear_when_no_existing():
    """should_rollback=False && 기존 비활성 → DEL/알림 모두 미발생."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    notifier = AsyncMock()
    notifier.send_system_alert = AsyncMock()
    ev = AutoRollbackEvaluator(
        redis_client=redis,
        session_factory=AsyncMock(),
        settings=_Cfg(),
        signal_count_loader=AsyncMock(),
        fallback_triggered_loader=AsyncMock(),
        fallback_signal_count_loader=AsyncMock(),
        primary_candidate_count_loader=AsyncMock(),
        tier_count_loader=AsyncMock(),
        notifier=notifier,
    )
    await ev.execute_rollback(RollbackEvaluation(should_rollback=False))
    redis.delete.assert_not_awaited()
    notifier.send_system_alert.assert_not_awaited()
