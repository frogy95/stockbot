"""Sprint 2 매매 API 테스트 — 신호/주문/엔진상태 조회."""
from __future__ import annotations

from datetime import datetime, date, time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.fixture
def app():
    """테스트용 FastAPI 앱 (lifespan 비활성화)."""
    test_app = create_app()
    test_app.router.lifespan_context = None
    return test_app


@pytest.fixture
def mock_session_factory():
    session = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


# === 테스트 ===


@pytest.mark.asyncio
async def test_get_signals(app, mock_session_factory):
    """GET /api/v1/trading/signals -> 200."""
    _, session = mock_session_factory

    # trade_signals mock 결과
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
    session.execute = AsyncMock(return_value=mock_result)

    with patch("api.routes.trading.get_session_factory", return_value=mock_session_factory[0]):
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
async def test_get_signals_with_status_filter(app, mock_session_factory):
    """GET /api/v1/trading/signals?status=pending -> 200."""
    _, session = mock_session_factory

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    with patch("api.routes.trading.get_session_factory", return_value=mock_session_factory[0]):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/trading/signals?status=pending")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_orders(app, mock_session_factory):
    """GET /api/v1/trading/orders -> 200."""
    _, session = mock_session_factory

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
    session.execute = AsyncMock(return_value=mock_result)

    with patch("api.routes.trading.get_session_factory", return_value=mock_session_factory[0]):
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
async def test_get_engine_status(app):
    """GET /api/v1/trading/engine-status -> 200."""
    # engine mock
    engine = MagicMock()
    engine._running = True
    engine._order_manager = MagicMock()
    engine._order_manager._queue = MagicMock()
    engine._order_manager._queue.qsize.return_value = 0
    app.state.trading_engine = engine

    with patch("api.routes.trading.get_session_factory") as mock_factory:
        # 활성 포지션 수 조회 mock
        session = AsyncMock()
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = factory

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 3
        session.execute = AsyncMock(return_value=mock_result)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/trading/engine-status")

    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
