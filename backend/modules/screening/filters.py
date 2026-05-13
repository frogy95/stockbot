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
    # 2026-05-13 hotfix(real-momentum): 7.0 → 30.0
    # 상한가/급등주(예: 한솔케미칼 +12%)가 1차 풀 진입 가능하도록 상한 해제.
    # 단타 모멘텀 전략 정체성 부합 (상한가 30%까지 후보화).
    change_rate_max: float = 30.0
    max_candidates: int = 20


@dataclass
class SecondaryFilters:
    """장중 2차 스크리닝 필터 (실시간 데이터 기반)."""

    # KIS CTTR(체결강도) 기준: 100=균형, >100=매수 우세, 120=중간 매수세
    # 2026-05-13 hotfix(real-momentum): 100.0 → 80.0
    # 상한가 모멘텀은 매도 호가가 비어서 CTTR이 100 아래로 떨어지는 경우가 많음.
    # 실측 사례: 014680 한솔케미칼 +12% 종목의 CTTR=50. 임계 80은 약한 매도 우세까지 허용.
    trade_strength_min: float = 80.0
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
