"""Phase 8.6 Sprint 1 Task 5 — G3 회로차단기 테스트."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.safety.circuit_breaker import (
    CIRCUIT_BREAKER_KEY,
    PHASE85_FALLBACK_OVERRIDE_KEY,
    CircuitBreaker,
    CircuitEvaluation,
)


@dataclass
class _Cfg:
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_PASS_RATE_THRESHOLD: float = 0.10
    CIRCUIT_BREAKER_CONSECUTIVE_DAYS: int = 3


def _make_redis(daily_total: dict[str, int], daily_passed: dict[str, int]) -> AsyncMock:
    """target=today, today-1, today-2의 total/passed counter를 흉내내는 redis mock."""
    redis = AsyncMock()

    async def _get(key: str):
        if key.startswith("screener:candidates:total:"):
            d = key.split(":")[-1]
            return str(daily_total.get(d, 0)) if d in daily_total else None
        if key.startswith("screener:candidates:passed:"):
            d = key.split(":")[-1]
            return str(daily_passed.get(d, 0)) if d in daily_passed else None
        return None

    redis.get.side_effect = _get
    redis.set = AsyncMock()
    return redis


def _three_days(today: date) -> list[str]:
    return [(today - timedelta(days=i)).isoformat() for i in range(3)]


@pytest.mark.asyncio
async def test_pass_rate_below_10pct_3days_triggers():
    today = date(2026, 4, 30)
    d0, d1, d2 = _three_days(today)
    # 일별 [3%, 5%, 8%] (today, today-1, today-2)
    redis = _make_redis(
        daily_total={d0: 100, d1: 100, d2: 100},
        daily_passed={d0: 3, d1: 5, d2: 8},
    )
    cb = CircuitBreaker(redis_client=redis, settings=_Cfg())

    result = await cb.evaluate(today)
    assert result.should_trigger is True
    assert result.reason == "all_below_threshold"


@pytest.mark.asyncio
async def test_pass_rate_above_threshold_does_not_trigger():
    today = date(2026, 4, 30)
    d0, d1, d2 = _three_days(today)
    # [12%, 8%, 11%] — 12%/11%가 임계 깨므로 미발동
    redis = _make_redis(
        daily_total={d0: 100, d1: 100, d2: 100},
        daily_passed={d0: 12, d1: 8, d2: 11},
    )
    cb = CircuitBreaker(redis_client=redis, settings=_Cfg())

    result = await cb.evaluate(today)
    assert result.should_trigger is False


@pytest.mark.asyncio
async def test_threshold_env_override():
    """CIRCUIT_BREAKER_PASS_RATE_THRESHOLD=0.05 일 때 [3%, 4%, 6%] → 6%>5%로 미발동."""
    today = date(2026, 4, 30)
    d0, d1, d2 = _three_days(today)
    redis = _make_redis(
        daily_total={d0: 100, d1: 100, d2: 100},
        daily_passed={d0: 3, d1: 4, d2: 6},
    )
    cb = CircuitBreaker(
        redis_client=redis,
        settings=_Cfg(CIRCUIT_BREAKER_PASS_RATE_THRESHOLD=0.05),
    )

    result = await cb.evaluate(today)
    assert result.should_trigger is False


@pytest.mark.asyncio
async def test_trigger_disables_phase86_and_phase85_fallback():
    """발동 시 Redis override 2종(phase86:circuit_breaker:active + Phase 8.5 폴백 차단) 동시 설정."""
    today = date(2026, 4, 30)
    d0, d1, d2 = _three_days(today)
    redis = _make_redis(
        daily_total={d0: 100, d1: 100, d2: 100},
        daily_passed={d0: 1, d1: 2, d2: 3},
    )
    notifier = AsyncMock()
    cb = CircuitBreaker(redis_client=redis, settings=_Cfg(), notifier=notifier)

    result = await cb.evaluate(today)
    assert result.should_trigger is True

    await cb.execute(result)

    set_calls = {call.args[0]: call.args[1] for call in redis.set.call_args_list}
    assert set_calls[CIRCUIT_BREAKER_KEY] == "true"
    assert set_calls[PHASE85_FALLBACK_OVERRIDE_KEY] == "False"
    notifier.send_system_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_zero_denominator_fails_safe_to_circuit_on():
    """P0 보강 #1 — total=0인 날 존재 시 강제 ON."""
    today = date(2026, 4, 30)
    d0, d1, d2 = _three_days(today)
    # d1(어제)이 total=0
    redis = _make_redis(
        daily_total={d0: 100, d1: 0, d2: 100},
        daily_passed={d0: 50, d1: 0, d2: 50},
    )
    cb = CircuitBreaker(redis_client=redis, settings=_Cfg())

    result = await cb.evaluate(today)
    assert result.should_trigger is True
    assert result.reason.startswith("zero_denominator")


