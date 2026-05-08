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


# ---------------------------------------------------------------------------
# record_block 테스트 (Phase 8.6 Sprint 3 hotfix — time_filter incr)
# ---------------------------------------------------------------------------

class _FakeRedis:
    """incr/expire 호출을 기록하는 mock."""
    def __init__(self) -> None:
        self.incr_calls: list[str] = []
        self.expire_calls: list[tuple[str, int]] = []
        self.fail = False

    async def incr(self, key: str) -> int:
        if self.fail:
            raise RuntimeError("redis down")
        self.incr_calls.append(key)
        return 1

    async def expire(self, key: str, ttl: int) -> bool:
        self.expire_calls.append((key, ttl))
        return True


@pytest.mark.asyncio
async def test_record_block_increments_counter_with_ttl():
    """차단 사유 + 날짜로 키 생성 후 INCR + EXPIRE(7d) 호출."""
    from modules.trading.strategies._time_filter import record_block

    redis = _FakeRedis()
    await record_block(redis, "morning_lockout", _dt(9, 5))

    assert redis.incr_calls == ["metrics:time_filter:morning_lockout:2026-05-07"]
    assert redis.expire_calls == [("metrics:time_filter:morning_lockout:2026-05-07", 7 * 24 * 3600)]


@pytest.mark.asyncio
async def test_record_block_skips_when_redis_none():
    """redis_client=None이면 graceful skip."""
    from modules.trading.strategies._time_filter import record_block

    await record_block(None, "morning_lockout", _dt(9, 5))  # 예외 미전파


@pytest.mark.asyncio
async def test_record_block_skips_empty_reason():
    """빈 reason이면 스킵 (정상 통과 경로 보호)."""
    from modules.trading.strategies._time_filter import record_block

    redis = _FakeRedis()
    await record_block(redis, "", _dt(9, 5))
    assert redis.incr_calls == []


@pytest.mark.asyncio
async def test_record_block_swallows_redis_errors():
    """Redis incr 예외는 graceful (호출자에게 전파 금지)."""
    from modules.trading.strategies._time_filter import record_block

    redis = _FakeRedis()
    redis.fail = True
    await record_block(redis, "afternoon_lockout", _dt(14, 30))  # 예외 미전파
