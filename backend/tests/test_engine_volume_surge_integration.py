"""Phase 8.6 Sprint 3 Task 3 — TradingEngine + VolumeSurgeStrategy 통합 회귀.

momentum_breakout만 / volume_surge만 / 둘 다 / dry_run / LIVE / disabled 케이스.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.trading.engine import TradingEngine
from modules.trading.strategy import TradeSignalData


def _make_redis(trading_mode: str = "auto") -> AsyncMock:
    mock_redis = AsyncMock()

    async def _get(key: str):
        if key == "scheduler:pipeline_healthy":
            return "true"
        if key == "trading:mode":
            return trading_mode
        return None

    mock_redis.get = AsyncMock(side_effect=_get)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    return mock_redis


def _make_signal(stock_code: str = "005930", tier: str = "prev_high") -> TradeSignalData:
    return TradeSignalData(
        stock_code=stock_code,
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=0.8,
        reason={"breakout_tier": tier},
        entry_price=73000,
        stop_loss=71540,
        take_profit=75190,
    )


def _make_position_size(quantity: int = 10) -> MagicMock:
    size = MagicMock()
    size.quantity = quantity
    size.invest_amount = 730000
    size.is_leverage = False
    size.size_pct = 10.0
    return size


def _make_volume_surge_result(stock_code: str = "005930", dry_run: bool = True) -> dict:
    return {
        "stock_code": stock_code,
        "tier": "volume_surge",
        "dry_run": dry_run,
        "vol_ratio": 6.0,
        "bid_ask_ratio": 2.5,
        "price_change": 0.012,
        "matched_tiers": ["volume_surge"],
        "confidence": 0.7,
    }


def _make_engine(
    *,
    volume_surge_strategy=None,
    notifier=None,
    trading_mode: str = "auto",
) -> TradingEngine:
    engine = TradingEngine(
        signal_generator=AsyncMock(),
        order_manager=AsyncMock(),
        position_manager=AsyncMock(),
        risk_manager=AsyncMock(),
        position_sizer=AsyncMock(),
        eod_liquidator=MagicMock(),
        redis_client=_make_redis(trading_mode),
        notifier_manager=notifier,
        session_factory=None,
        volume_surge_strategy=volume_surge_strategy,
    )
    engine._eod_liquidator.is_entry_blocked.return_value = False
    engine._risk_manager.can_trade = AsyncMock(return_value=MagicMock(allowed=True))
    engine._risk_manager.check_daily_trade_limit = AsyncMock(return_value=True)
    engine._position_sizer.calculate = AsyncMock(return_value=_make_position_size())
    return engine


@pytest.mark.asyncio
async def test_only_momentum_breakout_emits_single_signal():
    """momentum_breakout만 매칭 → 기존 흐름대로 단일 신호 + 주문."""
    engine = _make_engine(volume_surge_strategy=None)
    sig = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[sig])

    await engine.process_screening_results([{"stock_code": "005930", "current_price": 73000}])

    engine._order_manager.submit_order.assert_called_once()


@pytest.mark.asyncio
async def test_only_volume_surge_emits_dry_run_signal_and_blocks_order():
    """volume_surge만 매칭(dry_run=True) → DB 기록 + 알림, 주문은 차단."""
    vs_strategy = MagicMock()
    vs_strategy.evaluate = AsyncMock(return_value=_make_volume_surge_result(dry_run=True))

    notifier = AsyncMock()
    notifier.send_notification = AsyncMock()

    engine = _make_engine(volume_surge_strategy=vs_strategy, notifier=notifier)
    # momentum_breakout 미매칭
    engine._signal_generator.generate_signals = AsyncMock(return_value=[])
    engine._record_volume_surge_signal = AsyncMock()

    await engine.process_screening_results(
        [{"stock_code": "005930", "current_price": 73000}]
    )

    # OrderExecutor.place_order(submit_order) 호출 0회
    engine._order_manager.submit_order.assert_not_called()
    # dry_run 신호 DB 기록 시도
    engine._record_volume_surge_signal.assert_awaited_once()
    # 텔레그램 dry_run 알림
    notifier.send_notification.assert_awaited()
    text_arg = notifier.send_notification.call_args[0][0]
    assert "[DRY-RUN]" in text_arg


@pytest.mark.asyncio
async def test_both_matched_volume_surge_wins_with_merged_tiers():
    """momentum_breakout + volume_surge 동시 매칭 → volume_surge 우선, matched_tiers 병합."""
    vs_strategy = MagicMock()
    vs_strategy.evaluate = AsyncMock(return_value=_make_volume_surge_result(dry_run=True))

    notifier = AsyncMock()
    notifier.send_notification = AsyncMock()

    engine = _make_engine(volume_surge_strategy=vs_strategy, notifier=notifier)
    sig = _make_signal(tier="prev_high")
    engine._signal_generator.generate_signals = AsyncMock(return_value=[sig])

    captured: dict = {}

    async def _record(payload):
        captured.update(payload)

    engine._record_volume_surge_signal = AsyncMock(side_effect=_record)

    await engine.process_screening_results(
        [{"stock_code": "005930", "current_price": 73000}]
    )

    engine._order_manager.submit_order.assert_not_called()
    engine._record_volume_surge_signal.assert_awaited_once()
    assert "volume_surge" in captured["matched_tiers"]
    assert "prev_high" in captured["matched_tiers"]


@pytest.mark.asyncio
async def test_volume_surge_dry_run_true_skips_order_executor():
    """VOLUME_SURGE_DRY_RUN=True → place_order 호출 0회 보장."""
    vs_strategy = MagicMock()
    vs_strategy.evaluate = AsyncMock(return_value=_make_volume_surge_result(dry_run=True))

    engine = _make_engine(volume_surge_strategy=vs_strategy)
    engine._signal_generator.generate_signals = AsyncMock(return_value=[])
    engine._record_volume_surge_signal = AsyncMock()

    await engine.process_screening_results(
        [{"stock_code": "005930", "current_price": 73000}]
    )

    engine._order_manager.submit_order.assert_not_called()


@pytest.mark.asyncio
async def test_volume_surge_dry_run_false_executes_order():
    """VOLUME_SURGE_DRY_RUN=False (Sprint 4 LIVE 토글) → 주문 실제 진입."""
    vs_strategy = MagicMock()
    vs_strategy.evaluate = AsyncMock(return_value=_make_volume_surge_result(dry_run=False))

    engine = _make_engine(volume_surge_strategy=vs_strategy)
    engine._signal_generator.generate_signals = AsyncMock(return_value=[])

    await engine.process_screening_results(
        [{"stock_code": "005930", "current_price": 73000}]
    )

    # LIVE 신호이므로 submit_order 호출
    engine._order_manager.submit_order.assert_called_once()


@pytest.mark.asyncio
async def test_volume_surge_strategy_none_runs_only_momentum():
    """volume_surge_strategy=None → 기존 momentum_breakout만 평가 (회귀)."""
    engine = _make_engine(volume_surge_strategy=None)
    sig = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[sig])

    await engine.process_screening_results(
        [{"stock_code": "005930", "current_price": 73000}]
    )

    engine._order_manager.submit_order.assert_called_once()
