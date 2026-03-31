import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_get_all_settings(app, auth_headers):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 32


@pytest.mark.asyncio
async def test_get_settings_by_category(app, auth_headers):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings?category=risk", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["category"] == "risk" for item in data)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_setting_by_key(app, auth_headers):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/trading_env", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "trading_env"
    assert data["value"] == "paper"


@pytest.mark.asyncio
async def test_update_setting(app, auth_headers):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/trading_env", json={"value": "live"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["value"] == "live"

            resp = await client.get("/api/v1/settings/trading_env", headers=auth_headers)
            assert resp.json()["value"] == "live"

            await client.put(
                "/api/v1/settings/trading_env", json={"value": "paper"},
                headers=auth_headers,
            )


@pytest.mark.asyncio
async def test_get_nonexistent_setting(app, auth_headers):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_nonexistent_setting(app, auth_headers):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/nonexistent", json={"value": "test"},
                headers=auth_headers,
            )
    assert resp.status_code == 404
