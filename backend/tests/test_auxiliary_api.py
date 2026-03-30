"""보조 데이터 API 테스트 — financial, sentiment, status 엔드포인트."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from main import create_app
from api.deps import get_db


@pytest.fixture
def app():
    app = create_app()

    scheduler = MagicMock()
    scheduler.get_status.return_value = {"running": True, "job_count": 8}
    scheduler.get_screening_status.return_value = {
        "primary_last_run": None,
        "secondary_last_run": None,
        "secondary_interval": 30,
        "primary_screener_ready": True,
        "realtime_screener_ready": True,
    }
    scheduler.get_auxiliary_status.return_value = {
        "last_dart": None,
        "last_sentiment": None,
    }
    app.state.collector_scheduler = scheduler

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_result.scalars.return_value.first.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    return app


class TestFinancialAPI:
    """GET /api/v1/screening/auxiliary/financial/{stock_code}"""

    @pytest.mark.asyncio
    async def test_financial_200(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/financial/005930")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_financial_returns_stock_code(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/financial/005930")
        data = resp.json()
        assert "stock_code" in data

    @pytest.mark.asyncio
    async def test_financial_no_data_returns_null(self, app):
        """데이터 없으면 null 값 반환."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/financial/999999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stock_code"] == "999999"
        assert data["fiscal_year"] is None


class TestSentimentAPI:
    """GET /api/v1/screening/auxiliary/sentiment/{stock_code}"""

    @pytest.mark.asyncio
    async def test_sentiment_200(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/sentiment/005930")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sentiment_returns_list(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/sentiment/005930")
        data = resp.json()
        assert "sentiments" in data
        assert isinstance(data["sentiments"], list)

    @pytest.mark.asyncio
    async def test_sentiment_returns_stock_code(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/sentiment/005930")
        data = resp.json()
        assert data["stock_code"] == "005930"


class TestAuxiliaryStatusAPI:
    """GET /api/v1/screening/auxiliary/status"""

    @pytest.mark.asyncio
    async def test_status_200(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/status")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_status_has_dart_and_sentiment(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/status")
        data = resp.json()
        assert "last_dart" in data
        assert "last_sentiment" in data

    @pytest.mark.asyncio
    async def test_status_no_scheduler(self, app):
        """스케줄러 미초기화 시 기본 응답."""
        del app.state.collector_scheduler
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/status")
        assert resp.status_code == 200
