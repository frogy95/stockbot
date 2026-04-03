"""KIS REST 클라이언트 테스트

시세 조회, 주문, 잔고/포지션 조회, 에러 처리(토큰 만료·Rate Limit·주문 거부)를 검증한다.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.clients.kis_config import PAPER
from core.clients.kis_rest import (
    KISRestClient,
    KISDataError,
    KISOrderError,
    StockPrice,
    Orderbook,
    OrderRequest,
    OrderResponse,
    CancelRequest,
    Balance,
    Position,
    DailyPrice,
)
from core.clients.throttler import TokenBucketThrottler


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _make_env():
    """PAPER 환경 mock — app_key/app_secret/account_no 프로퍼티 대체"""
    env = MagicMock(wraps=PAPER)
    env.name = PAPER.name
    env.rest_domain = PAPER.rest_domain
    env.ws_url = PAPER.ws_url
    env.order_tr_prefix = PAPER.order_tr_prefix
    env.rate_limit_interval = PAPER.rate_limit_interval
    env.base_url = PAPER.base_url
    env.app_key = "test-app-key"
    env.app_secret = "test-app-secret"
    env.account_no = "1234567801"
    return env


def _make_token_manager():
    """TokenManager mock"""
    tm = AsyncMock()
    tm.get_access_token = AsyncMock(return_value="test-access-token")
    tm.refresh_token = AsyncMock(return_value="refreshed-token")
    tm.get_hashkey = AsyncMock(return_value="test-hashkey")
    return tm


def _make_throttler():
    """Throttler mock"""
    t = MagicMock(spec=TokenBucketThrottler)
    t.acquire = AsyncMock()
    t.backoff = MagicMock()
    t.reset_backoff = MagicMock()
    return t


def _make_http_response(json_data, status_code=200):
    """httpx 응답 mock 생성"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception("HTTP Error")
    return resp


def _make_client(env=None, tm=None, throttler=None, http_responses=None):
    """KISRestClient + mock 조립"""
    env = env or _make_env()
    tm = tm or _make_token_manager()
    throttler = throttler or _make_throttler()

    client = KISRestClient(env=env, token_manager=tm, throttler=throttler)

    if http_responses is not None:
        http = AsyncMock()
        call_idx = {"n": 0}

        async def _dispatch(*args, **kwargs):
            idx = min(call_idx["n"], len(http_responses) - 1)
            call_idx["n"] += 1
            r = http_responses[idx]
            return _make_http_response(r["json"], r.get("status_code", 200))

        http.get = AsyncMock(side_effect=_dispatch)
        http.post = AsyncMock(side_effect=_dispatch)
        http.aclose = AsyncMock()
        client._http = http

    return client


# ---------------------------------------------------------------------------
# 시세 조회 테스트
# ---------------------------------------------------------------------------

STOCK_PRICE_RESP = {
    "rt_cd": "0",
    "output": {
        "stck_prpr": "71000",
        "prdy_vrss": "500",
        "prdy_ctrt": "0.71",
        "acml_vol": "12345678",
        "acml_tr_pbmn": "876543210000",
        "stck_hgpr": "72000",
        "stck_lwpr": "70000",
        "stck_oprc": "70500",
    },
}


@pytest.mark.asyncio
async def test_get_stock_price_normal():
    """정상 시세 조회 → StockPrice 반환"""
    client = _make_client(http_responses=[{"json": STOCK_PRICE_RESP}])

    result = await client.get_stock_price("005930")

    assert isinstance(result, StockPrice)
    assert result.stock_code == "005930"
    assert result.price == 71000
    assert result.change == 500
    assert result.change_rate == 0.71
    assert result.volume == 12345678
    assert result.high == 72000
    assert result.low == 70000
    assert result.open_price == 70500


