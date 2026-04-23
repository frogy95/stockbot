"""Phase 8.5 Sprint 2 — Task 4: engine.py is_fallback 분기 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.trading.engine import TradingEngine
from modules.trading.strategy import TradeSignalData


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_redis(trading_mode: str = "auto") -> AsyncMock:
    mock_redis = AsyncMock()

    async def _get(key: str) -> str | None:
        if key == "scheduler:pipeline_healthy":
            return "true"
        if key == "trading:mode":
            return trading_mode
        return None

    mock_redis.get = AsyncMock(side_effect=_get)
    mock_redis.set = AsyncMock()
    return mock_redis


def _make_engine(trading_mode: str = "auto", notifier_manager=None) -> TradingEngine:
    engine = TradingEngine(
        signal_generator=AsyncMock(),
        order_manager=AsyncMock(),
        position_manager=AsyncMock(),
        risk_manager=AsyncMock(),
        position_sizer=AsyncMock(),
        eod_liquidator=MagicMock(),
        redis_client=_make_redis(trading_mode),
        notifier_manager=notifier_manager or AsyncMock(),
        session_factory=None,
    )
    engine._order_manager.get_queue_size.return_value = 0
    return engine


def _make_signal(entry_price: int = 73000, tier: str = "prev_high") -> TradeSignalData:
    return TradeSignalData(
        stock_code="005930",
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=0.85,
        reason={"breakout_tier": tier},
        entry_price=entry_price,
        stop_loss=int(entry_price * 0.98),
        take_profit=int(entry_price * 1.03),
    )


def _make_position_size(quantity: int = 10) -> MagicMock:
    size = MagicMock()
    size.quantity = quantity
    size.invest_amount = 730000
    size.is_leverage = False
    size.size_pct = 10.0
    return size


def _setup(engine: TradingEngine, signal: TradeSignalData, quantity: int = 10) -> None:
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(return_value=MagicMock(allowed=True))
    engine._position_sizer.calculate = AsyncMock(return_value=_make_position_size(quantity))
    engine._eod_liquidator.is_entry_blocked.return_value = False


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fallback_applies_half_position():
    """is_fallback=True → position_sizer.calculate에 size_ratio ≤ 0.5 전달."""
    engine = _make_engine()
    signal = _make_signal(tier="prev_high")
    _setup(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930", "is_fallback": True}])

    engine._position_sizer.calculate.assert_called_once()
    _, kwargs = engine._position_sizer.calculate.call_args
    assert kwargs["size_ratio"] <= 0.5


@pytest.mark.asyncio
async def test_fallback_applies_tight_stop_loss():
    """is_fallback=True → notify_signal에 전달된 signal의 stop_loss가 -1.5% 기준."""
    notifier = AsyncMock()
    notifier.notify_signal = AsyncMock(return_value="token-fb")
    engine = _make_engine(trading_mode="semi-auto", notifier_manager=notifier)
    signal = _make_signal(entry_price=73000)
    _setup(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930", "is_fallback": True}])

    notifier.notify_signal.assert_called_once()
    sent_signal: TradeSignalData = notifier.notify_signal.call_args[0][0]
    # entry_price=73000, FALLBACK_STOP_LOSS_PCT=-1.5 → stop_loss = int(73000 * 0.985) = 71905
    expected_stop = int(73000 * 0.985)
    assert sent_signal.stop_loss == expected_stop


@pytest.mark.asyncio
async def test_non_fallback_unchanged():
    """is_fallback=False → 기존 size_ratio(1.0) 그대로, 손절 변경 없음."""
    notifier = AsyncMock()
    notifier.notify_signal = AsyncMock(return_value="token-ok")
    engine = _make_engine(trading_mode="semi-auto", notifier_manager=notifier)
    signal = _make_signal(entry_price=73000, tier="prev_high")
    _setup(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930", "is_fallback": False}])

    _, kwargs = engine._position_sizer.calculate.call_args
    assert kwargs["size_ratio"] == 1.0

    sent_signal: TradeSignalData = notifier.notify_signal.call_args[0][0]
    assert sent_signal.stop_loss == int(73000 * 0.98)


@pytest.mark.asyncio
async def test_fallback_and_relaxed_combined():
    """is_fallback=True + is_relaxed=True → min(FALLBACK_POSITION_SIZE_RATIO, tier_ratio) 적용.

    두 플래그 모두 True면 더 보수적인 배수(min) 선택.
    prev_high tier(tier_ratio=1.0) + fallback(0.5) → min(1.0, 0.5) = 0.5.
    """
    engine = _make_engine()
    signal = _make_signal(tier="prev_high")
    _setup(engine, signal)

    candidate = {"stock_code": "005930", "is_fallback": True, "is_relaxed": True}
    await engine.process_screening_results([candidate])

    _, kwargs = engine._position_sizer.calculate.call_args
    # prev_close가 아닌 tier → tier_ratio=1.0, fallback=0.5 → min=0.5
    assert kwargs["size_ratio"] == 0.5
