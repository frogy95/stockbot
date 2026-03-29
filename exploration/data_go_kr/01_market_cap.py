"""공공데이터포털 API 시가총액/상장주식수 조회 — KOSPI/KOSDAQ/ETF."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import requests
from exploration.common.config import DATA_GO_KR_API_KEY, TEST_STOCKS


API_URL = "http://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"


def get_market_cap(stock_code: str) -> dict:
    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "numOfRows": 5,
        "pageNo": 1,
        "resultType": "json",
        "likeSrtnCd": stock_code,
    }
    return requests.get(API_URL, params=params).json()


def main():
    print("공공데이터포털 API 시가총액/상장주식수 조회")
    print("="*60)

    for market_type, info in TEST_STOCKS.items():
        code, name = info["code"], info["name"]
        print(f"\n{'='*60}")
        print(f"[{market_type}] {name} ({code})")
        print('='*60)

        data = get_market_cap(code)
        response = data.get("response", {})
        header = response.get("header", {})
        result_code = header.get("resultCode", "?")

        if result_code != "00":
            print(f"  [실패] {header.get('resultMsg', '알 수 없는 에러')}")
            continue

        body = response.get("body", {})
        items = body.get("items", {}).get("item", [])
        total = body.get("totalCount", 0)
        print(f"  총 결과: {total}건 (표시: {len(items)}건)")

        for item in items[:3]:
            print(f"  기준일: {item.get('basDt', 'N/A')}")
            print(f"  종목코드: {item.get('srtnCd', 'N/A')}")
            print(f"  종목명: {item.get('itmsNm', 'N/A')}")
            print(f"  시가총액: {item.get('mrktTotAmt', 'N/A')}")
            print(f"  상장주식수: {item.get('lstgStCnt', 'N/A')}")
            print(f"  종가: {item.get('clpr', 'N/A')}")
            print(f"  시장구분: {item.get('mrktCtg', 'N/A')}")
            print()


if __name__ == "__main__":
    main()
