"""모멘텀 브레이크아웃 전략 테스트."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.strategy import MarketSnapshot, RejectedSignal, TradeSignalData

_PATCH_PROGRESS = "modules.trading.strategies.momentum_breakout.calc_market_progress"
_PATCH_NOW_KST = "modules.trading.strategies.momentum_breakout._now_kst"
_KST = ZoneInfo("Asia/Seoul")
_MORNING = datetime(2026, 4, 22, 10, 0, tzinfo=_KST)
_AFTER_1300 = datetime(2026, 4, 22, 13, 30, tzinfo=_KST)


@pytest.fixture(autouse=True)
def _freeze_morning_kst():
    """prev_close tier 13:00 가드가 전 테스트에 랜덤하게 영향주지 않도록 오전(10:00)으로 고정."""
    with patch(_PATCH_NOW_KST, return_value=_MORNING):
        yield


# === 픽스처 ===


def _make_snapshot(**overrides) -> MarketSnapshot:
    """기본 MarketSnapshot을 생성하고 overrides를 적용."""
    defaults = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "stock_type": "STOCK",
        "current_price": 73000,  # prev_high 대비 ~3.5% 돌파 -> 높은 momentum
        "open_price": 69500,
        "high": 73000,
        "low": 69000,
        "prev_close": 69500,
        "prev_high": 70500,  # 전일 고가
        "volume": 40000000,  # 전일 대비 400% -> 높은 volume_score
        "prev_volume": 10000000,
        "change_rate": 5.04,
        "trade_strength": 120.0,  # 높은 체결강도 (>= 100.0 조건 통과)
        "total_bid_volume": 800000,  # 호가 비율 2.0 -> 높은 orderbook
        "total_ask_volume": 400000,
        "recent_highs": [70500, 70000, 69800, 69500, 69000],
        "recent_lows": [68000, 67500, 67800, 67200, 67000],
        "recent_closes": [69500, 69000, 68800, 68500, 68000],
    }
    defaults.update(overrides)
    return MarketSnapshot(**defaults)


# === 테스트 ===


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_breakout_buy_signal(mock_progress):
    """전일 고가 돌파 + 거래량 200%+ + 체결강도 70+ -> 매수 신호 생성."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot()  # current_price=73000 > prev_high=70500
    result = await strategy.generate_signal(snapshot)

    assert result is not None
    assert isinstance(result, TradeSignalData)
    assert result.signal_type == "buy"
    assert result.confidence > 0.6
    assert result.strategy_name == "momentum_breakout"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_no_breakout_returns_rejected(mock_progress):
    """어느 tier에서도 돌파 기준 미돌파 -> RejectedSignal(stage='breakout').

    current_price=69000 < prev_close=69500 이므로 prev_close tier에서도 미돌파.
    """
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(current_price=69000)
    result = await strategy.generate_signal(snapshot)

    assert isinstance(result, RejectedSignal)
    assert result.stage == "breakout"
    assert result.detail["current_price"] == 69000
    assert result.detail["breakout_ref"] == 69500
    assert result.detail["breakout_tier"] == "prev_close"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_low_volume_returns_rejected(mock_progress):
    """거래량 조건 미달 -> RejectedSignal(stage='volume_threshold')."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(volume=15000000, prev_volume=10000000)  # 1.5배 < 2.0배
    result = await strategy.generate_signal(snapshot)

    assert isinstance(result, RejectedSignal)
    assert result.stage == "volume_threshold"
    assert "adjusted_ratio" in result.detail
    # current_price=73000, prev_high=70500 → breakout_pct ≈ 3.55% → threshold=1.8
    assert result.detail["volume_threshold"] == 1.8


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_low_trade_strength_returns_rejected(mock_progress):
    """체결강도 조건 미달 -> RejectedSignal(stage='trade_strength')."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(trade_strength=60.0)  # < 100
    result = await strategy.generate_signal(snapshot)

    assert isinstance(result, RejectedSignal)
    assert result.stage == "trade_strength"
    assert result.detail["trade_strength"] == 60.0
    assert result.detail["required"] == 100.0


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_gap_switches_to_open_price(mock_progress):
    """갭 3%+ 시 돌파 기준이 open_price(당일 시가)로 전환된다."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # 갭: (72000 - 69500) / 69500 = 3.6% -> breakout_ref = open_price = 72000
    # current_price=74000 > open_price=72000 -> 돌파
    snapshot = _make_snapshot(
        open_price=72000,
        prev_close=69500,
        high=74000,
        current_price=74000,
    )
    result = await strategy.generate_signal(snapshot)
    assert result is not None

    # current_price=72000 <= open_price=72000 -> 미돌파
    snapshot2 = _make_snapshot(
        open_price=72000,
        prev_close=69500,
        high=73000,
        current_price=72000,
    )
    result2 = await strategy.generate_signal(snapshot2)
    assert isinstance(result2, RejectedSignal)
    assert result2.stage == "breakout"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_atr_filter_excludes_high_volatility(mock_progress):
    """ATR이 현재가 대비 5% 초과 시 RejectedSignal(stage='atr_filter')."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # ATR이 매우 높은 데이터: 고가-저가 차이가 큰 경우 (ATR/price > 5%)
    snapshot = _make_snapshot(
        current_price=73000,
        recent_highs=[80000, 79000, 78000, 77000, 76000],
        recent_lows=[60000, 61000, 62000, 63000, 64000],
        recent_closes=[69500, 69000, 68800, 68500, 68000],
    )
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "atr_filter"
    assert result.detail["atr_ratio"] > 0.05


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_confidence_weighted_average(mock_progress):
    """신뢰도 가중 평균 검증: 모멘텀30/거래량30/체결강도20/호가20."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(
        current_price=73000,
        prev_high=70500,
        volume=40000000,  # 4배
        prev_volume=10000000,
        trade_strength=120.0,
        total_bid_volume=800000,
        total_ask_volume=400000,
    )
    result = await strategy.generate_signal(snapshot)
    assert result is not None

    # 수동 검증 (progress=1.0이므로 adjusted_ratio = raw volume_ratio = 4.0)
    breakout_ref = 70500
    momentum_score = min((73000 - breakout_ref) / breakout_ref * 100 / 5.0, 1.0)
    adjusted_ratio = 40000000 / (10000000 * 1.0)  # = 4.0
    volume_score = min(adjusted_ratio / 5.0, 1.0)  # = 0.8
    strength_score = min((120.0 - 50) / 50, 1.0)
    orderbook_score = min(800000 / 400000 / 2.0, 1.0)
    expected = (
        momentum_score * 0.3
        + volume_score * 0.3
        + strength_score * 0.2
        + orderbook_score * 0.2
    )
    assert abs(result.confidence - expected) < 0.01


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_low_confidence_returns_rejected(mock_progress):
    """신뢰도 0.6 미만 -> RejectedSignal. 현재 테스트는 trade_strength에서 먼저 걸림."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # 각 팩터가 낮아서 합산 confidence < 0.6 하지만 trade_strength=71 < 100 에서 먼저 거부됨
    snapshot = _make_snapshot(
        current_price=70510,
        prev_high=70500,
        volume=20000000,
        prev_volume=10000000,
        trade_strength=71.0,
        total_bid_volume=300000,
        total_ask_volume=400000,
    )
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "trade_strength"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_stop_loss_take_profit_normal(mock_progress):
    """일반 종목 손절/익절 가격 검증: -2%/+3%."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(current_price=73000)
    result = await strategy.generate_signal(snapshot)

    assert result is not None
    assert result.stop_loss == int(73000 * 0.98)
    assert result.take_profit == int(73000 * 1.03)


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_stop_loss_take_profit_leverage(mock_progress):
    """레버리지 종목 손절/익절: -1.5%/+3%."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(stock_name="KODEX 레버리지")
    result = await strategy.generate_signal(snapshot)

    assert result is not None
    assert result.stop_loss == int(73000 * 0.985)
    assert result.take_profit == int(73000 * 1.03)


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_reason_dict_structure(mock_progress):
    """reason dict에 각 팩터 점수와 조건 정보가 포함되는지 검증."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot()
    result = await strategy.generate_signal(snapshot)

    assert result is not None
    reason = result.reason
    assert "momentum_score" in reason
    assert "volume_score" in reason
    assert "strength_score" in reason
    assert "orderbook_score" in reason
    assert "breakout_ref" in reason
    assert "gap_rate" in reason
    assert "adjusted_ratio" in reason
    assert "volume_threshold" in reason
    assert "breakout_pct" in reason
    assert "market_progress" in reason


# === 시간가중 거래량 보정 신규 테스트 ===


@patch(_PATCH_PROGRESS, return_value=90 / 390)
@pytest.mark.asyncio
async def test_morning_low_volume_returns_rejected(mock_progress):
    """장 초반(10:30) 낮은 거래량 -> MIN_VOLUME_FLOOR에서 차단."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # volume=2500000 / prev_volume=10000000 = 0.25 < MIN_VOLUME_FLOOR(0.5) -> 차단
    snapshot = _make_snapshot(
        current_price=73000,
        prev_high=70500,
        volume=2_500_000,
        prev_volume=10_000_000,
    )
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "min_volume_floor"


