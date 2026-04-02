"""CollectionValidator DB 후검증 메서드 테스트."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.collector.validator import CollectionValidator


@pytest.fixture
def validator():
    return CollectionValidator()


@pytest.fixture
def mock_session():
    return AsyncMock()


def _make_scalar_result(value: int) -> MagicMock:
    """session.execute() 반환값을 모방하는 MagicMock 생성."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


# --- validate_premarket_db ---


@pytest.mark.asyncio
async def test_validate_premarket_db_passed(validator, mock_session):
    """데이터 충분 + null 비율 정상 → passed."""
    # 첫 호출: total_count = 2000, 두 번째: null_count = 50 (2.5%)
    mock_session.execute.side_effect = [
        _make_scalar_result(2000),
        _make_scalar_result(50),
    ]

    result = await validator.validate_premarket_db(mock_session)

    assert result.passed is True
    assert result.details["total_count"] == 2000
    assert result.details["null_count"] == 50


@pytest.mark.asyncio
async def test_validate_premarket_db_zero_rows(validator, mock_session):
    """데이터 0건 → failed."""
    mock_session.execute.side_effect = [
        _make_scalar_result(0),
    ]

    result = await validator.validate_premarket_db(mock_session)

    assert result.passed is False
    assert "건수 부족" in result.failure_reason
    assert result.details["total_count"] == 0


@pytest.mark.asyncio
async def test_validate_premarket_db_high_null_ratio(validator, mock_session):
    """데이터 충분 + null 비율 초과 → failed."""
    # total_count = 2000, null_count = 200 (10%)
    mock_session.execute.side_effect = [
        _make_scalar_result(2000),
        _make_scalar_result(200),
    ]

    result = await validator.validate_premarket_db(mock_session)

    assert result.passed is False
    assert "null 비율 초과" in result.failure_reason
    assert result.details["null_ratio"] == pytest.approx(0.1)


# --- validate_etf_db ---


@pytest.mark.asyncio
async def test_validate_etf_db_passed(validator, mock_session):
    """건수 140 이상 → passed."""
    mock_session.execute.side_effect = [
        _make_scalar_result(280),
    ]

    result = await validator.validate_etf_db(mock_session)

    assert result.passed is True
    assert result.details["count"] == 280


@pytest.mark.asyncio
async def test_validate_etf_db_zero_rows(validator, mock_session):
    """건수 0건 → failed."""
    mock_session.execute.side_effect = [
        _make_scalar_result(0),
    ]

    result = await validator.validate_etf_db(mock_session)

    assert result.passed is False
    assert "건수 부족" in result.failure_reason
    assert result.details["count"] == 0
