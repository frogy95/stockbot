"""한투 모의거래 Rate Limit 실측."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import requests
from exploration.common.config import KIS_MOCK_BASE_URL, TEST_STOCKS
from exploration.kis._helpers import get_access_token, get_common_headers


def single_price_call(token: str, stock_code: str = "005930") -> tuple[int, str]:
    """현재가 API 1회 호출, (HTTP 상태코드, rt_cd or 에러) 반환."""
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers(token, "FHKST01010100")
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code}
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    return resp.status_code, data.get("rt_cd", "?"), data.get("msg1", "")


def test_interval(token: str, interval: float, count: int = 5):
    """지정 간격으로 반복 호출하여 성공/실패 기록."""
    print(f"\n  --- 간격 {interval}초, {count}회 ---")
    results = []
    for i in range(count):
        start = time.time()
        status, rt_cd, msg = single_price_call(token)
        elapsed = time.time() - start
        ok = "OK" if rt_cd == "0" else f"FAIL({rt_cd})"
        results.append(rt_cd == "0")
        print(f"  [{i+1}/{count}] HTTP {status} | {ok} | {elapsed:.3f}s | {msg[:50]}")
        if i < count - 1:
            time.sleep(interval)

    success = sum(results)
    print(f"  결과: {success}/{count} 성공")
    return success, count


def test_recovery(token: str):
    """Rate Limit 초과 후 복구 시간 측정."""
    print(f"\n  --- 복구 시간 측정 (빠른 연속 호출 후 대기) ---")
    # 빠른 5회 연속 호출로 Rate Limit 유도
    for i in range(5):
        status, rt_cd, msg = single_price_call(token)
        if rt_cd != "0":
            print(f"  Rate Limit 발생: 호출 {i+1}회 | msg: {msg[:50]}")
            # 복구 대기
            for wait in [1, 2, 3, 5]:
                time.sleep(wait)
                status, rt_cd, msg = single_price_call(token)
                if rt_cd == "0":
                    print(f"  복구 확인: {wait}초 대기 후 성공")
                    return wait
                print(f"  {wait}초 대기 후: {rt_cd} | {msg[:50]}")
            return -1
        time.sleep(0.1)

    print("  Rate Limit 미발생 (0.1초 간격 5회 모두 성공)")
    return 0


def main():
    token = get_access_token()
    if not token:
        sys.exit(1)

    print("=" * 60)
    print("한투 모의거래 Rate Limit 실측")
    print("공식 한도: 초당 1건")
    print("=" * 60)

    # 다양한 간격 테스트
    for interval in [2.0, 1.0, 0.5, 0.3]:
        test_interval(token, interval, count=5)
        time.sleep(2)  # 테스트 간 쿨다운

    # 복구 시간 측정
    recovery = test_recovery(token)
    print(f"\n최종 복구 시간: {recovery}초")


if __name__ == "__main__":
    main()
