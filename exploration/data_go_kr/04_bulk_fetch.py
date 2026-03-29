"""공공데이터포털 전 종목 일괄 수집 테스트 — 장전 스크리닝 소스."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import requests
from exploration.common.config import DATA_GO_KR_API_KEY


API_URL = "http://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"


def fetch_all_stocks(bas_dt: str, page_size: int = 500) -> list[dict]:
    """특정 날짜의 전 종목 데이터를 페이징으로 수집."""
    all_items = []
    page = 1

    while True:
        params = {
            "serviceKey": DATA_GO_KR_API_KEY,
            "numOfRows": page_size,
            "pageNo": page,
            "resultType": "json",
            "basDt": bas_dt,
        }
        resp = requests.get(API_URL, params=params)
        data = resp.json()
        body = data.get("response", {}).get("body", {})
        total = body.get("totalCount", 0)
        items = body.get("items", {}).get("item", [])

        if not items:
            break

        all_items.extend(items)
        print(f"  페이지 {page}: {len(items)}건 (누적 {len(all_items)}/{total})")

        if len(all_items) >= total:
            break

        page += 1
        time.sleep(0.5)

    return all_items


def main():
    # 최신 기준일 확인
    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "numOfRows": 1,
        "pageNo": 1,
        "resultType": "json",
    }
    resp = requests.get(API_URL, params=params)
    items = resp.json().get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if not items:
        print("[실패] 데이터 조회 실패")
        return

    latest_dt = items[0].get("basDt", "")
    print(f"최신 기준일: {latest_dt}")
    print("="*60)

    # 전 종목 수집
    start = time.time()
    stocks = fetch_all_stocks(latest_dt)
    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"수집 완료: {len(stocks)}종목, {elapsed:.1f}초")

    # 시장구분 통계
    markets = {}
    for s in stocks:
        m = s.get("mrktCtg", "?")
        markets[m] = markets.get(m, 0) + 1
    print(f"시장구분: {markets}")

    # 필드 확인
    if stocks:
        print(f"제공 필드: {list(stocks[0].keys())}")

    # 거래량 상위 10종목
    sorted_by_vol = sorted(stocks, key=lambda x: int(x.get("trqu", "0")), reverse=True)
    print(f"\n거래량 상위 10종목:")
    for s in sorted_by_vol[:10]:
        print(f"  {s.get('srtnCd')} | {s.get('itmsNm'):10s} | "
              f"종가:{int(s.get('clpr', 0)):>10,} | "
              f"거래량:{int(s.get('trqu', 0)):>15,} | "
              f"시총:{int(s.get('mrktTotAmt', 0)):>18,} | "
              f"{s.get('mrktCtg')}")

    # 시가총액 상위 10종목
    sorted_by_cap = sorted(stocks, key=lambda x: int(x.get("mrktTotAmt", "0")), reverse=True)
    print(f"\n시가총액 상위 10종목:")
    for s in sorted_by_cap[:10]:
        cap_조 = int(s.get("mrktTotAmt", 0)) / 1_000_000_000_000
        print(f"  {s.get('srtnCd')} | {s.get('itmsNm'):10s} | "
              f"종가:{int(s.get('clpr', 0)):>10,} | "
              f"시총:{cap_조:>8.1f}조 | "
              f"{s.get('mrktCtg')}")


if __name__ == "__main__":
    main()
