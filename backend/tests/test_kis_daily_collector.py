"""KIS 일봉 보조 수집기 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch
from datetime import date

from core.clients.kis_rest import DailyPrice
from modules.collector.models import CollectionResult
from modules.collector.sources.kis_daily_collector import KISDailyCollector


def _make_daily_price(stock_code: str = "005930", data_date: str = "20260402") -> DailyPrice:
    return DailyPrice(
        stock_code=stock_code,
        data_date=data_date,
        open_price=70000,
        high_price=72000,
        low_price=69500,
        close_price=71000,
        volume=10000000,
        change_rate=1.5,
    )


def _make_collector(stock_codes: list[str] | None = None, target_date: str = "20260402"):
    mock_rest = MagicMock()
    mock_db = AsyncMock()

    async def get_daily_price(code, start, end):
        return [_make_daily_price(code, target_date)]

    mock_rest.get_daily_price = AsyncMock(side_effect=get_daily_price)

    # stocks 테이블 조회 mock
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = stock_codes or ["005930", "000660", "035420"]
    mock_db.execute = AsyncMock(return_value=mock_result)

    return KISDailyCollector(mock_rest, mock_db), mock_rest, mock_db


@pytest.mark.asyncio
async def test_collect_all_stocks_success():
    """활성 주식 3종목 조회, 2종목 성공 1종목 실패 → CollectionResult(collected=2, failed=1, total_target=3)."""
    mock_rest = MagicMock()
    mock_db = AsyncMock()

    async def get_daily_price(code, start, end):
        if code == "000660":
            raise Exception("API 오류")
        return [_make_daily_price(code)]

    mock_rest.get_daily_price = AsyncMock(side_effect=get_daily_price)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["005930", "000660", "035420"]
    mock_db.execute = AsyncMock(return_value=mock_result)

    collector = KISDailyCollector(mock_rest, mock_db)

    with patch("modules.collector.sources.kis_daily_collector.get_prev_trading_day", return_value=date(2026, 4, 2)):
        result = await collector.collect_all()

    assert isinstance(result, CollectionResult)
    assert result.collected == 2
    assert result.failed == 1
    assert result.total_target == 3


@pytest.mark.asyncio
async def test_batch_commit():
    """50종목 배치 단위로 DB commit 호출."""
    mock_rest = MagicMock()
    mock_db = AsyncMock()

    codes = [f"{i:06d}" for i in range(55)]

    async def get_daily_price(code, start, end):
        return [_make_daily_price(code)]

    mock_rest.get_daily_price = AsyncMock(side_effect=get_daily_price)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = codes
    mock_db.execute = AsyncMock(return_value=mock_result)

    collector = KISDailyCollector(mock_rest, mock_db)

    with patch("modules.collector.sources.kis_daily_collector.get_prev_trading_day", return_value=date(2026, 4, 2)):
        await collector.collect_all()

    # 55종목 → 배치 2회 (50 + 5) → commit 2회
    assert mock_db.commit.call_count == 2


@pytest.mark.asyncio
async def test_source_tag_kis_daily():
    """저장된 MarketData.source가 'kis_daily'인지 확인."""
    mock_rest = MagicMock()
    mock_db = AsyncMock()

    async def get_daily_price(code, start, end):
        return [_make_daily_price(code)]

    mock_rest.get_daily_price = AsyncMock(side_effect=get_daily_price)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["005930"]
    mock_db.execute = AsyncMock(return_value=mock_result)

    collector = KISDailyCollector(mock_rest, mock_db)

    with patch("modules.collector.sources.kis_daily_collector.get_prev_trading_day", return_value=date(2026, 4, 2)):
        await collector.collect_all()

    # execute 호출 인자에서 source="kis_daily" 확인
    execute_calls = mock_db.execute.call_args_list
    # 첫 번째 execute는 stocks 조회, 두 번째부터 upsert
    upsert_call = execute_calls[1]
    stmt = upsert_call.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "kis_daily" in compiled


@pytest.mark.asyncio
async def test_collect_result_data_date():
    """CollectionResult.data_date가 전일(T-1) 날짜인지 확인."""
    mock_rest = MagicMock()
    mock_db = AsyncMock()

    async def get_daily_price(code, start, end):
        return [_make_daily_price(code, "20260402")]

    mock_rest.get_daily_price = AsyncMock(side_effect=get_daily_price)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["005930"]
    mock_db.execute = AsyncMock(return_value=mock_result)

    collector = KISDailyCollector(mock_rest, mock_db)

    with patch("modules.collector.sources.kis_daily_collector.get_prev_trading_day", return_value=date(2026, 4, 2)):
        result = await collector.collect_all()

    assert result.data_date == "20260402"


@pytest.mark.asyncio
async def test_minimum_success_rate():
    """80% 미만 수집 시 실패 판정 — CollectionResult로는 성공/실패를 validator가 판단한다."""
    mock_rest = MagicMock()
    mock_db = AsyncMock()

    codes = [f"{i:06d}" for i in range(10)]

    async def get_daily_price(code, start, end):
        # 10종목 중 3종목만 성공 (30% < 80%)
        if int(code) < 3:
            return [_make_daily_price(code)]
        raise Exception("실패")

    mock_rest.get_daily_price = AsyncMock(side_effect=get_daily_price)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = codes
    mock_db.execute = AsyncMock(return_value=mock_result)

    collector = KISDailyCollector(mock_rest, mock_db)

    with patch("modules.collector.sources.kis_daily_collector.get_prev_trading_day", return_value=date(2026, 4, 2)):
        result = await collector.collect_all()

    assert result.collected == 3
    assert result.total_target == 10
    # 30% < 80% → validator가 실패로 판정할 것
    ratio = result.collected / result.total_target
    assert ratio < 0.8
