"""공공데이터포털 API 데이터 갱신 주기 확인."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import datetime
import requests
from exploration.common.config import DATA_GO_KR_API_KEY


API_URL = "http://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"


def get_latest_date(stock_code: str = "005930") -> str | None:
    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "numOfRows": 1,
        "pageNo": 1,
        "resultType": "json",
        "likeSrtnCd": stock_code,
    }
    data = requests.get(API_URL, params=params).json()
    items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if items:
        return items[0].get("basDt")
    return None


def main():
    print("공공데이터포털 API 데이터 갱신 주기 확인")
    print("="*60)

    latest = get_latest_date("005930")
    if not latest:
        print("  [실패] 데이터 조회 실패")
        return

    today = datetime.now().strftime("%Y%m%d")
    print(f"  오늘 날짜: {today}")
    print(f"  최신 데이터 기준일: {latest}")

    try:
        latest_dt = datetime.strptime(latest, "%Y%m%d")
        today_dt = datetime.strptime(today, "%Y%m%d")
        diff = (today_dt - latest_dt).days
        print(f"  차이: {diff}일")

        if diff <= 1:
            print("  → 일 단위 갱신 (전일 기준)")
        elif diff <= 3:
            print("  → 1~3일 지연 (주말/공휴일 가능)")
        else:
            print(f"  → {diff}일 지연 (갱신 주기 확인 필요)")
    except ValueError:
        print("  → 날짜 파싱 실패")

    # 2회 연속 호출로 데이터 변화 확인
    print(f"\n  2회 연속 호출 비교:")
    d1 = get_latest_date("005930")
    d2 = get_latest_date("005930")
    print(f"  1차: {d1}")
    print(f"  2차: {d2}")
    print(f"  변화: {'있음' if d1 != d2 else '없음 (일 단위 갱신 확인)'}")


if __name__ == "__main__":
    main()
