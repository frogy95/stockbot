"""historical_loader 테스트 — 60일 KOSPI 일봉 로드 + 박스권/추세장 분류 + 데이터셋 충분성."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.backtest.historical_loader import (
    DatasetInsufficientError,
    classify_regime,
    is_dataset_sufficient,
    load_kospi_daily,
)


def _make_mock_session(rows: list[tuple]) -> AsyncMock:
    """SQLAlchemy 결과 mock — rows: list[(data_date, avg_close, stddev)]."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)
    return mock_session


@pytest.mark.asyncio
async def test_load_kospi_daily_returns_ascending_series():
    """7일치 mock data → 7 row, 날짜 오름차순."""
    base = date(2026, 5, 1)
    rows = [(base + timedelta(days=i), 2500.0 + i * 10, 50.0) for i in range(7)]
    session = _make_mock_session(rows)

    series = await load_kospi_daily(session, period_end=base + timedelta(days=6), n_days=7)

    assert len(series) == 7
    assert series[0]["date"] == base
    assert series[-1]["date"] == base + timedelta(days=6)
    # 오름차순
    dates = [r["date"] for r in series]
    assert dates == sorted(dates)
    # pct_change 첫 day는 0.0
    assert series[0]["pct_change"] == 0.0


@pytest.mark.asyncio
async def test_load_kospi_daily_raises_when_insufficient():
    """n_days=60 요청, DB 30일만 → DatasetInsufficientError."""
    base = date(2026, 5, 1)
    rows = [(base + timedelta(days=i), 2500.0, 50.0) for i in range(30)]
    session = _make_mock_session(rows)

    with pytest.raises(DatasetInsufficientError):
        await load_kospi_daily(session, period_end=base + timedelta(days=60), n_days=60)


def test_classify_regime_box_dominant():
    """저변동성 위주 시계열 → 박스권 일수 > 추세장 일수."""
    # 70일 시계열, 마지막 5일만 큰 변동, 나머지는 ±0.1%
    series = []
    base = date(2026, 3, 1)
    for i in range(70):
        if i >= 65:
            pct = 3.0 if i % 2 == 0 else -3.0
        else:
            pct = 0.1 if i % 2 == 0 else -0.1
        series.append({
            "date": base + timedelta(days=i),
            "avg_close": 2500.0,
            "pct_change": pct,
            "stddev": 50.0,
        })
    summary = classify_regime(series)
    assert summary["box_days"] > summary["trend_days"]
    assert len(summary["labels"]) == 70


def test_classify_regime_detects_trend_shift():
    """regime shift 검출: 박스권 베이스 + 후반 변동 급등 → trend 일수 발생.

    분류기 의미론(소수 모드 검출): σ_long_term × 1.5 임계는 다수 모드를
    따라가므로 `trend > box`는 수학적으로 도달 불가. 본 테스트는
    regime 전환 시점을 trend로 검출하는지(>0) 및 baseline은 box 다수임을 검증.
    """
    series = []
    base = date(2026, 3, 1)
    n = 90
    for i in range(n):
        # 앞 60일 박스권(±0.05%) → σ_long_term 낮춤, 뒤 30일 강변동(±5%) → trend 검출
        if i < 60:
            pct = 0.05 if i % 2 == 0 else -0.05
        else:
            pct = 5.0 if i % 2 == 0 else -5.0
        series.append({
            "date": base + timedelta(days=i),
            "avg_close": 2500.0,
            "pct_change": pct,
            "stddev": 50.0,
        })
    summary = classify_regime(series)
    assert summary["trend_days"] > 0
    assert summary["box_days"] > 0
    assert len(summary["labels"]) == n


def test_is_dataset_sufficient_all_pass():
    summary = {"box_days": 25, "trend_days": 25, "labels": ["box"] * 60}
    assert is_dataset_sufficient(summary) is True


def test_is_dataset_sufficient_box_short():
    summary = {"box_days": 15, "trend_days": 25, "labels": ["box"] * 60}
    assert is_dataset_sufficient(summary) is False


def test_is_dataset_sufficient_trend_short():
    summary = {"box_days": 30, "trend_days": 18, "labels": ["box"] * 60}
    assert is_dataset_sufficient(summary) is False


def test_is_dataset_sufficient_total_short():
    summary = {"box_days": 25, "trend_days": 25, "labels": ["box"] * 50}
    assert is_dataset_sufficient(summary) is False
