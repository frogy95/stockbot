"""한투 WS 체결/호가 파서 테스트."""

from modules.collector.sources.kis_realtime import (
    ExecutionData,
    OrderbookData,
    parse_raw_message,
    parse_execution,
    parse_orderbook,
)


def _make_execution_body(
    stock_code: str = "005930",
    time: str = "100530",
    price: int = 70000,
    change_sign: str = "2",
    change: int = 1000,
    change_rate: float = 1.45,
    volume: int = 100,
    acml_volume: int = 5000000,
    trade_strength: float = 100.0,
    sell_or_buy: str = "1",
    open_price: int = 69500,
    high: int = 70100,
    low: int = 69000,
) -> str:
    """체결 데이터 본문 생성 (KIS H0STCNT0 실제 필드 구조, 22개+)."""
    fields = [""] * 24
    fields[0] = stock_code
    fields[1] = time
    fields[2] = str(price)
    fields[3] = change_sign
    fields[4] = str(change)
    fields[5] = str(change_rate)
    fields[7] = str(open_price)
    fields[8] = str(high)
    fields[9] = str(low)
    fields[12] = str(volume)
    fields[13] = str(acml_volume)
    fields[18] = str(trade_strength)  # CTTR (KIS 체결강도)
    fields[21] = sell_or_buy  # CNTG_CLS_CODE ("1"=매수, "5"=매도)
    return "^".join(fields)


def _make_orderbook_body(
    stock_code: str = "005930",
    time: str = "100530",
) -> str:
    """호가 데이터 본문 생성 (최소 45개 필드)."""
    fields = ["0"] * 50
    fields[0] = stock_code
    fields[1] = time

    # 10단계 호가: ask_price, ask_vol, bid_price, bid_vol (step=4)
    for i in range(10):
        offset = i * 4
        fields[3 + offset] = str(70000 + (10 - i) * 100)  # 매도호가
        fields[4 + offset] = str(1000 + i * 100)  # 매도잔량
        fields[5 + offset] = str(69900 - i * 100)  # 매수호가
        fields[6 + offset] = str(2000 + i * 100)  # 매수잔량

    fields[43] = "15000"  # 총 매도잔량
    fields[44] = "25000"  # 총 매수잔량
    return "^".join(fields)


# ── parse_raw_message ──────────────────────────────────

def test_parse_raw_message_valid():
    raw = "0|H0STCNT0|1|005930^100530^70000"
    result = parse_raw_message(raw)
    assert result is not None
    tr_id, encrypted, body = result
    assert tr_id == "H0STCNT0"
    assert encrypted == "0"
    assert body == "005930^100530^70000"


def test_parse_raw_message_invalid():
    assert parse_raw_message("") is None
    assert parse_raw_message("no pipes here") is None
    assert parse_raw_message("a|b") is None  # 파이프 3개 미만


# ── parse_execution ─────────────────────────────────────

def test_parse_execution_data():
    body = _make_execution_body(trade_strength=125.5, sell_or_buy="1")
    result = parse_execution(body)

    assert result is not None
    assert isinstance(result, ExecutionData)
    assert result.stock_code == "005930"
    assert result.time == "100530"
    assert result.price == 70000
    assert result.volume == 100
    assert result.trade_strength == 125.5
    assert result.sell_or_buy == "1"


def test_parse_execution_fields():
    body = _make_execution_body(
        stock_code="035720",
        price=150000,
        change_sign="5",
        change=-500,
        change_rate=-0.33,
        volume=50,
        acml_volume=1000000,
        trade_strength=85.2,
        sell_or_buy="5",
    )
    result = parse_execution(body)

    assert result is not None
    assert result.stock_code == "035720"
    assert result.price == 150000
    assert result.change_sign == "5"
    assert result.change == -500
    assert result.change_rate == -0.33
    assert result.volume == 50
    assert result.acml_volume == 1000000
    assert result.trade_strength == 85.2
    assert result.sell_or_buy == "5"


def test_parse_execution_invalid():
    assert parse_execution("") is None
    assert parse_execution(None) is None
    assert parse_execution("too^few^fields") is None


