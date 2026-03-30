"""리스크 매니저 테스트 — DB 의존 최소화, 모킹 기반."""
from __future__ import annotations

from datetime import datetime, time, date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from modules.trading.risk_manager import (
    RiskCheckResult,
    RiskManager,
    RiskSettingsLocked,
    REDIS_COOLDOWN,
    REDIS_CONSECUTIVE_LOSS,
    REDIS_EMERGENCY_STOP,
)


# === 픽스처 ===


@pytest.fixture
def mock_redis():
    """Redis 클라이언트 모킹."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)
    return redis


@pytest.fixture
def mock_session_factory():
    """DB 세션 팩토리 모킹."""
    session = AsyncMock()
    factory = MagicMock()
    # async context manager 지원
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def risk_manager(mock_session_factory, mock_redis):
    """기본 설정이 로드된 RiskManager 인스턴스."""
    factory, _ = mock_session_factory
    rm = RiskManager(session_factory=factory, redis_client=mock_redis)
    # 기본 설정 직접 주입 (DB 조회 없이)
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
        "risk_lock_during_trading": "true",
    }
    rm._loaded = True
    return rm


def _mock_scalar_one(value):
    """execute 결과의 scalar_one() 모킹 헬퍼."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


# === 테스트 ===


@pytest.mark.asyncio
async def test_daily_loss_exceeded_blocks_trade(
    risk_manager, mock_session_factory, mock_redis
):
    """1. 일일 손실 한도 초과 시 can_trade() False."""
    _, session = mock_session_factory
    # can_trade 순서: emergency(Redis) → time → cooldown(Redis) → consecutive(Redis)
    #   → daily_loss(DB×3) → position_limit(DB×1)
    # 미실현 -200,000 + 실현 -100,000 / 원금 5,000,000 = -6% > -3% 한도
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_one(-200000),  # check_daily_loss: unrealized_pnl
            _mock_scalar_one(-100000),  # check_daily_loss: realized_pnl
            _mock_scalar_one(5000000),  # check_daily_loss: total_capital
        ]
    )
    mock_redis.get = AsyncMock(return_value=None)  # 비상정지/쿨다운/연속손절 없음
    mock_redis.ttl = AsyncMock(return_value=-2)     # 쿨다운 없음

    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 10, 0)
        mock_dt.combine = datetime.combine
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        result = await risk_manager.can_trade()

    assert result.allowed is False
    assert "손실" in result.reason
    assert result.risk_level == "blocked"


@pytest.mark.asyncio
async def test_max_position_exceeded_blocks_trade(
    risk_manager, mock_session_factory, mock_redis
):
    """2. 최대 포지션 수 초과 시 can_trade() False."""
    _, session = mock_session_factory
    # 포지션 5개 (한도 5 → 초과)
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_one(-50000),   # unrealized_pnl (한도 이내)
            _mock_scalar_one(0),        # realized_pnl
            _mock_scalar_one(5000000),  # total_capital → -1% 이내
            _mock_scalar_one(5),        # position count = max
        ]
    )
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.ttl = AsyncMock(return_value=-2)

    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 10, 0)
        mock_dt.combine = datetime.combine
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        result = await risk_manager.can_trade()

    assert result.allowed is False
    assert "포지션" in result.reason


@pytest.mark.asyncio
async def test_max_leverage_position_exceeded_blocks_trade(
    risk_manager, mock_session_factory, mock_redis
):
    """3. 최대 레버리지 포지션 초과 시 can_trade(is_leverage=True) False."""
    _, session = mock_session_factory
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_one(-10000),   # unrealized_pnl (이내)
            _mock_scalar_one(0),        # realized_pnl
            _mock_scalar_one(5000000),  # total_capital
            _mock_scalar_one(3),        # position count (이내: 3 < 5)
        ]
    )
    # 레버리지 포지션 2개 (한도 2 → 초과)
    async def mock_get(key):
        if key == REDIS_EMERGENCY_STOP:
            return None
        if key == REDIS_CONSECUTIVE_LOSS:
            return None
        if key == "risk:leverage_position_count":
            return "2"
        return None

    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.ttl = AsyncMock(return_value=-2)

    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 10, 0)
        mock_dt.combine = datetime.combine
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        result = await risk_manager.can_trade(is_leverage=True)

    assert result.allowed is False
    assert "레버리지" in result.reason


