"""모멘텀 브레이크아웃 전략 테스트."""

from unittest.mock import patch

import pytest

from modules.trading.strategy import MarketSnapshot, TradeSignalData

_PATCH_PROGRESS = "modules.trading.strategies.momentum_breakout.calc_market_progress"


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
async def test_no_breakout_returns_none(mock_progress):
    """전일 고가 미돌파 -> None 반환."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(current_price=70000)  # < prev_high=70500
    result = await strategy.generate_signal(snapshot)

    assert result is None


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_low_volume_returns_none(mock_progress):
    """거래량 조건 미달 -> None 반환."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(volume=15000000, prev_volume=10000000)  # 1.5배 < 2.0배
    result = await strategy.generate_signal(snapshot)

    assert result is None


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_low_trade_strength_returns_none(mock_progress):
    """체결강도 조건 미달 -> None 반환."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    snapshot = _make_snapshot(trade_strength=60.0)  # < 100
    result = await strategy.generate_signal(snapshot)

    assert result is None


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_gap_switches_to_daily_high(mock_progress):
    """갭 3%+ 시 당일 고가 기준으로 전환."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # 갭: (72000 - 69500) / 69500 = 3.6% -> 돌파 기준이 당일 high로 전환
    # current_price=74000 > high=73000 -> 돌파
    snapshot = _make_snapshot(
        open_price=72000,
        prev_close=69500,
        high=73000,
        current_price=74000,
    )
    result = await strategy.generate_signal(snapshot)
    assert result is not None

    # current_price=72000 < high=73000 -> 미돌파
    snapshot2 = _make_snapshot(
        open_price=72000,
        prev_close=69500,
        high=73000,
        current_price=72000,
    )
    result2 = await strategy.generate_signal(snapshot2)
    assert result2 is None


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_atr_filter_excludes_high_volatility(mock_progress):
    """ATR이 현재가 대비 5% 초과 시 None 반환."""
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
    assert result is None


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
async def test_low_confidence_returns_none(mock_progress):
    """신뢰도 0.6 미만 -> None 반환."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # 각 팩터가 낮아서 합산 confidence < 0.6
    snapshot = _make_snapshot(
        current_price=70510,  # 겨우 돌파 (momentum 극히 낮음)
        prev_high=70500,
        volume=20000000,  # 딱 2배
        prev_volume=10000000,
        trade_strength=71.0,  # < 100 체결강도 미달
        total_bid_volume=300000,  # 호가 비율 낮음
        total_ask_volume=400000,
    )
    result = await strategy.generate_signal(snapshot)
    assert result is None


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
async def test_morning_low_volume_returns_none(mock_progress):
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
    assert result is None


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
    assert result_c is None


@patch(_PATCH_PROGRESS, return_value=1.0)
@pytest.mark.asyncio
async def test_min_volume_floor_blocks(mock_progress):
    """전일 대비 절대 거래량이 MIN_VOLUME_FLOOR(50%) 미만이면 차단."""
    from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy

    strategy = MomentumBreakoutStrategy()
    # volume=4M / prev_volume=10M = 0.4 < 0.5 -> 차단
    snapshot = _make_snapshot(
        volume=4_000_000,
        prev_volume=10_000_000,
    )
    result = await strategy.generate_signal(snapshot)
    assert result is None


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
    assert result is None
