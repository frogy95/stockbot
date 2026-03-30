"""Phase 3 전체 흐름 통합 테스트 — 신호→승인→주문→포지션 사이클."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from core.config import settings
from core.redis import RedisClient
from modules.notifier.approval import ApprovalManager
from modules.notifier.manager import NotifierManager
from modules.trading.engine import TradingEngine
from modules.trading.strategy import TradeSignalData
from main import create_app

import pytest_asyncio


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


@pytest_asyncio.fixture
async def redis_client():
    client = RedisClient(settings.redis_url)
    await client.connect()
    yield client
    # 테스트 후 approval 키 정리
    keys = await client.scan_keys("approval:*")
    for k in keys:
        await client.delete(k)
    await client.disconnect()


@pytest_asyncio.fixture
async def approval_manager(redis_client):
    return ApprovalManager(redis_client)


@pytest.mark.asyncio
async def test_signal_to_approval_to_order(approval_manager, redis_client):
    """신호→승인토큰→승인콜백→주문실행 전체 흐름."""
    signal = _make_signal()
    bot = MagicMock()
    bot.send_signal_alert = AsyncMock(return_value=100)
    bot.format_fill_message = MagicMock(return_value="체결")
    bot.edit_message = AsyncMock()
    bot.format_signal_message = MagicMock(return_value=("msg", MagicMock()))

    notifier = NotifierManager(bot, approval_manager, MagicMock())

    # 1. 신호 알림 (승인 토큰 생성)
    token = await notifier.notify_signal(signal, quantity=10, timeout_sec=30)
    assert len(token) == 36

    # 2. 승인 처리
    result = await notifier.handle_approval(token, "approve")
    assert result is not None
    assert result["action"] == "approve"
    assert result["signal"]["stock_code"] == "005930"
    assert result["quantity"] == 10

    # 3. 일회용 확인 (재사용 불가)
    result2 = await notifier.handle_approval(token, "approve")
    assert result2 is None


@pytest.mark.asyncio
async def test_signal_rejection_flow(approval_manager, redis_client):
    """신호→승인토큰→거부콜백→주문 미실행."""
    signal = _make_signal()
    bot = MagicMock()
    bot.send_signal_alert = AsyncMock(return_value=100)
    bot.edit_message = AsyncMock()

    notifier = NotifierManager(bot, approval_manager, MagicMock())

    token = await notifier.notify_signal(signal, quantity=10, timeout_sec=30)
    result = await notifier.handle_approval(token, "reject")
    assert result is not None
    assert result["action"] == "reject"

    # 주문 관련 mock 없으므로 주문 실행 안 됨을 확인
    bot.edit_message.assert_called_once()


@pytest.mark.asyncio
async def test_signal_timeout_flow(approval_manager, redis_client):
    """신호→승인 타임아웃→만료 알림."""
    import asyncio

    signal = _make_signal()
    bot = MagicMock()
    bot.send_signal_alert = AsyncMock(return_value=200)
    bot.edit_message = AsyncMock()

    notifier = NotifierManager(bot, approval_manager, MagicMock())

    token = await notifier.notify_signal(signal, quantity=5, timeout_sec=1)
    await asyncio.sleep(1.5)

    # 만료된 토큰은 validate 실패
    result = await notifier.handle_approval(token, "approve")
    assert result is None

    # 타임아웃 알림
    await notifier.notify_timeout(token)
    bot.edit_message.assert_called_once()


@pytest.mark.asyncio
async def test_daily_report_generation(approval_manager):
    """일일 리포트 생성."""
    bot = MagicMock()
    bot.send_notification = AsyncMock(return_value=1)
    bot.format_daily_report = MagicMock(return_value="<b>일일 리포트</b>")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    notifier = NotifierManager(bot, approval_manager, mock_factory)
    await notifier.send_daily_report(mock_factory)

    bot.format_daily_report.assert_called_once()
    bot.send_notification.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_endpoint_integration():
    """POST /api/v1/telegram/webhook 콜백 처리 확인."""
    app = create_app()
    app.router.lifespan_context = None

    bot = MagicMock()
    bot.is_authorized = MagicMock(return_value=True)
    bot.parse_callback_data = MagicMock(return_value=("approve", "int-token"))
    engine = MagicMock()
    engine.approve_signal = AsyncMock(return_value=True)

    app.state.telegram_bot = bot
    app.state.trading_engine = engine

    payload = {
        "update_id": 1,
        "callback_query": {
            "id": "1",
            "chat_instance": "1",
            "data": "approve:int-token",
            "from": {"id": 12345},
            "message": {"message_id": 1, "chat": {"id": 12345}, "text": "test"},
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/telegram/webhook", json=payload)

    assert resp.status_code == 200
    engine.approve_signal.assert_called_once_with("int-token")


@pytest.mark.asyncio
async def test_command_via_webhook():
    """POST /api/v1/telegram/webhook /status 명령어 처리."""
    app = create_app()
    app.router.lifespan_context = None

    bot = MagicMock()
    bot.is_authorized = MagicMock(return_value=True)
    bot.send_notification = AsyncMock(return_value=1)

    cmd_handler = MagicMock()
    cmd_handler.dispatch = AsyncMock(return_value="활성 포지션 없음")

    app.state.telegram_bot = bot
    app.state.trading_engine = MagicMock()
    app.state.command_handler = cmd_handler

    payload = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 12345},
            "text": "/status",
            "from": {"id": 12345},
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/telegram/webhook", json=payload)

    assert resp.status_code == 200
    cmd_handler.dispatch.assert_called_once_with("/status", 12345)


@pytest.mark.asyncio
async def test_risk_check_then_approval():
    """리스크 차단 시 승인 요청 안 함."""
    notifier = AsyncMock()
    engine = TradingEngine(
        signal_generator=AsyncMock(),
        order_manager=AsyncMock(),
        position_manager=AsyncMock(),
        risk_manager=AsyncMock(),
        position_sizer=AsyncMock(),
        eod_liquidator=MagicMock(),
        redis_client=AsyncMock(),
        notifier_manager=notifier,
    )
    engine._order_manager._queue = MagicMock()
    engine._order_manager.get_queue_size.return_value = 0

    signal = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(
        return_value=MagicMock(allowed=False, reason="일일 손실 한도 초과")
    )
    engine._eod_liquidator.is_entry_blocked.return_value = False

    await engine.process_screening_results([{"stock_code": "005930"}])

    # 리스크 차단 -> 승인 요청 안 함
    notifier.notify_signal.assert_not_called()
    engine._order_manager.submit_order.assert_not_called()