def test_parse_execution_extracts_ohlc():
    body = _make_execution_body(open_price=69500, high=70100, low=69000)
    result = parse_execution(body)

    assert result is not None
    assert result.open_price == 69500
    assert result.high == 70100
    assert result.low == 69000


def test_parse_execution_handles_missing_ohlc_fields():
    # 필드가 10개 미만이면 None 반환 (기존 동작 유지)
    short_body = "^".join(["val"] * 9)
    assert parse_execution(short_body) is None


# Phase 8 Sprint 2 Task 5 — OHLC idx 7/8/9 경계값 회귀 픽스처


def test_parse_execution_handles_ohlc_zero_values():
    """OHLC 3필드가 '0' 문자열일 때 int(0) 정상 반환 (장 시작 전 케이스)."""
    body = _make_execution_body(open_price=0, high=0, low=0)
    result = parse_execution(body)
    assert result is not None
    assert result.open_price == 0
    assert result.high == 0
    assert result.low == 0


def test_parse_execution_handles_large_ohlc_values():
    """100만원대 고가 종목 시뮬레이션 (예: LG생활건강, 삼성바이오로직스)."""
    body = _make_execution_body(
        stock_code="051900",
        open_price=1_050_000,
        high=1_055_000,
        low=1_045_000,
        price=1_048_000,
    )
    result = parse_execution(body)
    assert result is not None
    assert result.open_price == 1_050_000
    assert result.high == 1_055_000
    assert result.low == 1_045_000


def test_parse_execution_field_offset_sanity():
    """EXECUTION_FIELD_MAP의 idx 7/8/9가 실제 open/high/low에 매핑되는지 검증."""
    from modules.collector.sources.kis_realtime import EXECUTION_FIELD_MAP

    assert EXECUTION_FIELD_MAP["open_price"] == 7
    assert EXECUTION_FIELD_MAP["high"] == 8
    assert EXECUTION_FIELD_MAP["low"] == 9

    # 실제 raw body의 해당 position 값이 파서 결과에 실려오는지 역매핑 확인
    raw_body = _make_execution_body(open_price=71234, high=71567, low=70890)
    fields = raw_body.split("^")
    assert fields[EXECUTION_FIELD_MAP["open_price"]] == "71234"
    assert fields[EXECUTION_FIELD_MAP["high"]] == "71567"
    assert fields[EXECUTION_FIELD_MAP["low"]] == "70890"

    result = parse_execution(raw_body)
    assert result is not None
    assert result.open_price == 71234
    assert result.high == 71567
    assert result.low == 70890


def test_parse_execution_handles_ohlc_whitespace():
    """OHLC 필드에 공백만 있을 때 0으로 처리 (빈 문자열 회귀)."""
    body = _make_execution_body()
    fields = body.split("^")
    fields[7] = "   "  # open_price whitespace
    fields[8] = ""  # high empty
    fields[9] = "  "  # low whitespace
    body = "^".join(fields)
    result = parse_execution(body)
    assert result is not None
    assert result.open_price == 0
    assert result.high == 0
    assert result.low == 0


# ── parse_orderbook ─────────────────────────────────────

def test_parse_orderbook_data():
    body = _make_orderbook_body()
    result = parse_orderbook(body)

    assert result is not None
    assert isinstance(result, OrderbookData)
    assert result.stock_code == "005930"
    assert result.time == "100530"
    assert len(result.asks) == 10
    assert len(result.bids) == 10
    assert result.total_ask_volume == 15000
    assert result.total_bid_volume == 25000


def test_parse_orderbook_fields():
    body = _make_orderbook_body()
    result = parse_orderbook(body)

    # 매도호가 1단계: 70000 + (10-0)*100 = 71000
    assert result.asks[0][0] == 71000
    assert result.asks[0][1] == 1000
    # 매수호가 1단계: 69900 - 0*100 = 69900
    assert result.bids[0][0] == 69900
    assert result.bids[0][1] == 2000


def test_parse_orderbook_invalid():
    assert parse_orderbook("") is None
    assert parse_orderbook(None) is None
    assert parse_orderbook("too^few") is None