@patch(_PATCH_PROGRESS, return_value=257 / 390)
@pytest.mark.asyncio
async def test_062040_isupetasis_scenario(mock_progress):
    """실제 시나리오: 062040 종목 13:17 시점 강한 돌파 -> 매수 신호 생성."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # breakout_ref=157900(prev_high), current_price=169900
    # breakout_pct = (169900-157900)/157900*100 ≈ 7.60% -> threshold=1.5
    # progress = 257/390 ≈ 0.6590
    # adjusted = 1080856 / (968175 * 0.6590) ≈ 1.694 >= 1.5 -> 통과
    snapshot = _make_snapshot(
        stock_code="062040",
        stock_name="이수페타시스",
        current_price=169900,
        open_price=158000,
        high=169900,
        low=156000,
        prev_close=157800,
        prev_high=157900,
        volume=1_080_856,
        prev_volume=968_175,
        change_rate=7.67,
        trade_strength=120.0,
        total_bid_volume=800000,
        total_ask_volume=400000,
        # 낮은 ATR을 위한 최근 데이터
        recent_highs=[158000, 157500, 157800, 157200, 157000],
        recent_lows=[155000, 155500, 155200, 155800, 155000],
        recent_closes=[157800, 157000, 156800, 156500, 156000],
    )
    result = await strategy.generate_signal(snapshot)

    assert result is not None
    assert result.signal_type == "buy"
    assert result.reason["volume_threshold"] == 1.5
    assert result.reason["breakout_pct"] == round(
        (169900 - 157900) / 157900 * 100, 2
    )


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_breakout_pct_thresholds(mock_progress):
    """돌파 강도별 거래량 임계값 단계 검증."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()

    # 시나리오 A: breakout_pct ~7% -> threshold=1.5, adjusted=1.6 -> 통과
    # current_price=75435, prev_high=70500 -> pct=(75435-70500)/70500*100=7.0%
    snapshot_a = _make_snapshot(
        current_price=75435,
        prev_high=70500,
        volume=16_000_000,  # adjusted = 16M / (10M * 1.0) = 1.6
        prev_volume=10_000_000,
    )
    result_a = await strategy.generate_signal(snapshot_a)
    assert result_a is not None
    assert result_a.reason["volume_threshold"] == 1.5

    # 시나리오 B: breakout_pct ~3.55% -> threshold=1.8, adjusted=1.9 -> 통과
    # current_price=73000, prev_high=70500 -> pct=3.55%
    snapshot_b = _make_snapshot(
        current_price=73000,
        prev_high=70500,
        volume=19_000_000,  # adjusted = 19M / (10M * 1.0) = 1.9
        prev_volume=10_000_000,
    )
    result_b = await strategy.generate_signal(snapshot_b)
    assert result_b is not None
    assert result_b.reason["volume_threshold"] == 1.8

    # 시나리오 C: breakout_pct ~1% -> threshold=2.0, adjusted=1.9 -> 차단
    # current_price=71205, prev_high=70500 -> pct=1.0%
    snapshot_c = _make_snapshot(
        current_price=71205,
        prev_high=70500,
        volume=19_000_000,  # adjusted = 1.9 < threshold 2.0
        prev_volume=10_000_000,
    )
    result_c = await strategy.generate_signal(snapshot_c)
    assert isinstance(result_c, RejectedSignal)
    assert result_c.stage == "volume_threshold"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_prev_volume_zero_rejected(mock_progress):
    """prev_volume=0 -> RejectedSignal(stage='prev_volume_zero')."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(prev_volume=0)
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "prev_volume_zero"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_confidence_stage_rejected(mock_progress):
    """모든 게이트 통과하지만 confidence < 0.6 -> stage='confidence'."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # breakout 간신히 통과(momentum~0) + volume 딱 2.0배(threshold 경계) + ts=100(경계)
    # + orderbook 최저 -> confidence ~0.32 < 0.6
    snapshot = _make_snapshot(
        current_price=70501,
        prev_high=70500,
        volume=20_000_000,
        prev_volume=10_000_000,
        trade_strength=100.0,
        total_bid_volume=0,
        total_ask_volume=400000,
        recent_highs=[70500, 70400, 70300, 70200, 70100],
        recent_lows=[70000, 69900, 69800, 69700, 69600],
        recent_closes=[70400, 70300, 70200, 70100, 70000],
    )
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "confidence"
    assert result.detail["confidence"] < 0.6
    assert "momentum_score" in result.detail


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_min_volume_floor_blocks(mock_progress):
    """전일 대비 절대 거래량 하한 미만이면 차단 (오후 시각 — 시간대 슬라이딩 미적용).

    dynamic 모드 + prev_high tier + weak breakout(breakout_pct < 3%): floor=0.5.
    volume=4M / prev_volume=10M = 0.4 < 0.5 → 차단.
    """
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    with patch(_PATCH_NOW_KST, return_value=_AFTER_1300):
        strategy = MomentumBreakoutStrategy()
        snapshot = _make_snapshot(
            current_price=70600,
            prev_high=70500,
            volume=4_000_000,
            prev_volume=10_000_000,
        )
        result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "min_volume_floor"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_min_volume_floor_passes_but_fails_threshold(mock_progress):
    """절대 거래량 하한은 통과하지만 시간가중 임계값에서 차단."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # volume=6M / prev_volume=10M = 0.6 >= 0.5 -> floor 통과
    # adjusted = 6M / (10M * 1.0) = 0.6
    # breakout_pct = (73000-70500)/70500*100 = 3.55% -> threshold=1.8
    # 0.6 < 1.8 -> 차단
    snapshot = _make_snapshot(
        volume=6_000_000,
        prev_volume=10_000_000,
    )
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "volume_threshold"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_gap_breakout_uses_open_price_as_ref(mock_progress):
    """갭 3%+ 시 breakout_ref가 open_price(시가)로 설정되어 시가 돌파 시 신호 생성."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # gap_rate = (72000 - 69500) / 69500 ≈ 3.6% -> 갭 경로
    # current_price == high (자기돌파 시나리오) -> open_price 기준이면 돌파, high 기준이면 거부
    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=72000,
        high=72600,
        current_price=72600,
        prev_high=70500,
    )
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, TradeSignalData)


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_non_gap_uses_prev_high_as_ref(mock_progress):
    """갭 3% 미만 시 breakout_ref가 prev_high(전일 고가)로 유지된다."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # gap_rate = (70000 - 69500) / 69500 ≈ 0.7% -> 비갭 경로
    # current_price=70800 > prev_high=70500 -> 돌파 -> 신호 생성
    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=70000,
        high=70800,
        current_price=70800,
        prev_high=70500,
    )
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, TradeSignalData)


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_gap_breakout_rejects_when_price_below_open(mock_progress):
    """갭 3%+ 이지만 current_price < open_price인 경우 breakout 단계에서 거부."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # gap_rate = (72000 - 69500) / 69500 ≈ 3.6% -> 갭 경로
    # current_price=71500 < open_price=72000 -> 시가 미돌파 -> 거부
    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=72000,
        high=72000,
        current_price=71500,
        prev_high=70500,
    )
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "breakout"


