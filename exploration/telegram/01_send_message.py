"""텔레그램 봇 메시지 발송 테스트 (텍스트 + 마크다운 + HTML)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import asyncio
from telegram import Bot
from exploration.common.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    # 1) 일반 텍스트
    print("[1] 일반 텍스트 메시지 발송...")
    msg = await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="StockBot 테스트 메시지 🤖")
    print(f"  성공: message_id={msg.message_id}")

    # 2) MarkdownV2 형식
    print("[2] MarkdownV2 형식 메시지 발송...")
    md_text = (
        "*삼성전자 매수 신호* 📈\n"
        "종목: `005930`\n"
        "현재가: `72,000원`\n"
        "신뢰도: `0\\.85`\n"
        "근거: 거래량 급등 \\+ 호가 우세"
    )
    msg2 = await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=md_text, parse_mode="MarkdownV2")
    print(f"  성공: message_id={msg2.message_id}")

    # 3) HTML 형식
    print("[3] HTML 형식 메시지 발송...")
    html_text = (
        "<b>에코프로비엠 매도 신호</b> 📉\n"
        "종목: <code>247540</code>\n"
        "현재가: <code>202,500원</code>\n"
        "손절: <i>-2.5% 도달</i>"
    )
    msg3 = await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=html_text, parse_mode="HTML")
    print(f"  성공: message_id={msg3.message_id}")

    print("\n✅ 텔레그램 앱에서 3개 메시지를 확인하세요.")


if __name__ == "__main__":
    asyncio.run(main())
