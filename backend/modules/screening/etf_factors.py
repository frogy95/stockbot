"""ETF 전용 팩터 계산기."""


def calc_tracking_error_factor(close_price: int, nav: float) -> float:
    """괴리율(%) = abs((종가 - NAV) / NAV * 100). NAV=0이면 0.0."""
    if nav == 0.0:
        return 0.0
    return abs((close_price - nav) / nav * 100)
