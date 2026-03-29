"""한투 모의거래 기타 검증 — hashkey, tr_id, 호가단위, 장상태, WS암호화키, 인코딩."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import json
import requests
from exploration.common.config import (
    KIS_MOCK_BASE_URL, KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_ACCOUNT_NO,
)
from exploration.kis._helpers import get_access_token, get_common_headers


def test_hashkey(token: str):
    """hashkey 발급 테스트."""
    print("\n[1] hashkey 발급")
    url = f"{KIS_MOCK_BASE_URL}/uapi/hashkey"
    headers = {
        "content-type": "application/json; charset=utf-8",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
    }
    body = {
        "CANO": KIS_MOCK_ACCOUNT_NO[:8],
        "ACNT_PRDT_CD": KIS_MOCK_ACCOUNT_NO[8:],
        "PDNO": "005930",
        "ORD_DVSN": "01",
        "ORD_QTY": "1",
        "ORD_UNPR": "0",
    }
    resp = requests.post(url, headers=headers, json=body)
    data = resp.json()
    hashkey = data.get("HASH", data.get("hash", ""))
    print(f"  HTTP: {resp.status_code}")
    print(f"  hashkey: {hashkey[:30]}..." if hashkey else f"  응답: {data}")


def test_tr_id_mapping():
    """tr_id 모의/실전 매핑 확인."""
    print("\n[2] tr_id 매핑 (모의 vs 실전)")
    mapping = {
        "매수": ("VTTC0802U", "TTTC0802U"),
        "매도": ("VTTC0801U", "TTTC0801U"),
        "취소": ("VTTC0803U", "TTTC0803U"),
        "체결내역": ("VTTC8001R", "TTTC8001R"),
        "현재가": ("FHKST01010100", "FHKST01010100"),  # 동일
        "호가": ("FHKST01010200", "FHKST01010200"),    # 동일
    }
    for name, (mock, live) in mapping.items():
        diff = "동일" if mock == live else f"모의={mock}, 실전={live}"
        print(f"  {name}: {diff}")


def test_price_unit():
    """호가단위 (가격대별)."""
    print("\n[3] 호가단위 (가격대별)")
    units = [
        ("~1,000원", 1),
        ("1,000~5,000원", 5),
        ("5,000~10,000원", 10),
        ("10,000~50,000원", 50),
        ("50,000~100,000원", 100),
        ("100,000~500,000원", 500),
        ("500,000원~", 1000),
    ]
    for range_str, unit in units:
        print(f"  {range_str}: {unit}원")
    print("  ※ ETF는 5원 단위 (가격 무관)")


def test_market_status(token: str):
    """장상태 확인 가능 여부."""
    print("\n[4] 장상태 조회")
    # 한투 API에서 직접 장상태를 조회하는 전용 엔드포인트는 없으므로
    # 현재가 응답의 관련 필드를 확인
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers(token, "FHKST01010100")
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"}
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    output = data.get("output", {})
    # 장상태 관련 필드 탐색
    status_fields = {k: v for k, v in output.items() if "stat" in k.lower() or "mrkt" in k.lower() or "opng" in k.lower()}
    if status_fields:
        print(f"  장상태 관련 필드: {json.dumps(status_fields, ensure_ascii=False)}")
    else:
        print("  장상태 전용 필드 미발견 — 별도 API 또는 웹소켓 이벤트로 확인 필요")


def test_ws_approval_key():
    """웹소켓 암호화 키(approval_key) 발급."""
    print("\n[5] 웹소켓 approval_key 발급")
    url = f"{KIS_MOCK_BASE_URL}/oauth2/Approval"
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_MOCK_APP_KEY,
        "secretkey": KIS_MOCK_APP_SECRET,
    }
    resp = requests.post(url, json=body)
    data = resp.json()
    approval_key = data.get("approval_key", "")
    print(f"  HTTP: {resp.status_code}")
    print(f"  approval_key: {approval_key[:30]}..." if approval_key else f"  응답: {data}")
    return approval_key


def test_encoding(token: str):
    """응답 인코딩 확인 (한글 종목명)."""
    print("\n[6] 응답 인코딩 확인")
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers(token, "FHKST01010100")
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"}
    resp = requests.get(url, headers=headers, params=params)
    print(f"  Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
    print(f"  인코딩: {resp.encoding}")
    # 한글 종목명 확인
    output = resp.json().get("output", {})
    name_fields = {k: v for k, v in output.items() if "hts_kor" in k.lower() or "prdt_name" in k.lower()}
    if name_fields:
        print(f"  한글 필드: {json.dumps(name_fields, ensure_ascii=False)}")
    else:
        print("  한글 종목명 필드 미발견")


def main():
    token = get_access_token()
    if not token:
        sys.exit(1)

    print("=" * 60)
    print("한투 모의거래 기타 검증")
    print("=" * 60)

    test_hashkey(token)
    test_tr_id_mapping()
    test_price_unit()
    test_market_status(token)
    test_ws_approval_key()
    test_encoding(token)


if __name__ == "__main__":
    main()
