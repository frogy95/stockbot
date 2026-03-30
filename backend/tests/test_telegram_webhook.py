"""텔레그램 웹훅 API 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.fixture
def app():
    test_app = create_app()
    test_app.router.lifespan_context = None

    # mock 의존성 설정
    bot = MagicMock()
    bot.is_authorized = MagicMock(return_value=True)
    bot.parse_callback_data = MagicMock(return_value=("approve", "test-token"))
    bot.send_notification = AsyncMock(return_value=1)

    engine = MagicMock()
    engine.approve_signal = AsyncMock(return_value=True)
    engine.reject_signal = AsyncMock(return_value=True)

    test_app.state.telegram_bot = bot
    test_app.state.trading_engine = engine

    return test_app


@pytest.mark.asyncio
async def test_webhook_approve_callback(app):
    """POST /api/v1/telegram/webhook 승인 콜백 -> approve_signal 호출."""
    payload = {
        "update_id": 1,
        "callback_query": {
            "id": "1",
            "chat_instance": "1",
            "data": "approve:test-token",
            "from": {"id": 12345},
            "message": {"message_id": 1, "chat": {"id": 12345}, "text": "test"},
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/telegram/webhook", json=payload)

    assert resp.status_code == 200
    app.state.trading_engine.approve_signal.assert_called_once_with("test-token")


@pytest.mark.asyncio
async def test_webhook_reject_callback(app):
    """POST /api/v1/telegram/webhook 거부 콜백 -> reject_signal 호출."""
    app.state.telegram_bot.parse_callback_data.return_value = ("reject", "test-token")
    payload = {
        "update_id": 1,
        "callback_query": {
            "id": "1",
            "chat_instance": "1",
            "data": "reject:test-token",
            "from": {"id": 12345},
            "message": {"message_id": 1, "chat": {"id": 12345}, "text": "test"},
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/telegram/webhook", json=payload)

    assert resp.status_code == 200
    app.state.trading_engine.reject_signal.assert_called_once_with("test-token")


@pytest.mark.asyncio
async def test_webhook_unauthorized_chat(app):
    """비인가 chat_id -> 차단."""
    app.state.telegram_bot.is_authorized.return_value = False
    payload = {
        "update_id": 1,
        "callback_query": {
            "id": "1",
            "chat_instance": "1",
            "data": "approve:test-token",
            "from": {"id": 99999},
            "message": {"message_id": 1, "chat": {"id": 99999}, "text": "test"},
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/telegram/webhook", json=payload)

    assert resp.status_code == 200
    app.state.trading_engine.approve_signal.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_message_command(app):
    """명령어 메시지 수신 시 command_handler 호출."""
    cmd_handler = MagicMock()
    cmd_handler.dispatch = AsyncMock(return_value="활성 포지션 없음")
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
    app.state.telegram_bot.send_notification.assert_called_once()
