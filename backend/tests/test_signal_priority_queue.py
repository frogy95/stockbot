"""Phase 8.6 Sprint 3 Task 3 — 신호 우선순위 큐 + 일일 한도 dry_run 제외."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_signal(tier: str, stock_code: str = "005930") -> TradeSignalData:
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
async def test_priority_queue_picks_volume_surge_when_4_tiers_match():
    """동일 틱 4 tier 매칭 → volume_surge 1건만 발행."""
    vs_strategy = MagicMock()
    vs_strategy.evaluate = AsyncMock(return_value=_make_volume_surge_result(dry_run=True))

    notifier = AsyncMock()
    notifier.send_notification = AsyncMock()

    engine = _make_engine(volume_surge_strategy=vs_strategy, notifier=notifier)
    # momentum_breakout 신호도 매칭
    sig = _make_signal(tier="prev_high")
    engine._signal_generator.generate_signals = AsyncMock(return_value=[sig])
    engine._record_volume_surge_signal = AsyncMock()

    await engine.process_screening_results(
        [{"stock_code": "005930", "current_price": 73000}]
    )

    # volume_surge가 우선 → place_order 0회, dry_run record 1회
    engine._order_manager.submit_order.assert_not_called()
    engine._record_volume_surge_signal.assert_awaited_once()


@pytest.mark.asyncio
async def test_priority_queue_falls_back_to_momentum_when_volume_surge_missing():
    """volume_surge 미매칭 → momentum_breakout 신호 발행."""
    vs_strategy = MagicMock()
    vs_strategy.evaluate = AsyncMock(return_value=None)  # 미매칭

    engine = _make_engine(volume_surge_strategy=vs_strategy)
    sig = _make_signal(tier="prev_high")
    engine._signal_generator.generate_signals = AsyncMock(return_value=[sig])

    await engine.process_screening_results(
        [{"stock_code": "005930", "current_price": 73000}]
    )

    engine._order_manager.submit_order.assert_called_once()


@pytest.mark.asyncio
async def test_priority_queue_disabled_emits_all_matches():
    """SIGNAL_PRIORITY_QUEUE_ENABLED=False → 모든 매칭 tier 신호 병렬 발행."""
    vs_strategy = MagicMock()
    vs_strategy.evaluate = AsyncMock(return_value=_make_volume_surge_result(dry_run=True))

    notifier = AsyncMock()
    notifier.send_notification = AsyncMock()

    engine = _make_engine(volume_surge_strategy=vs_strategy, notifier=notifier)
    sig = _make_signal(tier="prev_high")
    engine._signal_generator.generate_signals = AsyncMock(return_value=[sig])
    engine._record_volume_surge_signal = AsyncMock()

    with patch("modules.trading.engine.settings") as mock_settings:
        mock_settings.SIGNAL_PRIORITY_QUEUE_ENABLED = False
        mock_settings.FALLBACK_POSITION_SIZE_RATIO = 0.5
        mock_settings.FALLBACK_STOP_LOSS_PCT = -3.0

        await engine.process_screening_results(
            [{"stock_code": "005930", "current_price": 73000}]
        )

    # 큐 비활성: momentum (LIVE) submit_order + volume_surge dry_run record 모두 발생
    engine._order_manager.submit_order.assert_called_once()
    engine._record_volume_surge_signal.assert_awaited_once()


@pytest.mark.asyncio
async def test_daily_limit_excludes_dry_run_signals():
    """일일 한도 도달 시 LIVE 신호만 차단. dry_run 신호는 발행 계속."""
    vs_strategy = MagicMock()
    vs_strategy.evaluate = AsyncMock(return_value=_make_volume_surge_result(dry_run=True))

    notifier = AsyncMock()
    notifier.send_notification = AsyncMock()

    engine = _make_engine(volume_surge_strategy=vs_strategy, notifier=notifier)
    # 일일 한도 도달
    engine._risk_manager.can_trade = AsyncMock(
        return_value=MagicMock(
            allowed=False, reason="일일 거래 한도 초과", risk_level="blocked"
        )
    )
    sig = _make_signal(tier="prev_high")
    engine._signal_generator.generate_signals = AsyncMock(return_value=[sig])
    engine._record_volume_surge_signal = AsyncMock()

    await engine.process_screening_results(
        [{"stock_code": "005930", "current_price": 73000}]
    )

    # LIVE momentum 신호: 차단
    engine._order_manager.submit_order.assert_not_called()
    # dry_run volume_surge: 발행 계속 (자금/한도 무관)
    engine._record_volume_surge_signal.assert_awaited_once()
