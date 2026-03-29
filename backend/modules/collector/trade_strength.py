"""체결강도 계산 모듈 — 5분 윈도우 기반 매수/매도 체결 누적 비율."""

import time
from collections import deque


class TradeStrengthCalculator:
    """체결강도 계산기.

    체결강도 = (매수 체결량 / (매수 체결량 + 매도 체결량)) * 100
    5분(300초) 윈도우 내 데이터만 사용하며, 누적 시간이 5분 미만이면 중립값(50.0)을 반환한다.
    """

    def __init__(self, window_seconds: int = 300) -> None:
        self._window = window_seconds
        # {stock_code: deque[(timestamp, volume, sell_or_buy)]}
        self._data: dict[str, deque[tuple[float, int, str]]] = {}
        # {stock_code: first_timestamp} — 누적 시작 시점
        self._first_ts: dict[str, float] = {}

    def add_execution(
        self, stock_code: str, timestamp: float, volume: int, sell_or_buy: str
    ) -> None:
        """체결 데이터 추가. sell_or_buy: '1'=매도, '2'=매수."""
        if stock_code not in self._data:
            self._data[stock_code] = deque()
            self._first_ts[stock_code] = timestamp

        self._data[stock_code].append((timestamp, volume, sell_or_buy))

    def get_strength(self, stock_code: str, now: float | None = None) -> float:
        """체결강도 계산. 누적 5분 미만이면 중립값 50.0 반환."""
        if stock_code not in self._data:
            return 50.0

        if now is None:
            now = time.time()

        self._cleanup(stock_code, now)

        # 누적 시간 확인
        first_ts = self._first_ts.get(stock_code)
        if first_ts is None or (now - first_ts) < self._window:
            return 50.0

        buy_volume = 0
        sell_volume = 0

        for _, vol, sob in self._data[stock_code]:
            if sob == "2":
                buy_volume += vol
            else:
                sell_volume += vol

        total = buy_volume + sell_volume
        if total == 0:
            return 50.0

        return (buy_volume / total) * 100

    def reset(self, stock_code: str) -> None:
        """종목 데이터 초기화."""
        self._data.pop(stock_code, None)
        self._first_ts.pop(stock_code, None)

    def _cleanup(self, stock_code: str, now: float) -> None:
        """윈도우 밖 만료 데이터 정리."""
        if stock_code not in self._data:
            return

        dq = self._data[stock_code]
        cutoff = now - self._window

        while dq and dq[0][0] < cutoff:
            dq.popleft()

        if not dq:
            self._data.pop(stock_code, None)
            self._first_ts.pop(stock_code, None)
        else:
            # 남은 데이터 중 가장 오래된 것으로 first_ts 갱신
            self._first_ts[stock_code] = dq[0][0]
