"""Phase 2 Sprint 2 통합 테스트 + 회귀 검증."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from main import create_app
from modules.collector.trade_strength import TradeStrengthCalculator
from modules.screening.screener import PrimaryScreener
from modules.screening.realtime_screener import RealtimeScreener
from api.deps import get_db


@pytest.fixture
def app():
    app = create_app()
    # 스케줄러 mock
    scheduler = MagicMock()
    scheduler.get_status.return_value = {
        "running": True, "job_count": 6, "next_jobs": [],
        "ws_subscriptions": 0, "last_premarket": None, "last_etf": None,
    }
    scheduler.get_screening_status.return_value = {
        "primary_last_run": None, "secondary_last_run": None,
        "secondary_interval": 30,
        "primary_screener_ready": True, "realtime_screener_ready": True,
    }
    app.state.collector_scheduler = scheduler
    app.state.trade_strength = TradeStrengthCalculator()
    app.state.primary_screener = MagicMock(spec=PrimaryScreener)
    app.state.realtime_screener = MagicMock(spec=RealtimeScreener)

    # DB mock
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    return app


class TestScreeningEndpoints:
    """스크리닝 API 엔드포인트 통합 테스트."""

    @pytest.mark.asyncio
    async def test_primary_200(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/primary")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_secondary_200(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/secondary")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_status_200(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/status")
        assert resp.status_code == 200


class TestOpenAPISpec:
    """OpenAPI 스펙에 screening 경로 포함 확인."""

    @pytest.mark.asyncio
    async def test_openapi_contains_screening(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/openapi.json")
        assert resp.status_code == 200
        paths = list(resp.json()["paths"].keys())
        assert "/api/v1/screening/primary" in paths
        assert "/api/v1/screening/secondary" in paths
        assert "/api/v1/screening/status" in paths
        assert "/api/v1/screening/trigger/primary" in paths
        assert "/api/v1/screening/trigger/secondary" in paths


class TestRegressionSprint1:
    """기존 Sprint 1 API 회귀 테스트."""

    @pytest.mark.asyncio
    async def test_health_responds(self, app):
        """health 엔드포인트 응답 확인 (mock 환경에서 503도 정상)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/health")
        assert resp.status_code in (200, 503)
        assert "status" in resp.json()

    @pytest.mark.asyncio
    async def test_collector_status_200(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/collector/status")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_settings_200(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/settings")
        assert resp.status_code == 200
