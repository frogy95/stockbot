"""Phase 3 Sprint 1 통합 테스트 — 리스크/자금 관리 모듈 간 상호작용 검증."""

from datetime import datetime, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

KST = ZoneInfo("Asia/Seoul")

from core.clients.kis_rest import OrderResponse
from modules.trading.risk_manager import RiskManager, RiskCheckResult
from modules.trading.position_sizer import PositionSizer, PositionSize
from modules.trading.eod_liquidator import EodLiquidator


# === 헬퍼 ===

def _mock_session_factory():
    """테스트용 세션 팩토리 모킹."""
    session = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


def _mock_redis(**kv):
    """Redis 모킹. kv로 get 반환값 설정."""
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=lambda key: kv.get(key))
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)
    redis.ping = AsyncMock(return_value=True)
    return redis


def _make_risk_manager(session_factory, redis):
    """설정이 직접 주입된 RiskManager."""
    rm = RiskManager(session_factory, redis)
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


def _make_position(**overrides):
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


# === 시나리오 1: 시드 → 리스크 매니저 → can_trade 정상 ===

@pytest.mark.asyncio
async def test_initial_state_allows_trade():
    """초기 상태에서 can_trade() True."""
    factory, session = _mock_session_factory()
    redis = _mock_redis()

    rm = _make_risk_manager(factory, redis)

    # 포지션 0개, 일일 손실 0
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    session.execute = AsyncMock(return_value=count_result)

    with patch.object(rm, "check_time_restriction", return_value=True):
        result = await rm.can_trade()

    assert result.allowed is True
    assert result.risk_level == "normal"


# === 시나리오 2: 포지션 5개 → can_trade False ===

@pytest.mark.asyncio
async def test_max_positions_blocks_trade():
    """포지션 5개 채운 후 can_trade False."""
    factory, session = _mock_session_factory()
    redis = _mock_redis()

    rm = _make_risk_manager(factory, redis)

    count_result = MagicMock()
    count_result.scalar_one.return_value = 5
    session.execute = AsyncMock(return_value=count_result)

    with patch.object(rm, "check_time_restriction", return_value=True):
        result = await rm.can_trade()

    assert result.allowed is False
    assert "포지션" in result.reason


# === 시나리오 3: 포지션 사이저 정확도 ===

@pytest.mark.asyncio
async def test_position_sizer_accuracy():
    """잔고 1,000만원, 일반 종목 50,000원 → 수량 20."""
    factory, session = _mock_session_factory()
    ps = PositionSizer(factory)
    ps._position_size_pct = 10.0
    ps._leverage_position_size_pct = 5.0

    stock_mock = MagicMock()
    stock_mock.stock_name = "삼성전자"
    stock_mock.stock_type = "주식"

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = stock_mock
    session.execute = AsyncMock(return_value=result_mock)

    size = await ps.calculate("005930", 50000, 10_000_000)

    assert size.invest_amount == 1_000_000
    assert size.quantity == 20
    assert size.is_leverage is False
    assert size.size_pct == 10.0


# === 시나리오 4: 비상 정지 → 매매 전면 차단 ===

@pytest.mark.asyncio
async def test_emergency_stop_blocks_all_trading():
    """비상 정지 활성 시 can_trade() False (emergency)."""
    factory, session = _mock_session_factory()
    redis = _mock_redis(**{"risk:emergency_stop": "1"})

    rm = _make_risk_manager(factory, redis)

    with patch.object(rm, "check_time_restriction", return_value=True):
        result = await rm.can_trade()

    assert result.allowed is False
    assert result.risk_level == "emergency"
    assert "비상 정지" in result.reason


# === 시나리오 5: eod_liquidator 미청산 처리 ===

@pytest.mark.asyncio
async def test_eod_liquidator_clears_positions():
    """positions 2개 → liquidate_all() → 매도 주문 2건 + trade_history 기록."""
    factory, session = _mock_session_factory()
    redis = _mock_redis()

    rest_client = AsyncMock()
    rest_client.place_order = AsyncMock(
        return_value=OrderResponse(order_no="ODNO1", stock_code="005930", message="OK")
    )

    eod = EodLiquidator(factory, rest_client, redis)

    positions = [
        _make_position(),
        _make_position(id=2, stock_code="069500"),
    ]

    select_result = MagicMock()
    select_result.scalars.return_value.all.return_value = positions
    delete_result = MagicMock()
    session.execute = AsyncMock(side_effect=[select_result, delete_result])

    added = []
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))

    kst_now = datetime(2026, 3, 30, 14, 50, tzinfo=KST)
    with patch.object(eod, "_now_kst", return_value=kst_now):
        count = await eod.liquidate_all()

    assert count == 2
    assert rest_client.place_order.call_count == 2

    histories = [o for o in added if hasattr(o, "exit_reason")]
    assert len(histories) == 2
    assert all(h.exit_reason == "eod" for h in histories)

    session.commit.assert_awaited_once()
