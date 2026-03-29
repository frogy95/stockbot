"""Open Dart API 공시 검색 — 최근 공시 + 키워드 필터."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import datetime, timedelta
import requests
from exploration.common.config import DART_API_KEY


def search_disclosure(bgn_de: str = None, end_de: str = None, corp_code: str = None) -> dict:
    """공시 검색."""
    if not bgn_de:
        bgn_de = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    if not end_de:
        end_de = datetime.now().strftime("%Y%m%d")

    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_count": 20,
    }
    if corp_code:
        params["corp_code"] = corp_code
    return requests.get(url, params=params).json()


def main():
    print("Open Dart API 공시 검색")
    print("="*60)

    # 최근 7일 전체 공시
    print("\n[1] 최근 7일 공시 (전체)")
    data = search_disclosure()
    if data.get("status") == "000":
        items = data.get("list", [])
        print(f"  총 {data.get('total_count', '?')}건 (표시: {len(items)}건)")
        for item in items[:10]:
            print(f"  {item.get('rcept_dt', '?')} | {item.get('corp_name', '?')} | {item.get('report_nm', '?')[:40]}")
    else:
        print(f"  {data.get('status')}: {data.get('message', '')}")

    # 당일 공시
    print(f"\n[2] 당일 공시")
    today = datetime.now().strftime("%Y%m%d")
    data2 = search_disclosure(bgn_de=today, end_de=today)
    if data2.get("status") == "000":
        items2 = data2.get("list", [])
        print(f"  당일 공시: {data2.get('total_count', '?')}건")
        for item in items2[:5]:
            print(f"  {item.get('rcept_dt', '?')} | {item.get('corp_name', '?')} | {item.get('report_nm', '?')[:40]}")
    else:
        print(f"  {data2.get('status')}: {data2.get('message', '')}")

    # 키워드 필터 (유증, 자사주, 실적)
    print(f"\n[3] 키워드 필터 (유증/자사주/실적)")
    data3 = search_disclosure()
    if data3.get("status") == "000":
        keywords = ["유상증자", "자기주식", "자사주", "실적", "영업실적"]
        items3 = data3.get("list", [])
        matched = [i for i in items3 if any(k in i.get("report_nm", "") for k in keywords)]
        print(f"  키워드 매칭: {len(matched)}건 / {len(items3)}건")
        for item in matched[:5]:
            print(f"  {item.get('rcept_dt', '?')} | {item.get('corp_name', '?')} | {item.get('report_nm', '?')[:40]}")


if __name__ == "__main__":
    main()
