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
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        # safe_mode:active 는 항상 None 반환 (safe_mode 게이트 차단 방지)
        if key == "safe_mode:active":
            return None
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

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
    import json as _json
    redis = FakeRedis()
    # Sprint 2 — prev_close_volume_confirm 게이트 통과를 위해 양봉 2연속 데이터 주입
    redis.store["vol_5m:005930"] = _json.dumps([
        {"volume": 100_000, "is_bullish": True},
        {"volume": 110_000, "is_bullish": True},
        {"volume": 120_000, "is_bullish": True},
        {"volume": 130_000, "is_bullish": True},
        {"volume": 140_000, "is_bullish": True},
    ])
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
    """14:10 KST → prev_close_time_guard 발동 + 시간창(13~14) 밖이라 가상 신호 미기록.

    Sprint 2 변경: 14:30 이상은 temp_time_guard가 선행 차단하므로 14:10으로 검증.
    """
    import json as _json
    redis = FakeRedis()
    # Sprint 2 — prev_close_volume_confirm 게이트 통과를 위해 양봉 2연속 데이터 주입
    redis.store["vol_5m:005930"] = _json.dumps([
        {"volume": 100_000, "is_bullish": True},
        {"volume": 110_000, "is_bullish": True},
        {"volume": 120_000, "is_bullish": True},
        {"volume": 130_000, "is_bullish": True},
        {"volume": 140_000, "is_bullish": True},
    ])
    store: list = []
    strategy = MomentumBreakoutStrategy(
        redis_client=redis, session_factory=make_session_factory(store)
    )
    snapshot = _prev_close_snapshot()

    with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 22, 14, 10, tzinfo=_KST)):
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
    """redis_client/session_factory None이어도 전략 동작 정상 (기존 테스트 회귀 방지).

    Sprint 2 변경: redis_client=None이면 prev_close_volume_confirm(fail-safe)에서 먼저 reject.
    """
    strategy = MomentumBreakoutStrategy()
    snapshot = _prev_close_snapshot()

    with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 22, 13, 30, tzinfo=_KST)):
        result = await strategy.generate_signal(snapshot)

    assert isinstance(result, RejectedSignal)
    # redis_client=None → _check_prev_close_volume_confirm이 fail-safe(False) 반환
    # → prev_close_volume_confirm stage에서 reject (prev_close_time_guard 도달 전)
    assert result.stage == "prev_close_volume_confirm"


# ---------------------------------------------------------------------------
# Phase 8.5 Sprint 1.5 — Shadow evaluation 회귀 안전망 (TDD RED)
# ---------------------------------------------------------------------------

def _success_snapshot(**overrides) -> MarketSnapshot:
    """모든 조건 충족으로 TradeSignalData가 반환되는 스냅샷 (prev_high tier).

    주요 수치:
    - gap_rate 0.5% → prev_close tier 배제, current_price > prev_high → prev_high tier
    - breakout_pct ≈ 0.99%, threshold=2.0, adjusted_ratio = 3.25 → volume_threshold 통과
    - trade_strength 150 → trade_strength 통과
    - confidence ≈ 0.64 → MIN_CONFIDENCE 통과

    Sprint 2 ATR 조건:
    - recent_highs/lows 범위를 넓혀 ATR≈4000, atr_ratio≈3.9% (ATR_FLOOR=2.5% 통과)
    - atr_ratio < ATR_CEIL_HARD(8%) → atr_ceil 통과
    """
    defaults = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "stock_type": "STOCK",
        "current_price": 102_000,
        "open_price": 100_500,
        "high": 102_500,
        "low": 100_000,
        "prev_close": 100_000,
        "prev_high": 101_000,
        "volume": 3_250_000,
        "prev_volume": 1_000_000,
        "change_rate": 2.0,
        "trade_strength": 150.0,
        "total_bid_volume": 150_000,
        "total_ask_volume": 80_000,
        # ATR_FLOOR(0.025) 통과: high-low≈4000 → atr≈4000, ratio≈0.039 > 0.025
        # ATR_CEIL_HARD(0.08) 미초과: 4000/102000≈0.039 < 0.08
        "recent_highs": [105_000, 105_000, 105_000, 105_000, 105_000],
        "recent_lows": [101_000, 101_000, 101_000, 101_000, 101_000],
        "recent_closes": [103_000, 103_000, 103_000, 103_000, 103_000],
    }
    defaults.update(overrides)
    return MarketSnapshot(**defaults)


