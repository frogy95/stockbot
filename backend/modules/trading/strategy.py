"""매매 전략 추상 인터페이스 및 공통 데이터 스키마."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class TradeSignalData(BaseModel):
    """전략이 생성하는 매매 신호 데이터."""

    stock_code: str
    signal_type: str  # "buy" / "sell"
    strategy_name: str
    confidence: float  # 0~1
    reason: dict  # 신호 근거 상세
    entry_price: int
    stop_loss: int
    take_profit: int


class MarketSnapshot(BaseModel):
    """전략에 전달할 시장 데이터 스냅샷."""

    stock_code: str
    stock_name: str
    stock_type: str  # "STOCK" / "ETF"
    current_price: int
    open_price: int
    high: int
    low: int
    prev_close: int
    prev_high: int  # 전일 고가
    volume: int  # 당일 누적
    prev_volume: int  # 전일 거래량
    change_rate: float
    trade_strength: float  # 체결강도
    total_bid_volume: int
    total_ask_volume: int
    recent_highs: list[int]  # 최근 5일 고가, ATR 계산용
    recent_lows: list[int]  # 최근 5일 저가
    recent_closes: list[int]  # 최근 5일 종가


class Strategy(ABC):
    """매매 전략 추상 베이스 클래스."""

    @property
    @abstractmethod
    def name(self) -> str:
        """전략 이름."""

    @abstractmethod
    async def generate_signal(
        self, snapshot: MarketSnapshot
    ) -> TradeSignalData | None:
        """시장 데이터로부터 매매 신호 생성. 조건 미달 시 None 반환."""
