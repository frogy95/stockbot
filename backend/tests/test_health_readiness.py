"""health/readiness 엔드포인트 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.routes.health import router
from tests.conftest import FakeRedis


def _make_app(scheduler_running: bool = True, pipeline_healthy: str = "true") -> FastAPI:
    """테스트용 FastAPI 앱 생성."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    fake_redis = FakeRedis()

    async def _set_pipeline_healthy():
        await fake_redis.set("scheduler:pipeline_healthy", pipeline_healthy)

    import asyncio

    # 파이프라인 상태 미리 설정
    asyncio.get_event_loop().run_until_complete(_set_pipeline_healthy())

    # 스케줄러 mock
    mock_scheduler = MagicMock()
    mock_scheduler._running = scheduler_running

    app.state.collector_scheduler = mock_scheduler
    app.state._redis = fake_redis  # health route가 app.state._redis 또는 redis_client를 사용

    return app


@pytest.mark.asyncio
async def test_readiness_healthy():
    """DB+Redis+스케줄러+pipeline_healthy 모두 정상이면 200 + 'ready'."""
    from httpx import AsyncClient, ASGITransport

    fake_redis = FakeRedis()
    await fake_redis.set("scheduler:pipeline_healthy", "true")

    mock_scheduler = MagicMock()
    mock_scheduler._running = True

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.collector_scheduler = mock_scheduler

    with (
        patch("api.routes.health.get_engine") as mock_engine,
        patch("api.routes.health.redis_client", fake_redis),
    ):
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.execute = AsyncMock()
        mock_engine.return_value.connect.return_value = mock_conn

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/health/readiness")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"


@pytest.mark.asyncio
async def test_readiness_unhealthy_pipeline():
    """pipeline_healthy가 'false'이면 503."""
    from httpx import AsyncClient, ASGITransport

    fake_redis = FakeRedis()
    await fake_redis.set("scheduler:pipeline_healthy", "false")

    mock_scheduler = MagicMock()
    mock_scheduler._running = True

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.collector_scheduler = mock_scheduler

    with (
        patch("api.routes.health.get_engine") as mock_engine,
        patch("api.routes.health.redis_client", fake_redis),
    ):
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.execute = AsyncMock()
        mock_engine.return_value.connect.return_value = mock_conn

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/health/readiness")

    assert resp.status_code == 503
