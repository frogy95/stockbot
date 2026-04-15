"""필터 조건 정의 모듈 테스트."""
import pytest

from modules.screening.filters import (
    PrimaryFilters,
    SecondaryFilters,
    is_hot_stock,
    passes_primary_filter,
)


class TestPrimaryFilters:
    """1차 필터 기본값 검증."""

    def test_default_values(self):
        f = PrimaryFilters()
        assert f.volume_ratio == 1.5
        assert f.volume_min_stock == 50_000
        assert f.volume_min_etf == 10_000
        assert f.market_cap_min == 50_000_000_000
        assert f.change_rate_min == -2.0
        assert f.change_rate_max == 7.0
        assert f.max_candidates == 20


class TestSecondaryFilters:
    """2차 필터 기본값 검증."""

    def test_default_values(self):
        f = SecondaryFilters()
        assert f.trade_strength_min == 100.0
        assert f.orderbook_ratio_min == 1.2
        assert f.screening_interval == 30
        assert f.no_signal_before == "09:30"


class TestPassesPrimaryFilter:
    """1차 필터 적용 함수 테스트."""

    @pytest.fixture()
    def filters(self):
        return PrimaryFilters()

    def test_pass_all(self, filters):
        data = {
            "volume": 200_000,
            "prev_volume": 100_000,
            "market_cap": 100_000_000_000,
            "change_rate": 3.0,
            "stock_type": "STOCK",
        }
        assert passes_primary_filter(data, filters) is True

    def test_fail_market_cap(self, filters):
        data = {
            "volume": 200_000,
            "prev_volume": 100_000,
            "market_cap": 10_000_000_000,  # 500억 미만
            "change_rate": 3.0,
            "stock_type": "STOCK",
        }
        assert passes_primary_filter(data, filters) is False

    def test_fail_volume_ratio(self, filters):
        data = {
            "volume": 50_000,
            "prev_volume": 100_000,  # 비율 0.5 < 2.0
            "market_cap": 100_000_000_000,
            "change_rate": 3.0,
            "stock_type": "STOCK",
        }
        assert passes_primary_filter(data, filters) is False

    def test_fail_volume_min_stock(self, filters):
        data = {
            "volume": 10_000,  # 50,000 미만
            "prev_volume": 5_000,
            "market_cap": 100_000_000_000,
            "change_rate": 3.0,
            "stock_type": "STOCK",
        }
        assert passes_primary_filter(data, filters) is False

    def test_etf_volume_min(self, filters):
        data = {
            "volume": 30_000,
            "prev_volume": 10_000,  # 비율 3.0
            "market_cap": 100_000_000_000,
            "change_rate": 3.0,
            "stock_type": "ETF",
        }
        assert passes_primary_filter(data, filters) is True

    def test_etf_fail_volume_min(self, filters):
        data = {
            "volume": 5_000,  # ETF 10,000 미만
            "prev_volume": 2_000,
            "market_cap": 100_000_000_000,
            "change_rate": 3.0,
            "stock_type": "ETF",
        }
        assert passes_primary_filter(data, filters) is False

    def test_fail_change_rate_too_low(self, filters):
        data = {
            "volume": 200_000,
            "prev_volume": 100_000,
            "market_cap": 100_000_000_000,
            "change_rate": -3.0,  # -2.0 미만
            "stock_type": "STOCK",
        }
        assert passes_primary_filter(data, filters) is False

    def test_pass_negative_change_rate(self, filters):
        data = {
            "volume": 200_000,
            "prev_volume": 100_000,
            "market_cap": 100_000_000_000,
            "change_rate": -1.5,  # -2.0 이상 → 통과
            "stock_type": "STOCK",
        }
        assert passes_primary_filter(data, filters) is True

    def test_pass_zero_change_rate(self, filters):
        data = {
            "volume": 200_000,
            "prev_volume": 100_000,
            "market_cap": 100_000_000_000,
            "change_rate": 0.0,  # -2.0 이상 → 통과
            "stock_type": "STOCK",
        }
        assert passes_primary_filter(data, filters) is True

    def test_fail_change_rate_too_high(self, filters):
        data = {
            "volume": 200_000,
            "prev_volume": 100_000,
            "market_cap": 100_000_000_000,
            "change_rate": 8.0,  # 7.0 초과
            "stock_type": "STOCK",
        }
        assert passes_primary_filter(data, filters) is False

    def test_prev_volume_zero(self, filters):
        data = {
            "volume": 200_000,
            "prev_volume": 0,
            "market_cap": 100_000_000_000,
            "change_rate": 3.0,
            "stock_type": "STOCK",
        }
        assert passes_primary_filter(data, filters) is False


class TestIsHotStock:
    """핫 종목 판정 테스트."""

    def test_hot_stock(self):
        assert is_hot_stock(5.0) is True
        assert is_hot_stock(10.0) is True

    def test_not_hot_stock(self):
        assert is_hot_stock(4.9) is False
        assert is_hot_stock(2.0) is False
