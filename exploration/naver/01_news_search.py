"""네이버 뉴스 검색 API — 종목명/코드 검색 + 관련성 평가."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import requests
from exploration.common.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET


SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"
HEADERS = {
    "X-Naver-Client-Id": NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
}


def search_news(query: str, display: int = 10, sort: str = "date") -> dict:
    params = {"query": query, "display": display, "sort": sort}
    return requests.get(SEARCH_URL, headers=HEADERS, params=params).json()


def main():
    # 종목명 검색
    queries = ["삼성전자", "에코프로비엠", "KODEX 200", "카카오", "NAVER"]
    # 종목코드 검색
    code_queries = ["005930", "247540"]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"검색어: \"{query}\"")
        print('='*60)

        data = search_news(query)
        if "items" not in data:
            print(f"  [실패] {data}")
            continue

        items = data["items"]
        print(f"  총 결과: {data.get('total', '?')}건 (표시: {len(items)}건)")

        for i, item in enumerate(items, 1):
            title = item["title"].replace("<b>", "").replace("</b>", "")
            pub_date = item.get("pubDate", "?")
            print(f"  [{i:2d}] {title[:60]}")
            print(f"       발행: {pub_date}")

    # 종목코드 검색 — 관련성 비교
    print(f"\n{'='*60}")
    print("종목코드 검색 (관련성 비교)")
    print('='*60)

    for code in code_queries:
        data = search_news(code)
        items = data.get("items", [])
        total = data.get("total", 0)
        print(f"\n  코드 \"{code}\": 총 {total}건, 표시 {len(items)}건")
        for i, item in enumerate(items[:3], 1):
            title = item["title"].replace("<b>", "").replace("</b>", "")
            print(f"    [{i}] {title[:60]}")


if __name__ == "__main__":
    main()
