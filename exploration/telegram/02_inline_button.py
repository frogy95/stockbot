"""텔레그램 인라인 버튼 (승인/거부) 테스트."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler
from exploration.common.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


async def send_approval_message():
    """승인/거부/보류 버튼 메시지 발송."""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    keyboard = [
        [
            InlineKeyboardButton("✅ 승인", callback_data="approve_001"),
            InlineKeyboardButton("❌ 거부", callback_data="reject_001"),
            InlineKeyboardButton("⏸️ 보류", callback_data="hold_001"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "📊 <b>매매 승인 요청</b>\n\n"
        "종목: 삼성전자 (005930)\n"
        "방향: 매수\n"
        "수량: 10주\n"
        "가격: 시장가\n"
        "신뢰도: 0.82\n\n"
        "아래 버튼을 눌러주세요:"
    )
    msg = await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID, text=text,
        parse_mode="HTML", reply_markup=reply_markup,
    )
    print(f"[발송] 승인 요청 메시지: message_id={msg.message_id}")
    return msg.message_id


async def button_callback(update: Update, context):
    """버튼 클릭 콜백 처리."""
    query = update.callback_query
    await query.answer()

    action = query.data
    labels = {"approve_001": "✅ 승인됨", "reject_001": "❌ 거부됨", "hold_001": "⏸️ 보류됨"}
    label = labels.get(action, action)

    print(f"[콜백] 버튼 클릭: {action}")

    # 메시지 수정 (버튼 제거 + 결과 표시)
    await query.edit_message_text(
        text=f"{query.message.text}\n\n결과: {label}",
        parse_mode="HTML",
    )
    print(f"[완료] 메시지 업데이트: {label}")


async def main():
    # 메시지 발송
    await send_approval_message()

    # 콜백 대기 (폴링 모드, 30초)
    print("\n버튼을 클릭하세요 (30초 대기)...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(button_callback))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    await asyncio.sleep(30)

    await app.updater.stop()
    await app.stop()
    await app.shutdown()

    print("\n✅ 인라인 버튼 테스트 완료")


if __name__ == "__main__":
    asyncio.run(main())
