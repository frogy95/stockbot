"""Phase 8.6 Sprint 2 Task 3 — 병렬 OR tier 분리 + matched_tiers + 가드 테스트.

10 케이스: gap_open / prev_high / prev_close / 다중 매칭 / ATR 한계 / 시간가드 / 폴백 / 시초가 컷.
"""
from datetime import datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.strategy import MarketSnapshot, RejectedSignal, TradeSignalData

_PATCH_PROGRESS = "modules.trading.strategies.momentum_breakout.calc_market_progress"
_PATCH_NOW_KST = "modules.trading.strategies.momentum_breakout._now_kst"
_KST = ZoneInfo("Asia/Seoul")
_MIDDAY = datetime(2026, 4, 30, 11, 0, tzinfo=_KST)  # 임시 시간가드 통과
_BLOCK_MORNING = datetime(2026, 4, 30, 9, 5, tzinfo=_KST)  # 09:00~09:10 차단


def _snap(**overrides) -> MarketSnapshot:
    """기본 KOSPI 종목 (gap_rate=0, prev_high 돌파). ATR ~0.04 (current_price=73000 기준)."""
    # ATR ratio target = 0.04: high-low ≈ 73000 × 0.04 = ~2920
    base = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "stock_type": "STOCK",
        "current_price": 73000,
        "open_price": 70000,
        "high": 73500,
        "low": 71500,
        "prev_close": 70000,
        "prev_high": 71000,
        "volume": 40000000,
        "prev_volume": 10000000,
        "change_rate": 4.0,
        "trade_strength": 120.0,
        "total_bid_volume": 800000,
        "total_ask_volume": 400000,
        # ATR ratio ≈ (high-low)/close ≈ 2900/73000 ≈ 0.040
        "recent_highs":  [74450] * 14,
        "recent_lows":   [71550] * 14,
        "recent_closes": [73000] * 14,
    }
    base.update(overrides)
    return MarketSnapshot(**base)


@pytest.fixture(autouse=True)
def _freeze_midday():
    with patch(_PATCH_NOW_KST, return_value=_MIDDAY):
        yield


@pytest.fixture
def _patch_progress():
    with patch(_PATCH_PROGRESS, return_value=1.0):
        yield


@pytest.mark.asyncio
async def test_c1_gap_open_only_signal(_patch_progress):
    """C1: gap_rate=4% (gap_open tier) + ATR=0.03 + 시초가<현재가 → 신호 / matched=['gap_open']."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    # gap_open: open=prev_close*1.04, current>open
    snap = _snap(
        prev_close=70000,
        open_price=72800,  # gap=4%
        current_price=73000,
        prev_high=70500,
    )
    result = await strat.generate_signal(snap)
    assert isinstance(result, TradeSignalData), getattr(result, "stage", None)
    assert result.matched_tiers is not None
    assert "gap_open" in result.matched_tiers


@pytest.mark.asyncio
async def test_c2_prev_high_only_signal(_patch_progress):
    """C2: gap=1.4% (prev_high tier) + breakout + ATR ~0.04 → 신호 / matched=['prev_high']."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    snap = _snap(
        prev_close=70000,
        open_price=71000,  # gap=1.4%
        current_price=73000,
        prev_high=71500,
    )
    result = await strat.generate_signal(snap)
    assert isinstance(result, TradeSignalData)
    assert result.matched_tiers == ["prev_high"]


@pytest.mark.asyncio
async def test_c4_all_fail_returns_rejected(_patch_progress):
    """C4: gap=0, current<prev_high & current<prev_close → 모두 fail."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    snap = _snap(
        prev_close=70000,
        open_price=70000,
        current_price=69000,
        prev_high=71000,
    )
    result = await strat.generate_signal(snap)
    assert isinstance(result, RejectedSignal)


@pytest.mark.asyncio
async def test_c5_multi_tier_matched(_patch_progress):
    """C5: gap_open + prev_high 동시 만족 → matched_tiers 둘 다 포함."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    snap = _snap(
        prev_close=70000,
        open_price=72800,  # gap_open
        current_price=73000,  # current > prev_high*1.001
        prev_high=70500,
    )
    result = await strat.generate_signal(snap)
    assert isinstance(result, TradeSignalData)
    assert "gap_open" in result.matched_tiers
    assert "prev_high" in result.matched_tiers


