"""매매 API 엔드포인트 테스트."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_get_risk_status(app, auth_headers):
    """GET /api/v1/trading/risk-status -> 200, 리스크 상태 JSON."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/trading/risk-status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "emergency_stop" in data
    assert "position_count" in data
    assert "daily_max_loss_pct" in data


@pytest.mark.asyncio
async def test_get_positions(app, auth_headers):
    """GET /api/v1/trading/positions -> 200, 빈 배열."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/trading/positions", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_history(app, auth_headers):
    """GET /api/v1/trading/history -> 200, 빈 배열."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/trading/history?target_date=2026-03-30",
                headers=auth_headers,
            )
    assert resp.status_code == 200
    assert resp.json() == []