@pytest.mark.asyncio
async def test_emergency_stop_active(risk_manager, mock_redis):
    """4. 비상 정지 시 check_emergency_stop() True."""
    mock_redis.get = AsyncMock(return_value="1")

    result = await risk_manager.check_emergency_stop()
    assert result is True


@pytest.mark.asyncio
async def test_consecutive_loss_blocks_trade(
    risk_manager, mock_session_factory, mock_redis
):
    """5. 연속 손절 정지 시 can_trade() False."""
    _, session = mock_session_factory

    async def mock_get(key):
        if key == REDIS_EMERGENCY_STOP:
            return None
        if key == REDIS_CONSECUTIVE_LOSS:
            return "3"  # 한도 3 → 초과
        return None

    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.ttl = AsyncMock(return_value=-2)  # 쿨다운 없음

    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 10, 0)
        mock_dt.combine = datetime.combine
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        result = await risk_manager.can_trade()

    assert result.allowed is False
    assert "연속 손절" in result.reason
    assert result.risk_level == "blocked"


@pytest.mark.asyncio
async def test_cooldown_blocks_trade(
    risk_manager, mock_session_factory, mock_redis
):
    """6. 쿨다운 시 can_trade() False."""
    _, session = mock_session_factory
    mock_redis.get = AsyncMock(return_value=None)  # 비상정지 없음
    mock_redis.ttl = AsyncMock(return_value=1800)  # 쿨다운 30분 남음

    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 10, 0)
        mock_dt.combine = datetime.combine
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        result = await risk_manager.can_trade()

    assert result.allowed is False
    assert "쿨다운" in result.reason
    assert result.risk_level == "blocked"


@pytest.mark.asyncio
async def test_observation_period_blocks_trade(
    risk_manager, mock_session_factory, mock_redis
):
    """7. 09:00~09:30 관망 시 can_trade() False."""
    _, session = mock_session_factory
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.ttl = AsyncMock(return_value=-2)

    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 9, 15)
        mock_dt.combine = datetime.combine
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        result = await risk_manager.can_trade()

    assert result.allowed is False
    assert "시간" in result.reason
    assert result.risk_level == "blocked"


@pytest.mark.asyncio
async def test_no_new_entry_after_cutoff(
    risk_manager, mock_session_factory, mock_redis
):
    """8. 14:30 이후 진입 차단 시 can_trade() False."""
    _, session = mock_session_factory
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.ttl = AsyncMock(return_value=-2)

    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 14, 45)
        mock_dt.combine = datetime.combine
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        result = await risk_manager.can_trade()

    assert result.allowed is False
    assert "시간" in result.reason


@pytest.mark.asyncio
async def test_all_checks_pass_allows_trade(
    risk_manager, mock_session_factory, mock_redis
):
    """9. 모든 조건 충족 시 can_trade() True."""
    _, session = mock_session_factory
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_one(-10000),   # unrealized_pnl (-0.2%)
            _mock_scalar_one(0),        # realized_pnl
            _mock_scalar_one(5000000),  # total_capital
            _mock_scalar_one(2),        # position count (이내)
        ]
    )
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.ttl = AsyncMock(return_value=-2)

    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 10, 0)
        mock_dt.combine = datetime.combine
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        result = await risk_manager.can_trade()

    assert result.allowed is True
    assert result.reason is None
    assert result.risk_level == "normal"


def test_settings_locked_during_trading(risk_manager):
    """10. 장중 설정 변경 시도 시 예외 발생."""
    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 10, 30)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        with pytest.raises(RiskSettingsLocked):
            risk_manager.assert_settings_unlocked()
