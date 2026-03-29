"""공공데이터포털 API Rate Limit 실측."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import requests
from exploration.common.config import DATA_GO_KR_API_KEY


API_URL = "http://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"


def single_call() -> tuple[int, str]:
    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "numOfRows": 1,
        "pageNo": 1,
        "resultType": "json",
        "likeSrtnCd": "005930",
    }
    resp = requests.get(API_URL, params=params)
    result_code = "?"
    try:
        data = resp.json()
        result_code = data.get("response", {}).get("header", {}).get("resultCode", "?")
    except Exception:
        pass
    return resp.status_code, result_code


def main():
    print("공공데이터포털 API Rate Limit 실측")
    print("공식: 일 1,000건 (대량 호출 자제)")
    print("="*60)

    # 연속 10회
    print("\n  --- 연속 10회 호출 ---")
    results = []
    for i in range(10):
        start = time.time()
        status, result_code = single_call()
        elapsed = time.time() - start
        ok = result_code == "00"
        results.append(ok)
        print(f"  [{i+1:2d}/10] HTTP {status} | result={result_code} | {elapsed:.3f}s")
        if not ok:
            break

    success = sum(results)
    print(f"\n  결과: {success}/{len(results)} 성공")
    print(f"  일일 한도: 1,000건 (공식 기준, 실측 불가)")


if __name__ == "__main__":
    main()