@pytest.mark.asyncio
async def test_get_stock_price_empty_data():
    """존재하지 않는 종목(stck_prpr==0) → KISDataError"""
    resp = {"rt_cd": "0", "output": {"stck_prpr": "0"}}
    client = _make_client(http_responses=[{"json": resp}])

    with pytest.raises(KISDataError, match="종목 데이터 없음"):
        await client.get_stock_price("999999")


# ---------------------------------------------------------------------------
# 호가 조회 테스트
# ---------------------------------------------------------------------------

ORDERBOOK_RESP = {
    "rt_cd": "0",
    "output1": {
        "askp1": "71100",
        "askp_rsqn1": "1000",
        "bidp1": "71000",
        "bidp_rsqn1": "2000",
        "askp2": "71200",
        "askp_rsqn2": "500",
        "bidp2": "70900",
        "bidp_rsqn2": "800",
        "total_askp_rsqn": "15000",
        "total_bidp_rsqn": "28000",
    },
}


@pytest.mark.asyncio
async def test_get_orderbook_normal():
    """정상 호가 조회 → Orderbook 반환"""
    client = _make_client(http_responses=[{"json": ORDERBOOK_RESP}])

    result = await client.get_orderbook("005930")

    assert isinstance(result, Orderbook)
    assert len(result.asks) == 2
    assert len(result.bids) == 2
    assert result.asks[0].price == 71100
    assert result.bids[0].volume == 2000
    assert result.total_ask_volume == 15000
    assert result.total_bid_volume == 28000


# ---------------------------------------------------------------------------
# 주문 테스트
# ---------------------------------------------------------------------------

ORDER_RESP = {
    "rt_cd": "0",
    "msg1": "주문 접수 완료",
    "output": {"ODNO": "0001234567"},
}


@pytest.mark.asyncio
async def test_place_order_normal():
    """정상 매수 주문 → OrderResponse 반환"""
    client = _make_client(http_responses=[{"json": ORDER_RESP}])

    order = OrderRequest(
        stock_code="005930", order_type="buy", quantity=10, price=71000
    )
    result = await client.place_order(order)

    assert isinstance(result, OrderResponse)
    assert result.order_no == "0001234567"
    assert result.stock_code == "005930"
    assert result.message == "주문 접수 완료"

    # POST 호출 검증
    http = client._http
    assert http.post.call_count == 1
    call_kwargs = http.post.call_args
    # headers에 hashkey 포함 확인
    headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))
    assert headers.get("hashkey") == "test-hashkey"


@pytest.mark.asyncio
async def test_cancel_order_normal():
    """정상 주문 취소 → dict 반환"""
    resp = {"rt_cd": "0", "msg1": "취소 완료", "output": {"ODNO": "0001234567"}}
    client = _make_client(http_responses=[{"json": resp}])

    req = CancelRequest(stock_code="005930", quantity=5)
    result = await client.cancel_order("0001234567", req)

    assert isinstance(result, dict)
    assert result["rt_cd"] == "0"


@pytest.mark.asyncio
async def test_get_order_status_normal():
    """주문 체결 상태 조회 → dict 반환"""
    resp = {"rt_cd": "0", "output1": [{"odno": "0001234567", "ord_qty": "10"}]}
    client = _make_client(http_responses=[{"json": resp}])

    result = await client.get_order_status("0001234567")

    assert isinstance(result, dict)
    assert result["rt_cd"] == "0"


# ---------------------------------------------------------------------------
# 잔고 / 포지션 테스트
# ---------------------------------------------------------------------------

BALANCE_RESP = {
    "rt_cd": "0",
    "output1": [
        {
            "pdno": "005930",
            "prdt_name": "삼성전자",
            "hldg_qty": "100",
            "pchs_avg_pric": "70000",
            "prpr": "71000",
            "evlu_pfls_rt": "1.43",
        },
        {
            "pdno": "035720",
            "prdt_name": "카카오",
            "hldg_qty": "50",
            "pchs_avg_pric": "55000",
            "prpr": "56000",
            "evlu_pfls_rt": "1.82",
        },
    ],
    "output2": [
        {
            "tot_evlu_amt": "12700000",
            "evlu_pfls_smtl_amt": "250000",
            "evlu_pfls_rt": "2.01",
        }
    ],
}


