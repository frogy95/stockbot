"""텔레그램 메시지 발송 지연 측정 (10회)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import asyncio
import time
from telegram import Bot
from exploration.common.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    delays = []

    print("텔레그램 메시지 발송 지연 측정 (10회)")
    print("="*50)

    for i in range(10):
        start = time.time()
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"지연 측정 {i+1}/10")
        elapsed = time.time() - start
        delays.append(elapsed)
        print(f"  [{i+1:2d}/10] {elapsed:.3f}초")
        await asyncio.sleep(0.5)

    avg = sum(delays) / len(delays)
    min_d = min(delays)
    max_d = max(delays)

    print(f"\n{'='*50}")
    print(f"결과:")
    print(f"  평균: {avg:.3f}초")
    print(f"  최소: {min_d:.3f}초")
    print(f"  최대: {max_d:.3f}초")
    print(f"  목표(<1초): {'통과' if avg < 1 else '미달'}")
    print(f"  허용(<3초): {'통과' if max_d < 3 else '미달'}")


if __name__ == "__main__":
    asyncio.run(main())
