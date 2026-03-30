"""Strategy ABC 인터페이스 테스트."""

import pytest
import pytest_asyncio

from modules.trading.strategy import MarketSnapshot, Strategy, TradeSignalData


# === 헬퍼: 올바른 Strategy 구현 ===


class DummyStrategy(Strategy):
    """테스트용 전략 구현체."""

    @property
    def name(self) -> str:
        return "dummy"

    async def generate_signal(
        self, snapshot: MarketSnapshot
    ) -> TradeSignalData | None:
        return TradeSignalData(
            stock_code=snapshot.stock_code,
            signal_type="buy",
            strategy_name=self.name,
            confidence=0.8,
            reason={"test": True},
            entry_price=snapshot.current_price,
            stop_loss=int(snapshot.current_price * 0.98),
            take_profit=int(snapshot.current_price * 1.03),
        )


class IncompleteStrategy(Strategy):
    """generate_signal을 구현하지 않은 클래스."""

    @property
    def name(self) -> str:
        return "incomplete"


# === 픽스처 ===


@pytest.fixture
def sample_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        stock_code="005930",
        stock_name="삼성전자",
        stock_type="STOCK",
        current_price=70000,
        open_price=69000,
        high=71000,
        low=68500,
        prev_close=69500,
        prev_high=70500,
        volume=15000000,
        prev_volume=10000000,
        change_rate=0.72,
        trade_strength=85.0,
        total_bid_volume=500000,
        total_ask_volume=400000,
        recent_highs=[70500, 70000, 69800, 69500, 69000],
        recent_lows=[68000, 67500, 67800, 67200, 67000],
        recent_closes=[69500, 69000, 68800, 68500, 68000],
    )


# === 테스트 ===


def test_abc_cannot_instantiate_without_generate_signal():
    """Strategy ABC를 generate_signal 미구현으로 인스턴스화하면 TypeError."""
    with pytest.raises(TypeError):
        IncompleteStrategy()


def test_abc_can_instantiate_with_proper_implementation():
    """올바른 구현체는 인스턴스화 성공."""
    strategy = DummyStrategy()
    assert strategy.name == "dummy"


@pytest.mark.asyncio
async def test_generate_signal_returns_trade_signal_data(sample_snapshot):
    """generate_signal()의 반환 타입이 TradeSignalData | None."""
    strategy = DummyStrategy()
    result = await strategy.generate_signal(sample_snapshot)
    assert isinstance(result, TradeSignalData)
    assert result.stock_code == "005930"
    assert result.signal_type == "buy"
    assert 0 <= result.confidence <= 1
