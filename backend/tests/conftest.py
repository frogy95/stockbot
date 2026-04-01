from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

import core.database as db_module


class FakeRedis:
    """dict 기반 간이 Redis mock — 스케줄러 테스트용."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

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
