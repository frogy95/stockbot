"""DART 재무 수집기 테스트."""

import zipfile
import io
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from modules.collector.sources.dart import DartCollector, MAX_FINANCIAL_QUERIES


# ---------------------------------------------------------------------------
# 헬퍼: XML bytes 생성
# ---------------------------------------------------------------------------

def _make_corp_code_xml(items: list[dict]) -> bytes:
    """테스트용 corp_code XML bytes를 생성한다."""
    lines = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "<result>"]
    for item in items:
        stock_code_val = item.get("stock_code", "")
        lines.append("  <list>")
        lines.append(f"    <corp_code>{item['corp_code']}</corp_code>")
        lines.append(f"    <corp_name>{item['corp_name']}</corp_name>")
        lines.append(f"    <stock_code>{stock_code_val}</stock_code>")
        lines.append(f"    <modify_date>{item.get('modify_date', '20240101')}</modify_date>")
        lines.append("  </list>")
    lines.append("</result>")
    return "\n".join(lines).encode("utf-8")


def _make_financial_response(status: str = "000", items: list[dict] | None = None) -> dict:
    """DART fnlttSinglAcntAll API 응답을 생성한다."""
    return {
        "status": status,
        "message": "정상" if status == "000" else "오류",
        "list": items or [],
    }


# ---------------------------------------------------------------------------
# Test 1: parse_corp_code_xml
# ---------------------------------------------------------------------------

class TestParseCorpCodeXml:
    """DartCollector.parse_corp_code_xml 단위 테스트."""

    def setup_method(self):
        mock_session = AsyncMock(spec=AsyncSession)
        self.collector = DartCollector(mock_session)

    def test_parse_listed_company(self):
        """상장 기업은 stock_code를 그대로 반환한다."""
        xml_bytes = _make_corp_code_xml([
            {"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930", "modify_date": "20240101"},
        ])
        records = self.collector.parse_corp_code_xml(xml_bytes)

        assert len(records) == 1
        assert records[0]["corp_code"] == "00126380"
        assert records[0]["corp_name"] == "삼성전자"
        assert records[0]["stock_code"] == "005930"
        assert records[0]["modify_date"] == date(2024, 1, 1)

    def test_parse_unlisted_company_empty_stock_code(self):
        """비상장 기업(stock_code 빈 문자열 또는 공백)은 stock_code를 None으로 처리한다."""
        xml_bytes = _make_corp_code_xml([
            {"corp_code": "00999999", "corp_name": "비상장법인", "stock_code": "  ", "modify_date": "20240201"},
        ])
        records = self.collector.parse_corp_code_xml(xml_bytes)

        assert len(records) == 1
        assert records[0]["stock_code"] is None

    def test_parse_multiple_companies(self):
        """여러 기업을 한 번에 파싱한다."""
        xml_bytes = _make_corp_code_xml([
            {"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930", "modify_date": "20240101"},
            {"corp_code": "00126381", "corp_name": "SK하이닉스", "stock_code": "000660", "modify_date": "20240102"},
            {"corp_code": "00999999", "corp_name": "비상장법인", "stock_code": "", "modify_date": "20240103"},
        ])
        records = self.collector.parse_corp_code_xml(xml_bytes)

        assert len(records) == 3
        assert records[0]["stock_code"] == "005930"
        assert records[1]["stock_code"] == "000660"
        assert records[2]["stock_code"] is None

    def test_parse_invalid_modify_date(self):
        """modify_date가 잘못된 형식이면 None으로 처리한다."""
        xml_bytes = _make_corp_code_xml([
            {"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930", "modify_date": "invalid"},
        ])
        records = self.collector.parse_corp_code_xml(xml_bytes)

        assert len(records) == 1
        assert records[0]["modify_date"] is None

    def test_parse_empty_xml(self):
        """비어있는 result 태그는 빈 리스트를 반환한다."""
        xml_bytes = b"<?xml version=\"1.0\" encoding=\"UTF-8\"?><result></result>"
        records = self.collector.parse_corp_code_xml(xml_bytes)
        assert records == []


# ---------------------------------------------------------------------------
# Test 2: fetch_financial
# ---------------------------------------------------------------------------

