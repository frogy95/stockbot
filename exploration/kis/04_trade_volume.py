"""한투 모의거래 체결강도/거래량 조회 + 분봉 데이터."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import requests
from exploration.common.config import KIS_MOCK_BASE_URL, TEST_STOCKS
from exploration.kis._helpers import get_access_token, get_common_headers


def inquire_price(token: str, stock_code: str) -> dict:
    """현재가 API에서 체결강도 관련 필드를 추출."""
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers(token, "FHKST01010100")
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code}
    return requests.get(url, headers=headers, params=params).json()


def inquire_time_chart(token: str, stock_code: str) -> dict:
    """분봉 데이터 조회 (가능한 경우)."""
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    headers = get_common_headers(token, "FHKST03010200")
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_ETC_CLS_CODE": "",
        "FID_INPUT_HOUR_1": "100000",  # 10시 기준
        "FID_PW_DATA_INCU_YN": "Y",
    }
    return requests.get(url, headers=headers, params=params).json()


def main():
    token = get_access_token()
    if not token:
        sys.exit(1)

    for i, (market_type, info) in enumerate(TEST_STOCKS.items()):
        if i > 0:
            time.sleep(1.5)  # 모의거래 Rate Limit 대응

        code, name = info["code"], info["name"]
        print(f"\n{'='*60}")
        print(f"[{market_type}] {name} ({code})")
        print('='*60)

        # 현재가 API에서 체결강도 관련 필드
        data = inquire_price(token, code)
        output = data.get("output", {})

        if data.get("rt_cd") != "0":
            print(f"  [실패] {data.get('msg1', '알 수 없는 에러')}")
            continue

        sell_vol = output.get("seln_cntg_smtn", "N/A")
        buy_vol = output.get("shnu_cntg_smtn", "N/A")
        acml_vol = output.get("acml_vol", "N/A")
        prdy_vol = output.get("prdy_vol", "N/A")

        print(f"  매도체결합계: {sell_vol}")
        print(f"  매수체결합계: {buy_vol}")
        if sell_vol != "N/A" and buy_vol != "N/A" and int(sell_vol) > 0:
            strength = round(int(buy_vol) / int(sell_vol) * 100, 2)
            print(f"  체결강도: {strength}%")
        print(f"  누적거래량: {acml_vol}")
        print(f"  전일거래량: {prdy_vol}")
        if prdy_vol != "N/A" and int(prdy_vol) > 0:
            ratio = round(int(acml_vol) / int(prdy_vol) * 100, 2)
            print(f"  거래량비율(대비전일): {ratio}%")

        # 분봉 데이터
        time.sleep(1.5)
        print(f"\n  --- 분봉 데이터 ---")
        chart_data = inquire_time_chart(token, code)
        if chart_data.get("rt_cd") != "0":
            print(f"  [분봉] {chart_data.get('msg1', '조회 실패 또는 미지원')}")
        else:
            items = chart_data.get("output2", [])[:5]
            for item in items:
                print(f"  {item.get('stck_cntg_hour', '?')} | "
                      f"시가:{item.get('stck_oprc', '?')} "
                      f"고가:{item.get('stck_hgpr', '?')} "
                      f"저가:{item.get('stck_lwpr', '?')} "
                      f"종가:{item.get('stck_prpr', '?')} "
                      f"거래량:{item.get('cntg_vol', '?')}")


if __name__ == "__main__":
    main()
