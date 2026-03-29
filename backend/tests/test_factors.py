"""팩터 계산기 모듈 테스트 (주식 5팩터 + ETF 괴리율)."""
import pytest

from modules.screening.factors import (
    calc_momentum_factor,
    calc_orderbook_ratio_factor,
    calc_trade_strength_factor,
    calc_volatility_factor,
    calc_volume_factor,
)
from modules.screening.etf_factors import calc_tracking_error_factor


class TestCalcVolumeFactor:
    """거래량 팩터 (전일 대비 비율)."""

    def test_normal(self):
        assert calc_volume_factor(200_000, 100_000) == 2.0

    def test_high_ratio(self):
        assert calc_volume_factor(1_000_000, 100_000) == 10.0

    def test_prev_volume_zero(self):
        assert calc_volume_factor(200_000, 0) == 0.0


class TestCalcVolatilityFactor:
    """변동성 팩터 (ATR 5일)."""

    def test_normal_5days(self):
        highs = [10500, 10700, 10600, 10800, 10900]
        lows = [10000, 10200, 10100, 10300, 10400]
        closes = [10200, 10500, 10300, 10600, 10700]
        result = calc_volatility_factor(highs, lows, closes)
        # 1일차: H-L = 500
        # 2일차: max(500, |10700-10200|, |10200-10200|) = max(500, 500, 0) = 500
        # 3일차: max(500, |10600-10500|, |10100-10500|) = max(500, 100, 400) = 500
        # 4일차: max(500, |10800-10300|, |10300-10300|) = max(500, 500, 0) = 500
        # 5일차: max(500, |10900-10600|, |10400-10600|) = max(500, 300, 200) = 500
        # ATR = mean([500, 500, 500, 500, 500]) = 500.0
        assert result == 500.0

    def test_insufficient_data(self):
        assert calc_volatility_factor([], [], []) == 0.0
        assert calc_volatility_factor([100], [90], [95]) == 0.0


class TestCalcMomentumFactor:
    """모멘텀 팩터 (3일 수익률)."""

    def test_positive_momentum(self):
        closes = [10000, 10100, 10200, 10300]
        result = calc_momentum_factor(closes)
        # (10300 - 10000) / 10000 * 100 = 3.0
        assert result == 3.0

    def test_negative_momentum(self):
        closes = [10000, 9900, 9800, 9700]
        result = calc_momentum_factor(closes)
        # (9700 - 10000) / 10000 * 100 = -3.0
        assert result == -3.0

    def test_insufficient_data(self):
        assert calc_momentum_factor([]) == 0.0
        assert calc_momentum_factor([100, 200]) == 0.0
        assert calc_momentum_factor([100, 200, 300]) == 0.0


class TestCalcTradeStrengthFactor:
    """체결강도 팩터 (pass-through)."""

    def test_normal(self):
        assert calc_trade_strength_factor(85.5) == 85.5

    def test_zero(self):
        assert calc_trade_strength_factor(0.0) == 0.0


class TestCalcOrderbookRatioFactor:
    """호가잔량 비율 팩터."""

    def test_normal(self):
        assert calc_orderbook_ratio_factor(150_000, 100_000) == 1.5

    def test_equal(self):
        assert calc_orderbook_ratio_factor(100_000, 100_000) == 1.0

    def test_ask_zero(self):
        assert calc_orderbook_ratio_factor(100_000, 0) == 0.0


class TestCalcTrackingErrorFactor:
    """ETF 괴리율 팩터."""

    def test_positive_gap(self):
        # |((10500 - 10000) / 10000) * 100| = 5.0
        assert calc_tracking_error_factor(10500, 10000.0) == 5.0

    def test_negative_gap(self):
        # |((9500 - 10000) / 10000) * 100| = 5.0
        assert calc_tracking_error_factor(9500, 10000.0) == 5.0

    def test_no_gap(self):
        assert calc_tracking_error_factor(10000, 10000.0) == 0.0

    def test_nav_zero(self):
        assert calc_tracking_error_factor(10000, 0.0) == 0.0
