import pytest
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from core.clients.kis_rest import StockPrice, KISDataError
from main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_kis_status(app):
    async with app.router.lifespan_context(app):
        # lifespan 후 mock 교체
        app.state.kis_token_manager = AsyncMock()
        app.state.kis_token_manager.get_access_token = AsyncMock(return_value="token")
        app.state.kis_env = MagicMock()
        app.state.kis_env.name = "paper"
        app.state.kis_ws = MagicMock()
        app.state.kis_ws.connected = False
        app.state.kis_ws.subscription_count = 0

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/kis/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["environment"] == "paper"


@pytest.mark.asyncio
async def test_kis_price(app):
    async with app.router.lifespan_context(app):
        # lifespan 후 mock 교체
        mock_rest = AsyncMock()
        mock_rest.get_stock_price = AsyncMock(
            return_value=StockPrice(
                stock_code="005930",
                price=70000,
                change=-500,
                change_rate=-0.71,
                volume=10000000,
                trade_amount=700000000000,
                high=71000,
                low=69500,
                open_price=70500,
            )
        )
        app.state.kis_rest = mock_rest

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/kis/price/005930")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stock_code"] == "005930"
    assert data["price"] == 70000


@pytest.mark.asyncio
async def test_kis_price_invalid_stock(app):
    async with app.router.lifespan_context(app):
        mock_rest = AsyncMock()
        mock_rest.get_stock_price = AsyncMock(
            side_effect=KISDataError("빈 데이터")
        )
        app.state.kis_rest = mock_rest

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/kis/price/999999")
    assert resp.status_code == 400
