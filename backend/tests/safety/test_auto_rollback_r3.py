"""Phase 8.6 Sprint 3 — Task 4: R3 활성화 검증 (AUTO_ROLLBACK_R3_ENABLED=True 기준).

Task 1에서 AUTO_ROLLBACK_R3_ENABLED 기본값이 True로 변경됨.
기존 test_auto_rollback.py의 R3 기본 비활성 케이스와 독립적으로
활성화 상태(True)에서의 동작 4가지를 추가 검증한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from modules.safety.auto_rollback import AutoRollbackEvaluator


@dataclass
class _CfgR3On:
    """R3 활성화된 설정 (Task 1 이후 프로덕션 기본값 반영)."""

    AUTO_ROLLBACK_ENABLED: bool = True
    AUTO_ROLLBACK_R1_ENABLED: bool = False  # R1/R2/R4는 꺼서 R3 격리 테스트
    AUTO_ROLLBACK_R2_ENABLED: bool = False
    AUTO_ROLLBACK_R3_ENABLED: bool = True
    AUTO_ROLLBACK_R4_ENABLED: bool = False


def _make_r3_evaluator(
    *,
    daily_tier_count: dict[date, int],
    settings: _CfgR3On | None = None,
) -> AutoRollbackEvaluator:
    return AutoRollbackEvaluator(
        redis_client=AsyncMock(),
        session_factory=AsyncMock(),
        settings=settings or _CfgR3On(),
        signal_count_loader=AsyncMock(return_value=5),
        fallback_triggered_loader=AsyncMock(return_value=0),
        fallback_signal_count_loader=AsyncMock(return_value=0),
        primary_candidate_count_loader=AsyncMock(return_value=10),
        tier_count_loader=AsyncMock(
            side_effect=lambda d: daily_tier_count.get(d, 2)
        ),
    )


def _prev_days(today: date, n: int) -> list[date]:
    return [today - timedelta(days=i) for i in range(n)]


# ---------------------------------------------------------------------------
# 케이스 1: tier 다양성 1종 5거래일 연속 → R3 발동
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_enabled_one_tier_5days_consecutive_triggers():
    """tier ≤1 이 5일 연속이면 R3 발동."""
    today = date(2026, 5, 7)
    days = _prev_days(today, 5)
    tier_counts = {d: 1 for d in days}  # prev_high만 활성
    ev = _make_r3_evaluator(daily_tier_count=tier_counts)
    result = await ev.evaluate(today)
    assert "R3" in result.triggered
    assert result.should_rollback is True


# ---------------------------------------------------------------------------
# 케이스 2: tier 다양성 2종 이상 → R3 미발동
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_enabled_two_or_more_tiers_does_not_trigger():
    """tier 종류가 2개 이상이면 R3 미발동."""
    today = date(2026, 5, 7)
    days = _prev_days(today, 5)
    # 5일 모두 tier=2 (volume_surge + prev_high 등)
    tier_counts = {d: 2 for d in days}
    ev = _make_r3_evaluator(daily_tier_count=tier_counts)
    result = await ev.evaluate(today)
    assert "R3" not in result.triggered
    assert result.should_rollback is False


# ---------------------------------------------------------------------------
# 케이스 3: AUTO_ROLLBACK_R3_ENABLED=False → 항상 미발동
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_disabled_via_env_always_not_triggered():
    """AUTO_ROLLBACK_R3_ENABLED=False이면 tier 1 연속 5일이어도 미발동."""
    today = date(2026, 5, 7)
    days = _prev_days(today, 5)
    tier_counts = {d: 1 for d in days}

    cfg_off = _CfgR3On(AUTO_ROLLBACK_R3_ENABLED=False)
    ev = _make_r3_evaluator(daily_tier_count=tier_counts, settings=cfg_off)
    result = await ev.evaluate(today)
    assert "R3" not in result.triggered
    assert result.should_rollback is False


# ---------------------------------------------------------------------------
# 케이스 4: 4거래일 연속 후 오늘 다양성 회복(tier≥2) → 미발동
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r3_4days_streak_but_today_diversity_recovers_not_triggered():
    """4일 연속 tier=1 이후 5일째(오늘) tier=2로 회복 → R3 미발동.

    _check_r3는 매 호출 시 직전 5일을 재평가하므로 카운터 별도 관리 없이
    today의 tier 값만 2 이상이면 all(c<=1) == False가 된다.
    """
    today = date(2026, 5, 7)
    days = _prev_days(today, 5)
    # days[0]=today(tier=2), days[1]~days[4]=tier=1
    tier_counts = {d: 1 for d in days}
    tier_counts[today] = 2  # 오늘 다양성 회복
    ev = _make_r3_evaluator(daily_tier_count=tier_counts)
    result = await ev.evaluate(today)
    assert "R3" not in result.triggered
    assert result.should_rollback is False
