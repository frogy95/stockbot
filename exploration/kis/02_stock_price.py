"""한투 모의거래 현재가 조회 — KOSPI/KOSDAQ/ETF 3종목."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import requests
from exploration.common.config import KIS_MOCK_BASE_URL, TEST_STOCKS
from exploration.kis._helpers import get_access_token, get_common_headers


def inquire_price(token: str, stock_code: str, market_code: str = "J") -> dict:
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers(token, "FHKST01010100")
    params = {
        "FID_COND_MRKT_DIV_CODE": market_code,
        "FID_INPUT_ISCD": stock_code,
    }
    return requests.get(url, headers=headers, params=params).json()


def main():
    token = get_access_token()
    if not token:
        sys.exit(1)

    for market_type, info in TEST_STOCKS.items():
        code, name = info["code"], info["name"]
        print(f"\n{'='*60}")
        print(f"[{market_type}] {name} ({code})")
        print('='*60)

        data = inquire_price(token, code)
        output = data.get("output", {})

        if data.get("rt_cd") != "0":
            print(f"  [실패] {data.get('msg1', '알 수 없는 에러')}")
            continue

        print(f"  현재가: {output.get('stck_prpr', 'N/A')}")
        print(f"  전일대비: {output.get('prdy_vrss', 'N/A')}")
        print(f"  등락률: {output.get('prdy_ctrt', 'N/A')}%")
        print(f"  거래량: {output.get('acml_vol', 'N/A')}")
        print(f"  거래대금: {output.get('acml_tr_pbmn', 'N/A')}")
        print(f"  응답 필드 수: {len(output)}")


if __name__ == "__main__":
    main()
