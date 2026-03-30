"""수집 API 엔드포인트 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from main import create_app
from modules.collector.scheduler import CollectorScheduler
from modules.collector.trade_strength import TradeStrengthCalculator


def _make_mock_scheduler():
    scheduler = MagicMock(spec=CollectorScheduler)
    scheduler.get_status.return_value = {
        "running": True,
        "job_count": 4,
        "next_jobs": [],
        "ws_subscriptions": 5,
        "last_premarket": None,
        "last_etf": None,
    }
    scheduler.trigger_premarket = AsyncMock(return_value={"stocks_collected": 100})
    scheduler.trigger_etf = AsyncMock(return_value={"etfs_collected": 10})
    return scheduler


@pytest.fixture
def app():
    app = create_app()
    app.state.collector_scheduler = _make_mock_scheduler()
    app.state.trade_strength = TradeStrengthCalculator()
    return app


@pytest.mark.asyncio
async def test_get_collector_status(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/collector/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is True
    assert data["job_count"] == 4


@pytest.mark.asyncio
async def test_trigger_premarket(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/collector/trigger/premarket")

    assert resp.status_code == 200
    data = resp.json()
    assert data["triggered"] is True
    assert "message" in data


@pytest.mark.asyncio
async def test_get_realtime_data(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/collector/realtime/005930")

    assert resp.status_code == 200
    data = resp.json()
    assert "execution" in data
    assert "orderbook" in data
    assert "trade_strength" in data
    assert data["trade_strength"] == 50.0  # 중립값
