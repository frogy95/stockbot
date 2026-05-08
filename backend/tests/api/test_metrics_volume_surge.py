"""Phase 8.6 Sprint 3 — volume-surge-stats API 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
def mock_session():
    return AsyncMock()


@pytest.fixture
def fake_redis():
    return _FakeRedis()


@pytest.fixture
def app(mock_session, fake_redis):
    """테스트용 FastAPI 앱 — lifespan 비활성화, DB/Redis/Auth override."""
    test_app = create_app()
    test_app.router.lifespan_context = None

    async def override_get_db():
        yield mock_session

    async def override_get_redis():
        yield fake_redis

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_redis] = override_get_redis
    test_app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="admin", trading_env="paper"
    )
    yield test_app
    test_app.dependency_overrides.clear()


def _make_scalar_result(value: int) -> MagicMock:
    """scalar() 호출 시 value를 반환하는 mock execute 결과."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _make_all_result(rows: list) -> MagicMock:
    """all() 호출 시 rows를 반환하는 mock execute 결과."""
    result = MagicMock()
    result.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_volume_surge_stats_with_signals(app, mock_session):
    """dry_run=True 신호 5건, LIVE 신호 2건 시드 → 카운트 검증."""
    # execute()가 3번 호출됨:
    # 1) dry_run 카운트 쿼리, 2) real 카운트 쿼리, 3) 7일 group-by 쿼리
    dry_run_result = _make_scalar_result(5)
    real_result = _make_scalar_result(2)

    # 7일 집계: 3일치 데이터 (각 4건, 3건, 2건)
    row1 = MagicMock()
    row1.cnt = 4
    row2 = MagicMock()
    row2.cnt = 3
    row3 = MagicMock()
    row3.cnt = 2
    ma7_result = _make_all_result([row1, row2, row3])

    mock_session.execute = AsyncMock(
        side_effect=[dry_run_result, real_result, ma7_result]
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/metrics/volume-surge-stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run_count"] == 5
    assert data["real_count"] == 2
    # ma7 = (4+3+2) / 7 = 1.29
    assert data["ma7_dry_run"] == round((4 + 3 + 2) / 7.0, 2)
    assert "date" in data


@pytest.mark.asyncio
async def test_volume_surge_stats_empty_table(app, mock_session):
    """signals 테이블 비어있을 때 → 모두 0 반환."""
    empty_scalar = _make_scalar_result(0)
    empty_all = _make_all_result([])

    mock_session.execute = AsyncMock(
        side_effect=[empty_scalar, empty_scalar, empty_all]
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/metrics/volume-surge-stats")

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run_count"] == 0
    assert data["real_count"] == 0
    assert data["ma7_dry_run"] == 0.0


@pytest.mark.asyncio
async def test_volume_surge_stats_date_param(app, mock_session):
    """date 파라미터 전달 시 응답의 date 필드와 일치하는지 검증."""
    mock_session.execute = AsyncMock(
        side_effect=[
            _make_scalar_result(3),
            _make_scalar_result(0),
            _make_all_result([]),
        ]
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/metrics/volume-surge-stats?date=2026-05-01"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-05-01"
    assert data["dry_run_count"] == 3
