"""Phase 2 전체 파이프라인 통합 테스트.

시나리오:
1. 데이터 수집 → 1차 스크리닝 파이프라인
2. 1차 스크리닝 → DART 재무 수집 파이프라인
3. 1차 스크리닝 → 네이버 센티멘트 수집 파이프라인
4. 보조 데이터 API 조회 정합성
5. 기존 회귀 테스트 (Sprint 1/2 모듈 정상 동작)
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from main import create_app
from api.deps import get_db
from modules.collector.sources.dart import DartCollector
from modules.collector.sources.naver import NaverCollector
from modules.screening.screener import PrimaryScreener


# ── 공통 픽스처 ────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    app = create_app()

    scheduler = MagicMock()
    scheduler.get_status.return_value = {"running": True, "job_count": 8}
    scheduler.get_screening_status.return_value = {
        "primary_last_run": None, "secondary_last_run": None,
        "secondary_interval": 30,
        "primary_screener_ready": True, "realtime_screener_ready": True,
    }
    scheduler.get_auxiliary_status.return_value = {"last_dart": None, "last_sentiment": None}
    app.state.collector_scheduler = scheduler
    app.state.trade_strength = MagicMock()
    app.state.primary_screener = MagicMock(spec=PrimaryScreener)
    app.state.realtime_screener = MagicMock()

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


# ── 시나리오 1: 데이터 수집 → 1차 스크리닝 파이프라인 ──────────────────────────────

class TestPrimaryScreeningPipeline:
    """PrimaryScreener.screen() → save_results() 파이프라인 검증."""

    @pytest.mark.asyncio
    async def test_screener_screen_returns_list(self):
        """screen()은 리스트를 반환해야 한다."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        screener = PrimaryScreener()
        results = await screener.screen(mock_db)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_screener_save_results_returns_count(self):
        """save_results()는 저장 건수를 반환해야 한다."""
        mock_db = AsyncMock()
        screener = PrimaryScreener()
        count = await screener.save_results(mock_db, [])
        assert isinstance(count, int)
        assert count == 0

    @pytest.mark.asyncio
    async def test_primary_screening_api_200(self, app):
        """1차 스크리닝 API가 200을 반환해야 한다."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/primary")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data


# ── 시나리오 2: 1차 스크리닝 → DART 재무 수집 파이프라인 ──────────────────────────

class TestDartFinancialPipeline:
    """DartCollector가 1차 스크리닝 결과 종목의 재무 데이터를 수집한다."""

    @pytest.mark.asyncio
    async def test_collect_financials_with_no_corp_mapping(self):
        """corp_code 매핑이 없으면 빈 결과를 반환한다."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []  # 매핑 없음
        mock_db.execute = AsyncMock(return_value=mock_result)

        collector = DartCollector(mock_db)
        result = await collector.collect_financials(["005930", "000660"])
        assert result.collected == 0

    @pytest.mark.asyncio
    async def test_collect_financials_skips_etf(self):
        """ETF/비상장(corp_code 없음) 종목은 스킵된다."""
        mock_db = AsyncMock()
        # SQLAlchemy Row는 속성 접근을 지원하는 namedtuple-like 객체
        row = MagicMock()
        row.stock_code = "005930"
        row.corp_code = "00126380"

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [row]  # 005930만 매핑 있음
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(DartCollector, "fetch_financial", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None  # API 응답 없음
            collector = DartCollector(mock_db)
            result = await collector.collect_financials(["005930", "069500"])  # 069500 = KODEX200 ETF
        # 005930만 시도, 결과 없어서 collected=0
        assert result.collected == 0
        assert mock_fetch.call_count == 1  # ETF는 매핑 없어서 호출 안 됨

    @pytest.mark.asyncio
    async def test_dart_financial_api_200(self, app):
        """재무 API가 200과 올바른 구조를 반환해야 한다."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/financial/005930")
        assert resp.status_code == 200
        data = resp.json()
        assert "stock_code" in data
        assert data["stock_code"] == "005930"


# ── 시나리오 3: 1차 스크리닝 → 네이버 센티멘트 수집 파이프라인 ────────────────────

class TestNaverSentimentPipeline:
    """NaverCollector가 1차 스크리닝 결과 종목의 센티멘트를 수집한다."""

    @pytest.mark.asyncio
    async def test_collect_sentiments_empty_input(self):
        """빈 입력이면 0을 반환한다."""
        mock_db = AsyncMock()
        collector = NaverCollector(mock_db)
        result = await collector.collect_sentiments([])
        assert result.collected == 0

    @pytest.mark.asyncio
    async def test_collect_sentiments_with_mocked_api(self):
        """뉴스 API 모킹 시 센티멘트가 수집되고 DB에 저장된다."""
        mock_db = AsyncMock()
        news_items = [
            {"title": "삼성전자 급등 호재", "link": "http://example.com/1", "pubDate": "Mon, 30 Mar 2026 08:00:00 +0900"},
            {"title": "반도체 상승세 지속", "link": "http://example.com/2", "pubDate": "Mon, 30 Mar 2026 07:00:00 +0900"},
        ]

        with patch.object(NaverCollector, "search_news", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = news_items
            collector = NaverCollector(mock_db)
            result = await collector.collect_sentiments([
                {"stock_code": "005930", "stock_name": "삼성전자"}
            ])

        assert result.collected == 1  # 종목 수 기준 (뉴스가 1건 이상인 종목)
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_naver_sentiment_api_200(self, app):
        """센티멘트 API가 200과 올바른 구조를 반환해야 한다."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/sentiment/005930")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stock_code"] == "005930"
        assert isinstance(data["sentiments"], list)