# === Phase 8 Sprint 2: 3단계 tier (gap_open / prev_close / prev_high) ===


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_gap_open_tier_sets_breakout_tier_and_uses_open_price(mock_progress):
    """갭 3.5% + current_price = open+1% -> breakout_tier='gap_open', breakout_ref=open_price."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # gap_rate = (71925 - 69500) / 69500 = 3.49% -> gap_open
    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=71925,
        prev_high=70500,
        current_price=72644,  # open_price + 1%
        high=72644,
        volume=40_000_000,
        prev_volume=10_000_000,
    )
    strategy = MomentumBreakoutStrategy()
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, TradeSignalData)
    assert result.reason["breakout_tier"] == "gap_open"
    assert result.reason["breakout_ref"] == 71925


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_prev_close_tier_requires_intraday_prev_close_breakout(mock_progress):
    """gap < 3%, current_price > prev_close but <= prev_high -> prev_close tier."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # gap_rate ≈ 0.5%, current_price=70000 > prev_close=69500, <= prev_high=70500
    # breakout_pct = (70000-69500)/69500*100 ≈ 0.72%
    # prev_close tier threshold=2.5 -> volume_ratio 3.0배 필요
    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=69850,
        prev_high=70500,
        current_price=70000,
        high=70000,
        volume=30_000_000,  # adjusted = 3.0 >= 2.5
        prev_volume=10_000_000,
    )
    strategy = MomentumBreakoutStrategy()
    result = await strategy.generate_signal(snapshot)
    # confidence 계산 결과에 따라 pass/reject 가능 — 중요한 건 tier가 prev_close로 설정되는 것
    if isinstance(result, TradeSignalData):
        assert result.reason["breakout_tier"] == "prev_close"
        assert result.reason["breakout_ref"] == 69500
    else:
        # reject도 가능하지만 detail에 tier 있는 stage면 검증
        assert result.stage != "breakout"  # breakout은 통과해야 함
        if "breakout_tier" in result.detail:
            assert result.detail["breakout_tier"] == "prev_close"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_prev_high_tier_when_breaks_prev_high(mock_progress):
    """gap < 3%, current_price > prev_high -> prev_high tier."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # gap_rate ≈ 0.7%, current_price=71000 > prev_high=70500
    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=70000,
        prev_high=70500,
        current_price=71000,
        high=71000,
    )
    strategy = MomentumBreakoutStrategy()
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, TradeSignalData)
    assert result.reason["breakout_tier"] == "prev_high"
    assert result.reason["breakout_ref"] == 70500


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_prev_close_tier_confidence_cap_0_75(mock_progress):
    """prev_close tier는 만점 팩터여도 confidence <= 0.75."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # prev_close tier, 모든 팩터 만점에 가깝게
    # current_price=74365 > prev_close=69500 -> breakout_pct=7.0% (momentum_score max * 0.7 = 0.7)
    # 하지만 current_price > prev_high=74500이면 prev_high tier로 빠짐 — prev_high를 더 높게 설정
    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=69700,  # gap_rate < 3%
        prev_high=80000,  # current_price < prev_high 이어야 prev_close tier
        current_price=74365,
        high=74365,
        volume=100_000_000,
        prev_volume=10_000_000,
        trade_strength=200.0,
        total_bid_volume=10_000_000,
        total_ask_volume=100_000,
    )
    strategy = MomentumBreakoutStrategy()
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, TradeSignalData)
    assert result.reason["breakout_tier"] == "prev_close"
    assert result.confidence <= 0.75


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_prev_close_tier_momentum_score_scales_pct_7_times_0_7(mock_progress):
    """prev_close tier momentum_score == min(pct/7.0, 1.0) * 0.7 — pct=7%에서 0.7."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # breakout_pct = (74365-69500)/69500*100 = 7.0%
    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=69700,
        prev_high=80000,
        current_price=74365,
        high=74365,
        volume=30_000_000,
        prev_volume=10_000_000,
    )
    strategy = MomentumBreakoutStrategy()
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, TradeSignalData)
    assert result.reason["breakout_tier"] == "prev_close"
    # momentum_score ≈ min(7.0/7.0, 1.0) * 0.7 = 0.7
    assert abs(result.reason["momentum_score"] - 0.7) < 0.01


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_prev_close_tier_volume_threshold_fixed_2_5(mock_progress):
    """prev_close tier volume_threshold는 breakout_pct 무관하게 2.5 고정."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # breakout_pct = 7% (강 돌파) — gap_open/prev_high라면 threshold=1.5지만 prev_close는 2.5
    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=69700,
        prev_high=80000,
        current_price=74365,
        high=74365,
        volume=24_000_000,  # adjusted=2.4 < 2.5 -> 차단
        prev_volume=10_000_000,
    )
    strategy = MomentumBreakoutStrategy()
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "volume_threshold"
    assert result.detail["volume_threshold"] == 2.5
    assert result.detail["breakout_tier"] == "prev_close"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_prev_close_tier_disabled_after_1300_kst(mock_progress):
    """13:00 이후 prev_close tier -> RejectedSignal(stage='prev_close_time_guard')."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    snapshot = _make_snapshot(
        prev_close=69500,
        open_price=69700,
        prev_high=80000,
        current_price=74365,
        high=74365,
    )
    strategy = MomentumBreakoutStrategy()
    with patch(_PATCH_NOW_KST, return_value=_AFTER_1300):
        result = await strategy.generate_signal(snapshot)
    assert isinstance(result, RejectedSignal)
    assert result.stage == "prev_close_time_guard"
    assert result.detail["breakout_tier"] == "prev_close"


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_gap_breakout_uses_redis_realtime_ohlc(mock_progress):
    """Phase 8 Sprint 2 Task 5 — snapshot.open_price는 Redis 실시간 OHLC 값.

    gap_rate = (Redis open_price - prev_close) / prev_close 으로 계산되며,
    WS H0STCNT0 idx 7 필드가 snapshot.open_price로 전달되어야 한다.
    정확한 값 매핑은 test_kis_realtime의 field_offset_sanity와 병행 검증.
    """
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # Redis 실시간으로부터 전달된 OHLC 값이라는 전제
    realtime_open = 72000  # WS idx 7에서 읽힌 시가
    prev_close = 69500
    expected_gap_rate = (realtime_open - prev_close) / prev_close
    assert expected_gap_rate >= 0.03  # gap_open tier 판정 전제

    snapshot = _make_snapshot(
        prev_close=prev_close,
        open_price=realtime_open,
        current_price=72720,  # open + 1%
        high=72720,
        prev_high=70500,
    )
    strategy = MomentumBreakoutStrategy()
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, TradeSignalData)
    assert result.reason["breakout_tier"] == "gap_open"
    assert result.reason["breakout_ref"] == realtime_open


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_gap_open_tier_uses_existing_volume_threshold_logic(mock_progress):
    """gap_open tier는 기존 breakout_pct 기반 volume_threshold 로직을 유지."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    # gap_rate = 5% -> gap_open
    # breakout_pct = (75600-72000)/72000*100 = 5.0% -> threshold=1.5
    snapshot = _make_snapshot(
        prev_close=68571,
        open_price=72000,
        prev_high=70500,
        current_price=75600,
        high=75600,
        volume=16_000_000,  # adjusted=1.6 >= 1.5
        prev_volume=10_000_000,
    )
    strategy = MomentumBreakoutStrategy()
    result = await strategy.generate_signal(snapshot)
    assert isinstance(result, TradeSignalData)
    assert result.reason["breakout_tier"] == "gap_open"
    assert result.reason["volume_threshold"] == 1.5


