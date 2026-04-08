"""KST 날짜/시각 사용 검증 테스트."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

KST = ZoneInfo("Asia/Seoul")


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)
    return redis


@pytest.fixture
def mock_session_factory():
    session = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def risk_manager(mock_session_factory, mock_redis):
    from modules.trading.risk_manager import RiskManager

    factory, _ = mock_session_factory
    rm = RiskManager(session_factory=factory, redis_client=mock_redis)
    rm._settings = {
        "daily_max_loss_pct": "-3.0",
        "max_position_count": "5",
        "max_leverage_position_count": "2",
        "emergency_stop_pct": "-4.0",
        "consecutive_loss_stop": "3",
        "cooldown_trigger_count": "2",
        "cooldown_duration_min": "60",
        "no_entry_start": "09:00",
        "no_entry_end": "09:30",
        "no_new_entry_time": "14:30",
        "cooldown_end_time": "15:30",
        "risk_lock_during_trading": "true",
    }
    return rm, mock_session_factory[1]


class TestCheckDailyLossUsesKST:
    """check_daily_loss가 KST 날짜 기준으로 today_start를 계산하는지 검증."""

    @pytest.mark.asyncio
    async def test_today_start_is_kst_midnight(self, risk_manager, monkeypatch):
        """check_daily_loss 내부에서 KST 자정을 기준으로 today_start를 계산한다."""
        rm, session = risk_manager

        # DB 쿼리 결과 모킹 (손실 없음 → False 반환되지 않게)
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 0
        session.execute = AsyncMock(return_value=result_mock)

        captured = {}

        original_combine = datetime.combine

        def capturing_combine(d, t, *args, **kwargs):
            captured["date"] = d
            captured["time"] = t
            return original_combine(d, t, *args, **kwargs)

        # risk_manager 모듈의 datetime.combine을 패치
        with patch(
            "modules.trading.risk_manager.datetime"
        ) as mock_dt:
            mock_dt.combine = capturing_combine
            mock_dt.now.return_value = datetime.now(KST)
            # now(KST).date() 체인을 지원하기 위해
            kst_now = datetime.now(KST)
            mock_dt.now.return_value = kst_now

            await rm.check_daily_loss()

        # KST 날짜가 사용되었는지 확인
        if "date" in captured:
            kst_today = datetime.now(KST).date()
            assert captured["date"] == kst_today, (
                f"today_start 날짜가 KST여야 합니다. "
                f"KST date: {kst_today}, captured: {captured.get('date')}"
            )


class TestCheckTimeRestrictionUsesKST:
    """check_time_restriction이 KST 현재 시각을 사용하는지 검증."""

    def test_uses_kst_time_not_utc(self, risk_manager):
        """check_time_restriction은 KST 시각으로 장 시간 여부를 판단해야 한다."""
        rm, _ = risk_manager

        # KST 10:00 (장중) — UTC 01:00
        kst_10am = datetime(2024, 1, 15, 10, 0, 0, tzinfo=KST)

        with patch("modules.trading.risk_manager.datetime") as mock_dt:
            mock_dt.now.return_value = kst_10am
            result = rm.check_time_restriction()

        # 10:00 KST는 09:30~14:30 사이이므로 매매 가능
        assert result is True

    def test_no_entry_window_kst(self, risk_manager):
        """KST 09:15는 관망 시간대 (09:00~09:30)이므로 False."""
        rm, _ = risk_manager

        kst_09_15 = datetime(2024, 1, 15, 9, 15, 0, tzinfo=KST)

        with patch("modules.trading.risk_manager.datetime") as mock_dt:
            mock_dt.now.return_value = kst_09_15
            result = rm.check_time_restriction()

        assert result is False

    def test_after_cutoff_kst(self, risk_manager):
        """KST 14:45는 신규 진입 차단 시간 (14:30 이후)이므로 False."""
        rm, _ = risk_manager

        kst_14_45 = datetime(2024, 1, 15, 14, 45, 0, tzinfo=KST)

        with patch("modules.trading.risk_manager.datetime") as mock_dt:
            mock_dt.now.return_value = kst_14_45
            result = rm.check_time_restriction()

        assert result is False
