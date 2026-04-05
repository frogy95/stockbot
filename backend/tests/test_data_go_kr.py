"""공공데이터포털 수집기 테스트."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from modules.collector.models import CollectionResult
from modules.collector.sources.data_go_kr import DataGoKrCollector


def _make_response_json(items: list[dict], total_count: int = 1) -> dict:
    """공공데이터포털 JSON 응답 구조를 생성."""
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "numOfRows": 500,
                "pageNo": 1,
                "totalCount": total_count,
                "items": {"item": items},
            },
        }
    }


SAMPLE_ITEM = {
    "basDt": "20260329",
    "srtnCd": "005930",
    "itmsNm": "삼성전자",
    "mrktCtg": "KOSPI",
    "clpr": "70000",
    "mkp": "69500",
    "hipr": "70500",
    "lopr": "69000",
    "trqu": "15000000",
    "mrktTotAmt": "417900000000000",
    "lstgStCnt": "5969782550",
    "fltRt": "1.45",
}


@pytest.mark.asyncio
async def test_fetch_page_success():
    """정상 JSON 응답 파싱 테스트."""
    mock_session = AsyncMock(spec=AsyncSession)
    collector = DataGoKrCollector(mock_session)

    response_json = _make_response_json([SAMPLE_ITEM])
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = response_json

    with patch("modules.collector.sources.data_go_kr.httpx.AsyncClient") as mock_client:
        mock_ctx = AsyncMock()
        mock_ctx.get.return_value = mock_resp
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        items = await collector._fetch_page(1, 500)

    assert len(items) == 1
    assert items[0]["srtnCd"] == "005930"


@pytest.mark.asyncio
async def test_fetch_page_retry():
    """첫 호출 실패 후 재시도 성공."""
    mock_session = AsyncMock(spec=AsyncSession)
    collector = DataGoKrCollector(mock_session)

    response_json = _make_response_json([SAMPLE_ITEM])
    mock_resp_ok = MagicMock()
    mock_resp_ok.raise_for_status = MagicMock()
    mock_resp_ok.json.return_value = response_json

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("network error")
        return mock_resp_ok

    with patch("modules.collector.sources.data_go_kr.httpx.AsyncClient") as mock_client:
        mock_ctx = AsyncMock()
        mock_ctx.get.side_effect = side_effect
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        items = await collector._fetch_page(1, 500, retry_delay=0)

    assert len(items) == 1
    assert call_count == 2


@pytest.mark.asyncio
async def test_fetch_page_all_fail():
    """3회 모두 실패 시 빈 리스트 반환."""
    mock_session = AsyncMock(spec=AsyncSession)
    collector = DataGoKrCollector(mock_session)

    with patch("modules.collector.sources.data_go_kr.httpx.AsyncClient") as mock_client:
        mock_ctx = AsyncMock()
        mock_ctx.get.side_effect = Exception("network error")
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        items = await collector._fetch_page(1, 500, retry_delay=0)

    assert items == []


def test_parse_int():
    assert DataGoKrCollector._parse_int("15000000") == 15000000
    assert DataGoKrCollector._parse_int("1,500") == 1500
    assert DataGoKrCollector._parse_int(None) is None
    assert DataGoKrCollector._parse_int("") is None


def test_parse_float():
    assert DataGoKrCollector._parse_float("1.45") == 1.45
    assert DataGoKrCollector._parse_float(None) is None


def test_parse_date():
    assert DataGoKrCollector._parse_date("20260329") == date(2026, 3, 29)
    assert DataGoKrCollector._parse_date("") is None
    assert DataGoKrCollector._parse_date("invalid") is None


@pytest.mark.asyncio
async def test_collect_all_success():
    """collect_all이 CollectionResult를 정확히 반환하는지 확인."""
    mock_session = AsyncMock(spec=AsyncSession)
    collector = DataGoKrCollector(mock_session)

    # target_date와 basDt가 일치하도록 설정
    target = "20260403"
    item = {**SAMPLE_ITEM, "basDt": target}
    response_json = _make_response_json([item])
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = response_json

    with (
        patch("modules.collector.sources.data_go_kr.httpx.AsyncClient") as mock_client,
        patch.object(DataGoKrCollector, "_latest_trading_date", return_value=target),
    ):
        mock_ctx = AsyncMock()
        mock_ctx.get.return_value = mock_resp
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await collector.collect_all(retry_delay=0)

    assert isinstance(result, CollectionResult)
    assert result.collected == 1
    assert result.null_counts is not None
    assert "close_price" in result.null_counts
    assert "volume" in result.null_counts
    assert result.null_counts["close_price"] == 0
    assert result.null_counts["volume"] == 0
    assert mock_session.execute.call_count == 2  # upsert_stock + save_market_data
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_collect_all_returns_zero_when_no_data():
    """최신 거래일에 0건이면 날짜 폴백 없이 collected=0을 반환하는지 확인."""
    mock_session = AsyncMock(spec=AsyncSession)
    collector = DataGoKrCollector(mock_session)

    empty_response = _make_response_json([], total_count=0)
    mock_resp_empty = MagicMock()
    mock_resp_empty.raise_for_status = MagicMock()
    mock_resp_empty.json.return_value = empty_response

    with patch("modules.collector.sources.data_go_kr.httpx.AsyncClient") as mock_client:
        mock_ctx = AsyncMock()
        mock_ctx.get.return_value = mock_resp_empty
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await collector.collect_all(retry_delay=0)

    assert isinstance(result, CollectionResult)
    assert result.collected == 0
    assert result.data_date is not None


@pytest.mark.asyncio
async def test_collect_all_date_mismatch_returns_zero():
    """API 응답 basDt가 target_date와 다르면 collected=0 반환."""
    mock_session = AsyncMock(spec=AsyncSession)
    collector = DataGoKrCollector(mock_session)

    # target_date는 "20260403"이지만 API가 "20260402" 데이터를 반환
    stale_item = {**SAMPLE_ITEM, "basDt": "20260402"}
    response_json = _make_response_json([stale_item])
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = response_json

    with (
        patch("modules.collector.sources.data_go_kr.httpx.AsyncClient") as mock_client,
        patch.object(DataGoKrCollector, "_latest_trading_date", return_value="20260403"),
    ):
        mock_ctx = AsyncMock()
        mock_ctx.get.return_value = mock_resp
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await collector.collect_all(retry_delay=0)

    assert result.collected == 0
    assert result.data_date == "20260402"
    # DB 저장 시도 없어야 함 (upsert_stock, save_market_data 호출 없음)
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_collect_all_date_match_proceeds_normally():
    """API 응답 basDt가 target_date와 일치하면 정상 수집."""
    mock_session = AsyncMock(spec=AsyncSession)
    collector = DataGoKrCollector(mock_session)

    matching_item = {**SAMPLE_ITEM, "basDt": "20260403"}
    response_json = _make_response_json([matching_item])
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = response_json

    with (
        patch("modules.collector.sources.data_go_kr.httpx.AsyncClient") as mock_client,
        patch.object(DataGoKrCollector, "_latest_trading_date", return_value="20260403"),
    ):
        mock_ctx = AsyncMock()
        mock_ctx.get.return_value = mock_resp
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await collector.collect_all(retry_delay=0)

    assert result.collected == 1
    assert result.data_date == "20260403"
    assert mock_session.execute.call_count == 2  # upsert_stock + save_market_data
