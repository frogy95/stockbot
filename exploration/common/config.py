"""탐색 스크립트 공통 설정 — .env 로드 및 환경변수 노출."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트의 .env 로드
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

# --- 한국투자증권 (모의거래) ---
KIS_MOCK_APP_KEY = os.getenv("KIS_MOCK_APP_KEY", "")
KIS_MOCK_APP_SECRET = os.getenv("KIS_MOCK_APP_SECRET", "")
KIS_MOCK_ACCOUNT_NO = os.getenv("KIS_MOCK_ACCOUNT_NO", "")

# --- 네이버 검색 API ---
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# --- Open Dart API ---
DART_API_KEY = os.getenv("DART_API_KEY", "")

# --- 공공데이터포털 API ---
DATA_GO_KR_API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")

# --- Telegram Bot API ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- 한투 모의거래 기본 URL ---
KIS_MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"

# --- 테스트 종목 (전 Task 공통) ---
TEST_STOCKS = {
    "KOSPI": {"code": "005930", "name": "삼성전자"},
    "KOSDAQ": {"code": "247540", "name": "에코프로비엠"},
    "ETF": {"code": "069500", "name": "KODEX 200"},
}

# --- 키 누락 경고 ---
_REQUIRED_KEYS = {
    "KIS_MOCK_APP_KEY": KIS_MOCK_APP_KEY,
    "KIS_MOCK_APP_SECRET": KIS_MOCK_APP_SECRET,
    "KIS_MOCK_ACCOUNT_NO": KIS_MOCK_ACCOUNT_NO,
    "NAVER_CLIENT_ID": NAVER_CLIENT_ID,
    "NAVER_CLIENT_SECRET": NAVER_CLIENT_SECRET,
    "DART_API_KEY": DART_API_KEY,
    "DATA_GO_KR_API_KEY": DATA_GO_KR_API_KEY,
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
}

_missing = [k for k, v in _REQUIRED_KEYS.items() if not v]
if _missing:
    print(f"[경고] 다음 환경변수가 설정되지 않았습니다: {', '.join(_missing)}", file=sys.stderr)
