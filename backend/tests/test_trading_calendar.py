"""trading_calendar 유닛 테스트 -- 한국거래소 2026년 휴장일 캘린더."""

from datetime import date

from core.trading_calendar import (
    get_latest_trading_day,
    get_prev_trading_day,
    is_trading_day,
)


class TestIsTradingDay:
    """is_trading_day 함수 테스트."""

    def test_new_year_holiday(self):
        """신정(1/1)은 휴장일."""
        assert is_trading_day(date(2026, 1, 1)) is False

    def test_sunday(self):
        """일요일은 휴장일."""
        assert is_trading_day(date(2026, 4, 5)) is False  # 일요일

    def test_saturday(self):
        """토요일은 휴장일."""
        assert is_trading_day(date(2026, 4, 4)) is False  # 토요일

    def test_normal_weekday(self):
        """평일이면서 공휴일이 아닌 날은 거래일."""
        assert is_trading_day(date(2026, 4, 3)) is True  # 금요일

    def test_chuseok(self):
        """추석(9/14~9/16)은 휴장일."""
        assert is_trading_day(date(2026, 9, 14)) is False
        assert is_trading_day(date(2026, 9, 15)) is False
        assert is_trading_day(date(2026, 9, 16)) is False

    def test_seollal(self):
        """설날(1/28~1/30)은 휴장일."""
        assert is_trading_day(date(2026, 1, 28)) is False
        assert is_trading_day(date(2026, 1, 29)) is False
        assert is_trading_day(date(2026, 1, 30)) is False


class TestGetLatestTradingDay:
    """get_latest_trading_day 함수 테스트."""

    def test_holiday_fallback(self):
        """신정(1/1)이면 전일 영업일(12/31) 반환."""
        result = get_latest_trading_day(date(2026, 1, 1))
        assert result == date(2025, 12, 31)  # 수요일

    def test_trading_day_returns_self(self):
        """거래일이면 자기 자신 반환."""
        d = date(2026, 4, 3)  # 금요일
        assert get_latest_trading_day(d) == d

    def test_weekend_fallback(self):
        """주말이면 직전 금요일 반환."""
        result = get_latest_trading_day(date(2026, 4, 5))  # 일요일
        assert result == date(2026, 4, 3)  # 금요일

    def test_saturday_fallback(self):
        """토요일이면 직전 금요일 반환."""
        result = get_latest_trading_day(date(2026, 4, 4))  # 토요일
        assert result == date(2026, 4, 3)  # 금요일


class TestGetPrevTradingDay:
    """get_prev_trading_day 함수 테스트."""

    def test_prev_1(self):
        """T-1 거래일 계산."""
        result = get_prev_trading_day(date(2026, 4, 3), n=1)  # 금요일
        assert result == date(2026, 4, 2)  # 목요일

    def test_prev_2_over_weekend(self):
        """주말을 건너뛴 T-2 거래일."""
        result = get_prev_trading_day(date(2026, 4, 7), n=2)  # 화→T-1 월→T-2 금
        assert result == date(2026, 4, 3)

    def test_prev_across_holiday(self):
        """공휴일을 건너뛴 T-N 거래일."""
        # 1/2(금) 기준 T-1 → 12/31(수) (1/1은 신정)
        result = get_prev_trading_day(date(2026, 1, 2), n=1)
        assert result == date(2025, 12, 31)