# ── 시나리오 4: 보조 데이터 API 정합성 ─────────────────────────────────────────

class TestAuxiliaryAPIConsistency:
    """저장된 재무/센티멘트 데이터를 API로 조회하여 정합성을 검증한다."""

    @pytest.mark.asyncio
    async def test_financial_api_returns_correct_fields(self, app):
        """재무 API 응답에 모든 필수 필드가 포함되어야 한다."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/financial/005930")
        data = resp.json()
        required_fields = {"stock_code", "fiscal_year", "fiscal_quarter", "revenue",
                           "operating_profit", "net_income", "source", "collected_at"}
        assert required_fields.issubset(data.keys())

    @pytest.mark.asyncio
    async def test_sentiment_api_returns_correct_structure(self, app):
        """센티멘트 API 응답이 올바른 구조를 가져야 한다."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/sentiment/005930")
        data = resp.json()
        assert "stock_code" in data
        assert "sentiments" in data
        assert isinstance(data["sentiments"], list)

    @pytest.mark.asyncio
    async def test_auxiliary_status_api_fields(self, app):
        """보조 데이터 상태 API 응답에 last_dart, last_sentiment가 있어야 한다."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/auxiliary/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "last_dart" in data
        assert "last_sentiment" in data


# ── 시나리오 5: 기존 회귀 테스트 ───────────────────────────────────────────────

class TestRegressionPhase2:
    """Sprint 1/2에서 구현된 모듈이 변경 없이 정상 동작한다."""

    @pytest.mark.asyncio
    async def test_primary_screening_endpoint_still_works(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/primary")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_secondary_screening_endpoint_still_works(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/secondary")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_screening_status_endpoint_still_works(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/screening/status")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_endpoint_still_works(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/health")
        # 엔드포인트가 존재하면 OK (KIS 의존성 미초기화로 503 가능)
        assert resp.status_code in (200, 503)

    def test_dart_collector_parse_xml_still_works(self):
        """DartCollector.parse_corp_code_xml이 정상 동작한다."""
        xml = (
            b"<result><list>"
            b"<corp_code>00126380</corp_code>"
            b"<corp_name>Samsung</corp_name>"
            b"<stock_code>005930</stock_code>"
            b"<modify_date>20240101</modify_date>"
            b"</list></result>"
        )
        mock_db = AsyncMock()
        collector = DartCollector(mock_db)
        records = collector.parse_corp_code_xml(xml)
        assert len(records) == 1
        assert records[0]["stock_code"] == "005930"

    def test_naver_collector_calc_sentiment_still_works(self):
        """NaverCollector.calc_sentiment이 정상 동작한다."""
        mock_db = AsyncMock()
        collector = NaverCollector(mock_db)
        assert collector.calc_sentiment("삼성전자 급등 호재") > 0
        assert collector.calc_sentiment("주가 폭락 악재") < 0
        assert collector.calc_sentiment("일반 뉴스") == 0.0