class TestFetchFinancial:
    """DartCollector.fetch_financial 단위 테스트 (httpx 모킹)."""

    def setup_method(self):
        mock_session = AsyncMock(spec=AsyncSession)
        self.collector = DartCollector(mock_session)

    @pytest.mark.asyncio
    async def test_fetch_financial_success(self):
        """status==000이면 매출액/영업이익/당기순이익을 파싱한다."""
        financial_items = [
            {"account_nm": "매출액", "thstrm_amount": "100,000,000"},
            {"account_nm": "영업이익", "thstrm_amount": "20,000,000"},
            {"account_nm": "당기순이익", "thstrm_amount": "15,000,000"},
        ]
        response_data = _make_financial_response("000", financial_items)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response_data

        with patch("modules.collector.sources.dart.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await self.collector.fetch_financial("00126380", "2025", "11011")

        assert result is not None
        assert result["revenue"] == 100_000_000
        assert result["operating_profit"] == 20_000_000
        assert result["net_income"] == 15_000_000

    @pytest.mark.asyncio
    async def test_fetch_financial_error_status(self):
        """status가 000이 아니면 None을 반환한다."""
        response_data = _make_financial_response("013", [])

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response_data

        with patch("modules.collector.sources.dart.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await self.collector.fetch_financial("00126380", "2025", "11011")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_financial_http_error(self):
        """HTTP 오류 시 None을 반환하고 예외를 로깅한다."""
        with patch("modules.collector.sources.dart.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get.side_effect = Exception("connection error")
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await self.collector.fetch_financial("00126380", "2025", "11011")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_financial_partial_data(self):
        """일부 항목만 존재해도 파싱 가능한 항목을 반환한다."""
        financial_items = [
            {"account_nm": "매출액", "thstrm_amount": "50,000,000"},
            # 영업이익/당기순이익 없음
        ]
        response_data = _make_financial_response("000", financial_items)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response_data

        with patch("modules.collector.sources.dart.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await self.collector.fetch_financial("00126380", "2025", "11011")

        assert result is not None
        assert result["revenue"] == 50_000_000
        assert result["operating_profit"] is None
        assert result["net_income"] is None


# ---------------------------------------------------------------------------
# Test 3: collect_financials
# ---------------------------------------------------------------------------

class TestCollectFinancials:
    """DartCollector.collect_financials 단위 테스트."""

    def _make_mock_session(self, corp_code_rows: list[tuple]) -> AsyncMock:
        """DB 세션 mock을 생성한다."""
        mock_session = AsyncMock(spec=AsyncSession)

        # select(CorpCode) 결과 mock
        mock_result = MagicMock()
        mock_rows = []
        for stock_code, corp_code in corp_code_rows:
            row = MagicMock()
            row.stock_code = stock_code
            row.corp_code = corp_code
            mock_rows.append(row)
        mock_result.fetchall.return_value = mock_rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        return mock_session

    @pytest.mark.asyncio
    async def test_collect_financials_basic(self):
        """매핑된 종목의 재무 데이터를 수집하고 저장 건수를 반환한다."""
        mock_session = self._make_mock_session([
            ("005930", "00126380"),
        ])
        collector = DartCollector(mock_session)

        financial_data = {"revenue": 100_000, "operating_profit": 20_000, "net_income": 15_000}
        with patch.object(collector, "fetch_financial", return_value=financial_data) as mock_fetch:
            count = await collector.collect_financials(["005930"])

        assert count == 1
        mock_fetch.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_financials_skip_unlisted(self):
        """corp_code 매핑이 없는 종목(ETF/비상장)은 스킵한다."""
        # 매핑 없음 → fetchall이 빈 리스트 반환
        mock_session = self._make_mock_session([])
        collector = DartCollector(mock_session)

        with patch.object(collector, "fetch_financial") as mock_fetch:
            count = await collector.collect_financials(["069500"])  # KODEX200 ETF

        assert count == 0
        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_financials_max_limit(self):
        """MAX_FINANCIAL_QUERIES(30) 이상 종목은 잘라낸다."""
        # 35개 종목 매핑 생성
        corp_code_rows = [(f"{i:06d}", f"{i:08d}") for i in range(35)]
        mock_session = self._make_mock_session(corp_code_rows)
        collector = DartCollector(mock_session)

        financial_data = {"revenue": 1000, "operating_profit": 200, "net_income": 100}
        with patch.object(collector, "fetch_financial", return_value=financial_data) as mock_fetch:
            stock_codes = [f"{i:06d}" for i in range(35)]
            count = await collector.collect_financials(stock_codes)

        assert count == MAX_FINANCIAL_QUERIES
        assert mock_fetch.call_count == MAX_FINANCIAL_QUERIES

    @pytest.mark.asyncio
    async def test_collect_financials_skip_none_result(self):
        """fetch_financial이 None을 반환하면 해당 종목을 스킵한다."""
        mock_session = self._make_mock_session([
            ("005930", "00126380"),
            ("000660", "00126381"),
        ])
        collector = DartCollector(mock_session)

        # 첫 번째는 None(실패), 두 번째는 성공
        financial_data = {"revenue": 50_000, "operating_profit": 5_000, "net_income": 3_000}
        with patch.object(
            collector, "fetch_financial", side_effect=[None, financial_data]
        ):
            count = await collector.collect_financials(["005930", "000660"])

        assert count == 1

    @pytest.mark.asyncio
    async def test_collect_financials_empty_input(self):
        """빈 stock_codes 리스트이면 0을 반환한다."""
        mock_session = AsyncMock(spec=AsyncSession)
        collector = DartCollector(mock_session)

        count = await collector.collect_financials([])
        assert count == 0


# ---------------------------------------------------------------------------
# Test 4: MAX_FINANCIAL_QUERIES 상수
# ---------------------------------------------------------------------------

def test_max_financial_queries_constant():
    """MAX_FINANCIAL_QUERIES 상수가 30임을 검증한다."""
    assert MAX_FINANCIAL_QUERIES == 30
