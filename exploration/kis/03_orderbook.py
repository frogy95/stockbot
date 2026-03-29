"""한투 모의거래 호가(10단계) 조회 — KOSPI/KOSDAQ/ETF 3종목."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import requests
from exploration.common.config import KIS_MOCK_BASE_URL, TEST_STOCKS
from exploration.kis._helpers import get_access_token, get_common_headers


def inquire_orderbook(token: str, stock_code: str) -> dict:
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
    headers = get_common_headers(token, "FHKST01010200")
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
    }
    return requests.get(url, headers=headers, params=params).json()


def print_orderbook(output: dict):
    """10단계 호가를 테이블 형식으로 출력."""
    print(f"  {'매도잔량':>12}  {'매도호가':>10}  |  {'매수호가':>10}  {'매수잔량':>12}")
    print(f"  {'-'*12}  {'-'*10}  +  {'-'*10}  {'-'*12}")
    for i in range(10, 0, -1):
        sell_price = output.get(f"askp{i}", "")
        sell_qty = output.get(f"askp_rsqn{i}", "")
        print(f"  {sell_qty:>12}  {sell_price:>10}  |")

    for i in range(1, 11):
        buy_price = output.get(f"bidp{i}", "")
        buy_qty = output.get(f"bidp_rsqn{i}", "")
        print(f"  {'':>12}  {'':>10}  |  {buy_price:>10}  {buy_qty:>12}")

    total_ask = output.get("total_askp_rsqn", "N/A")
    total_bid = output.get("total_bidp_rsqn", "N/A")
    print(f"\n  총 매도잔량: {total_ask}  |  총 매수잔량: {total_bid}")


def main():
    token = get_access_token()
    if not token:
        sys.exit(1)

    for market_type, info in TEST_STOCKS.items():
        code, name = info["code"], info["name"]
        print(f"\n{'='*60}")
        print(f"[{market_type}] {name} ({code})")
        print('='*60)

        data = inquire_orderbook(token, code)
        output = data.get("output1", data.get("output", {}))

        if data.get("rt_cd") != "0":
            print(f"  [실패] {data.get('msg1', '알 수 없는 에러')}")
            continue

        print_orderbook(output)

        # 호가 갱신 빈도 — 1초 후 재호출하여 변화 확인
        time.sleep(1.5)
        data2 = inquire_orderbook(token, code)
        output2 = data2.get("output1", data2.get("output", {}))
        changed = output.get("askp1") != output2.get("askp1") or output.get("bidp1") != output2.get("bidp1")
        print(f"\n  호가 변화 여부 (1.5초 후): {'변화 있음' if changed else '변화 없음'}")


if __name__ == "__main__":
    main()
