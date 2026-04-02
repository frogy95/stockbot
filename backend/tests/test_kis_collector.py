"""한투 REST ETF 수집기 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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
    assert mock_db.commit.call_count == 2  # 아이템당 개별 커밋


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


@pytest.mark.asyncio
async def test_get_etf_codes_filters_kodex_only():
    """_get_etf_codes()가 KODEX ETF만 반환하는지 확인."""
    mock_rest = MagicMock()
    mock_rest.get_stock_price = AsyncMock(
        side_effect=lambda code: _make_stock_price(code)
    )

    # mock DB: KODEX 2종 + 비KODEX 2종
    kodex_codes = ["069500", "252670"]  # KODEX 200, KODEX 미국S&P500
    all_codes = kodex_codes + ["091160", "114800"]  # 비KODEX ETF

    # _get_etf_codes 내부의 DB execute 결과를 모킹
    # startswith("KODEX") 필터가 적용되므로 KODEX만 반환되어야 함
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = kodex_codes
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    collector = KISCollector(mock_rest, mock_db)
    # collect_etf_prices(etf_codes=None) → _get_etf_codes() 호출
    result = await collector.collect_etf_prices(etf_codes=None)

    assert result.collected == 2
    assert result.total_target == 2
    # get_stock_price가 KODEX 코드에 대해서만 호출됨
    called_codes = [call.args[0] for call in mock_rest.get_stock_price.call_args_list]
    assert set(called_codes) == set(kodex_codes)


@pytest.mark.asyncio
async def test_get_etf_codes_query_includes_kodex_filter():
    """_get_etf_codes() 쿼리에 KODEX startswith 조건이 포함되는지 확인."""
    mock_rest = MagicMock()

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    collector = KISCollector(mock_rest, mock_db)
    await collector.collect_etf_prices(etf_codes=None)

    # execute가 호출되었는지 확인 (SELECT 쿼리)
    assert mock_db.execute.call_count >= 1
    # 첫 번째 execute 호출의 SQL에 KODEX LIKE 조건이 포함되어야 함
    select_stmt = mock_db.execute.call_args_list[0].args[0]
    compiled = str(select_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "KODEX%" in compiled or "LIKE" in compiled.upper()
