"""텔레그램 웹훅 API 라우터."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """텔레그램 웹훅 수신 엔드포인트. 항상 200 반환 (재전송 방지)."""
    body = await request.json()

    telegram_bot = getattr(request.app.state, "telegram_bot", None)
    trading_engine = getattr(request.app.state, "trading_engine", None)

    if not telegram_bot:
        return JSONResponse({"ok": True})

    # 콜백 쿼리 처리 (승인/거부 버튼 클릭)
    callback_query = body.get("callback_query")
    if callback_query:
        chat_id = callback_query.get("from", {}).get("id", 0)
        if not telegram_bot.is_authorized(int(chat_id)):
            logger.warning("비인가 콜백: chat_id=%s", chat_id)
            return JSONResponse({"ok": True})

        data = callback_query.get("data", "")
        action, token = telegram_bot.parse_callback_data(data)

        if trading_engine and action == "approve":
            result = await trading_engine.approve_signal(token)
            logger.info("승인 처리: token=%s, result=%s", token, result)
        elif trading_engine and action == "reject":
            result = await trading_engine.reject_signal(token)
            logger.info("거부 처리: token=%s, result=%s", token, result)

        return JSONResponse({"ok": True})

    # 메시지 처리 (명령어)
    message = body.get("message")
    if message:
        chat_id = message.get("chat", {}).get("id", 0)
        if not telegram_bot.is_authorized(int(chat_id)):
            return JSONResponse({"ok": True})

        text = message.get("text", "")
        if text.startswith("/"):
            command_handler = getattr(request.app.state, "command_handler", None)
            if command_handler:
                response_text = await command_handler.dispatch(text.split()[0], chat_id)
                await telegram_bot.send_notification(response_text)

    return JSONResponse({"ok": True})