@pytest.mark.asyncio
async def test_get_balance():
    """잔고 조회 → Balance 반환"""
    client = _make_client(http_responses=[{"json": BALANCE_RESP}])

    result = await client.get_balance()

    assert isinstance(result, Balance)
    assert result.total_eval_amount == 12700000
    assert result.total_profit == 250000
    assert result.total_profit_rate == 2.01


@pytest.mark.asyncio
async def test_get_positions():
    """보유 종목 조회 → list[Position] 반환"""
    client = _make_client(http_responses=[{"json": BALANCE_RESP}])

    result = await client.get_positions()

    assert isinstance(result, list)
    assert len(result) == 2
    assert isinstance(result[0], Position)
    assert result[0].stock_code == "005930"
    assert result[0].stock_name == "삼성전자"
    assert result[0].quantity == 100
    assert result[0].avg_price == 70000
    assert result[0].current_price == 71000
    assert result[0].profit_rate == 1.43
    assert result[1].stock_code == "035720"


# ---------------------------------------------------------------------------
# 에러 처리 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_expired_retry():
    """토큰 만료(EGW00121) → refresh_token 호출 후 재시도 성공"""
    expired_resp = {"msg_cd": "EGW00121", "msg1": "접근토큰이 만료되었습니다"}
    success_resp = STOCK_PRICE_RESP

    # 첫 번째 호출: 만료, 두 번째 호출: 성공
    client = _make_client(http_responses=[{"json": expired_resp}, {"json": success_resp}])

    result = await client.get_stock_price("005930")

    assert isinstance(result, StockPrice)
    assert result.price == 71000
    # refresh_token이 호출됐는지 확인
    client._token_manager.refresh_token.assert_called_once()
    # throttler.reset_backoff가 호출됐는지 확인
    client._throttler.reset_backoff.assert_called()


@pytest.mark.asyncio
async def test_rate_limit_retry():
    """Rate Limit 초과 → backoff 후 재시도 성공"""
    rate_limit_resp = {"msg_cd": "EGW00000", "msg1": "초당 거래건수를 초과하였습니다"}
    success_resp = STOCK_PRICE_RESP

    client = _make_client(
        http_responses=[
            {"json": rate_limit_resp},
            {"json": rate_limit_resp},
            {"json": success_resp},
        ]
    )

    result = await client.get_stock_price("005930")

    assert isinstance(result, StockPrice)
    assert result.price == 71000
    # backoff가 2번 호출됐는지 확인
    assert client._throttler.backoff.call_count == 2
    # 성공 후 reset_backoff 호출
    client._throttler.reset_backoff.assert_called()


@pytest.mark.asyncio
async def test_rate_limit_max_retries():
    """Rate Limit 최대 재시도 초과 → KISDataError"""
    rate_limit_resp = {"msg_cd": "EGW00000", "msg1": "초당 거래건수를 초과하였습니다"}

    client = _make_client(
        http_responses=[
            {"json": rate_limit_resp},
            {"json": rate_limit_resp},
            {"json": rate_limit_resp},
            {"json": rate_limit_resp},
        ]
    )

    with pytest.raises(KISDataError, match="Rate Limit 초과"):
        await client.get_stock_price("005930")


@pytest.mark.asyncio
async def test_order_rejected():
    """주문 거부(rt_cd=1) → KISOrderError"""
    reject_resp = {"rt_cd": "1", "msg1": "주문가능수량 부족"}
    client = _make_client(http_responses=[{"json": reject_resp}])

    order = OrderRequest(
        stock_code="005930", order_type="buy", quantity=10, price=71000
    )

    with pytest.raises(KISOrderError, match="주문 실패"):
        await client.place_order(order)


