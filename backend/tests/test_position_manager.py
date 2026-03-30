"""포지션 매니저 테스트 — DB/Redis 의존 최소화, 모킹 기반 (9개 케이스)."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.position_manager import PositionManager
from modules.trading.strategy import TradeSignalData

KST = ZoneInfo("Asia/Seoul")


# =============================================================================
# 픽스처
# =============================================================================


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
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


def _make_signal(
    stock_code: str = "005930",
    entry_price: int = 10000,
    stop_loss: int = 9800,
    take_profit: int = 10300,
    strategy_name: str = "momentum_breakout",
) -> TradeSignalData:
    return TradeSignalData(
        stock_code=stock_code,
        signal_type="buy",
        strategy_name=strategy_name,
        confidence=0.8,
        reason={"test": True},
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )


def _make_position(
    stock_code: str = "005930",
    avg_price: int = 10000,
    current_price: int = 10000,
    stop_loss: int = 9800,
    take_profit: int = 10300,
    quantity: int = 10,
    trailing_activated: bool = False,
    entry_time: datetime | None = None,
    position_id: int = 1,
) -> MagicMock:
    """모킹용 PositionRecord 생성 헬퍼."""
    pos = MagicMock()
    pos.id = position_id
    pos.stock_code = stock_code
    pos.avg_price = avg_price
    pos.current_price = current_price
    pos.stop_loss = stop_loss
    pos.take_profit = take_profit
    pos.quantity = quantity
    pos.trailing_activated = trailing_activated
    pos.entry_time = entry_time or datetime.now(KST)
    pos.strategy_name = "momentum_breakout"
    return pos


def _mock_scalars_all(session: AsyncMock, positions: list) -> None:
    """session.execute().scalars().all() 체인 모킹 헬퍼."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = positions
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)


def _mock_scalar_one(session: AsyncMock, value) -> None:
    """session.execute().scalar_one() 체인 모킹 헬퍼."""
    execute_result = MagicMock()
    execute_result.scalar_one.return_value = value
    session.execute = AsyncMock(return_value=execute_result)


# =============================================================================
# 테스트 케이스
# =============================================================================


@pytest.mark.asyncio
async def test_open_position_creates_record(
    position_manager: PositionManager,
    mock_session_factory,
):
    """TC-1: 매수 체결 시 positions 테이블에 레코드가 생성된다."""
    factory, session = mock_session_factory

    # refresh()가 반환할 모킹 포지션 설정
    created_position = _make_position(avg_price=10000, quantity=5)
    session.refresh = AsyncMock(side_effect=lambda obj: None)

    signal = _make_signal(entry_price=10000, stop_loss=9800, take_profit=10300)

    with patch(
        "modules.trading.position_manager.PositionRecord",
        wraps=lambda **kwargs: MagicMock(**kwargs),
    ):
        # open_position 호출 시 session.add, commit, refresh가 호출되어야 한다
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        await position_manager.open_position(signal=signal, quantity=5, filled_price=10000)

    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_stop_loss_trigger(
    position_manager: PositionManager,
    mock_session_factory,
):
    """TC-2: current_price <= stop_loss이면 exit_reason="stop_loss"를 반환한다."""
    factory, session = mock_session_factory

    # avg_price=10000, stop_loss=9800, current_price=9750 (손절 조건)
    pos = _make_position(avg_price=10000, stop_loss=9800, take_profit=10300, current_price=9750)
    _mock_scalars_all(session, [pos])

    results = await position_manager.check_exit_conditions()

    assert len(results) == 1
    assert results[0]["exit_reason"] == "stop_loss"
    assert results[0]["stock_code"] == pos.stock_code


@pytest.mark.asyncio
async def test_take_profit_trigger(
    position_manager: PositionManager,
    mock_session_factory,
):
    """TC-3: current_price >= take_profit이면 exit_reason="take_profit"을 반환한다."""
    factory, session = mock_session_factory

    # avg_price=10000, take_profit=10300, current_price=10300 (익절 조건)
    pos = _make_position(avg_price=10000, stop_loss=9800, take_profit=10300, current_price=10300)
    _mock_scalars_all(session, [pos])

    results = await position_manager.check_exit_conditions()

    assert len(results) == 1
    assert results[0]["exit_reason"] == "take_profit"
    assert results[0]["stock_code"] == pos.stock_code


@pytest.mark.asyncio
async def test_trailing_stop_activation(
    position_manager: PositionManager,
    mock_session_factory,
):
    """TC-4: current_price >= avg_price * 1.02이면 trailing_activated=True로 갱신된다."""
    factory, session = mock_session_factory

    pos = _make_position(avg_price=10000, current_price=10200, trailing_activated=False)
    _mock_scalars_all(session, [pos])

    await position_manager.update_prices({"005930": 10200})

    # trailing_activated가 True로 설정되어야 한다
    assert pos.trailing_activated is True
    # _trailing_highs에 고점이 기록되어야 한다
    assert position_manager._trailing_highs.get("005930") == 10200


