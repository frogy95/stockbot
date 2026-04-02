"""한국거래소 2026년 휴장일 캘린더 유틸.

공휴일/주말 기반으로 거래일 여부를 판별하고,
가장 최근 거래일 · N번째 이전 거래일을 계산한다.
"""

from datetime import date, timedelta

# 2026년 한국 공휴일 (대체공휴일 포함)
# NOTE: 2026년 확정 대체공휴일 확인 필요
KR_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 1),   # 신정
    date(2026, 1, 28),  # 설날 연휴
    date(2026, 1, 29),  # 설날
    date(2026, 1, 30),  # 설날 연휴
    date(2026, 3, 1),   # 삼일절
    date(2026, 3, 2),   # 삼일절 대체공휴일
    date(2026, 5, 5),   # 어린이날
    date(2026, 5, 24),  # 석가탄신일
    date(2026, 6, 6),   # 현충일
    date(2026, 8, 15),  # 광복절
    date(2026, 9, 14),  # 추석 연휴
    date(2026, 9, 15),  # 추석
    date(2026, 9, 16),  # 추석 연휴
    date(2026, 10, 3),  # 개천절
    date(2026, 10, 5),  # 추석 대체공휴일
    date(2026, 10, 9),  # 한글날
    date(2026, 12, 25), # 성탄절
}


def is_trading_day(d: date) -> bool:
    """주말(토/일) 또는 공휴일이면 False."""
    if d.weekday() >= 5:  # 토(5), 일(6)
        return False
    return d not in KR_HOLIDAYS_2026


def get_latest_trading_day(d: date) -> date:
    """d 이전의 가장 최근 거래일 반환. d가 거래일이면 d 반환."""
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def get_prev_trading_day(d: date, n: int = 1) -> date:
    """d 기준 n번째 이전 거래일 반환."""
    current = d
    count = 0
    while count < n:
        current -= timedelta(days=1)
        if is_trading_day(current):
            count += 1
    return current