# ---------------------------------------------------------------------------
# 헤더 검증 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_headers():
    """모든 요청에 authorization, appkey, appsecret, tr_id 헤더가 포함됨"""
    client = _make_client(http_responses=[{"json": STOCK_PRICE_RESP}])

    await client.get_stock_price("005930")

    http = client._http
    call_kwargs = http.get.call_args
    headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))

    assert "Bearer test-access-token" in headers.get("authorization", "")
    assert headers.get("appkey") == "test-app-key"
    assert headers.get("appsecret") == "test-app-secret"
    assert headers.get("tr_id") == "FHKST01010100"


@pytest.mark.asyncio
async def test_paper_order_tr_id():
    """모의투자 주문 tr_id는 'V'로 시작"""
    client = _make_client(http_responses=[{"json": ORDER_RESP}])

    order = OrderRequest(
        stock_code="005930", order_type="buy", quantity=10, price=71000
    )
    await client.place_order(order)

    http = client._http
    call_kwargs = http.post.call_args
    headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))

    assert headers.get("tr_id") == "VTTC0802U"


@pytest.mark.asyncio
async def test_sell_order_tr_id():
    """매도 주문 tr_id 확인"""
    client = _make_client(http_responses=[{"json": ORDER_RESP}])

    order = OrderRequest(
        stock_code="005930", order_type="sell", quantity=10, price=71000
    )
    await client.place_order(order)

    http = client._http
    call_kwargs = http.post.call_args
    headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))

    assert headers.get("tr_id") == "VTTC0801U"


# ---------------------------------------------------------------------------
# 일봉 조회 테스트
# ---------------------------------------------------------------------------

DAILY_PRICE_RESP = {
    "rt_cd": "0",
    "output2": [
        {
            "stck_bsop_date": "20260403",
            "stck_oprc": "70500",
            "stck_hgpr": "72000",
            "stck_lwpr": "70000",
            "stck_clpr": "71000",
            "acml_vol": "12345678",
            "prdy_ctrt": "0.71",
        },
        {
            "stck_bsop_date": "20260402",
            "stck_oprc": "69000",
            "stck_hgpr": "71000",
            "stck_lwpr": "68500",
            "stck_clpr": "70500",
            "acml_vol": "9876543",
            "prdy_ctrt": "-0.50",
        },
    ],
}


@pytest.mark.asyncio
async def test_get_daily_price():
    """일봉 조회 → list[DailyPrice] 반환"""
    client = _make_client(http_responses=[{"json": DAILY_PRICE_RESP}])

    result = await client.get_daily_price("005930", "20260402", "20260403")

    assert isinstance(result, list)
    assert len(result) == 2
    first = result[0]
    assert isinstance(first, DailyPrice)
    assert first.stock_code == "005930"
    assert first.data_date == "20260403"
    assert first.open_price == 70500
    assert first.high_price == 72000
    assert first.low_price == 70000
    assert first.close_price == 71000
    assert first.volume == 12345678
    assert first.change_rate == 0.71

    second = result[1]
    assert second.data_date == "20260402"
    assert second.close_price == 70500


@pytest.mark.asyncio
async def test_get_daily_price_empty():
    """output2가 없으면 빈 리스트 반환"""
    resp = {"rt_cd": "0", "output2": []}
    client = _make_client(http_responses=[{"json": resp}])

    result = await client.get_daily_price("005930", "20260402", "20260403")

    assert result == []


@pytest.mark.asyncio
async def test_get_daily_price_tr_id():
    """일봉 조회 tr_id가 FHKST03010100인지 확인"""
    client = _make_client(http_responses=[{"json": DAILY_PRICE_RESP}])

    await client.get_daily_price("005930", "20260402", "20260403")

    http = client._http
    call_kwargs = http.get.call_args
    headers = call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))
    assert headers.get("tr_id") == "FHKST03010100"
