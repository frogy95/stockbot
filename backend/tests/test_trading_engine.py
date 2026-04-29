"""매매 엔진 오케스트레이터 테스트."""
from __future__ import annotations

from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.strategy import TradeSignalData
from modules.trading.position_sizer import PositionSize

KST = ZoneInfo("Asia/Seoul")


# === 헬퍼 ===


def _make_signal(stock_code: str = "005930") -> TradeSignalData:
    return TradeSignalData(
        stock_code=stock_code,
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=0.75,
        reason={"test": True},
        entry_price=73000,
        stop_loss=71540,
        take_profit=75190,
    )


def _make_position_size() -> PositionSize:
    return PositionSize(
        invest_amount=730000,
        quantity=10,
        is_leverage=False,
        size_pct=10.0,
    )


# === 픽스처 ===


@pytest.fixture
def mock_signal_generator():
    gen = AsyncMock()
    gen.generate_signals = AsyncMock(return_value=[_make_signal()])
    return gen


@pytest.fixture
def mock_order_manager():
    om = AsyncMock()
    om.start = AsyncMock()
    om.stop = AsyncMock()
    om.submit_order = AsyncMock(return_value=MagicMock(id=1))
    return om


@pytest.fixture
def mock_position_manager():
    pm = AsyncMock()
    pm.update_prices = AsyncMock()
    pm.check_exit_conditions = AsyncMock(return_value=[])
    pm.close_position = AsyncMock()
    pm.open_position = AsyncMock()
    return pm


@pytest.fixture
def mock_risk_manager():
    rm = AsyncMock()
    from modules.trading.risk_manager import RiskCheckResult
    rm.can_trade = AsyncMock(return_value=RiskCheckResult(allowed=True))
    return rm


@pytest.fixture
def mock_position_sizer():
    ps = AsyncMock()
    ps.calculate = AsyncMock(return_value=_make_position_size())
    return ps


@pytest.fixture
def mock_eod_liquidator():
    eod = MagicMock()
    eod.is_entry_blocked = MagicMock(return_value=False)
    return eod


@pytest.fixture
def mock_redis():
    redis = AsyncMock()

    async def _redis_get(key):  # Phase 8.6 Sprint 2 — key-aware mock
        if key == "scheduler:pipeline_healthy":
            return "true"
        return None  # safe_mode:active 등 기본 None

    redis.get = AsyncMock(side_effect=_redis_get)
    return redis


@pytest.fixture
def engine(
    mock_signal_generator,
    mock_order_manager,
    mock_position_manager,
    mock_risk_manager,
    mock_position_sizer,
    mock_eod_liquidator,
    mock_redis,
):
    from modules.trading.engine import TradingEngine

    return TradingEngine(
        signal_generator=mock_signal_generator,
        order_manager=mock_order_manager,
        position_manager=mock_position_manager,
        risk_manager=mock_risk_manager,
        position_sizer=mock_position_sizer,
        eod_liquidator=mock_eod_liquidator,
        redis_client=mock_redis,
    )


# === 테스트 ===


@pytest.mark.asyncio
async def test_normal_flow(engine, mock_signal_generator, mock_risk_manager, mock_position_sizer, mock_order_manager):
    """정상 흐름: 스크리닝 -> 신호 -> 리스크 통과 -> 주문."""
    candidates = [{"stock_code": "005930", "stock_name": "삼성전자"}]

    await engine.process_screening_results(candidates)

    mock_signal_generator.generate_signals.assert_called_once_with(candidates)
    mock_risk_manager.can_trade.assert_called_once()
    mock_position_sizer.calculate.assert_called_once()
    mock_order_manager.submit_order.assert_called_once()


@pytest.mark.asyncio
async def test_risk_blocked(engine, mock_risk_manager, mock_order_manager):
    """리스크 차단: can_trade False -> 주문 미실행."""
    from modules.trading.risk_manager import RiskCheckResult
    mock_risk_manager.can_trade = AsyncMock(
        return_value=RiskCheckResult(allowed=False, reason="테스트 차단")
    )

    await engine.process_screening_results([{"stock_code": "005930"}])

    mock_order_manager.submit_order.assert_not_called()


