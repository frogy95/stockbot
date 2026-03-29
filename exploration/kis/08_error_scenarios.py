"""한투 모의거래 에러 시나리오 5가지 검증."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import json
import time
import requests
from exploration.common.config import (
    KIS_MOCK_BASE_URL, KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_ACCOUNT_NO,
)
from exploration.kis._helpers import get_access_token, get_common_headers


def scenario_invalid_stock(token: str):
    """시나리오 1: 잘못된 종목 코드(999999)."""
    print("\n[시나리오 1] 잘못된 종목 코드 (999999)")
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers(token, "FHKST01010100")
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "999999"}
    resp = requests.get(url, headers=headers, params=params)
    print(f"  HTTP: {resp.status_code}")
    print(f"  응답: {json.dumps(resp.json(), indent=2, ensure_ascii=False)[:500]}")


def scenario_expired_token():
    """시나리오 2: 만료/잘못된 토큰."""
    print("\n[시나리오 2] 만료/잘못된 토큰")
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers("INVALID_TOKEN_12345", "FHKST01010100")
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"}
    resp = requests.get(url, headers=headers, params=params)
    print(f"  HTTP: {resp.status_code}")
    print(f"  응답: {json.dumps(resp.json(), indent=2, ensure_ascii=False)[:500]}")


def scenario_rate_limit(token: str):
    """시나리오 3: Rate Limit 초과."""
    print("\n[시나리오 3] Rate Limit 초과 (빠른 연속 호출)")
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers(token, "FHKST01010100")
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"}
    for i in range(5):
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        rt_cd = data.get("rt_cd", "?")
        msg = data.get("msg1", "")
        status = "OK" if rt_cd == "0" else "FAIL"
        print(f"  [{i+1}] HTTP {resp.status_code} | {status} | {msg[:60]}")
        if rt_cd != "0":
            break
        time.sleep(0.1)


def scenario_after_hours_price(token: str):
    """시나리오 4: 장 외 시간 시세 조회."""
    print("\n[시나리오 4] 장 외 시간 시세 조회")
    print("  (현재 시간 기준으로 실행 — 장외 시간이면 응답 차이 기록)")
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers(token, "FHKST01010100")
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"}
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    print(f"  HTTP: {resp.status_code}")
    print(f"  rt_cd: {data.get('rt_cd')}")
    print(f"  msg1: {data.get('msg1', '')}")
    output = data.get("output", {})
    print(f"  현재가: {output.get('stck_prpr', 'N/A')}")
    print(f"  거래량: {output.get('acml_vol', 'N/A')}")


def scenario_after_hours_order(token: str):
    """시나리오 5: 장 외 시간 주문."""
    print("\n[시나리오 5] 장 외 시간 주문")
    print("  (현재 시간 기준으로 실행 — 장외 시간이면 거부 응답 기록)")
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    headers = get_common_headers(token, "VTTC0802U")
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
    print(f"  HTTP: {resp.status_code}")
    print(f"  rt_cd: {data.get('rt_cd')}")
    print(f"  msg1: {data.get('msg1', '')}")


def main():
    token = get_access_token()
    if not token:
        sys.exit(1)

    print("=" * 60)
    print("한투 모의거래 에러 시나리오 검증 (5가지)")
    print("=" * 60)

    scenario_invalid_stock(token)
    time.sleep(1)
    scenario_expired_token()
    time.sleep(1)
    scenario_rate_limit(token)
    time.sleep(2)
    scenario_after_hours_price(token)
    time.sleep(1)
    scenario_after_hours_order(token)


if __name__ == "__main__":
    main()
