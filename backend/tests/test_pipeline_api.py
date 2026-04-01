"""수동 파이프라인 API 테스트."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from api.routes.collector import router
from modules.collector.scheduler import PIPELINE_STATUS_KEY, PIPELINE_HEALTHY_KEY
from tests.conftest import FakeRedis


def _make_app(fake_redis: FakeRedis | None = None) -> tuple[FastAPI, MagicMock]:
    """테스트용 FastAPI 앱 + mock 스케줄러 반환."""
    if fake_redis is None:
        fake_redis = FakeRedis()

    mock_scheduler = MagicMock()
    mock_scheduler.get_pipeline_status = AsyncMock(return_value={})
    mock_scheduler.run_premarket_pipeline = AsyncMock(return_value={"completed": True})
    mock_scheduler._running = True

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.collector_scheduler = mock_scheduler
    app.state._fake_redis = fake_redis  # 참조 보관

    return app, mock_scheduler


@pytest.mark.asyncio
async def test_pipeline_status_endpoint():
    """GET /api/v1/collector/pipeline-status가 pipeline_status JSON 반환."""
    fake_redis = FakeRedis()
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps({"premarket": {"status": "success"}}))
    await fake_redis.set(PIPELINE_HEALTHY_KEY, "true")

    app, mock_scheduler = _make_app(fake_redis)
    mock_scheduler.get_pipeline_status = AsyncMock(return_value={"premarket": {"status": "success"}})

    with patch("api.routes.collector.redis_client", fake_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/collector/pipeline-status")

    assert resp.status_code == 200
    body = resp.json()
    assert "pipeline_status" in body
    assert "pipeline_healthy" in body


@pytest.mark.asyncio
async def test_trigger_premarket_pipeline():
    """POST /api/v1/collector/trigger/premarket-pipeline이 202와 triggered=True 반환."""
    fake_redis = FakeRedis()
    app, mock_scheduler = _make_app(fake_redis)

    with patch("api.routes.collector.redis_client", fake_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/collector/trigger/premarket-pipeline")

    assert resp.status_code == 202
    body = resp.json()
    assert body["triggered"] is True


@pytest.mark.asyncio
async def test_trigger_pipeline_rejects_duplicate():
    """파이프라인 실행 중 중복 요청 시 409 반환."""
    fake_redis = FakeRedis()
    await fake_redis.set("scheduler:pipeline_running", "true")  # 이미 실행 중

    app, mock_scheduler = _make_app(fake_redis)

    with patch("api.routes.collector.redis_client", fake_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/collector/trigger/premarket-pipeline")

    assert resp.status_code == 409