class TestShadowEvaluationInvariance:
    """shadow evaluation 추가가 generate_signal() 반환값/타이밍에 영향 없음을 증명.

    주문 경로 불변 원칙 — Sprint 1.5 최우선 요건.
    """

    @pytest.mark.asyncio
    async def test_shadow_does_not_affect_breakout_reject(self):
        """gap_open tier + 시초가 >= 현재가 케이스: RejectedSignal(stage='gap_open_absorb').

        Sprint 2 변경: gap_open_absorb 게이트가 breakout 게이트 앞에 추가됨.
        open_price(72_000) >= current_price(70_000) → gap_open_absorb에서 먼저 reject.
        """
        redis = FakeRedis()
        strategy = MomentumBreakoutStrategy(redis_client=redis)
        snapshot = _prev_close_snapshot(
            current_price=70_000, prev_high=71_000, open_price=72_000
        )
        # gap_rate ≈ 3.6% → gap_open tier, breakout_ref = open_price = 72_000
        # Sprint 2: open_price(72_000) >= current_price(70_000) → gap_open_absorb reject (breakout 전)

        with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 23, 10, 0, tzinfo=_KST)):
            result = await strategy.generate_signal(snapshot)

        assert isinstance(result, RejectedSignal)
        assert result.stage == "gap_open_absorb"
        assert result.detail.get("breakout_tier") == "gap_open"
        # gap_open_absorb에서 short-circuit — 기존 stage 카운터 1건만 기록
        strategy_stage_keys = [k for k in redis.counters if k.startswith("metrics:strategy:stage:")]
        strategy_absorb = [k for k in strategy_stage_keys if ":gap_open_absorb:" in k]
        assert len(strategy_absorb) == 1, (
            "Sprint 2 short-circuit 동작 불변: gap_open_absorb reject 시 stage 카운터는 1건만"
        )

    @pytest.mark.asyncio
    async def test_shadow_does_not_affect_success_signal(self):
        """모든 조건 통과 → TradeSignalData + confidence 결정 요인 불변."""
        redis = FakeRedis()
        strategy = MomentumBreakoutStrategy(redis_client=redis)
        snapshot = _success_snapshot()

        with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 23, 11, 0, tzinfo=_KST)):
            result = await strategy.generate_signal(snapshot)

        assert isinstance(result, TradeSignalData), (
            f"TradeSignalData 예상, 실제: {type(result).__name__} stage={getattr(result, 'stage', None)} detail={getattr(result, 'detail', None)}"
        )
        assert result.signal_type == "buy"
        assert result.confidence >= 0.6
        assert result.reason.get("breakout_tier") == "prev_high"
        # Sprint 1 pass 카운터 1건
        strategy_pass = [k for k in redis.counters if ":strategy:stage:" in k and ":pass:" in k]
        assert len(strategy_pass) == 1

    @pytest.mark.asyncio
    async def test_shadow_exception_does_not_propagate(self):
        """_shadow_evaluate에서 예외가 던져져도 generate_signal 반환값이 동일해야 한다."""
        redis = FakeRedis()
        strategy = MomentumBreakoutStrategy(redis_client=redis)
        snapshot = _prev_close_snapshot(
            current_price=70_000, prev_high=71_000, open_price=72_000
        )

        # _shadow_evaluate를 강제로 예외 발생 버전으로 교체
        async def _raise(*_args, **_kwargs):
            raise RuntimeError("shadow fault injection")

        assert hasattr(strategy, "_shadow_evaluate"), (
            "Task 2 미구현: _shadow_evaluate 메서드가 존재해야 한다"
        )
        object.__setattr__(strategy, "_shadow_evaluate", _raise)

        with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 23, 10, 0, tzinfo=_KST)):
            result = await strategy.generate_signal(snapshot)

        assert isinstance(result, RejectedSignal)
        # Sprint 2: gap_open_absorb 게이트가 breakout 앞에 추가됨 → gap_open_absorb reject
        assert result.stage == "gap_open_absorb"

    @pytest.mark.asyncio
    async def test_shadow_records_all_stages_regardless_of_short_circuit(self):
        """breakout에서 short-circuit되더라도 shadow 네임스페이스는 나머지 stage도 독립 평가.

        gap_open tier + current_price <= open_price 케이스:
        기존 경로: breakout 1건만 기록.
        shadow 경로: prev_close_time_guard(pass), breakout(fail), prev_volume_zero(pass),
                     min_volume_floor, volume_threshold, trade_strength, atr_filter, confidence
                     중 평가 가능한 모두 기록 (skip 규칙 제외).
        """
        redis = FakeRedis()
        strategy = MomentumBreakoutStrategy(redis_client=redis)
        snapshot = _prev_close_snapshot(
            current_price=70_000, prev_high=71_000, open_price=72_000
        )

        with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 23, 10, 0, tzinfo=_KST)):
            await strategy.generate_signal(snapshot)

        shadow_keys = [k for k in redis.counters if k.startswith("metrics:shadow:stage:")]
        assert shadow_keys, "shadow 카운터 네임스페이스가 기록되어야 한다"

        # breakout fail 기록 필수
        breakout_fail = [k for k in shadow_keys if ":breakout:fail:" in k]
        assert breakout_fail, f"shadow breakout fail 기록 필수 (keys={shadow_keys})"

        # 최소 4개 이상의 서로 다른 stage가 독립 평가되어야 한다 (short-circuit 무관)
        stages_seen = set()
        for k in shadow_keys:
            # metrics:shadow:stage:{date}:{stage}:{outcome}:{hh}:{mm}
            parts = k.split(":")
            if len(parts) >= 6:
                stages_seen.add(parts[4])
        assert len(stages_seen) >= 4, (
            f"shadow는 최소 4개 이상의 stage를 독립 평가해야 한다. 실제: {stages_seen}"
        )


