"""매매 엔진 승인 흐름 통합 테스트."""
from __future__ import annotations

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.engine import TradingEngine
from modules.trading.strategy import TradeSignalData

KST = ZoneInfo("Asia/Seoul")


def _make_engine(notifier_manager=None):
    """테스트용 엔진 생성 헬퍼."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="true")  # pipeline_healthy 가드 통과
    engine = TradingEngine(
        signal_generator=AsyncMock(),
        order_manager=AsyncMock(),
        position_manager=AsyncMock(),
        risk_manager=AsyncMock(),
        position_sizer=AsyncMock(),
        eod_liquidator=MagicMock(),
        redis_client=mock_redis,
        notifier_manager=notifier_manager,
    )
    # order_manager._queue mock
    engine._order_manager._queue = MagicMock()
    engine._order_manager._queue.qsize.return_value = 0
    engine._order_manager.get_queue_size.return_value = 0
    return engine


def _make_signal():
    return TradeSignalData(
        stock_code="005930",
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=0.85,
        reason={"rsi": 72, "volume_surge": True},
        entry_price=73000,
        stop_loss=71540,
        take_profit=75190,
    )


def _make_position_size():
    size = MagicMock()
    size.quantity = 10
    size.invest_amount = 730000
    size.is_leverage = False
    size.size_pct = 10.0
    return size


@pytest.mark.asyncio
async def test_semi_auto_signal_creates_approval():
    """반자동 모드: 신호 발생 시 주문 즉시 실행 안 함, 승인 토큰 생성."""
    notifier = AsyncMock()
    notifier.notify_signal = AsyncMock(return_value="test-token-123")
    engine = _make_engine(notifier_manager=notifier)

    signal = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(
        return_value=MagicMock(allowed=True)
    )
    engine._position_sizer.calculate = AsyncMock(return_value=_make_position_size())
    engine._eod_liquidator.is_entry_blocked.return_value = False

    await engine.process_screening_results([{"stock_code": "005930"}])

    # 주문 즉시 실행 안 함
    engine._order_manager.submit_order.assert_not_called()
    # 승인 요청 발송
    notifier.notify_signal.assert_called_once()


@pytest.mark.asyncio
async def test_approval_triggers_order():
    """승인 시 주문 실행."""
    notifier = AsyncMock()
    notifier.handle_approval = AsyncMock(return_value={
        "signal": _make_signal().model_dump(),
        "quantity": 10,
        "action": "approve",
    })
    engine = _make_engine(notifier_manager=notifier)

    result = await engine.approve_signal("test-token-123")
    assert result is True
    engine._order_manager.submit_order.assert_called_once()


@pytest.mark.asyncio
async def test_rejection_cancels_signal():
    """거부 시 주문 미실행."""
    notifier = AsyncMock()
    notifier.handle_approval = AsyncMock(return_value={
        "signal": _make_signal().model_dump(),
        "quantity": 10,
        "action": "reject",
    })
    engine = _make_engine(notifier_manager=notifier)

    result = await engine.reject_signal("test-token-123")
    assert result is True
    engine._order_manager.submit_order.assert_not_called()


@pytest.mark.asyncio
async def test_timeout_expires_signal():
    """타임아웃 시 승인 만료."""
    notifier = AsyncMock()
    notifier.handle_approval = AsyncMock(return_value=None)
    engine = _make_engine(notifier_manager=notifier)

    result = await engine.approve_signal("expired-token")
    assert result is False


@pytest.mark.asyncio
async def test_auto_mode_bypasses_approval():
    """자동 모드 (notifier_manager=None): 승인 없이 즉시 주문."""
    engine = _make_engine(notifier_manager=None)

    signal = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(
        return_value=MagicMock(allowed=True)
    )
    engine._position_sizer.calculate = AsyncMock(return_value=_make_position_size())
    engine._eod_liquidator.is_entry_blocked.return_value = False

    await engine.process_screening_results([{"stock_code": "005930"}])

    # 즉시 주문 실행
    engine._order_manager.submit_order.assert_called_once()


@pytest.mark.asyncio
async def test_approval_timeout_by_time_zone():
    """시간대별 승인 타임아웃: 골든타임(20초), 마감전(15초), 일반(30초)."""
    # 골든타임: 09:30~10:30
    golden = datetime(2026, 3, 30, 10, 0, 0, tzinfo=KST)
    assert TradingEngine._get_approval_timeout_static(golden) == 20

    # 마감 전: 14:00~14:30
    closing = datetime(2026, 3, 30, 14, 15, 0, tzinfo=KST)
    assert TradingEngine._get_approval_timeout_static(closing) == 15

    # 일반
    normal = datetime(2026, 3, 30, 11, 0, 0, tzinfo=KST)
    assert TradingEngine._get_approval_timeout_static(normal) == 30
