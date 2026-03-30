"""한투 WS 실시간 데이터 파서 — H0STCNT0(체결), H0STASP0(호가) 파싱."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 필드 인덱스 설정 딕셔너리 (하드코딩 방지 — Phase 2 미해결사항 #5)
EXECUTION_FIELD_MAP = {
    "stock_code": 0,
    "time": 1,
    "price": 2,
    "change_sign": 3,
    "change": 4,
    "change_rate": 5,
    "volume": 12,
    "acml_volume": 13,
    "sell_or_buy": 17,
}

ORDERBOOK_FIELD_MAP = {
    "stock_code": 0,
    "time": 1,
    # 매도호가 1~10: 인덱스 3,7,11,15,19,23,27,31,35,39
    # 매도잔량 1~10: 인덱스 4,8,12,16,20,24,28,32,36,40
    # 매수호가 1~10: 인덱스 5,9,13,17,21,25,29,33,37,41
    # 매수잔량 1~10: 인덱스 6,10,14,18,22,26,30,34,38,42
    "ask_price_start": 3,
    "ask_volume_start": 4,
    "bid_price_start": 5,
    "bid_volume_start": 6,
    "step": 4,  # 각 호가 단계 간격
    "total_ask_volume": 43,
    "total_bid_volume": 44,
}


@dataclass
class ExecutionData:
    """체결 데이터 (H0STCNT0)."""
    stock_code: str
    time: str
    price: int
    change_sign: str
    change: int
    change_rate: float
    volume: int
    acml_volume: int
    sell_or_buy: str  # "1"=매도, "2"=매수


@dataclass
class OrderbookData:
    """호가 데이터 (H0STASP0)."""
    stock_code: str
    time: str
    asks: list[tuple[int, int]]  # [(가격, 수량), ...] 10단계
    bids: list[tuple[int, int]]  # [(가격, 수량), ...] 10단계
    total_ask_volume: int
    total_bid_volume: int


def parse_raw_message(raw: str) -> tuple[str, str, str] | None:
    """파이프 구분 원시 메시지 파싱 -> (tr_id, encrypted, body) 또는 None.

    한투 WS 형식: 암호화여부|tr_id|건수|데이터본문
    """
    if not raw or "|" not in raw:
        return None

    parts = raw.split("|", 3)
    if len(parts) < 4:
        return None

    encrypted = parts[0]
    tr_id = parts[1]
    body = parts[3]
    return tr_id, encrypted, body


def parse_execution(body: str) -> ExecutionData | None:
    """H0STCNT0 체결 데이터 본문 파싱."""
    if not body:
        return None

    fields = body.split("^")
    fm = EXECUTION_FIELD_MAP

    max_index = max(fm.values())
    if len(fields) <= max_index:
        logger.warning("체결 데이터 필드 부족: %d <= %d", len(fields), max_index)
        return None

    try:
        return ExecutionData(
            stock_code=fields[fm["stock_code"]].strip(),
            time=fields[fm["time"]].strip(),
            price=int(fields[fm["price"]]),
            change_sign=fields[fm["change_sign"]].strip(),
            change=int(fields[fm["change"]]),
            change_rate=float(fields[fm["change_rate"]]),
            volume=int(fields[fm["volume"]]),
            acml_volume=int(fields[fm["acml_volume"]]),
            sell_or_buy=fields[fm["sell_or_buy"]].strip(),
        )
    except (ValueError, IndexError) as e:
        logger.warning("체결 데이터 파싱 실패: %s", e)
        return None


def parse_orderbook(body: str) -> OrderbookData | None:
    """H0STASP0 호가 데이터 본문 파싱."""
    if not body:
        return None

    fields = body.split("^")
    fm = ORDERBOOK_FIELD_MAP

    min_fields = max(fm["total_ask_volume"], fm["total_bid_volume"]) + 1
    if len(fields) < min_fields:
        logger.warning("호가 데이터 필드 부족: %d < %d", len(fields), min_fields)
        return None

    try:
        asks: list[tuple[int, int]] = []
        bids: list[tuple[int, int]] = []
        step = fm["step"]

        for i in range(10):
            offset = i * step
            ask_price = int(fields[fm["ask_price_start"] + offset])
            ask_vol = int(fields[fm["ask_volume_start"] + offset])
            bid_price = int(fields[fm["bid_price_start"] + offset])
            bid_vol = int(fields[fm["bid_volume_start"] + offset])
            asks.append((ask_price, ask_vol))
            bids.append((bid_price, bid_vol))

        return OrderbookData(
            stock_code=fields[fm["stock_code"]].strip(),
            time=fields[fm["time"]].strip(),
            asks=asks,
            bids=bids,
            total_ask_volume=int(fields[fm["total_ask_volume"]]),
            total_bid_volume=int(fields[fm["total_bid_volume"]]),
        )
    except (ValueError, IndexError) as e:
        logger.warning("호가 데이터 파싱 실패: %s", e)
        return None
