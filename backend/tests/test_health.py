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
