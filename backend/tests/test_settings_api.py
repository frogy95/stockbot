import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_get_all_settings(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 21


@pytest.mark.asyncio
async def test_get_settings_by_category(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings?category=risk")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["category"] == "risk" for item in data)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_setting_by_key(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/trading_env")
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "trading_env"
    assert data["value"] == "paper"


@pytest.mark.asyncio
async def test_update_setting(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 수정
            resp = await client.put(
                "/api/v1/settings/trading_env", json={"value": "live"}
            )
            assert resp.status_code == 200
            assert resp.json()["value"] == "live"

            # 확인
            resp = await client.get("/api/v1/settings/trading_env")
            assert resp.json()["value"] == "live"

            # 복원
            await client.put(
                "/api/v1/settings/trading_env", json={"value": "paper"}
            )


@pytest.mark.asyncio
async def test_get_nonexistent_setting(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/settings/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_nonexistent_setting(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/nonexistent", json={"value": "test"}
            )
    assert resp.status_code == 404
