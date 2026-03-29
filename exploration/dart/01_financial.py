"""Open Dart API 재무정보 조회 — 삼성전자/에코프로비엠/KODEX200."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import requests
from exploration.common.config import DART_API_KEY

# DART 기업 고유번호 (corp_code) — 사전 조회 필요
# 종목코드 → corp_code 매핑은 corpCode.xml에서 추출해야 하지만, 탐색 목적으로 하드코딩
CORP_CODES = {
    "삼성전자": "00126380",
    "에코프로비엠": "01160363",
    "KODEX 200": None,  # ETF는 DART에 없을 수 있음
}


def get_financial(corp_code: str, bsns_year: str = "2025", reprt_code: str = "11011") -> dict:
    """재무정보 조회 (reprt_code: 11011=사업보고서, 11012=반기, 11013=1분기, 11014=3분기)."""
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": "OFS",  # OFS=개별, CFS=연결
    }
    return requests.get(url, params=params).json()


def main():
    print("Open Dart API 재무정보 조회")
    print("="*60)

    for name, corp_code in CORP_CODES.items():
        print(f"\n{'='*60}")
        print(f"[{name}] corp_code={corp_code}")
        print('='*60)

        if corp_code is None:
            print("  → ETF는 DART 재무정보 미제공 (예상)")
            continue

        # 2025년 사업보고서 (없으면 2024년 시도)
        for year in ["2025", "2024"]:
            data = get_financial(corp_code, bsns_year=year)
            status = data.get("status", "")

            if status == "000":  # 정상
                items = data.get("list", [])
                print(f"  {year}년 사업보고서: {len(items)}건 항목")
                # 주요 항목 출력
                key_accounts = ["매출액", "영업이익", "당기순이익"]
                for item in items:
                    account_nm = item.get("account_nm", "")
                    if any(k in account_nm for k in key_accounts):
                        amount = item.get("thstrm_amount", "N/A")
                        print(f"  {account_nm}: {amount}")
                break
            else:
                msg = data.get("message", "")
                print(f"  {year}년: {status} — {msg}")


if __name__ == "__main__":
    main()