# ---------------------------------------------------------------------------
# Phase 8.5 Sprint 2 — Task 2: shadow/본체 floor 일관성 테스트
# ---------------------------------------------------------------------------


class TestShadowBodyFloorConsistency:
    """shadow와 generate_signal 본체가 동일 _resolve_min_volume_floor를 사용하는지 검증."""

    @pytest.mark.asyncio
    async def test_shadow_and_body_use_same_floor(self, monkeypatch):
        """동일 snapshot에서 shadow와 본체 모두 _resolve_min_volume_floor를 호출한다.

        monkeypatch로 _resolve_min_volume_floor를 spy하여
        generate_signal 1회 호출 시 최소 2번(shadow + 본체) 이상 호출되는지 확인한다.
        """
        import modules.trading.strategies.momentum_breakout as mb_module

        call_count = 0
        original_fn = mb_module._resolve_min_volume_floor

        def spy_floor(snapshot, tier, gap_rate, breakout_ref, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_fn(snapshot, tier, gap_rate, breakout_ref, **kwargs)

        monkeypatch.setattr(mb_module, "_resolve_min_volume_floor", spy_floor)

        redis = FakeRedis()
        strategy = MomentumBreakoutStrategy(redis_client=redis)
        # prev_volume > 0 이어야 두 경로 모두 floor 계산에 도달
        snapshot = _success_snapshot()

        with patch(_PATCH_NOW_KST, return_value=datetime(2026, 4, 23, 11, 0, tzinfo=_KST)):
            await strategy.generate_signal(snapshot)

        assert call_count >= 2, (
            f"_resolve_min_volume_floor가 shadow + 본체에서 각 1회씩 최소 2번 호출되어야 한다. "
            f"실제 호출 횟수: {call_count}"
        )
