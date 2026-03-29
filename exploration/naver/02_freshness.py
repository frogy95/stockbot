"""네이버 뉴스 속보 반영 속도 측정."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import datetime
from email.utils import parsedate_to_datetime
import requests
from exploration.common.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET


SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"
HEADERS = {
    "X-Naver-Client-Id": NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
}


def measure_freshness(query: str) -> float | None:
    """최신 뉴스의 발행 시간과 현재 시간 차이(분)를 반환."""
    params = {"query": query, "display": 1, "sort": "date"}
    data = requests.get(SEARCH_URL, headers=HEADERS, params=params).json()
    items = data.get("items", [])
    if not items:
        return None

    pub_date_str = items[0].get("pubDate", "")
    try:
        pub_date = parsedate_to_datetime(pub_date_str)
        now = datetime.now(pub_date.tzinfo)
        diff = (now - pub_date).total_seconds() / 60
        return diff
    except Exception:
        return None


def main():
    queries = ["삼성전자", "에코프로비엠", "KODEX 200", "카카오", "NAVER"]

    print("네이버 뉴스 속보 반영 속도 측정")
    print("Go/No-Go 기준: 속보 반영 1시간(60분) 이내면 Go")
    print("="*60)

    results = []
    for query in queries:
        diff = measure_freshness(query)
        if diff is not None:
            status = "Go" if diff < 60 else "주의"
            print(f"  \"{query}\": 최신 뉴스 {diff:.1f}분 전 ({status})")
            results.append(diff)
        else:
            print(f"  \"{query}\": 결과 없음")

    if results:
        avg = sum(results) / len(results)
        print(f"\n  평균: {avg:.1f}분")
        print(f"  Go/No-Go: {'Go' if avg < 60 else 'Conditional (센티멘트만 활용)'}")


if __name__ == "__main__":
    main()
