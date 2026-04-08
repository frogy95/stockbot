"""1차/2차 스크리닝 필터 조건 정의."""
from dataclasses import dataclass


@dataclass
class PrimaryFilters:
    """장전 1차 스크리닝 필터 (DB 정적 데이터 기반)."""

    volume_ratio: float = 1.5
    volume_min_stock: int = 50_000
    volume_min_etf: int = 10_000
    market_cap_min: int = 50_000_000_000
    change_rate_min: float = -2.0
    change_rate_max: float = 7.0
    max_candidates: int = 30


@dataclass
class SecondaryFilters:
    """장중 2차 스크리닝 필터 (실시간 데이터 기반)."""

    trade_strength_min: float = 70
    orderbook_ratio_min: float = 1.2
    screening_interval: int = 30
    no_signal_before: str = "09:30"


def passes_primary_filter(stock_data: dict, filters: PrimaryFilters) -> bool:
    """종목 데이터가 1차 필터를 통과하는지 판단."""
    prev_volume = stock_data["prev_volume"]
    if prev_volume == 0:
        return False

    volume = stock_data["volume"]
    volume_ratio = volume / prev_volume
    if volume_ratio < filters.volume_ratio:
        return False

    volume_min = (
        filters.volume_min_etf
        if stock_data["stock_type"] == "ETF"
        else filters.volume_min_stock
    )
    if volume < volume_min:
        return False

    if stock_data["market_cap"] < filters.market_cap_min:
        return False

    change_rate = stock_data["change_rate"]
    if change_rate < filters.change_rate_min or change_rate > filters.change_rate_max:
        return False

    return True


def is_hot_stock(volume_ratio: float) -> bool:
    """거래량 비율 500%+ 시 핫 종목 판정."""
    return volume_ratio >= 5.0
