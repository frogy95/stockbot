"""시간대 본 가드 + 점심 거래량 하한 조정 (Phase 8.6 Sprint 3)."""

from datetime import datetime, time

from core.config import settings

# 시간 경계 상수 (KST)
_MORNING_GAP_EXCEPTION_END = time(9, 5)   # gap_open 예외 허용 구간 종료 (09:05 이후 차단)
_MORNING_LOCKOUT_END = time(9, 10)         # 아침 차단 구간 종료
_AFTERNOON_LOCKOUT_START = time(14, 30)    # 오후 차단 구간 시작
_LUNCH_START = time(11, 30)                # 점심 거래량 조정 시작
_LUNCH_END = time(13, 0)                   # 점심 거래량 조정 종료
_MARKET_OPEN = time(9, 0)


def should_block_entry(now_kst: datetime, tier: str) -> tuple[bool, str]:
    """현재 시각과 tier에 따라 진입 차단 여부를 반환한다.

    Args:
        now_kst: KST 기준 현재 시각.
        tier: 진입 tier 문자열 ("gap_open", "prev_high", "prev_close", "volume_surge" 등).

    Returns:
        (blocked: bool, reason: str) 튜플.
        blocked=True면 진입 차단, reason은 차단 사유 코드.

    규칙:
        - TIME_FILTER_ENABLED=False → 항상 (False, "")
        - 09:00 <= t < 09:05 & tier == "gap_open" → (False, "gap_open_morning_exception")
        - 09:00 <= t < 09:10 → (True, "morning_lockout")
        - t >= 14:30 → (True, "afternoon_lockout")
        - 그 외 → (False, "")
    """
    if not settings.TIME_FILTER_ENABLED:
        return (False, "")

    t = now_kst.time()

    if _MARKET_OPEN <= t < _MORNING_GAP_EXCEPTION_END and tier == "gap_open":
        return (False, "gap_open_morning_exception")

    if _MARKET_OPEN <= t < _MORNING_LOCKOUT_END:
        return (True, "morning_lockout")

    if t >= _AFTERNOON_LOCKOUT_START:
        return (True, "afternoon_lockout")

    return (False, "")


def lunch_floor_adjustment(now_kst: datetime, tier: str) -> float | None:
    """점심 시간대(11:30~12:59) prev_close tier에 거래량 하한 조정값을 반환한다.

    Args:
        now_kst: KST 기준 현재 시각.
        tier: 진입 tier 문자열.

    Returns:
        float — 적용할 거래량 하한 조정값 (0.7).
        None  — 해당 없음 (점심 외 시간 또는 prev_close 외 tier).
    """
    t = now_kst.time()
    if _LUNCH_START <= t < _LUNCH_END and tier == "prev_close":
        return 0.7
    return None