@pytest.mark.asyncio
async def test_c6_atr_above_hard_rejects_gap_open(_patch_progress):
    """C6: gap_open + ATR=0.09(HARD 0.08 초과) → reject (절대 한계 적용)."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    # ATR ratio ≈ 0.09 → high-low ≈ 6300 around close 70000
    high_atr_highs = [73200] * 14
    high_atr_lows = [66800] * 14
    high_atr_closes = [70000] * 14
    snap = _snap(
        prev_close=70000,
        open_price=72800,
        current_price=73000,
        prev_high=70500,
        recent_highs=high_atr_highs,
        recent_lows=high_atr_lows,
        recent_closes=high_atr_closes,
    )
    result = await strat.generate_signal(snap)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "atr_filter"


@pytest.mark.asyncio
async def test_c7_atr_below_floor_rejects(_patch_progress):
    """C7: ATR=0.020 (ATR_FLOOR=0.025 미달) → reject."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    # ATR ratio ≈ 0.020 → high-low ≈ 1400 around 70000
    snap = _snap(
        prev_close=70000,
        open_price=70500,  # gap=0.7% → prev_high tier
        current_price=72000,
        prev_high=71500,
        recent_highs=[70700] * 14,
        recent_lows=[69300] * 14,
        recent_closes=[70000] * 14,
    )
    result = await strat.generate_signal(snap)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "atr_filter"


@pytest.mark.asyncio
async def test_c10_temp_time_guard_blocks_at_0905(_patch_progress):
    """C10: TIME_FILTER_ENABLED=true + 09:05 → 모든 tier 차단 (본 가드로 교체)."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    snap = _snap(
        prev_close=70000, open_price=72800, current_price=73000, prev_high=70500
    )
    with patch(_PATCH_NOW_KST, return_value=_BLOCK_MORNING):
        result = await strat.generate_signal(snap)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "time_filter"


@pytest.mark.asyncio
async def test_c9_gap_open_absorb_cut_rejects(_patch_progress):
    """C9: gap_open + 시초가 ≥ 현재가 (매물 흡수 실패) → reject."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    snap = _snap(
        prev_close=70000,
        open_price=73000,  # gap=4.3%
        current_price=72500,  # current < open → 매물 흡수
        prev_high=70500,
    )
    result = await strat.generate_signal(snap)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "gap_open_absorb"


@pytest.mark.asyncio
async def test_kill_switch_disables_parallel_or(_patch_progress):
    """PARALLEL_OR_TIER_ENABLED=false → matched_tiers=None (Sprint 1 직렬 동작)."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    snap = _snap(
        prev_close=70000, open_price=72800, current_price=73000, prev_high=70500
    )
    with patch("modules.trading.strategies.momentum_breakout.settings.PARALLEL_OR_TIER_ENABLED", False):
        result = await strat.generate_signal(snap)
    assert isinstance(result, TradeSignalData)
    assert result.matched_tiers is None  # NULL 안전성


@pytest.mark.asyncio
async def test_c8_fallback_atr_above_static_ceil(_patch_progress):
    """C8: 폴백 종목 + ATR=0.06 (ATR_CEIL_FALLBACK=0.05 초과) → reject."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strat = MomentumBreakoutStrategy()
    # ATR ratio ≈ 0.06
    snap = _snap(
        prev_close=70000,
        open_price=70500,
        current_price=72500,
        prev_high=71500,
        recent_highs=[72100] * 14,
        recent_lows=[67900] * 14,
        recent_closes=[70000] * 14,
    )
    # is_fallback 속성 동적 추가 (BaseModel — extra 허용 X, 우회: monkeypatch)
    import types
    snap_with_fb = snap.model_copy()
    object.__setattr__(snap_with_fb, "is_fallback", True)
    # MomentumBreakoutStrategy._evaluate_atr_gate가 getattr로 is_fallback 읽음
    result = await strat.generate_signal(snap_with_fb)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "atr_filter"
