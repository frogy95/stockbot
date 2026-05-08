"""Phase 8.6 Sprint 3 — time-filter-stats API 테스트."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import get_current_user, get_db, get_redis, UserInfo
from main import create_app


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._store[key] = value

    async def scan_keys(self, pattern: str) -> list[str]:
        return [k for k in self._store if k.startswith(pattern.rstrip("*"))]

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        return []

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def ping(self) -> bool:
        return True


@pytest.fixture
def fake_redis():
    return _FakeRedis()


@pytest.fixture
def app(fake_redis):
    """테스트용 FastAPI 앱 — lifespan 비활성화, Redis/Auth override."""
    test_app = create_app()
    test_app.router.lifespan_context = None

    async def override_get_redis():
        yield fake_redis

    test_app.dependency_overrides[get_redis] = override_get_redis
    test_app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="admin", trading_env="paper"
    )
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_time_filter_stats_with_redis_data(app, fake_redis):
    """Redis 카운터 시드 → 응답 검증."""
    target_date = "2026-05-07"
    await fake_redis.set(f"metrics:time_filter:morning_lockout:{target_date}", "12")
    await fake_redis.set(f"metrics:time_filter:afternoon_lockout:{target_date}", "8")
    await fake_redis.set(
        f"metrics:time_filter:gap_open_morning_exception:{target_date}", "3"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v1/metrics/time-filter-stats?date={target_date}"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == target_date
    assert data["morning_lockout"] == 12
    assert data["afternoon_lockout"] == 8
    assert data["gap_open_morning_exception"] == 3


@pytest.mark.asyncio
async def test_time_filter_stats_no_keys(app, fake_redis):
    """Redis 키 부재 → 모두 0 반환."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/metrics/time-filter-stats?date=2026-05-01"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["morning_lockout"] == 0
    assert data["afternoon_lockout"] == 0
    assert data["gap_open_morning_exception"] == 0


@pytest.mark.asyncio
async def test_time_filter_stats_partial_keys(app, fake_redis):
    """일부 카운터만 존재 → 나머지는 0."""
    target_date = "2026-05-06"
    await fake_redis.set(f"metrics:time_filter:morning_lockout:{target_date}", "5")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v1/metrics/time-filter-stats?date={target_date}"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["morning_lockout"] == 5
    assert data["afternoon_lockout"] == 0
    assert data["gap_open_morning_exception"] == 0
