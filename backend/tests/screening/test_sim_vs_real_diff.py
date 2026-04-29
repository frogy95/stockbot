"""Phase 8.6 Sprint 2 Task 4 — 시뮬-실측 통과율 절대차 테스트."""
from datetime import date
from unittest.mock import AsyncMock

import pytest

from modules.screening.sim_vs_real_diff import (
    DIFF_KEY_PREFIX,
    compute_sim_vs_real_diff,
    run_daily_check,
)


class _FakeRedis:
    def __init__(self, init=None):
        self._store = init or {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ttl=None):
        self._store[key] = value


@pytest.mark.asyncio
async def test_diff_zero_when_rates_equal():
    redis = _FakeRedis({
        "shadow:tier:gap_open:passed:2026-04-30": "10",
        "shadow:tier:gap_open:failed:2026-04-30": "10",
    })
    result = await compute_sim_vs_real_diff(
        redis, target_date=date(2026, 4, 30),
        real_signal_count=10, real_eligible_count=20,
    )
    assert result["shadow_pass_rate"] == pytest.approx(0.5)
    assert result["real_pass_rate"] == pytest.approx(0.5)
    assert result["diff"] == pytest.approx(0.0)
    assert result["exceeded"] is False
    assert f"{DIFF_KEY_PREFIX}:2026-04-30" in redis._store


@pytest.mark.asyncio
async def test_diff_exceeds_threshold_triggers_alert():
    redis = _FakeRedis({
        "shadow:tier:gap_open:passed:2026-04-30": "10",
        "shadow:tier:gap_open:failed:2026-04-30": "10",
    })
    notifier = AsyncMock()
    # shadow=0.5, real=0.1 → diff=0.4 ≥ 0.15
    result = await run_daily_check(
        redis, notifier,
        target_date=date(2026, 4, 30),
        real_signal_count=1, real_eligible_count=10,
    )
    assert result["exceeded"] is True
    notifier.send_sim_real_diff_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_diff_handles_zero_eligible():
    redis = _FakeRedis()
    result = await compute_sim_vs_real_diff(
        redis, target_date=date(2026, 4, 30),
        real_signal_count=0, real_eligible_count=0,
    )
    assert result["real_pass_rate"] == 0.0
    assert result["shadow_pass_rate"] == 0.0
    assert result["exceeded"] is False
