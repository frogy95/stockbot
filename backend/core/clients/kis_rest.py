"""한국투자증권 REST API 클라이언트

시세 조회, 주문 실행, 잔고/포지션 조회 등 REST API 호출을 담당한다.
"""

import logging

import httpx
from pydantic import BaseModel

from core.clients.kis_config import KISEnvironment
from core.clients.token_manager import KISTokenManager
from core.clients.throttler import TokenBucketThrottler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic 스키마
# ---------------------------------------------------------------------------


class StockPrice(BaseModel):
    stock_code: str
    price: int
    change: int
    change_rate: float
    volume: int
    trade_amount: int
    high: int
    low: int
    open_price: int


class OrderbookItem(BaseModel):
    price: int
    volume: int


class Orderbook(BaseModel):
    asks: list[OrderbookItem]
    bids: list[OrderbookItem]
    total_ask_volume: int
    total_bid_volume: int


class OrderRequest(BaseModel):
    stock_code: str
    order_type: str  # "buy" / "sell"
    quantity: int
    price: int = 0  # 0이면 시장가
    order_division: str = "01"


class OrderResponse(BaseModel):
    order_no: str
    stock_code: str
    message: str


class CancelRequest(BaseModel):
    stock_code: str
    quantity: int
    cancel_type: str = "02"


class Balance(BaseModel):
    total_eval_amount: int
    total_profit: int
    total_profit_rate: float


class Position(BaseModel):
    stock_code: str
    stock_name: str
    quantity: int
    avg_price: int
    current_price: int
    profit_rate: float


class DailyPrice(BaseModel):
    stock_code: str
    data_date: str
    open_price: int
    high_price: int
    low_price: int
    close_price: int
    volume: int
    change_rate: float


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------


class KISDataError(Exception):
    """데이터 조회 실패"""


class KISOrderError(Exception):
    """주문 실패"""


# ---------------------------------------------------------------------------
# REST 클라이언트
# ---------------------------------------------------------------------------

_MAX_RATE_LIMIT_RETRIES = 3


