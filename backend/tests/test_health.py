import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_status_200(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/health")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_response_keys(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/health")
        data = resp.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data


@pytest.mark.asyncio
async def test_health_connected(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/health")
        data = resp.json()
        assert data["database"] == "connected"
        assert data["redis"] == "connected"


@pytest.mark.asyncio
async def test_health_sprint3_keys_shape(app):
    """Phase 8.6 진단 hotfix — Sprint 3 Paper 관찰 키 카운트 API."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/health/sprint3-keys")
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "orderbook_count" in data
        assert isinstance(data["orderbook_count"], int)
        assert "vol5m_count" in data
        assert isinstance(data["vol5m_count"], int)
        assert "scheduler" in data
        assert set(data["scheduler"].keys()) == {
            "last_portal_supplement",
            "last_metrics_rollup",
            "last_auto_rollback_check",
        }