@pytest.mark.asyncio
async def test_no_signals(engine, mock_signal_generator, mock_order_manager):
    """신호 없음: 빈 리스트 -> 주문 미실행."""
    mock_signal_generator.generate_signals = AsyncMock(return_value=[])

    await engine.process_screening_results([{"stock_code": "005930"}])

    mock_order_manager.submit_order.assert_not_called()


@pytest.mark.asyncio
async def test_position_monitoring(engine, mock_position_manager, mock_order_manager):
    """포지션 모니터링: 청산 대상 발견 -> 매도 처리."""
    mock_position_manager.check_exit_conditions = AsyncMock(return_value=[
        {"stock_code": "005930", "quantity": 10, "exit_reason": "stop_loss", "position_id": 1}
    ])

    exits = await engine.monitor_positions()

    assert len(exits) == 1
    assert exits[0]["exit_reason"] == "stop_loss"


@pytest.mark.asyncio
async def test_golden_time_timeout():
    """시간대 정책: 골든타임(09:30~10:30) -> 20초."""
    from modules.trading.engine import TradingEngine

    # 10:00 KST
    with patch("modules.trading.engine.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 3, 30, 10, 0, 0, tzinfo=KST)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        timeout = TradingEngine._get_approval_timeout_static(
            datetime(2026, 3, 30, 10, 0, 0, tzinfo=KST)
        )
        assert timeout == 20


@pytest.mark.asyncio
async def test_eod_entry_blocked(engine, mock_eod_liquidator, mock_signal_generator, mock_order_manager):
    """14:30 이후 신규 진입 차단."""
    mock_eod_liquidator.is_entry_blocked = MagicMock(return_value=True)

    await engine.process_screening_results([{"stock_code": "005930"}])

    mock_signal_generator.generate_signals.assert_not_called()
    mock_order_manager.submit_order.assert_not_called()


# === Phase 8 Sprint 2: 일일 거래 카운터 ===


@pytest.mark.asyncio
async def test_on_order_filled_increments_daily_trade_count(
    engine, mock_position_manager, mock_risk_manager
):
    """on_order_filled 시 incr_daily_trade_count 호출."""
    mock_risk_manager.incr_daily_trade_count = AsyncMock(return_value=1)
    signal = _make_signal()

    await engine.on_order_filled(
        order_id=1, filled_price=73000, signal_data=signal, quantity=10
    )

    mock_position_manager.open_position.assert_awaited_once()
    mock_risk_manager.incr_daily_trade_count.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_order_filled_counter_failure_does_not_block_position(
    engine, mock_position_manager, mock_risk_manager
):
    """카운터 증가 실패가 포지션 생성을 막지 않음 (에러 격리)."""
    mock_risk_manager.incr_daily_trade_count = AsyncMock(
        side_effect=Exception("Redis 일시 장애")
    )
    signal = _make_signal()

    # 예외가 밖으로 전파되지 않아야 함
    await engine.on_order_filled(
        order_id=1, filled_price=73000, signal_data=signal, quantity=10
    )

    mock_position_manager.open_position.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_screening_results_blocked_when_daily_limit_reached(
    engine, mock_risk_manager, mock_order_manager
):
    """can_trade가 일일 한도로 차단 시 submit_order 미호출."""
    from modules.trading.risk_manager import RiskCheckResult

    mock_risk_manager.can_trade = AsyncMock(
        return_value=RiskCheckResult(
            allowed=False,
            reason="일일 거래 횟수 한도(10건)에 도달했습니다",
            risk_level="blocked",
        )
    )

    await engine.process_screening_results([{"stock_code": "005930"}])

    mock_order_manager.submit_order.assert_not_called()