@pytest.mark.asyncio
async def test_circuit_breaker_does_not_block_exit_signals():
    """P0 보강 #3 (Daytrader Critical) — 회로차단기 활성 상태에서도 청산 계열 신호는 통과."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="true")  # circuit active
    cb = CircuitBreaker(redis_client=redis, settings=_Cfg())

    exit_signal = SimpleNamespace(action="exit", signal_type="sell")
    sl_signal = SimpleNamespace(action="stop_loss", signal_type="sell")
    tp_signal = SimpleNamespace(action="take_profit", signal_type="sell")
    sell_signal = SimpleNamespace(action=None, signal_type="sell")

    assert await cb.allow_signal(exit_signal) is True
    assert await cb.allow_signal(sl_signal) is True
    assert await cb.allow_signal(tp_signal) is True
    assert await cb.allow_signal(sell_signal) is True


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_only_entry_signals():
    """회로차단기 활성 시 신규 진입(entry / signal_type=='buy')만 차단."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="true")
    cb = CircuitBreaker(redis_client=redis, settings=_Cfg())

    entry_signal = SimpleNamespace(action="entry", signal_type="buy")
    buy_signal = SimpleNamespace(action=None, signal_type="buy")

    assert await cb.allow_signal(entry_signal) is False
    assert await cb.allow_signal(buy_signal) is False

    # 비활성 상태(inactive)에서는 모두 통과
    redis.get = AsyncMock(return_value=None)
    cb_inactive = CircuitBreaker(redis_client=redis, settings=_Cfg())
    assert await cb_inactive.allow_signal(entry_signal) is True
    assert await cb_inactive.allow_signal(buy_signal) is True


@pytest.mark.asyncio
async def test_master_disabled_does_not_trigger():
    """CIRCUIT_BREAKER_ENABLED=False 시 평가 결과 should_trigger=False."""
    today = date(2026, 4, 30)
    redis = _make_redis(daily_total={}, daily_passed={})
    cb = CircuitBreaker(
        redis_client=redis,
        settings=_Cfg(CIRCUIT_BREAKER_ENABLED=False),
    )

    result = await cb.evaluate(today)
    assert result.should_trigger is False
    assert result.reason == "disabled"


@pytest.mark.asyncio
async def test_execute_noop_when_should_not_trigger_and_no_existing():
    """should_trigger=False + 기존 비활성 → set/delete 모두 호출 없음."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    cb = CircuitBreaker(redis_client=redis, settings=_Cfg())
    await cb.execute(CircuitEvaluation(should_trigger=False))
    redis.set.assert_not_called()
    redis.delete.assert_not_called()


@pytest.mark.asyncio
async def test_execute_self_clears_when_no_trigger_and_existing():
    """2026-05-12 hotfix — should_trigger=False && 기존 활성 시 phase86 + phase85 둘 다 DEL."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="true")
    redis.delete = AsyncMock()
    notifier = AsyncMock()
    notifier.send_system_alert = AsyncMock()
    cb = CircuitBreaker(redis_client=redis, settings=_Cfg(), notifier=notifier)
    await cb.execute(CircuitEvaluation(should_trigger=False))
    deleted_keys = {call.args[0] for call in redis.delete.await_args_list}
    assert CIRCUIT_BREAKER_KEY in deleted_keys
    assert PHASE85_FALLBACK_OVERRIDE_KEY in deleted_keys
    redis.set.assert_not_called()
    notifier.send_system_alert.assert_awaited_once()
    args = notifier.send_system_alert.call_args[0]
    assert args[0] == "phase86_circuit_breaker"
    assert "해제" in args[1]
