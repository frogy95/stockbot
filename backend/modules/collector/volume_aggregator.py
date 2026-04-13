"""5분봉 거래량 집계 모듈.

틱 단위 체결 데이터를 5분 슬롯별로 Redis에 누적 저장한다.
GET → parse → modify → SET 패턴 사용 (RedisClient에 INCRBY 미노출).
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from core.redis import RedisClient

# ── 상수 ────────────────────────────────────────────────────

VOL5M_TTL = 60 * 60 * 24 * 30  # 30일
MARKET_OPEN_MINUTES = 9 * 60  # 09:00 = 540분
SLOT_COUNT = 78  # 09:00~15:30 = 390분 / 5분
SLOT_MINUTES = 5

_KST = ZoneInfo("Asia/Seoul")


# ── 유틸 함수 ────────────────────────────────────────────────


def calc_5min_slot(hour: int, minute: int) -> int:
    """시:분을 5분봉 슬롯 인덱스(0~77)로 변환한다."""
    elapsed = (hour * 60 + minute) - MARKET_OPEN_MINUTES
    return max(0, min(SLOT_COUNT - 1, elapsed // SLOT_MINUTES))


def make_redis_key(stock_code: str, date_str: str, slot: int) -> str:
    """Redis 키 생성. 형식: vol5m:{code}:{date}:{slot}."""
    return f"vol5m:{stock_code}:{date_str}:{slot}"


# ── 집계 클래스 ──────────────────────────────────────────────


class VolumeAggregator:
    """틱 체결 데이터를 5분봉 슬롯별로 Redis에 누적한다."""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def aggregate_execution(
        self,
        stock_code: str,
        exec_time: str,
        volume: int,
        sell_or_buy: str,
    ) -> None:
        """체결 데이터를 해당 5분 슬롯에 누적한다.

        Args:
            stock_code: 종목코드 (예: "005930")
            exec_time: 체결시각 "HHMMSS" (한투 WS 형식)
            volume: 체결 수량
            sell_or_buy: "1"=매도, "2"=매수
        """
        hour = int(exec_time[0:2])
        minute = int(exec_time[2:4])
        slot = calc_5min_slot(hour, minute)

        date_str = datetime.now(_KST).strftime("%Y%m%d")
        key = make_redis_key(stock_code, date_str, slot)

        # GET → modify → SET (단일 프로세스, 레이스 없음)
        raw = await self._redis.get(key)
        if raw is None:
            data = {"buy_vol": 0, "sell_vol": 0, "total_vol": 0, "trade_count": 0}
        else:
            data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw

        if sell_or_buy == "2":
            data["buy_vol"] += volume
        else:
            data["sell_vol"] += volume
        data["total_vol"] += volume
        data["trade_count"] += 1

        await self._redis.set(key, json.dumps(data), ttl=VOL5M_TTL)

    async def get_recent_slots(
        self, stock_code: str, count: int = 12
    ) -> list[dict]:
        """현재 시각 기준 최근 N개 슬롯 데이터를 반환한다.

        빈 슬롯은 0으로 채워서 항상 count개 항목을 반환한다.
        """
        now = datetime.now(_KST)
        date_str = now.strftime("%Y%m%d")
        current_slot = calc_5min_slot(now.hour, now.minute)

        results: list[dict] = []
        for offset in range(count):
            slot = current_slot - (count - 1) + offset
            empty = {"slot": slot, "buy_vol": 0, "sell_vol": 0, "total_vol": 0, "trade_count": 0}
            if slot < 0:
                results.append(empty)
                continue

            key = make_redis_key(stock_code, date_str, slot)
            raw = await self._redis.get(key)
            if raw is None:
                results.append(empty)
            else:
                data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                results.append({"slot": slot, **data})

        return results

    async def get_first_seen_date(self) -> str | None:
        """저장된 vol5m 키 중 가장 이른 날짜를 반환한다."""
        keys = await self._redis.scan_keys("vol5m:*")
        earliest: str | None = None
        for key in keys:
            k = key if isinstance(key, str) else key.decode()
            parts = k.split(":")
            if len(parts) >= 3:
                date_str = parts[2]
                if earliest is None or date_str < earliest:
                    earliest = date_str
        return earliest
