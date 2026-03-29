import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_api_still_works(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_settings_list_21_items(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings")
    assert resp.status_code == 200
    assert len(resp.json()) == 21


@pytest.mark.asyncio
async def test_settings_category_filter(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings?category=risk")
    data = resp.json()
    assert all(item["category"] == "risk" for item in data)


@pytest.mark.asyncio
async def test_kis_status_api(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/kis/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "environment" in data
    assert data["environment"] in ("paper", "live")


@pytest.mark.asyncio
async def test_swagger_includes_new_routers(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/v1/settings" in paths
    assert "/api/v1/kis/status" in paths
    assert "/api/v1/kis/price/{stock_code}" in paths
    assert "/api/v1/health" in paths