# === Phase 8.5 Sprint 2: _resolve_min_volume_floor 순수 함수 테스트 ===


class TestResolveMinVolumeFloor:
    """_resolve_min_volume_floor 순수 함수의 각 분기를 단위 테스트."""

    def _make_snapshot(self, current_price: int = 73000, **overrides) -> "MarketSnapshot":
        """테스트용 MarketSnapshot 생성."""
        return _make_snapshot(current_price=current_price, **overrides)

    def test_legacy_mode_returns_0_5(self):
        """mode='legacy'이면 tier/gap_rate 무관하게 항상 0.5 반환."""
        from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor

        snapshot = self._make_snapshot()
        result = _resolve_min_volume_floor(
            snapshot,
            tier="gap_open",
            gap_rate=0.10,
            breakout_ref=70000,
            mode="legacy",
            hard_floor=0.0,
        )
        assert result == 0.5

    def test_strong_gap_returns_0_4(self):
        """gap_rate >= 0.05이면 strong 조건 충족 → 0.4 반환 (오후 시각, 시간대 슬라이딩 미적용)."""
        from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor

        snapshot = self._make_snapshot(current_price=73000)
        result = _resolve_min_volume_floor(
            snapshot,
            tier="gap_open",
            gap_rate=0.06,
            breakout_ref=70000,
            mode="dynamic",
            hard_floor=0.0,
            now_kst=_AFTER_1300,
        )
        assert result == 0.4

    def test_prev_close_tier_returns_0_6(self):
        """tier='prev_close'이면 gap/breakout 무관하게 0.6 반환 (오후 시각)."""
        from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor

        snapshot = self._make_snapshot(current_price=70000)
        result = _resolve_min_volume_floor(
            snapshot,
            tier="prev_close",
            gap_rate=0.02,
            breakout_ref=69500,
            mode="dynamic",
            hard_floor=0.0,
            now_kst=_AFTER_1300,
        )
        assert result == 0.6

    def test_default_returns_0_5(self):
        """tier='prev_high', gap_rate=0.02 (weak) → strong 조건 미충족 → 0.5 반환 (오후 시각)."""
        from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor

        # current_price=73000, breakout_ref=72000 → 73000 < 72000*1.03=74160 → strong_breakout=False
        snapshot = self._make_snapshot(current_price=73000)
        result = _resolve_min_volume_floor(
            snapshot,
            tier="prev_high",
            gap_rate=0.02,
            breakout_ref=72000,
            mode="dynamic",
            hard_floor=0.0,
            now_kst=_AFTER_1300,
        )
        assert result == 0.5

    def test_hard_floor_enforced(self):
        """결과가 hard_floor 미만이면 hard_floor로 강제 대체."""
        from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor

        # dynamic mode, strong_gap=True → result=0.4, hard_floor=0.7 → 0.7 반환
        snapshot = self._make_snapshot(current_price=73000)
        result = _resolve_min_volume_floor(
            snapshot,
            tier="gap_open",
            gap_rate=0.06,
            breakout_ref=70000,
            mode="dynamic",
            hard_floor=0.7,
            now_kst=_AFTER_1300,
        )
        assert result == 0.7

    def test_breakout_ref_1_03_trigger(self):
        """current_price >= breakout_ref * 1.03 이면 strong_breakout → 0.4 반환 (오후 시각)."""
        from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor

        # breakout_ref=70000, 70000*1.03=72100, current_price=72200 >= 72100 → strong
        snapshot = self._make_snapshot(current_price=72200)
        result = _resolve_min_volume_floor(
            snapshot,
            tier="prev_high",
            gap_rate=0.01,  # weak gap
            breakout_ref=70000,
            mode="dynamic",
            hard_floor=0.0,
            now_kst=_AFTER_1300,
        )
        assert result == 0.4

    # === Phase 8.6 Sprint 1: 09:00~11:00 KST 시간대 슬라이딩 (분기 D 손실 차단) ===

    def test_resolve_min_volume_floor_morning_window_returns_0_3(self):
        """09:00~11:00 KST 윈도우에서는 dynamic 결과를 0.3으로 추가 완화."""
        from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor

        snapshot = self._make_snapshot(current_price=73000)
        morning = datetime(2026, 4, 22, 9, 30, tzinfo=_KST)
        # tier=prev_high, weak gap → 원래 0.5 → 슬라이딩 적용 시 0.3
        result = _resolve_min_volume_floor(
            snapshot,
            tier="prev_high",
            gap_rate=0.02,
            breakout_ref=72000,
            mode="dynamic",
            hard_floor=0.0,
            now_kst=morning,
        )
        assert result == 0.3

    def test_resolve_min_volume_floor_afternoon_window_keeps_legacy(self):
        """13:00 KST는 윈도우 밖 — 슬라이딩 미적용 (기존 0.5 유지)."""
        from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor

        snapshot = self._make_snapshot(current_price=73000)
        result = _resolve_min_volume_floor(
            snapshot,
            tier="prev_high",
            gap_rate=0.02,
            breakout_ref=72000,
            mode="dynamic",
            hard_floor=0.0,
            now_kst=_AFTER_1300,
        )
        assert result == 0.5

    def test_resolve_min_volume_floor_morning_window_respects_hard_floor(self):
        """오전 슬라이딩으로 0.3이 나와도 hard_floor=0.4면 0.4로 강제 상향."""
        from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor

        snapshot = self._make_snapshot(current_price=73000)
        morning = datetime(2026, 4, 22, 9, 30, tzinfo=_KST)
        result = _resolve_min_volume_floor(
            snapshot,
            tier="prev_high",
            gap_rate=0.02,
            breakout_ref=72000,
            mode="dynamic",
            hard_floor=0.4,
            now_kst=morning,
        )
        assert result == 0.4
