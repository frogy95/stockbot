"""Phase 8.5 Sprint 1 — Task 4: 전략 stage 카운터 + 가상 신호 로깅 검증.

핵심 검증: 가상 신호 기록 동안 TradeSignalData 생성/주문 발생이 절대 없다.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy
from modules.trading.strategy import MarketSnapshot, RejectedSignal, TradeSignalData

_PATCH_NOW_KST = "modules.trading.strategies.momentum_breakout._now_kst"
_KST = ZoneInfo("Asia/Seoul")


class FakeRedis:
    def __init__(self):
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.lists: dict[str, list[str]] = {}

    async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        self.counters[key] = self.counters.get(key, 0) + amount
        if ttl is not None and key not in self.ttls:
            self.ttls[key] = ttl
        return self.counters[key]

    async def lpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        if key in self.lists:
            self.lists[key] = self.lists[key][start : stop + 1]


class FakeSession:
    def __init__(self, store: list):
        self.store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def add(self, obj):
        self.store.append(obj)

    async def commit(self):
        return None


def make_session_factory(store: list):
    def factory():
        return FakeSession(store)

    return factory


def _prev_close_snapshot(**overrides) -> MarketSnapshot:
    """prev_close tier가 선택되는 스냅샷 (gap < 3% AND current_price <= prev_high)."""
    defaults = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "stock_type": "STOCK",
        "current_price": 70000,
        "open_price": 70000,  # gap 0.7%
        "high": 70000,
        "low": 69500,
        "prev_close": 69500,
        "prev_high": 71000,  # current_price <= prev_high → prev_close tier
        "volume": 20_000_000,
        "prev_volume": 30_000_000,
        "change_rate": 0.7,
        "trade_strength": 110.0,
        "total_bid_volume": 100_000,
        "total_ask_volume": 80_000,
        "recent_highs": [71000, 70800, 70500, 70000, 70200],
        "recent_lows": [69000, 68800, 68500, 68000, 68200],
        "recent_closes": [70500, 70200, 70000, 69800, 69500],
    }
    defaults.update(overrides)
    return MarketSnapshot(**defaults)


@pytest.mark.asyncio
async def test_virtual_signal_recorded_within_13_14_window():
    """13:30 KST prev_close tier → virtual_signals 1건 INSERT + RejectedSignal 반환."""
    redis = FakeRedis()
    store: list = []
    strategy = MomentumBreakoutStrategy(
        redis_client=redis, session_factory=make_session_factory(store)
    )
    snapshot = _prev_close_snapshot()

    with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 22, 13, 30, tzinfo=_KST)):
        result = await strategy.generate_signal(snapshot)

    # 주문 경로 절대 차단 — RejectedSignal 만 반환
    assert isinstance(result, RejectedSignal)
    assert not isinstance(result, TradeSignalData)
    assert result.stage == "prev_close_time_guard"

    # virtual_signals 1건 INSERT
    assert len(store) == 1
    assert store[0].virtual_stage == "prev_close_time_guard_bypass"
    assert store[0].would_execute is False
    assert store[0].stock_code == "005930"

    # stage 카운터 +1
    assert any("prev_close_time_guard" in k for k in redis.counters.keys())


@pytest.mark.asyncio
async def test_no_virtual_signal_before_1300():
    """12:59 KST → 동일 조건이어도 prev_close_time_guard 미발동 (13:00 이전) → 가상 신호 미기록."""
    redis = FakeRedis()
    store: list = []
    strategy = MomentumBreakoutStrategy(
        redis_client=redis, session_factory=make_session_factory(store)
    )
    snapshot = _prev_close_snapshot()

    with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 22, 12, 59, tzinfo=_KST)):
        result = await strategy.generate_signal(snapshot)

    # 13:00 이전이므로 PREV_CLOSE_TIER_BLOCK_TIME 미발동 → 다른 stage로 reject 또는 통과
    # 어느 쪽이든 virtual_signals INSERT 0건이어야 한다.
    assert len(store) == 0


@pytest.mark.asyncio
async def test_no_virtual_signal_after_1400():
    """14:30 KST → prev_close_time_guard는 발동하지만 시간창(13~14) 밖이라 가상 신호 미기록."""
    redis = FakeRedis()
    store: list = []
    strategy = MomentumBreakoutStrategy(
        redis_client=redis, session_factory=make_session_factory(store)
    )
    snapshot = _prev_close_snapshot()

    with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 22, 14, 30, tzinfo=_KST)):
        result = await strategy.generate_signal(snapshot)

    assert isinstance(result, RejectedSignal)
    assert result.stage == "prev_close_time_guard"
    assert len(store) == 0


@pytest.mark.asyncio
async def test_no_virtual_signal_for_different_tier():
    """13:30 KST, gap_open tier (gap >= 3%) → prev_close_time_guard 미발동 → 가상 신호 미기록."""
    redis = FakeRedis()
    store: list = []
    strategy = MomentumBreakoutStrategy(
        redis_client=redis, session_factory=make_session_factory(store)
    )
    snapshot = _prev_close_snapshot(open_price=72000)  # gap_rate ≈ 3.6% → gap_open tier

    with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 22, 13, 30, tzinfo=_KST)):
        result = await strategy.generate_signal(snapshot)

    # gap_open tier는 prev_close_time_guard와 무관 → virtual_signals INSERT 0건
    assert len(store) == 0


@pytest.mark.asyncio
async def test_stage_counter_recorded_on_reject():
    """어느 reject 경로든 stage 카운터가 +1 되어야 한다."""
    redis = FakeRedis()
    strategy = MomentumBreakoutStrategy(redis_client=redis)

    # current_price <= breakout_ref → breakout stage reject
    snapshot = _prev_close_snapshot(current_price=70000, prev_high=71000, open_price=72000)
    with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 22, 10, 0, tzinfo=_KST)):
        result = await strategy.generate_signal(snapshot)

    assert isinstance(result, RejectedSignal)
    assert any("breakout" in k for k in redis.counters.keys())


@pytest.mark.asyncio
async def test_backward_compatible_no_deps():
    """redis_client/session_factory None이어도 전략 동작 정상 (기존 테스트 회귀 방지)."""
    strategy = MomentumBreakoutStrategy()
    snapshot = _prev_close_snapshot()

    with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 22, 13, 30, tzinfo=_KST)):
        result = await strategy.generate_signal(snapshot)

    assert isinstance(result, RejectedSignal)
    assert result.stage == "prev_close_time_guard"
