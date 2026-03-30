"""당일 청산 강제 (eod_liquidator) 테스트."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from core.clients.kis_rest import OrderResponse
from modules.trading.eod_liquidator import EodLiquidator

KST = ZoneInfo("Asia/Seoul")


def _make_position(**overrides):
    """PositionRecord를 모킹한 간단한 객체 생성."""
    defaults = {
        "id": 1,
        "stock_code": "005930",
        "quantity": 10,
        "avg_price": Decimal("50000"),
        "current_price": Decimal("51000"),
        "unrealized_pnl": 10000,
        "stop_loss": Decimal("49000"),
        "take_profit": Decimal("53000"),
        "trailing_activated": False,
        "entry_time": datetime(2026, 3, 30, 10, 0, tzinfo=KST),
        "strategy_name": "momentum_breakout",
    }
    defaults.update(overrides)
    pos = MagicMock()
    for k, v in defaults.items():
        setattr(pos, k, v)
    return pos


def _make_liquidator():
    """테스트용 EodLiquidator 생성."""
    session = AsyncMock()
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    rest_client = AsyncMock()
    rest_client.place_order = AsyncMock(
        return_value=OrderResponse(
            order_no="ODNO123", stock_code="005930", message="OK"
        )
    )

    redis_client = AsyncMock()

    liquidator = EodLiquidator(session_factory, rest_client, redis_client)
    return liquidator, session, rest_client


# --- 14:50 강제 청산 ---

@pytest.mark.asyncio
async def test_liquidate_all_creates_sell_orders():
    """미청산 포지션 존재 시 매도 주문 + trade_history 기록."""
    liquidator, session, rest_client = _make_liquidator()
    positions = [_make_position(), _make_position(id=2, stock_code="069500")]

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = positions

    execute_returns = [result_mock, MagicMock()]  # select, delete
    session.execute = AsyncMock(side_effect=execute_returns)

    with patch.object(liquidator, "_now_kst", return_value=datetime(2026, 3, 30, 14, 50, tzinfo=KST)):
        count = await liquidator.liquidate_all()

    assert count == 2
    assert rest_client.place_order.call_count == 2
    assert session.add.call_count == 4  # 2 orders + 2 histories
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_liquidate_all_no_positions():
    """포지션 0개 시 아무 동작 없음."""
    liquidator, session, rest_client = _make_liquidator()

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result_mock)

    with patch.object(liquidator, "_now_kst", return_value=datetime(2026, 3, 30, 14, 50, tzinfo=KST)):
        count = await liquidator.liquidate_all()

    assert count == 0
    rest_client.place_order.assert_not_called()


# --- 14:30 진입 차단 ---

def test_entry_blocked_after_1430():
    """14:30 이후 is_entry_blocked() True."""
    liquidator, _, _ = _make_liquidator()
    with patch.object(liquidator, "_now_kst", return_value=datetime(2026, 3, 30, 14, 35, tzinfo=KST)):
        assert liquidator.is_entry_blocked() is True


def test_entry_allowed_before_1430():
    """14:30 이전 is_entry_blocked() False."""
    liquidator, _, _ = _make_liquidator()
    with patch.object(liquidator, "_now_kst", return_value=datetime(2026, 3, 30, 13, 0, tzinfo=KST)):
        assert liquidator.is_entry_blocked() is False


# --- 재시작 시 미청산 처리 ---

@pytest.mark.asyncio
async def test_startup_liquidation_after_1450():
    """14:50 이후 재시작 시 미청산 포지션 즉시 청산."""
    liquidator, session, _ = _make_liquidator()

    # check_and_liquidate_on_startup 내부: select(PositionRecord.id).limit(1)
    id_result_mock = MagicMock()
    id_result_mock.scalar_one_or_none.return_value = 1  # 포지션 존재

    # liquidate_all 내부: select(PositionRecord) + delete
    pos_result_mock = MagicMock()
    pos_result_mock.scalars.return_value.all.return_value = [_make_position()]
    delete_result_mock = MagicMock()

    session.execute = AsyncMock(
        side_effect=[id_result_mock, pos_result_mock, delete_result_mock]
    )

    with patch.object(liquidator, "_now_kst", return_value=datetime(2026, 3, 30, 15, 0, tzinfo=KST)):
        await liquidator.check_and_liquidate_on_startup()

    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_no_liquidation_before_1450():
    """14:50 이전 재시작 시 청산 안함."""
    liquidator, session, rest_client = _make_liquidator()

    with patch.object(liquidator, "_now_kst", return_value=datetime(2026, 3, 30, 10, 0, tzinfo=KST)):
        await liquidator.check_and_liquidate_on_startup()

    rest_client.place_order.assert_not_called()


# --- 청산 결과 trade_history ---

@pytest.mark.asyncio
async def test_liquidation_records_eod_exit_reason():
    """청산 시 trade_history에 exit_reason='eod' 기록."""
    liquidator, session, _ = _make_liquidator()
    positions = [_make_position()]

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = positions

    added_objects = []
    session.execute = AsyncMock(side_effect=[result_mock, MagicMock()])
    session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

    with patch.object(liquidator, "_now_kst", return_value=datetime(2026, 3, 30, 14, 50, tzinfo=KST)):
        await liquidator.liquidate_all()

    histories = [o for o in added_objects if hasattr(o, "exit_reason")]
    assert len(histories) == 1
    assert histories[0].exit_reason == "eod"
