"""Task 2 테스트: record_loss 트리거 확장 + trailing_highs Redis 이관."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from modules.trading.position_manager import (
    PositionManager,
    REDIS_TRAILING_HIGHS_KEY,
)

KST = ZoneInfo("Asia/Seoul")
REDIS_CONSECUTIVE_LOSS = "risk:consecutive_loss_count"


# === 픽스처 ===


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.hset = AsyncMock()
    redis.hget = AsyncMock(return_value=None)
    redis.hdel = AsyncMock(return_value=True)
    redis.hgetall = AsyncMock(return_value={})
    return redis


@pytest.fixture
def mock_session_factory():
    session = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def mock_risk_manager():
    rm = AsyncMock()
    rm.record_loss = AsyncMock()
    return rm


@pytest.fixture
def position_manager(mock_session_factory, mock_redis, mock_risk_manager):
    factory, _ = mock_session_factory
    return PositionManager(
        session_factory=factory,
        redis_client=mock_redis,
        risk_manager=mock_risk_manager,
    )


def _make_position(
    stock_code: str = "005930",
    avg_price: int = 10000,
    current_price: int = 10000,
    quantity: int = 10,
    trailing_activated: bool = False,
    entry_time: datetime | None = None,
    position_id: int = 1,
) -> MagicMock:
    pos = MagicMock()
    pos.id = position_id
    pos.stock_code = stock_code
    pos.avg_price = avg_price
    pos.current_price = current_price
    pos.stop_loss = 9800
    pos.take_profit = 10300
    pos.quantity = quantity
    pos.trailing_activated = trailing_activated
    pos.entry_time = entry_time or datetime.now(KST) - timedelta(minutes=5)
    pos.strategy_name = "momentum_breakout"
    return pos


def _mock_scalar_one(session: AsyncMock, value) -> None:
    execute_result = MagicMock()
    execute_result.scalar_one.return_value = value
    session.execute = AsyncMock(return_value=execute_result)


def _mock_scalars_all(session: AsyncMock, positions: list) -> None:
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = positions
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)


async def _run_close(
    pm: PositionManager, session: AsyncMock, pos: MagicMock, exit_price: int, reason: str
):
    _mock_scalar_one(session, pos)
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    await pm.close_position(position_id=pos.id, exit_price=exit_price, exit_reason=reason)


# === record_loss 확장 테스트 ===


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_reason", ["trailing", "timeout", "stop_loss"])
async def test_close_position_loss_calls_record_loss_regardless_of_reason(
    position_manager, mock_session_factory, mock_risk_manager, exit_reason
):
    """realized_pnl < 0이면 exit_reason 무관하게 record_loss() 호출."""
    _, session = mock_session_factory
    pos = _make_position(avg_price=10000, quantity=10)
    # exit_price 9500 < avg_price 10000 → realized_pnl = -5000
    await _run_close(position_manager, session, pos, 9500, exit_reason)

    mock_risk_manager.record_loss.assert_called_once()


@pytest.mark.asyncio
async def test_close_position_profit_does_not_call_record_loss(
    position_manager, mock_session_factory, mock_risk_manager
):
    """realized_pnl > 0일 때 record_loss() 미호출 (exit_reason 무관)."""
    _, session = mock_session_factory
    pos = _make_position(avg_price=10000, quantity=10)
    await _run_close(position_manager, session, pos, 10500, "take_profit")

    mock_risk_manager.record_loss.assert_not_called()


@pytest.mark.asyncio
async def test_close_position_profit_resets_consecutive_loss(
    position_manager, mock_session_factory, mock_redis
):
    """수익 청산 시 Redis `risk:consecutive_loss_count` 삭제."""
    _, session = mock_session_factory
    pos = _make_position(avg_price=10000, quantity=10)
    await _run_close(position_manager, session, pos, 10500, "take_profit")

    delete_calls = [c.args[0] for c in mock_redis.delete.await_args_list if c.args]
    assert REDIS_CONSECUTIVE_LOSS in delete_calls


# === trailing_highs Redis 이관 테스트 ===


@pytest.mark.asyncio
async def test_update_prices_stores_trailing_high_in_redis(
    position_manager, mock_session_factory, mock_redis
):
    """trailing_activated 종목의 신규 고점이 Redis HSET에 기록된다."""
    _, session = mock_session_factory
    pos = _make_position(
        avg_price=10000, current_price=10000, trailing_activated=True
    )
    position_manager._trailing_highs["005930"] = 10100  # 기존 고점
    _mock_scalars_all(session, [pos])

    await position_manager.update_prices({"005930": 10300})

    assert position_manager._trailing_highs["005930"] == 10300
    mock_redis.hset.assert_awaited_with(REDIS_TRAILING_HIGHS_KEY, "005930", "10300")


@pytest.mark.asyncio
async def test_update_prices_no_redis_write_when_not_new_high(
    position_manager, mock_session_factory, mock_redis
):
    """고점 갱신이 없으면 Redis HSET 호출도 없다."""
    _, session = mock_session_factory
    pos = _make_position(
        avg_price=10000, current_price=10500, trailing_activated=True
    )
    position_manager._trailing_highs["005930"] = 10500  # 이미 더 높거나 같음
    _mock_scalars_all(session, [pos])

    await position_manager.update_prices({"005930": 10400})

    mock_redis.hset.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_trailing_highs_restores_from_redis(
    position_manager, mock_redis
):
    """load_trailing_highs()가 Redis HGETALL 결과를 로컬 캐시에 복원한다."""
    mock_redis.hgetall = AsyncMock(
        return_value={"005930": "10500", "000660": "48000"}
    )

    await position_manager.load_trailing_highs()

    assert position_manager._trailing_highs == {"005930": 10500, "000660": 48000}


@pytest.mark.asyncio
async def test_close_position_removes_trailing_high_from_redis(
    position_manager, mock_session_factory, mock_redis
):
    """close_position 시 Redis HSET에서 해당 종목 제거."""
    _, session = mock_session_factory
    pos = _make_position(avg_price=10000, quantity=10)
    position_manager._trailing_highs["005930"] = 10500
    await _run_close(position_manager, session, pos, 10200, "take_profit")

    mock_redis.hdel.assert_awaited_with(REDIS_TRAILING_HIGHS_KEY, "005930")
    assert "005930" not in position_manager._trailing_highs


@pytest.mark.asyncio
async def test_trailing_highs_survives_restart(
    mock_session_factory, mock_redis, mock_risk_manager
):
    """서버 재시작 시나리오: 이전 프로세스가 저장한 고점을 새 PositionManager가 복원."""
    # 1) 이전 프로세스: 고점을 Redis에 기록
    mock_redis.hgetall = AsyncMock(return_value={"005930": "10800"})

    # 2) 새 프로세스: PositionManager 생성 + load_trailing_highs 호출
    factory, _ = mock_session_factory
    new_pm = PositionManager(
        session_factory=factory,
        redis_client=mock_redis,
        risk_manager=mock_risk_manager,
    )
    assert new_pm._trailing_highs == {}  # 인메모리 초기 상태

    await new_pm.load_trailing_highs()
    assert new_pm._trailing_highs == {"005930": 10800}
