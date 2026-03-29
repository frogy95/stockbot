"""네이버 검색 API Rate Limit 실측."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import requests
from exploration.common.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET


SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"
HEADERS = {
    "X-Naver-Client-Id": NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
}


def main():
    print("네이버 검색 API Rate Limit 실측")
    print("공식: 일 25,000건")
    print("="*60)

    # 빠른 연속 호출 20회
    print("\n  --- 빠른 연속 호출 20회 ---")
    results = []
    for i in range(20):
        start = time.time()
        resp = requests.get(SEARCH_URL, headers=HEADERS, params={"query": "삼성전자", "display": 1})
        elapsed = time.time() - start
        status = resp.status_code
        ok = status == 200
        results.append(ok)
        if not ok or i < 5 or i >= 18:
            error_msg = ""
            if not ok:
                error_msg = f" | {resp.json().get('errorMessage', resp.text[:50])}"
            print(f"  [{i+1:2d}/20] HTTP {status} | {elapsed:.3f}s{error_msg}")
        elif i == 5:
            print(f"  ... (중간 생략)")

        if not ok:
            break

    success = sum(results)
    print(f"\n  결과: {success}/{len(results)} 성공")

    if success == len(results):
        print("  → 초당 호출 한도: 20회 연속 모두 성공 (관대한 한도)")
    print(f"  일일 한도: 25,000건 (실측 불가, 공식 기준 사용)")


if __name__ == "__main__":
    main()
