import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock
import jwt as pyjwt
from datetime import datetime, timedelta, timezone

from main import create_app

_JWT_SECRET = "test-secret-key-32bytes-long-abc"


def _make_token() -> str:
    return pyjwt.encode(
        {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            "trading_env": "paper",
        },
        _JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {_make_token()}"}


@pytest.mark.asyncio
async def test_dashboard_summary_200(app, auth_headers):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.deps.settings") as mock_settings:
                mock_settings.JWT_SECRET = _JWT_SECRET
                mock_settings.TRADING_ENV = "paper"

                resp = await client.get("/api/v1/dashboard/summary", headers=auth_headers)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_summary_required_fields(app, auth_headers):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.deps.settings") as mock_settings:
                mock_settings.JWT_SECRET = _JWT_SECRET
                mock_settings.TRADING_ENV = "paper"

                resp = await client.get("/api/v1/dashboard/summary", headers=auth_headers)

    data = resp.json()
    required_fields = [
        "today_pnl",
        "today_pnl_rate",
        "today_trade_count",
        "active_positions",
        "unrealized_pnl",
        "trading_env",
        "engine_running",
        "risk_status",
    ]
    for field in required_fields:
        assert field in data, f"필드 누락: {field}"


@pytest.mark.asyncio
async def test_dashboard_summary_no_trades_defaults(app, auth_headers):
    """거래 이력 없는 경우 손익 0, 거래 건수 0."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.deps.settings") as mock_settings:
                mock_settings.JWT_SECRET = _JWT_SECRET
                mock_settings.TRADING_ENV = "paper"

                resp = await client.get("/api/v1/dashboard/summary", headers=auth_headers)

    data = resp.json()
    assert data["today_pnl"] == 0
    assert data["today_trade_count"] == 0


@pytest.mark.asyncio
async def test_dashboard_summary_no_auth(app):
    """인증 없이 접근 불가."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/dashboard/summary")

    assert resp.status_code == 401