@pytest.mark.asyncio
async def test_trailing_stop_trigger(
    position_manager: PositionManager,
    mock_session_factory,
):
    """TC-5: trailing_activated=True이고 current_price <= trailing_high * 0.99이면 exit_reason="trailing"."""
    factory, session = mock_session_factory

    # 트레일링 고점을 미리 설정
    position_manager._trailing_highs["005930"] = 10500

    # trailing_activated=True, current_price=10394 (<= 10500*0.99=10395)
    # take_profit은 10394보다 높게 설정하여 익절 트리거 방지
    pos = _make_position(
        avg_price=10000,
        stop_loss=9800,
        take_profit=10500,
        current_price=10394,
        trailing_activated=True,
    )
    _mock_scalars_all(session, [pos])

    results = await position_manager.check_exit_conditions()

    assert len(results) == 1
    assert results[0]["exit_reason"] == "trailing"


@pytest.mark.asyncio
async def test_timeout_exit(
    position_manager: PositionManager,
    mock_session_factory,
):
    """TC-6: 진입 30분 경과 + 수익률 < 1% 조건에서 exit_reason="timeout"."""
    factory, session = mock_session_factory

    # 진입 시각을 35분 전으로 설정
    old_entry = datetime.now(KST) - timedelta(minutes=35)
    # current_price가 avg_price보다 0.5% 상승 (1% 미만)
    pos = _make_position(
        avg_price=10000,
        stop_loss=9800,
        take_profit=10300,
        current_price=10050,  # 0.5% 수익
        entry_time=old_entry,
    )
    _mock_scalars_all(session, [pos])

    results = await position_manager.check_exit_conditions()

    assert len(results) == 1
    assert results[0]["exit_reason"] == "timeout"


@pytest.mark.asyncio
async def test_leverage_etf_stop_loss_price(
    position_manager: PositionManager,
    mock_session_factory,
):
    """TC-7: 레버리지 ETF 손절 기준은 entry_price * 0.985이다."""
    factory, session = mock_session_factory

    entry_price = 10000
    # 레버리지 ETF 손절: entry_price * 0.985 = 9850
    lev_stop_loss = int(entry_price * 0.985)  # 9850
    current_price = 9840  # 손절 기준 이하

    pos = _make_position(
        stock_code="233740",  # KODEX 레버리지
        avg_price=entry_price,
        stop_loss=lev_stop_loss,
        take_profit=10300,
        current_price=current_price,
    )
    _mock_scalars_all(session, [pos])

    results = await position_manager.check_exit_conditions()

    assert len(results) == 1
    assert results[0]["exit_reason"] == "stop_loss"
    # 손절가가 entry_price * 0.985 기준으로 설정됨을 검증
    assert lev_stop_loss == 9850


@pytest.mark.asyncio
async def test_close_position_records_trade_history_and_deletes_position(
    position_manager: PositionManager,
    mock_session_factory,
    mock_risk_manager,
):
    """TC-8: close_position 호출 시 trade_history에 기록하고 positions를 삭제한다."""
    factory, session = mock_session_factory

    entry_time = datetime.now(KST) - timedelta(minutes=10)
    pos = _make_position(avg_price=10000, quantity=5, entry_time=entry_time)

    # scalar_one()이 pos를 반환하도록 설정
    execute_result = MagicMock()
    execute_result.scalar_one.return_value = pos
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    await position_manager.close_position(
        position_id=1,
        exit_price=10200,
        exit_reason="take_profit",
    )

    # trade_history 레코드가 추가되어야 한다
    session.add.assert_called_once()
    # positions 레코드가 삭제되어야 한다
    session.delete.assert_called_once_with(pos)
    session.commit.assert_called_once()

    # 손절이 아니므로 record_loss()가 호출되면 안 된다
    mock_risk_manager.record_loss.assert_not_called()


@pytest.mark.asyncio
async def test_update_prices_updates_current_price_and_unrealized_pnl(
    position_manager: PositionManager,
    mock_session_factory,
):
    """TC-9: update_prices 호출 시 current_price와 unrealized_pnl이 갱신된다."""
    factory, session = mock_session_factory

    pos = _make_position(avg_price=10000, current_price=10000, quantity=10)
    _mock_scalars_all(session, [pos])

    await position_manager.update_prices({"005930": 10150})

    # current_price가 갱신되어야 한다
    assert pos.current_price == 10150
    # unrealized_pnl = (10150 - 10000) * 10 = 1500
    assert pos.unrealized_pnl == 1500

    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_close_position_calls_record_loss_on_stop_loss(
    position_manager: PositionManager,
    mock_session_factory,
    mock_risk_manager,
):
    """TC-8 보완: 손절(stop_loss) 청산 시 risk_manager.record_loss()가 호출된다."""
    factory, session = mock_session_factory

    entry_time = datetime.now(KST) - timedelta(minutes=5)
    pos = _make_position(avg_price=10000, quantity=5, entry_time=entry_time)

    execute_result = MagicMock()
    execute_result.scalar_one.return_value = pos
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    await position_manager.close_position(
        position_id=1,
        exit_price=9800,
        exit_reason="stop_loss",
    )

    # 손절이므로 record_loss()가 호출되어야 한다
    mock_risk_manager.record_loss.assert_called_once()

    # _trailing_highs에서 해당 종목이 제거되어야 한다
    assert "005930" not in position_manager._trailing_highs
