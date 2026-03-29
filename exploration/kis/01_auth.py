"""한투 모의거래 OAuth 토큰 발급 (파일 캐싱 포함)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import json
import time
from pathlib import Path
import requests
from exploration.common.config import KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_BASE_URL

_TOKEN_CACHE = Path(__file__).parent / ".token_cache.json"


def get_access_token() -> str:
    """모의거래 OAuth 토큰을 발급받아 반환한다. 캐시된 토큰이 유효하면 재사용."""
    # 캐시 확인
    if _TOKEN_CACHE.exists():
        cache = json.loads(_TOKEN_CACHE.read_text())
        if cache.get("expires_at", 0) > time.time() + 600:  # 10분 여유
            token = cache["access_token"]
            print(f"[캐시] access_token: {token[:20]}...{token[-10:]}")
            return token

    # 신규 발급
    url = f"{KIS_MOCK_BASE_URL}/oauth2/tokenP"
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
    }
    resp = requests.post(url, json=body)
    data = resp.json()

    if "access_token" not in data:
        print(f"[실패] 토큰 발급 실패: {data}")
        return ""

    token = data["access_token"]
    expires = data.get("token_token_expired", data.get("access_token_token_expired", "알 수 없음"))
    print(f"[성공] access_token: {token[:20]}...{token[-10:]}")
    print(f"[정보] 만료 시각: {expires}")

    # 캐시 저장 (약 23시간 유효)
    _TOKEN_CACHE.write_text(json.dumps({
        "access_token": token,
        "expires_at": time.time() + 23 * 3600,
    }))
    return token


def get_common_headers(token: str, tr_id: str) -> dict:
    """한투 API 공통 헤더를 반환한다."""
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
        "tr_id": tr_id,
    }


if __name__ == "__main__":
    token = get_access_token()
    if not token:
        sys.exit(1)
