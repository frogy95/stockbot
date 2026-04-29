"""Phase 3 Sprint 2 통합 테스트 — 매매 사이클/손절/리스크/보합/ATR."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.engine import TradingEngine
from modules.trading.position_sizer import PositionSize
from modules.trading.risk_manager import RiskCheckResult
from modules.trading.strategy import MarketSnapshot, TradeSignalData

KST = ZoneInfo("Asia/Seoul")


# === 헬퍼 ===


def _make_signal(stock_code: str = "005930", confidence: float = 0.75) -> TradeSignalData:
    return TradeSignalData(
        stock_code=stock_code,
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=confidence,
        reason={"is_leverage": False, "test": True},
        entry_price=73000,
        stop_loss=71540,
        take_profit=75190,
    )


def _make_position_size(quantity: int = 10) -> PositionSize:
    return PositionSize(
        invest_amount=730000,
        quantity=quantity,
        is_leverage=False,
        size_pct=10.0,
    )


def _build_engine(
    signals=None,
    risk_allowed=True,
    quantity=10,
    exit_conditions=None,
    entry_blocked=False,
):
    """통합 테스트용 TradingEngine 생성."""
    signal_gen = AsyncMock()
    signal_gen.generate_signals = AsyncMock(return_value=signals or [])

    order_mgr = AsyncMock()
    order_mgr.start = AsyncMock()
    order_mgr.stop = AsyncMock()
    order_mgr.submit_order = AsyncMock(return_value=MagicMock(id=1))
    order_mgr._queue = MagicMock()
    order_mgr._queue.qsize.return_value = 0

    position_mgr = AsyncMock()
    position_mgr.update_prices = AsyncMock()
    position_mgr.check_exit_conditions = AsyncMock(return_value=exit_conditions or [])
    position_mgr.close_position = AsyncMock()
    position_mgr.open_position = AsyncMock()

    risk_mgr = AsyncMock()
    risk_mgr.can_trade = AsyncMock(
        return_value=RiskCheckResult(
            allowed=risk_allowed,
            reason=None if risk_allowed else "리스크 차단",
        )
    )

    pos_sizer = AsyncMock()
    pos_sizer.calculate = AsyncMock(return_value=_make_position_size(quantity))

    eod = MagicMock()
    eod.is_entry_blocked = MagicMock(return_value=entry_blocked)

    redis = AsyncMock()

    async def _redis_get(key):  # Phase 8.6 Sprint 2 — key-aware mock
        if key == "scheduler:pipeline_healthy":
            return "true"
        return None  # safe_mode:active 등 기본 None

    redis.get = AsyncMock(side_effect=_redis_get)

    engine = TradingEngine(
        signal_generator=signal_gen,
        order_manager=order_mgr,
        position_manager=position_mgr,
        risk_manager=risk_mgr,
        position_sizer=pos_sizer,
        eod_liquidator=eod,
        redis_client=redis,
    )

    return engine, {
        "signal_gen": signal_gen,
        "order_mgr": order_mgr,
        "position_mgr": position_mgr,
        "risk_mgr": risk_mgr,
        "pos_sizer": pos_sizer,
        "eod": eod,
    }


# === 통합 테스트 ===


@pytest.mark.asyncio
async def test_full_trading_cycle():
    """시나리오 1: 전체 매매 사이클 — 스크리닝 -> 신호 -> 리스크 통과 -> 주문."""
    signal = _make_signal()
    engine, mocks = _build_engine(signals=[signal])

    candidates = [{"stock_code": "005930", "stock_name": "삼성전자"}]
    await engine.process_screening_results(candidates)

    # 신호 생성 호출
    mocks["signal_gen"].generate_signals.assert_called_once_with(candidates)
    # 리스크 체크
    mocks["risk_mgr"].can_trade.assert_called_once()
    # 포지션 사이징
    mocks["pos_sizer"].calculate.assert_called_once()
    # 주문 제출
    mocks["order_mgr"].submit_order.assert_called_once()

    # 포지션 모니터링 (청산 대상 없음)
    exits = await engine.monitor_positions()
    assert len(exits) == 0


@pytest.mark.asyncio
async def test_stop_loss_scenario():
    """시나리오 2: 손절 — 포지션 모니터링에서 stop_loss 트리거."""
    engine, mocks = _build_engine(
        exit_conditions=[
            {
                "stock_code": "005930",
                "quantity": 10,
                "exit_reason": "stop_loss",
                "position_id": 1,
            }
        ]
    )

    exits = await engine.monitor_positions()
    assert len(exits) == 1
    assert exits[0]["exit_reason"] == "stop_loss"


@pytest.mark.asyncio
async def test_risk_blocked_scenario():
    """시나리오 3: 리스크 차단 — 일일 손실 한도 초과 시 주문 미실행."""
    signal = _make_signal()
    engine, mocks = _build_engine(signals=[signal], risk_allowed=False)

    await engine.process_screening_results([{"stock_code": "005930"}])

    mocks["order_mgr"].submit_order.assert_not_called()


@pytest.mark.asyncio
async def test_timeout_exit_scenario():
    """시나리오 4: 보합 청산 — 30분 경과 + 수익률 < 1%."""
    engine, mocks = _build_engine(
        exit_conditions=[
            {
                "stock_code": "005930",
                "quantity": 10,
                "exit_reason": "timeout",
                "position_id": 1,
            }
        ]
    )

    exits = await engine.monitor_positions()
    assert len(exits) == 1
    assert exits[0]["exit_reason"] == "timeout"


@pytest.mark.asyncio
async def test_atr_filter_scenario():
    """시나리오 5: ATR 필터 — 전략이 None 반환 시 주문 없음."""
    # signal_gen이 빈 리스트 반환 (ATR 필터에 걸려서)
    engine, mocks = _build_engine(signals=[])

    await engine.process_screening_results([{"stock_code": "005930"}])

    mocks["order_mgr"].submit_order.assert_not_called()
