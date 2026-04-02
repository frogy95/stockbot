"""한투 REST ETF 수집기 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.clients.kis_rest import StockPrice
from modules.collector.models import CollectionResult
from modules.collector.sources.kis_collector import KISCollector


def _make_stock_price(stock_code: str = "069500", price: int = 40000) -> StockPrice:
    return StockPrice(
        stock_code=stock_code,
        price=price,
        change=500,
        change_rate=1.27,
        volume=3000000,
        trade_amount=120000000000,
        high=40500,
        low=39500,
        open_price=39800,
    )


@pytest.mark.asyncio
async def test_collect_etf_prices():
    """ETF 종목 리스트로 시세 수집."""
    mock_rest = MagicMock()
    mock_rest.get_stock_price = AsyncMock(
        side_effect=lambda code: _make_stock_price(code)
    )
    mock_db = AsyncMock()

    collector = KISCollector(mock_rest, mock_db)
    result = await collector.collect_etf_prices(["069500", "252670"])

    assert isinstance(result, CollectionResult)
    assert result.collected == 2
    assert result.total_target == 2
    assert result.failed == 0
    assert mock_rest.get_stock_price.call_count == 2
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_collect_etf_save_to_db():
    """수집 데이터가 DB execute에 전달되는지 확인."""
    mock_rest = MagicMock()
    mock_rest.get_stock_price = AsyncMock(return_value=_make_stock_price())
    mock_db = AsyncMock()

    collector = KISCollector(mock_rest, mock_db)
    result = await collector.collect_etf_prices(["069500"])

    assert isinstance(result, CollectionResult)
    assert result.collected == 1
    # upsert용 execute 호출
    assert mock_db.execute.call_count == 1


@pytest.mark.asyncio
async def test_collect_etf_partial_failure():
    """일부 종목 실패 시 나머지 정상 수집."""
    mock_rest = MagicMock()

    async def get_price(code):
        if code == "FAIL":
            raise Exception("API error")
        return _make_stock_price(code)

    mock_rest.get_stock_price = AsyncMock(side_effect=get_price)
    mock_db = AsyncMock()

    collector = KISCollector(mock_rest, mock_db)
    result = await collector.collect_etf_prices(["069500", "FAIL", "252670"])

    assert result.collected == 2  # FAIL 제외
    assert result.failed == 1
    assert result.total_target == 3


@pytest.mark.asyncio
async def test_collect_etf_empty_list():
    """빈 리스트 시 collected=0 반환."""
    mock_rest = MagicMock()
    mock_db = AsyncMock()

    collector = KISCollector(mock_rest, mock_db)
    result = await collector.collect_etf_prices([])

    assert result.collected == 0
    assert result.total_target == 0
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_collect_etf_close_price_zero():
    """close_price가 0인 종목은 수집에서 제외하고 null_counts에 기록."""
    mock_rest = MagicMock()

    async def get_price(code):
        if code == "ZERO":
            return _make_stock_price(code, price=0)
        return _make_stock_price(code)

    mock_rest.get_stock_price = AsyncMock(side_effect=get_price)
    mock_db = AsyncMock()

    collector = KISCollector(mock_rest, mock_db)
    result = await collector.collect_etf_prices(["069500", "ZERO", "252670"])

    assert result.collected == 2
    assert result.failed == 0
    assert result.total_target == 3
    assert result.null_counts is not None
    assert result.null_counts["close_price_zero"] == 1
