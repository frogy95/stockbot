"""validate_screening_readiness 단위 테스트."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.collector.validator import CollectionValidator


def _make_session_mock(
    total_count: int,
    latest_date: date | None,
    stats_rows: list[tuple],  # (source, total_per_source, null_per_source)
):
    """AsyncSession mock 생성.

    호출 순서:
      1. total_stmt  → (total_count, latest_date)
      2. stats_stmt  → [(source, total, null_count), ...]  (null+source 단일 쿼리)
    """
    session = AsyncMock()

    total_row = MagicMock()
    total_row.one.return_value = (total_count, latest_date)

    stats_row = MagicMock()
    stats_row.all.return_value = stats_rows

    session.execute.side_effect = [total_row, stats_row]
    return session


@pytest.mark.asyncio
async def test_screening_readiness_pass_t1():
    """T-1 데이터 1500건 이상, null_ratio < 5% → passed=True, severity='info'."""
    today = date.today()
    prev_trading_day = today - timedelta(days=1)

    session = _make_session_mock(
        total_count=1800,
        latest_date=prev_trading_day,
        stats_rows=[("data_go_kr", 1800, 10)],
    )

    validator = CollectionValidator()
    result = await validator.validate_screening_readiness(session)

    assert result.passed is True
    assert result.severity == "info"
    assert result.details["total_count"] == 1800
    assert result.details["is_stale"] is False


@pytest.mark.asyncio
async def test_screening_readiness_pass_t2_stale():
    """latest_date가 T-1보다 오래됨 → passed=True, severity='warning', is_stale=True."""
    today = date.today()
    stale_date = today - timedelta(days=5)

    session = _make_session_mock(
        total_count=1600,
        latest_date=stale_date,
        stats_rows=[("data_go_kr", 1000, 15), ("kis_daily", 600, 5)],
    )

    from core.trading_calendar import get_prev_trading_day
    real_prev = get_prev_trading_day(today, n=1)

    validator = CollectionValidator()
    result = await validator.validate_screening_readiness(session)

    assert result.passed is True
    if stale_date < real_prev:
        assert result.severity == "warning"
        assert result.details["is_stale"] is True
    else:
        assert result.severity == "info"


@pytest.mark.asyncio
async def test_screening_readiness_fail_insufficient():
    """데이터 1000건 → passed=False, failure_type='data_insufficient'."""
    today = date.today()
    prev_day = today - timedelta(days=1)

    session = _make_session_mock(
        total_count=1000,
        latest_date=prev_day,
        stats_rows=[("data_go_kr", 1000, 0)],
    )

    validator = CollectionValidator()
    result = await validator.validate_screening_readiness(session)

    assert result.passed is False
    assert result.failure_type == "data_insufficient"
    assert "1000" in result.failure_reason
    # 데이터 부족 시 stats_stmt는 호출되지 않음
    assert session.execute.call_count == 1


@pytest.mark.asyncio
async def test_screening_readiness_fail_null_ratio():
    """null_ratio >= 5% → passed=False, failure_type='data_quality'."""
    today = date.today()
    prev_day = today - timedelta(days=1)

    session = _make_session_mock(
        total_count=1500,
        latest_date=prev_day,
        stats_rows=[("data_go_kr", 1500, 100)],  # 100/1500 = 6.7% >= 5%
    )

    validator = CollectionValidator()
    result = await validator.validate_screening_readiness(session)

    assert result.passed is False
    assert result.failure_type == "data_quality"
    assert "null" in result.failure_reason.lower()


@pytest.mark.asyncio
async def test_screening_readiness_empty_db():
    """데이터 0건 → passed=False."""
    today = date.today()

    session = _make_session_mock(
        total_count=0,
        latest_date=None,
        stats_rows=[],
    )

    validator = CollectionValidator()
    result = await validator.validate_screening_readiness(session)

    assert result.passed is False
    assert result.failure_type == "data_insufficient"