class KISRestClient:
    """한국투자증권 REST API 클라이언트"""

    def __init__(
        self,
        env: KISEnvironment,
        token_manager: KISTokenManager,
        throttler: TokenBucketThrottler,
    ):
        self._env = env
        self._token_manager = token_manager
        self._throttler = throttler
        self._http: httpx.AsyncClient | None = None

    def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._env.base_url, timeout=30.0
            )
        return self._http

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    async def _get_headers(self, tr_id: str) -> dict:
        """API 요청 공통 헤더 구성"""
        token = await self._token_manager.get_access_token()
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self._env.app_key,
            "appsecret": self._env.app_secret,
            "tr_id": tr_id,
        }

    async def _request(
        self,
        method: str,
        path: str,
        tr_id: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """공통 요청 메서드 — 토큰 만료/Rate Limit 자동 재시도"""
        http = self._ensure_http()

        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            await self._throttler.acquire()
            headers = await self._get_headers(tr_id)

            if body is not None:
                hashkey = await self._token_manager.get_hashkey(body)
                headers["hashkey"] = hashkey

            try:
                if method.upper() == "GET":
                    resp = await http.get(path, headers=headers, params=params)
                else:
                    resp = await http.post(path, headers=headers, json=body)

                resp.raise_for_status()
                data = resp.json()

            except httpx.HTTPStatusError as exc:
                raise exc

            # 토큰 만료(EGW00121) → 갱신 후 1회 재시도
            if data.get("msg_cd") == "EGW00121":
                logger.warning("토큰 만료(EGW00121), 갱신 후 재시도")
                await self._token_manager.refresh_token()
                headers = await self._get_headers(tr_id)

                if body is not None:
                    hashkey = await self._token_manager.get_hashkey(body)
                    headers["hashkey"] = hashkey

                if method.upper() == "GET":
                    resp = await http.get(path, headers=headers, params=params)
                else:
                    resp = await http.post(path, headers=headers, json=body)

                resp.raise_for_status()
                data = resp.json()
                self._throttler.reset_backoff()
                return data

            # Rate Limit → backoff 후 재시도 (최대 3회)
            msg1 = data.get("msg1", "")
            if "초당 거래건수를 초과" in msg1:
                if attempt < _MAX_RATE_LIMIT_RETRIES:
                    logger.warning(
                        "Rate Limit 초과, backoff 후 재시도 (%d/%d)",
                        attempt + 1,
                        _MAX_RATE_LIMIT_RETRIES,
                    )
                    self._throttler.backoff()
                    continue
                else:
                    raise KISDataError(f"Rate Limit 초과 (최대 재시도 횟수 도달): {msg1}")

            # 정상 응답
            self._throttler.reset_backoff()
            return data

        # 여기에 도달하면 안 되지만 안전장치
        raise KISDataError("요청 처리 실패")  # pragma: no cover

    # ------------------------------------------------------------------
    # 시세 조회
    # ------------------------------------------------------------------

    async def get_stock_price(self, stock_code: str) -> StockPrice:
        """주식 현재가 조회"""
        data = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
            },
        )

        output = data.get("output", {})
        if output.get("stck_prpr") == "0":
            raise KISDataError(f"종목 데이터 없음: {stock_code}")

        return StockPrice(
            stock_code=stock_code,
            price=int(output.get("stck_prpr", 0)),
            change=int(output.get("prdy_vrss", 0)),
            change_rate=float(output.get("prdy_ctrt", 0)),
            volume=int(output.get("acml_vol", 0)),
            trade_amount=int(output.get("acml_tr_pbmn", 0)),
            high=int(output.get("stck_hgpr", 0)),
            low=int(output.get("stck_lwpr", 0)),
            open_price=int(output.get("stck_oprc", 0)),
        )

    async def get_daily_price(
        self, stock_code: str, start_date: str, end_date: str
    ) -> list[DailyPrice]:
        """일봉 조회 (FHKST03010100) — output2 배열을 DailyPrice 리스트로 반환."""
        data = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            tr_id="FHKST03010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
                "FID_INPUT_DATE_1": start_date,
                "FID_INPUT_DATE_2": end_date,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
        )

        return [
            DailyPrice(
                stock_code=stock_code,
                data_date=item.get("stck_bsop_date", ""),
                open_price=int(item.get("stck_oprc", 0)),
                high_price=int(item.get("stck_hgpr", 0)),
                low_price=int(item.get("stck_lwpr", 0)),
                close_price=int(item.get("stck_clpr", 0)),
                volume=int(item.get("acml_vol", 0)),
                change_rate=float(item.get("prdy_ctrt", 0)),
            )
            for item in data.get("output2", [])
        ]

    async def get_orderbook(self, stock_code: str) -> Orderbook:
        """호가 조회"""
        data = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
            tr_id="FHKST01010200",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
            },
        )

        output = data.get("output1", {})
        asks = []
        bids = []
        for i in range(1, 11):
            ask_price = int(output.get(f"askp{i}", 0))
            ask_vol = int(output.get(f"askp_rsqn{i}", 0))
            bid_price = int(output.get(f"bidp{i}", 0))
            bid_vol = int(output.get(f"bidp_rsqn{i}", 0))
            if ask_price:
                asks.append(OrderbookItem(price=ask_price, volume=ask_vol))
            if bid_price:
                bids.append(OrderbookItem(price=bid_price, volume=bid_vol))

        return Orderbook(
            asks=asks,
            bids=bids,
            total_ask_volume=int(output.get("total_askp_rsqn", 0)),
            total_bid_volume=int(output.get("total_bidp_rsqn", 0)),
        )

    # ------------------------------------------------------------------
    # 주문
    # ------------------------------------------------------------------

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """매수/매도 주문"""
        account_no = self._env.account_no
        prefix = self._env.order_tr_prefix

        if order.order_type == "buy":
            tr_id = f"{prefix}TTC0802U"
        else:
            tr_id = f"{prefix}TTC0801U"

        body = {
            "CANO": account_no[:8],
            "ACNT_PRDT_CD": account_no[8:],
            "PDNO": order.stock_code,
            "ORD_DVSN": order.order_division,
            "ORD_QTY": str(order.quantity),
            "ORD_UNPR": str(order.price),
        }

        data = await self._request("POST", "/uapi/domestic-stock/v1/trading/order-cash", tr_id=tr_id, body=body)

        if data.get("rt_cd") != "0":
            raise KISOrderError(f"주문 실패: {data.get('msg1', '알 수 없는 오류')}")

        output = data.get("output", {})
        return OrderResponse(
            order_no=output.get("ODNO", ""),
            stock_code=order.stock_code,
            message=data.get("msg1", ""),
        )

    async def cancel_order(self, order_no: str, request: CancelRequest) -> dict:
        """주문 취소"""
        account_no = self._env.account_no
        tr_id = f"{self._env.order_tr_prefix}TTC0803U"

        body = {
            "CANO": account_no[:8],
            "ACNT_PRDT_CD": account_no[8:],
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": order_no,
            "ORD_DVSN": request.cancel_type,
            "RVSE_CNCL_DVSN_CD": "02",
            "ORD_QTY": str(request.quantity),
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "N",
        }

        return await self._request("POST", "/uapi/domestic-stock/v1/trading/order-cash", tr_id=tr_id, body=body)

    async def get_order_status(self, order_no: str) -> dict:
        """주문 체결 상태 조회"""
        account_no = self._env.account_no
        tr_id = f"{self._env.order_tr_prefix}TTC8001R"

        return await self._request(
            "GET",
            "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            tr_id=tr_id,
            params={
                "CANO": account_no[:8],
                "ACNT_PRDT_CD": account_no[8:],
                "INQR_STRT_DT": "",
                "INQR_END_DT": "",
                "SLL_BUY_DVSN_CD": "00",
                "INQR_DVSN": "00",
                "PDNO": "",
                "CCLD_DVSN": "00",
                "ORD_GNO_BRNO": "",
                "ODNO": order_no,
                "INQR_DVSN_3": "00",
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )

    # ------------------------------------------------------------------
    # 잔고 / 포지션
    # ------------------------------------------------------------------

    async def get_balance(self) -> Balance:
        """계좌 잔고 조회"""
        account_no = self._env.account_no
        tr_id = f"{self._env.order_tr_prefix}TTS3320R"

        data = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            tr_id=tr_id,
            params={
                "CANO": account_no[:8],
                "ACNT_PRDT_CD": account_no[8:],
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "01",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )

        output2 = data.get("output2", [{}])
        if isinstance(output2, list) and output2:
            summary = output2[0]
        else:
            summary = output2 if isinstance(output2, dict) else {}

        return Balance(
            total_eval_amount=int(summary.get("tot_evlu_amt", 0)),
            total_profit=int(summary.get("evlu_pfls_smtl_amt", 0)),
            total_profit_rate=float(summary.get("evlu_pfls_rt", 0)),
        )

    async def get_positions(self) -> list[Position]:
        """보유 종목 목록 조회"""
        account_no = self._env.account_no
        tr_id = f"{self._env.order_tr_prefix}TTS3320R"

        data = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            tr_id=tr_id,
            params={
                "CANO": account_no[:8],
                "ACNT_PRDT_CD": account_no[8:],
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "01",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )

        positions = []
        for item in data.get("output1", []):
            qty = int(item.get("hldg_qty", 0))
            if qty > 0:
                positions.append(
                    Position(
                        stock_code=item.get("pdno", ""),
                        stock_name=item.get("prdt_name", ""),
                        quantity=qty,
                        avg_price=int(item.get("pchs_avg_pric", 0)),
                        current_price=int(item.get("prpr", 0)),
                        profit_rate=float(item.get("evlu_pfls_rt", 0)),
                    )
                )

        return positions

    # ------------------------------------------------------------------
    # 정리
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """httpx 클라이언트 종료"""
        if self._http:
            await self._http.aclose()
            self._http = None
