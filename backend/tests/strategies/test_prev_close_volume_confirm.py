"""Phase 8.6 Sprint 2 Task 3 — prev_close tier 5분봉 거래량 컨펌.

Hotfix: Sprint 2 게이트가 사용하던 `vol_5m:{code}` 단일 키(JSON 배열)는
collector(`VolumeAggregator`)가 적재하지 않아 항상 fail-safe로 차단됐다.
이 테스트는 collector가 실제 적재하는 `vol5m:{code}:{date}:{slot}` 슬롯 키를
게이트가 직접 조회하도록 통합된 동작을 검증한다.
"""
import json
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from modules.collector.volume_aggregator import calc_5min_slot, make_redis_key
from modules.trading.strategy import MarketSnapshot, RejectedSignal

_KST = ZoneInfo("Asia/Seoul")
_MIDDAY = datetime(2026, 4, 30, 11, 0, tzinfo=_KST)
_DATE_STR = _MIDDAY.strftime("%Y%m%d")
_CURRENT_SLOT = calc_5min_slot(_MIDDAY.hour, _MIDDAY.minute)
_STOCK = "000660"


def _snap_prev_close(**overrides) -> MarketSnapshot:
    """prev_close tier (gap=0.5%, current > prev_close+0.1%, current < prev_high)."""
    base = {
        "stock_code": _STOCK,
        "stock_name": "SK하이닉스",
        "stock_type": "STOCK",
        "current_price": 100100,
        "open_price": 100500,
        "high": 100200,
        "low": 99800,
        "prev_close": 100000,
        "prev_high": 102000,
        "volume": 5000000,
        "prev_volume": 2000000,
        "change_rate": 0.1,
        "trade_strength": 110.0,
        "total_bid_volume": 600000,
        "total_ask_volume": 400000,
        "recent_highs":  [102000] * 14,
        "recent_lows":   [98000] * 14,
        "recent_closes": [100000] * 14,
    }
    base.update(overrides)
    return MarketSnapshot(**base)


class _FakeRedis:
    """slot key → JSON dict 매핑 fake."""

    def __init__(self, slot_data: dict[int, dict] | None = None):
        self._slot_data = slot_data or {}

    async def get(self, key: str):
        # 슬롯 매핑된 키만 반환, 그 외는 None
        for slot, data in self._slot_data.items():
            if key == make_redis_key(_STOCK, _DATE_STR, slot):
                return json.dumps(data)
        return None


def _build_slots(bars: list[dict]) -> dict[int, dict]:
    """최근 5슬롯(_CURRENT_SLOT-4..._CURRENT_SLOT)에 bars를 매핑."""
    return {_CURRENT_SLOT - 4 + i: bars[i] for i in range(len(bars))}


@pytest.fixture
def _setup():
    with patch("modules.trading.strategies.momentum_breakout._now_kst", return_value=_MIDDAY), \
         patch("modules.trading.strategies.momentum_breakout.calc_market_progress", return_value=1.0):
        yield


@pytest.mark.asyncio
async def test_v1_total_vol_ratio_passes(_setup):
    """V1: 최신 슬롯 total_vol ≥ 직전 4슬롯 평균 ×2 → 통과."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    bars = [
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 100, "sell_vol": 150, "total_vol": 250},
    ]
    redis = _FakeRedis(_build_slots(bars))
    strat = MomentumBreakoutStrategy(redis_client=redis)

    result = await strat.generate_signal(_snap_prev_close())
    if isinstance(result, RejectedSignal):
        assert result.stage != "prev_close_volume_confirm"


@pytest.mark.asyncio
async def test_v2_consecutive_bullish_passes(_setup):
    """V2: 최근 2슬롯 모두 buy_vol > sell_vol (양봉 2연속) → 통과."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    bars = [
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 70, "sell_vol": 30, "total_vol": 100},
        {"buy_vol": 80, "sell_vol": 30, "total_vol": 110},
    ]
    redis = _FakeRedis(_build_slots(bars))
    strat = MomentumBreakoutStrategy(redis_client=redis)

    result = await strat.generate_signal(_snap_prev_close())
    if isinstance(result, RejectedSignal):
        assert result.stage != "prev_close_volume_confirm"


@pytest.mark.asyncio
async def test_v3_neither_condition_rejects(_setup):
    """V3: total_vol=1.5× + 양봉 1개만 → 거부."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    bars = [
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 80, "sell_vol": 70, "total_vol": 150},  # 양봉 1, 1.5x
    ]
    redis = _FakeRedis(_build_slots(bars))
    strat = MomentumBreakoutStrategy(redis_client=redis)

    result = await strat.generate_signal(_snap_prev_close())
    assert isinstance(result, RejectedSignal)
    assert result.stage == "prev_close_volume_confirm"


@pytest.mark.asyncio
async def test_v4_no_data_fail_safe(_setup):
    """V4: 5분봉 슬롯 데이터 전무 → fail-safe(거부)."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    redis = _FakeRedis(slot_data={})
    strat = MomentumBreakoutStrategy(redis_client=redis)

    result = await strat.generate_signal(_snap_prev_close())
    assert isinstance(result, RejectedSignal)
    assert result.stage == "prev_close_volume_confirm"


@pytest.mark.asyncio
async def test_v5_or_combination(_setup):
    """V5: 양봉 2연속만 만족(거래량 비율 미달)이어도 통과."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    bars = [
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 40, "sell_vol": 60, "total_vol": 100},
        {"buy_vol": 70, "sell_vol": 40, "total_vol": 110},
        {"buy_vol": 60, "sell_vol": 30, "total_vol": 90},  # 거래량은 평균 미달
    ]
    redis = _FakeRedis(_build_slots(bars))
    strat = MomentumBreakoutStrategy(redis_client=redis)

    result = await strat.generate_signal(_snap_prev_close())
    if isinstance(result, RejectedSignal):
        assert result.stage != "prev_close_volume_confirm"


@pytest.mark.asyncio
async def test_v6_partial_data_uses_available(_setup):
    """V6: 일부 슬롯만 적재되어도 데이터가 있으면 평가 진행."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # 최근 2슬롯만 적재, 둘 다 양봉 → 통과
    bars_partial = {
        _CURRENT_SLOT - 1: {"buy_vol": 70, "sell_vol": 30, "total_vol": 100},
        _CURRENT_SLOT:     {"buy_vol": 80, "sell_vol": 20, "total_vol": 100},
    }
    redis = _FakeRedis(slot_data=bars_partial)
    strat = MomentumBreakoutStrategy(redis_client=redis)

    result = await strat.generate_signal(_snap_prev_close())
    if isinstance(result, RejectedSignal):
        assert result.stage != "prev_close_volume_confirm"
