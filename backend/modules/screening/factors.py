"""주식 팩터 계산기 (5팩터: 거래량/변동성/모멘텀/체결강도/호가잔량)."""


def calc_volume_factor(volume: int, prev_volume: int) -> float:
    """전일 대비 거래량 비율."""
    if prev_volume == 0:
        return 0.0
    return volume / prev_volume


def calc_volatility_factor(
    highs: list[int], lows: list[int], closes: list[int]
) -> float:
    """ATR 5일 계산. 데이터 2일 미만이면 0.0."""
    n = len(highs)
    if n < 2:
        return 0.0

    true_ranges: list[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        prev_close = closes[i - 1]
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - prev_close),
            abs(lows[i] - prev_close),
        )
        true_ranges.append(tr)

    return sum(true_ranges) / len(true_ranges)


def calc_momentum_factor(closes: list[int]) -> float:
    """3일 단기 수익률(%). closes 최소 4개 필요, 부족 시 0.0."""
    if len(closes) < 4:
        return 0.0
    base = closes[-4]
    if base == 0:
        return 0.0
    return (closes[-1] - base) / base * 100


def calc_trade_strength_factor(trade_strength: float) -> float:
    """체결강도 그대로 반환."""
    return trade_strength


def calc_orderbook_ratio_factor(total_bid_volume: int, total_ask_volume: int) -> float:
    """매수/매도 호가잔량 비율."""
    if total_ask_volume == 0:
        return 0.0
    return total_bid_volume / total_ask_volume
