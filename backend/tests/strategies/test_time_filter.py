"""시간 필터 모듈 단위 테스트 (8 케이스)."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

_KST = ZoneInfo("Asia/Seoul")


def _dt(h: int, m: int) -> datetime:
    """KST datetime 헬퍼."""
    return datetime(2026, 5, 7, h, m, 0, tzinfo=_KST)


# ---------------------------------------------------------------------------
# should_block_entry 테스트
# ---------------------------------------------------------------------------

def test_gap_open_at_0900_is_not_blocked():
    """09:00 gap_open → 아침 예외 (False, gap_open_morning_exception)."""
    from modules.trading.strategies._time_filter import should_block_entry

    blocked, reason = should_block_entry(_dt(9, 0), "gap_open")
    assert blocked is False
    assert reason == "gap_open_morning_exception"


def test_gap_open_at_0906_is_blocked():
    """09:06 gap_open → 아침 차단 (09:05~09:10은 gap_open도 차단)."""
    from modules.trading.strategies._time_filter import should_block_entry

    blocked, reason = should_block_entry(_dt(9, 6), "gap_open")
    assert blocked is True
    assert reason == "morning_lockout"


def test_prev_high_at_0906_is_blocked():
    """09:06 prev_high → 아침 차단."""
    from modules.trading.strategies._time_filter import should_block_entry

    blocked, reason = should_block_entry(_dt(9, 6), "prev_high")
    assert blocked is True
    assert reason == "morning_lockout"


def test_prev_high_at_0911_is_not_blocked():
    """09:11 prev_high → 차단 없음."""
    from modules.trading.strategies._time_filter import should_block_entry

    blocked, reason = should_block_entry(_dt(9, 11), "prev_high")
    assert blocked is False
    assert reason == ""


def test_volume_surge_at_1430_is_blocked():
    """14:30 volume_surge → 오후 차단."""
    from modules.trading.strategies._time_filter import should_block_entry

    blocked, reason = should_block_entry(_dt(14, 30), "volume_surge")
    assert blocked is True
    assert reason == "afternoon_lockout"


def test_volume_surge_at_1429_is_not_blocked():
    """14:29 volume_surge → 차단 없음."""
    from modules.trading.strategies._time_filter import should_block_entry

    blocked, reason = should_block_entry(_dt(14, 29), "volume_surge")
    assert blocked is False
    assert reason == ""


def test_time_filter_disabled_bypasses_all():
    """TIME_FILTER_ENABLED=False → 모든 시간대에서 (False, "")."""
    import modules.trading.strategies._time_filter as tf_module

    with patch.object(tf_module, "settings") as mock_s:
        mock_s.TIME_FILTER_ENABLED = False
        for h, m, tier in [(9, 0, "gap_open"), (9, 6, "prev_high"), (14, 30, "volume_surge")]:
            blocked, reason = tf_module.should_block_entry(_dt(h, m), tier)
            assert blocked is False, f"TIME_FILTER_ENABLED=False인데 {h}:{m:02d} {tier}가 차단됨"
            assert reason == ""


# ---------------------------------------------------------------------------
# lunch_floor_adjustment 테스트
# ---------------------------------------------------------------------------

def test_lunch_floor_adjustment_prev_close_at_1200():
    """점심 시간대 prev_close → 0.7 반환."""
    from modules.trading.strategies._time_filter import lunch_floor_adjustment

    result = lunch_floor_adjustment(_dt(12, 0), "prev_close")
    assert result == pytest.approx(0.7)


def test_lunch_floor_adjustment_prev_high_at_1200():
    """점심 시간대 prev_high → None (적용 안 함)."""
    from modules.trading.strategies._time_filter import lunch_floor_adjustment

    result = lunch_floor_adjustment(_dt(12, 0), "prev_high")
    assert result is None
