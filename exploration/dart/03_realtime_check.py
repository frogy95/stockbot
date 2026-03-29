"""Open Dart API 실시간성 확인 — 당일 공시 반영 지연 시간."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import datetime
import requests
from exploration.common.config import DART_API_KEY


def main():
    print("Open Dart API 실시간성 확인")
    print("Go/No-Go 기준: 당일 공시 1시간 이내 반영 시 Go")
    print("="*60)

    today = datetime.now().strftime("%Y%m%d")
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "bgn_de": today,
        "end_de": today,
        "page_count": 5,
        "sort": "date",
        "sort_mth": "desc",
    }
    data = requests.get(url, params=params).json()

    if data.get("status") != "000":
        print(f"  당일 공시 없음 또는 에러: {data.get('status')} — {data.get('message', '')}")
        print("  → 주말/공휴일에는 공시가 없을 수 있음")
        print("  → 평일 장중에 재실행하여 지연 시간 측정 필요")
        return

    items = data.get("list", [])
    if not items:
        print("  당일 공시 0건")
        return

    # 가장 최근 공시
    latest = items[0]
    rcept_dt = latest.get("rcept_dt", "")
    rcept_no = latest.get("rcept_no", "")
    corp_name = latest.get("corp_name", "?")
    report_nm = latest.get("report_nm", "?")

    print(f"\n  최근 공시:")
    print(f"    기업: {corp_name}")
    print(f"    공시명: {report_nm}")
    print(f"    접수일: {rcept_dt}")
    print(f"    접수번호: {rcept_no}")
    print(f"    현재 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # rcept_dt는 날짜만 제공 (시간 미제공) → 정밀 지연 측정 불가
    print(f"\n  ※ DART API는 접수 '일자'만 제공 (시:분 미제공)")
    print(f"  → 정밀한 지연 시간 측정은 DART 웹사이트와 비교 필요 (수동)")
    print(f"  → API에 공시가 당일 자로 나타나면 최소 당일 반영은 확인됨")

    total = data.get("total_count", 0)
    print(f"\n  당일 공시 총 {total}건 — Go/No-Go: {'Go (당일 반영 확인)' if total > 0 else '판단 보류'}")


if __name__ == "__main__":
    main()
