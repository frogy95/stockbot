"""calc_market_progress 유틸 단위 테스트."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from modules.trading.strategies.momentum_breakout import (
    MARKET_CLOSE,
    MARKET_MINUTES,
    MARKET_OPEN,
    MIN_MARKET_PROGRESS,
    calc_market_progress,
)


KST = ZoneInfo("Asia/Seoul")


def _kst(hour: int, minute: int) -> datetime:
    """2026-04-13 기준 KST 시각 생성."""
    return datetime(2026, 4, 13, hour, minute, tzinfo=KST)


def test_constants_sanity():
    """상수 기본 검증."""
    assert MARKET_OPEN.hour == 9 and MARKET_OPEN.minute == 0
    assert MARKET_CLOSE.hour == 15 and MARKET_CLOSE.minute == 30
    assert MARKET_MINUTES == 390
    assert MIN_MARKET_PROGRESS == 0.15


def test_progress_market_open():
    """09:00 시점 -> elapsed=0 -> 하한 0.15 적용."""
    result = calc_market_progress(_kst(9, 0))
    assert result == pytest.approx(MIN_MARKET_PROGRESS)


def test_progress_midday():
    """12:15 시점 -> 195/390 = 0.5."""
    result = calc_market_progress(_kst(12, 15))
    assert result == pytest.approx(0.5, abs=1e-4)


def test_progress_market_close():
    """15:30 시점 -> 1.0."""
    result = calc_market_progress(_kst(15, 30))
    assert result == pytest.approx(1.0)


def test_progress_before_market():
    """08:00 시점 -> MIN_MARKET_PROGRESS (0.15)."""
    result = calc_market_progress(_kst(8, 0))
    assert result == pytest.approx(MIN_MARKET_PROGRESS)


def test_progress_after_market():
    """16:00 시점 -> 1.0."""
    result = calc_market_progress(_kst(16, 0))
    assert result == pytest.approx(1.0)


def test_progress_min_floor():
    """09:30 시점 -> 30/390 = 0.077 -> 하한 0.15 적용."""
    result = calc_market_progress(_kst(9, 30))
    assert result == pytest.approx(MIN_MARKET_PROGRESS)


def test_progress_at_0958():
    """09:58 시점 -> 58/390 = 0.1487 -> 하한 0.15 적용 (경계)."""
    result = calc_market_progress(_kst(9, 58))
    assert result == pytest.approx(MIN_MARKET_PROGRESS)


def test_progress_at_1000():
    """10:00 시점 -> 60/390 = 0.1538 > 0.15 -> 그대로."""
    result = calc_market_progress(_kst(10, 0))
    assert result == pytest.approx(60 / 390, abs=1e-4)
    assert result > MIN_MARKET_PROGRESS
