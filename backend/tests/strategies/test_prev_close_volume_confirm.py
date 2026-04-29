"""Phase 8.6 Sprint 2 Task 3 — prev_close tier 5분봉 거래량 컨펌."""
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.strategy import MarketSnapshot, RejectedSignal, TradeSignalData

_KST = ZoneInfo("Asia/Seoul")
_MIDDAY = datetime(2026, 4, 30, 11, 0, tzinfo=_KST)


def _snap_prev_close(**overrides) -> MarketSnapshot:
    """prev_close tier (gap=0.5%, current > prev_close+0.1%, current < prev_high)."""
    base = {
        "stock_code": "000660",
        "stock_name": "SK하이닉스",
        "stock_type": "STOCK",
        "current_price": 100100,  # > prev_close 100000 +0.1%
        "open_price": 100500,  # gap=0.5% (< 3% so not gap_open)
        "high": 100200,
        "low": 99800,
        "prev_close": 100000,
        "prev_high": 102000,  # current < prev_high → not prev_high tier
        "volume": 5000000,
        "prev_volume": 2000000,
        "change_rate": 0.1,
        "trade_strength": 110.0,
        "total_bid_volume": 600000,
        "total_ask_volume": 400000,
        # ATR ratio ≈ (high-low)/close ≈ 4000/100000 = 0.04 — 유효 범위
        "recent_highs":  [102000] * 14,
        "recent_lows":   [98000] * 14,
        "recent_closes": [100000] * 14,
    }
    base.update(overrides)
    return MarketSnapshot(**base)


class _FakeRedis:
    def __init__(self, vol_5m=None):
        self._vol_5m = vol_5m

    async def get(self, key):
        if key.startswith("vol_5m:") and self._vol_5m is not None:
            return self._vol_5m
        return None


@pytest.fixture
def _setup():
    with patch("modules.trading.strategies.momentum_breakout._now_kst", return_value=_MIDDAY), \
         patch("modules.trading.strategies.momentum_breakout.calc_market_progress", return_value=1.0):
        yield


@pytest.mark.asyncio
async def test_v1_vol_5m_ratio_passes(_setup):
    """V1: 5분봉 vol_5m ≥ 직전 4봉 평균 ×2 → 통과."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    bars = [{"volume": 100, "is_bullish": False}] * 4 + [{"volume": 250, "is_bullish": False}]
    redis = _FakeRedis(vol_5m=json.dumps(bars))
    strat = MomentumBreakoutStrategy(redis_client=redis)

    snap = _snap_prev_close()
    result = await strat.generate_signal(snap)
    # 통과 조건 충분: 신호 또는 prev_close_volume_confirm 스테이지가 아닌 다른 게이트
    if isinstance(result, RejectedSignal):
        assert result.stage != "prev_close_volume_confirm"
    else:
        assert "prev_close" in result.matched_tiers


@pytest.mark.asyncio
async def test_v2_consecutive_bullish_passes(_setup):
    """V2: 5분봉 양봉 2연속 → 통과."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    bars = [{"volume": 100, "is_bullish": False}] * 3 + \
           [{"volume": 100, "is_bullish": True}, {"volume": 110, "is_bullish": True}]
    redis = _FakeRedis(vol_5m=json.dumps(bars))
    strat = MomentumBreakoutStrategy(redis_client=redis)

    snap = _snap_prev_close()
    result = await strat.generate_signal(snap)
    if isinstance(result, RejectedSignal):
        assert result.stage != "prev_close_volume_confirm"


@pytest.mark.asyncio
async def test_v3_neither_condition_rejects(_setup):
    """V3: vol_5m=1.5× + 양봉 1개 → fail."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    bars = [{"volume": 100, "is_bullish": False}] * 4 + [{"volume": 150, "is_bullish": True}]
    redis = _FakeRedis(vol_5m=json.dumps(bars))
    strat = MomentumBreakoutStrategy(redis_client=redis)

    snap = _snap_prev_close()
    result = await strat.generate_signal(snap)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "prev_close_volume_confirm"


@pytest.mark.asyncio
async def test_v4_no_vol_5m_data_fail_safe(_setup):
    """V4: 5분봉 데이터 부재 → fail-safe(거름)."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    redis = _FakeRedis(vol_5m=None)
    strat = MomentumBreakoutStrategy(redis_client=redis)

    snap = _snap_prev_close()
    result = await strat.generate_signal(snap)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "prev_close_volume_confirm"


@pytest.mark.asyncio
async def test_v5_or_combination(_setup):
    """V5: 양봉 2연속 OR vol_5m 둘 중 하나만 만족해도 통과."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # 양봉 2연속만 만족
    bars = [{"volume": 100, "is_bullish": False}, {"volume": 100, "is_bullish": False},
            {"volume": 100, "is_bullish": False}, {"volume": 110, "is_bullish": True},
            {"volume": 90, "is_bullish": True}]
    redis = _FakeRedis(vol_5m=json.dumps(bars))
    strat = MomentumBreakoutStrategy(redis_client=redis)

    snap = _snap_prev_close()
    result = await strat.generate_signal(snap)
    if isinstance(result, RejectedSignal):
        assert result.stage != "prev_close_volume_confirm"
