"""스크리닝 API 엔드포인트 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from main import create_app
from modules.collector.trade_strength import TradeStrengthCalculator
from modules.screening.screener import PrimaryScreener
from modules.screening.realtime_screener import RealtimeScreener
from api.deps import get_db


def _make_mock_scheduler():
    scheduler = MagicMock()
    scheduler.get_status.return_value = {
        "running": True,
        "job_count": 6,
        "next_jobs": [],
        "ws_subscriptions": 5,
        "last_premarket": None,
        "last_etf": None,
    }
    scheduler.trigger_primary_screening = AsyncMock(
        return_value={"candidates": 100, "passed": 15}
    )
    scheduler.trigger_secondary_screening = AsyncMock(
        return_value={"candidates": 15, "passed": 5}
    )
    scheduler.get_screening_status.return_value = {
        "primary_last_run": None,
        "secondary_last_run": None,
        "secondary_interval": 30,
        "primary_screener_ready": True,
        "realtime_screener_ready": True,
    }
    return scheduler


def _make_mock_db():
    """DB mock — scalar()과 scalars().all()을 모두 지원."""
    mock_db = AsyncMock()
    # scalar() → None (최신 결과 없음)
    mock_scalar_result = MagicMock()
    mock_scalar_result.scalar.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_scalar_result)
    return mock_db


@pytest.fixture
def app():
    app = create_app()
    app.state.collector_scheduler = _make_mock_scheduler()
    app.state.trade_strength = TradeStrengthCalculator()
    app.state.primary_screener = MagicMock(spec=PrimaryScreener)
    app.state.realtime_screener = MagicMock(spec=RealtimeScreener)

    mock_db = _make_mock_db()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_get_primary_results(app):
    """GET /screening/primary — 최신 1차 스크리닝 결과 조회."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/screening/primary")

    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data
    assert data["results"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_secondary_results(app):
    """GET /screening/secondary — 최신 2차 스크리닝 결과 조회."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/screening/secondary")

    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_trigger_primary(app):
    """POST /screening/trigger/primary — 수동 1차 스크리닝 트리거."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/screening/trigger/primary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["triggered"] is True
    assert "result" in data
    assert data["result"]["candidates"] == 100
    assert data["result"]["passed"] == 15


@pytest.mark.asyncio
async def test_trigger_secondary(app):
    """POST /screening/trigger/secondary — 수동 2차 스크리닝 트리거."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/screening/trigger/secondary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["triggered"] is True
    assert data["result"]["candidates"] == 15


@pytest.mark.asyncio
async def test_get_screening_status(app):
    """GET /screening/status — 스크리닝 상태 조회."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/screening/status")

    assert resp.status_code == 200
    data = resp.json()
    assert "primary_last_run" in data
    assert "secondary_last_run" in data
    assert "secondary_interval" in data
    assert data["secondary_interval"] == 30
