from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

import core.database as db_module

_TEST_JWT_SECRET = "test-secret-key-for-pytest"


def _make_test_token() -> str:
    return pyjwt.encode(
        {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            "trading_env": "paper",
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def auth_headers(monkeypatch):
    """JWT 인증이 필요한 엔드포인트 테스트용 헤더."""
    monkeypatch.setattr("api.deps.settings.JWT_SECRET", _TEST_JWT_SECRET)
    return {"Authorization": f"Bearer {_make_test_token()}"}


def pytest_runtest_setup(item):
    """각 테스트 전에 DB 엔진 글로벌 상태를 리셋하여 이벤트 루프 충돌 방지"""
    db_module._engine = None
    db_module._async_session = None
