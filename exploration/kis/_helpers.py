"""한투 탐색 스크립트 공통 헬퍼 — 01_auth 모듈 로딩."""

import importlib.util
import sys
from pathlib import Path


def _load_auth():
    """01_auth.py를 모듈로 로드한다 (숫자 시작 파일명 우회)."""
    auth_path = Path(__file__).parent / "01_auth.py"
    spec = importlib.util.spec_from_file_location("kis_auth", auth_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


auth = _load_auth()
get_access_token = auth.get_access_token
get_common_headers = auth.get_common_headers
