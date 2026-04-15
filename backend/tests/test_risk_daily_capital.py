"""Task 1 테스트: daily_loss 분모를 당일 시작 잔고(Redis 캐시)로 교체.

- reset_daily_counters() 호출 시 KIS 잔고 + 활성 포지션 원금 합계를 Redis에 캐시
- check_daily_loss() / record_loss() 비상 정지 체크에서 캐시된 값을 분모로 사용
- 캐시 미스 시 기존 방식(활성 포지션 원금 합계)으로 폴백
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.trading.risk_manager import (
    REDIS_CONSECUTIVE_LOSS,
    REDIS_EMERGENCY_STOP,
    RiskManager,
)


REDIS_DAILY_CAPITAL = "risk:daily_capital"


# === 픽스처 ===


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
def mock_rest_client():
    client = AsyncMock()
    balance = MagicMock()
    balance.available_cash = 3_000_000
    balance.total_eval_amount = 5_000_000
    client.get_balance = AsyncMock(return_value=balance)
    return client


@pytest.fixture
def risk_manager(mock_session_factory, mock_redis, mock_rest_client):
    factory, _ = mock_session_factory
    rm = RiskManager(
        session_factory=factory,
        redis_client=mock_redis,
        rest_client=mock_rest_client,
    )
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
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


# === 테스트 ===


@pytest.mark.asyncio
async def test_reset_daily_counters_caches_daily_capital(
    risk_manager, mock_session_factory, mock_redis, mock_rest_client
):
    """reset_daily_counters 호출 시 KIS 가용잔고 + 활성 포지션 원금을 Redis에 캐시."""
    _, session = mock_session_factory
    # 활성 포지션 원금 합계 2,000,000
    session.execute = AsyncMock(side_effect=[_mock_scalar_one(2_000_000)])

    await risk_manager.reset_daily_counters()

    # 기존 카운터 삭제 확인
    assert mock_redis.delete.await_count >= 3

    # daily_capital = 가용현금(3,000,000) + 포지션 원금(2,000,000) = 5,000,000
    set_calls = [c for c in mock_redis.set.await_args_list if c.args and c.args[0] == REDIS_DAILY_CAPITAL]
    assert len(set_calls) == 1
    assert set_calls[0].args[1] == "5000000"


@pytest.mark.asyncio
async def test_reset_daily_counters_no_cache_when_rest_client_fails(
    risk_manager, mock_session_factory, mock_redis, mock_rest_client
):
    """rest_client.get_balance 실패 시 Redis 캐시 설정 안 함 (폴백 유지)."""
    _, _ = mock_session_factory
    mock_rest_client.get_balance = AsyncMock(side_effect=Exception("KIS 일시 장애"))

    await risk_manager.reset_daily_counters()

    set_calls = [c for c in mock_redis.set.await_args_list if c.args and c.args[0] == REDIS_DAILY_CAPITAL]
    assert len(set_calls) == 0


@pytest.mark.asyncio
async def test_check_daily_loss_uses_cached_capital(
    risk_manager, mock_session_factory, mock_redis
):
    """Redis 캐시가 있으면 분모로 사용하고 total_capital DB 쿼리는 스킵."""
    _, session = mock_session_factory
    # unrealized -100,000 + realized -200,000 = -300,000
    # 캐시된 daily_capital = 5,000,000 → -6.0% <= -3% → True
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_one(-100_000),  # unrealized
            _mock_scalar_one(-200_000),  # realized
        ]
    )

    async def redis_get(key):
        if key == REDIS_DAILY_CAPITAL:
            return "5000000"
        return None

    mock_redis.get = AsyncMock(side_effect=redis_get)

    result = await risk_manager.check_daily_loss()

    assert result is True
    # total_capital DB 쿼리가 실행되지 않음 (2회만 호출)
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_check_daily_loss_fallback_when_no_cache(
    risk_manager, mock_session_factory, mock_redis
):
    """캐시 미스 시 기존 방식(포지션 원금 합계)으로 폴백."""
    _, session = mock_session_factory
    # 3회 호출: unrealized, realized, total_capital
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_one(-50_000),
            _mock_scalar_one(-50_000),
            _mock_scalar_one(5_000_000),
        ]
    )
    mock_redis.get = AsyncMock(return_value=None)

    result = await risk_manager.check_daily_loss()

    # -100,000 / 5,000,000 = -2% > -3% → False
    assert result is False
    assert session.execute.await_count == 3


@pytest.mark.asyncio
async def test_daily_loss_blocks_after_full_exit(
    risk_manager, mock_session_factory, mock_redis
):
    """전액 청산 후(포지션 0)에도 캐시된 시작 잔고 기준으로 loss 판단."""
    _, session = mock_session_factory
    # 활성 포지션 전액 청산 → unrealized=0, realized=-200,000
    # 캐시된 daily_capital = 5,000,000 → -4% <= -3% → True
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_one(0),          # unrealized (포지션 없음)
            _mock_scalar_one(-200_000),   # realized 손실
        ]
    )

    async def redis_get(key):
        if key == REDIS_DAILY_CAPITAL:
            return "5000000"
        return None

    mock_redis.get = AsyncMock(side_effect=redis_get)

    result = await risk_manager.check_daily_loss()
    assert result is True


@pytest.mark.asyncio
async def test_record_loss_emergency_uses_cached_capital(
    risk_manager, mock_session_factory, mock_redis
):
    """record_loss 내부 비상 정지 체크도 캐시된 시작 잔고를 분모로 사용."""
    _, session = mock_session_factory
    # unrealized 0 + realized -250,000 / daily_capital 5,000,000 = -5% <= -4% → 비상 정지
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_one(0),          # unrealized
            _mock_scalar_one(-250_000),   # realized
        ]
    )

    async def redis_get(key):
        if key == REDIS_CONSECUTIVE_LOSS:
            return "0"
        if key == REDIS_DAILY_CAPITAL:
            return "5000000"
        return None

    mock_redis.get = AsyncMock(side_effect=redis_get)

    with patch("modules.trading.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 10, 0)
        mock_dt.combine = datetime.combine
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        await risk_manager.record_loss()

    # REDIS_EMERGENCY_STOP 플래그 설정됐는지 확인
    emergency_calls = [
        c for c in mock_redis.set.await_args_list
        if c.args and c.args[0] == REDIS_EMERGENCY_STOP
    ]
    assert len(emergency_calls) == 1
    # total_capital DB 쿼리는 호출되지 않음 (캐시만 사용)
    assert session.execute.await_count == 2
