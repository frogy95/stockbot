"""Sprint 2 매매 API 테스트 — 신호/주문/엔진상태 조회."""
from __future__ import annotations

from datetime import datetime, date, time
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import get_db, get_current_user, UserInfo
from main import create_app


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def app(mock_session):
    """테스트용 FastAPI 앱 (lifespan 비활성화, get_db override)."""
    test_app = create_app()
    test_app.router.lifespan_context = None
    async def override_get_db():
        yield mock_session

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="admin", trading_env="paper"
    )
    yield test_app
    test_app.dependency_overrides.clear()


# === 테스트 ===


@pytest.mark.asyncio
async def test_get_signals(app, mock_session):
    """GET /api/v1/trading/signals -> 200."""
    signal = MagicMock()
    signal.id = 1
    signal.stock_code = "005930"
    signal.signal_type = "buy"
    signal.strategy_name = "momentum_breakout"
    signal.confidence = 0.75
    signal.reason = {"test": True}
    signal.entry_price = 73000
    signal.stop_loss = 71540
    signal.take_profit = 75190
    signal.status = "pending"
    signal.created_at = datetime(2026, 3, 30, 10, 0, 0)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [signal]
    mock_session.execute = AsyncMock(return_value=mock_result)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/trading/signals")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["stock_code"] == "005930"


@pytest.mark.asyncio
async def test_get_signals_with_status_filter(app, mock_session):
    """GET /api/v1/trading/signals?status=pending -> 200."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/trading/signals?status=pending")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_orders(app, mock_session):
    """GET /api/v1/trading/orders -> 200."""
    order = MagicMock()
    order.id = 1
    order.signal_id = 1
    order.stock_code = "005930"
    order.order_type = "buy"
    order.order_no = "0001"
    order.quantity = 10
    order.price = 73000
    order.order_division = "01"
    order.status = "filled"
    order.submitted_at = datetime(2026, 3, 30, 10, 0, 0)
    order.filled_at = datetime(2026, 3, 30, 10, 0, 5)
    order.created_at = datetime(2026, 3, 30, 10, 0, 0)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [order]
    mock_session.execute = AsyncMock(return_value=mock_result)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/trading/orders")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["stock_code"] == "005930"


@pytest.mark.asyncio
async def test_get_engine_status(app, mock_session):
    """GET /api/v1/trading/engine-status -> 200."""
    engine = MagicMock()
    engine.get_status.return_value = {
        "is_running": True,
        "queue_size": 0,
        "monitor_active": False,
    }
    app.state.trading_engine = engine

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 3
    mock_session.execute = AsyncMock(return_value=mock_result)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/trading/engine-status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is True
    assert data["active_positions"] == 3
