"""CollectionValidator.cross_check_prices 테스트."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.collector.validator import CollectionValidator


@pytest.fixture
def validator():
    return CollectionValidator()


@pytest.fixture
def mock_session():
    return AsyncMock()


def _make_rows_result(rows: list) -> MagicMock:
    """session.execute() 반환값 중 .all()을 반환하는 MagicMock 생성."""
    result = MagicMock()
    result.all.return_value = rows
    return result


DATA_DATE = date(2026, 4, 1)


@pytest.mark.asyncio
async def test_crosscheck_no_divergence(validator, mock_session):
    """포털/KIS 종가 동일 → 빈 리스트 반환."""
    # data_go_kr 레코드: (stock_code, close_price)
    portal_rows = [("005930", Decimal("70000")), ("000660", Decimal("100000"))]
    # kis_daily 레코드: (stock_code, close_price)
    kis_rows = [("005930", Decimal("70000")), ("000660", Decimal("100000"))]

    mock_session.execute.side_effect = [
        _make_rows_result(portal_rows),
        _make_rows_result(kis_rows),
    ]

    result = await validator.cross_check_prices(mock_session, DATA_DATE)

    assert result == []


@pytest.mark.asyncio
async def test_crosscheck_within_1pct(validator, mock_session):
    """종가 차이 0.5% → 빈 리스트 반환."""
    # 포털: 70000, KIS: 70350 → 차이 0.5%
    portal_rows = [("005930", Decimal("70000"))]
    kis_rows = [("005930", Decimal("70350"))]

    mock_session.execute.side_effect = [
        _make_rows_result(portal_rows),
        _make_rows_result(kis_rows),
    ]

    result = await validator.cross_check_prices(mock_session, DATA_DATE)

    assert result == []


@pytest.mark.asyncio
async def test_crosscheck_exceeds_1pct(validator, mock_session):
    """종가 차이 2% → 해당 종목코드 리스트 반환."""
    # 포털: 70000, KIS: 71400 → 차이 2%
    portal_rows = [("005930", Decimal("70000")), ("000660", Decimal("100000"))]
    kis_rows = [("005930", Decimal("71400")), ("000660", Decimal("100000"))]

    mock_session.execute.side_effect = [
        _make_rows_result(portal_rows),
        _make_rows_result(kis_rows),
    ]

    result = await validator.cross_check_prices(mock_session, DATA_DATE)

    assert len(result) == 1
    assert result[0]["stock_code"] == "005930"
    assert result[0]["portal_close"] == Decimal("70000")
    assert result[0]["kis_close"] == Decimal("71400")
    assert result[0]["divergence_pct"] == pytest.approx(2.0, rel=1e-3)


@pytest.mark.asyncio
async def test_crosscheck_no_overlap(validator, mock_session):
    """포털에만 있는 종목, KIS에만 있는 종목 → 빈 리스트 (양쪽 모두 있는 종목만 비교)."""
    # 포털에는 005930, KIS에는 000660 — 겹치는 종목 없음
    portal_rows = [("005930", Decimal("70000"))]
    kis_rows = [("000660", Decimal("100000"))]

    mock_session.execute.side_effect = [
        _make_rows_result(portal_rows),
        _make_rows_result(kis_rows),
    ]

    result = await validator.cross_check_prices(mock_session, DATA_DATE)

    assert result == []
