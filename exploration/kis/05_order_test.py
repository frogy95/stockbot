"""한투 모의거래 주문 실행/취소 테스트 — KOSPI/KOSDAQ/ETF 3종목."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import requests
from exploration.common.config import KIS_MOCK_BASE_URL, KIS_MOCK_ACCOUNT_NO, TEST_STOCKS
from exploration.kis._helpers import get_access_token, get_common_headers


def place_order(token: str, stock_code: str) -> dict:
    """시장가 매수 주문 (1주)."""
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    headers = get_common_headers(token, "VTTC0802U")  # 모의투자 매수
    body = {
        "CANO": KIS_MOCK_ACCOUNT_NO[:8],
        "ACNT_PRDT_CD": KIS_MOCK_ACCOUNT_NO[8:],
        "PDNO": stock_code,
        "ORD_DVSN": "01",  # 시장가
        "ORD_QTY": "1",
        "ORD_UNPR": "0",   # 시장가이므로 0
    }
    return requests.post(url, headers=headers, json=body).json()


def cancel_order(token: str, order_no: str, stock_code: str) -> dict:
    """주문 취소."""
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-rvsecncl"
    headers = get_common_headers(token, "VTTC0803U")  # 모의투자 취소
    body = {
        "CANO": KIS_MOCK_ACCOUNT_NO[:8],
        "ACNT_PRDT_CD": KIS_MOCK_ACCOUNT_NO[8:],
        "KRX_FWDG_ORD_ORGNO": "",
        "ORGN_ODNO": order_no,
        "ORD_DVSN": "01",
        "RVSE_CNCL_DVSN_CD": "02",  # 취소
        "ORD_QTY": "1",
        "ORD_UNPR": "0",
        "QTY_ALL_ORD_YN": "Y",
    }
    return requests.post(url, headers=headers, json=body).json()


def inquire_orders(token: str) -> dict:
    """당일 체결내역 조회."""
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
    headers = get_common_headers(token, "VTTC8001R")  # 모의투자 체결내역
    params = {
        "CANO": KIS_MOCK_ACCOUNT_NO[:8],
        "ACNT_PRDT_CD": KIS_MOCK_ACCOUNT_NO[8:],
        "INQR_STRT_DT": time.strftime("%Y%m%d"),
        "INQR_END_DT": time.strftime("%Y%m%d"),
        "SLL_BUY_DVSN_CD": "00",
        "INQR_DVSN": "00",
        "PDNO": "",
        "CCLD_DVSN": "00",
        "ORD_GNO_BRNO": "",
        "ODNO": "",
        "INQR_DVSN_3": "00",
        "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    return requests.get(url, headers=headers, params=params).json()


def main():
    token = get_access_token()
    if not token:
        sys.exit(1)

    for market_type, info in TEST_STOCKS.items():
        code, name = info["code"], info["name"]
        print(f"\n{'='*60}")
        print(f"[{market_type}] {name} ({code}) — 주문 테스트")
        print('='*60)

        # 매수 주문
        print("  1) 시장가 매수 주문 (1주)...")
        order_data = place_order(token, code)
        print(f"  응답: rt_cd={order_data.get('rt_cd')}, msg={order_data.get('msg1', '')}")

        output = order_data.get("output", {})
        order_no = output.get("ODNO", "")
        if not order_no:
            print(f"  [실패] 주문번호 없음 — {order_data}")
            continue
        print(f"  주문번호: {order_no}")

        time.sleep(1.5)  # 모의거래 Rate Limit

        # 주문 취소
        print("  2) 주문 취소...")
        cancel_data = cancel_order(token, order_no, code)
        print(f"  취소 응답: rt_cd={cancel_data.get('rt_cd')}, msg={cancel_data.get('msg1', '')}")

        time.sleep(1.5)

    # 체결내역 조회
    print(f"\n{'='*60}")
    print("당일 체결내역 조회")
    print('='*60)
    orders = inquire_orders(token)
    if orders.get("rt_cd") == "0":
        items = orders.get("output1", [])[:5]
        for item in items:
            print(f"  {item.get('pdno', '?')} | {item.get('sll_buy_dvsn_cd_name', '?')} | "
                  f"수량:{item.get('ord_qty', '?')} | 가격:{item.get('ord_unpr', '?')} | "
                  f"상태:{item.get('ord_dvsn_name', '?')}")
    else:
        print(f"  [실패] {orders.get('msg1', '알 수 없는 에러')}")


if __name__ == "__main__":
    main()
