"""매매 엔진 자동 모드 분기 + 안전장치 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.trading.engine import TradingEngine
from modules.trading.strategy import TradeSignalData


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_redis(trading_mode: str | None = None) -> AsyncMock:
    """FakeRedis-like AsyncMock — pipeline_healthy + trading:mode 대응."""
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


def _make_engine(
    notifier_manager=None,
    trading_mode: str = "semi-auto",
    session_factory=None,
) -> TradingEngine:
    """테스트용 TradingEngine 생성 헬퍼."""
    mock_redis = _make_redis(trading_mode=trading_mode)

    if session_factory is None:
        # settings 테이블 조회를 건너뛰기 위해 None 전달 → _get_trading_mode가 Redis만 사용
        session_factory = None

    engine = TradingEngine(
        signal_generator=AsyncMock(),
        order_manager=AsyncMock(),
        position_manager=AsyncMock(),
        risk_manager=AsyncMock(),
        position_sizer=AsyncMock(),
        eod_liquidator=MagicMock(),
        redis_client=mock_redis,
        notifier_manager=notifier_manager,
        session_factory=session_factory,
    )
    engine._order_manager.get_queue_size.return_value = 0
    return engine


def _make_signal(stock_code: str = "005930") -> TradeSignalData:
    return TradeSignalData(
        stock_code=stock_code,
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=0.85,
        reason={"rsi": 72, "volume_surge": True},
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


def _setup_engine_basics(engine: TradingEngine, signal: TradeSignalData, quantity: int = 10) -> None:
    """공통 mock 설정 헬퍼."""
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(return_value=MagicMock(allowed=True))
    engine._position_sizer.calculate = AsyncMock(return_value=_make_position_size(quantity))
    engine._eod_liquidator.is_entry_blocked.return_value = False


# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_mode_submits_order_without_approval():
    """auto 모드: 승인 없이 order_manager.submit_order 직접 호출."""
    notifier = AsyncMock()
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")
    signal = _make_signal()
    _setup_engine_basics(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930"}])

    # 즉시 주문 실행
    engine._order_manager.submit_order.assert_called_once()
    # 승인 요청(notify_signal) 호출 안 함
    notifier.notify_signal.assert_not_called()


@pytest.mark.asyncio
async def test_semi_auto_mode_calls_notify_signal():
    """semi-auto 모드: notifier.notify_signal 호출 (기존 동작 유지)."""
    notifier = AsyncMock()
    notifier.notify_signal = AsyncMock(return_value="token-abc")
    engine = _make_engine(notifier_manager=notifier, trading_mode="semi-auto")
    signal = _make_signal()
    _setup_engine_basics(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930"}])

    notifier.notify_signal.assert_called_once()
    engine._order_manager.submit_order.assert_not_called()


@pytest.mark.asyncio
async def test_manual_mode_skips_order_and_notify():
    """manual 모드: 주문/승인 요청 모두 스킵, 신호 생성만."""
    notifier = AsyncMock()
    engine = _make_engine(notifier_manager=notifier, trading_mode="manual")
    signal = _make_signal()
    _setup_engine_basics(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930"}])

    engine._order_manager.submit_order.assert_not_called()
    notifier.notify_signal.assert_not_called()


@pytest.mark.asyncio
async def test_auto_mode_fallback_forces_semi_auto():
    """auto 모드에서 is_fallback=True 종목은 반자동 강제 전환 (notify_signal 호출)."""
    notifier = AsyncMock()
    notifier.notify_signal = AsyncMock(return_value="token-fallback")
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")
    signal = _make_signal()
    _setup_engine_basics(engine, signal)

    candidate = {"stock_code": "005930", "is_fallback": True}
    await engine.process_screening_results([candidate])

    # 반자동으로 강제 전환 → notify_signal 호출
    notifier.notify_signal.assert_called_once()
    engine._order_manager.submit_order.assert_not_called()


@pytest.mark.asyncio
async def test_auto_mode_relaxed_forces_semi_auto():
    """auto 모드에서 is_relaxed=True 종목도 반자동 강제 전환."""
    notifier = AsyncMock()
    notifier.notify_signal = AsyncMock(return_value="token-relaxed")
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")
    signal = _make_signal()
    _setup_engine_basics(engine, signal)

    candidate = {"stock_code": "005930", "is_relaxed": True}
    await engine.process_screening_results([candidate])

    notifier.notify_signal.assert_called_once()
    engine._order_manager.submit_order.assert_not_called()


@pytest.mark.asyncio
async def test_auto_mode_risk_check_blocks_order():
    """auto 모드에서도 리스크 체크(can_trade) 실패 시 주문 차단."""
    notifier = AsyncMock()
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")
    signal = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(
        return_value=MagicMock(allowed=False, reason="손실 한도 초과")
    )
    engine._position_sizer.calculate = AsyncMock(return_value=_make_position_size())
    engine._eod_liquidator.is_entry_blocked.return_value = False

    await engine.process_screening_results([{"stock_code": "005930"}])

    engine._order_manager.submit_order.assert_not_called()
    notifier.notify_signal.assert_not_called()


@pytest.mark.asyncio
async def test_position_size_ratio_applied():
    """position_size_ratio=0.5 플래그가 있으면 주문 수량 50% 적용."""
    from modules.trading.position_sizer import PositionSizer
    from contextlib import asynccontextmanager

    # is_leverage 조회를 위한 session mock
    mock_session = AsyncMock()
    stock_result = AsyncMock()
    stock_result.scalar_one_or_none = MagicMock(return_value=None)  # 레버리지 아님
    mock_session.execute = AsyncMock(return_value=stock_result)

    @asynccontextmanager
    async def mock_session_factory():
        yield mock_session

    sizer = PositionSizer(session_factory=mock_session_factory)
    sizer._position_size_pct = 10.0

    # balance 10,000,000원, 가격 73,000원
    # invest_amount = 10,000,000 * 10 / 100 = 1,000,000
    # quantity = 1,000,000 // 73,000 = 13
    result_full = await sizer.calculate("005930", 73000, 10_000_000, size_ratio=1.0)
    result_half = await sizer.calculate("005930", 73000, 10_000_000, size_ratio=0.5)

    assert result_half.quantity == int(result_full.quantity * 0.5)
    assert result_half.invest_amount == int(result_full.invest_amount * 0.5)


# ---------------------------------------------------------------------------
# Phase 8 Sprint 2 Task 6: 차단 사유 구조화 로그 + 선택적 텔레그램 알림
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_structured_block_log_on_risk_blocked(caplog):
    """risk_blocked 차단 시 구조화 필드 로그 기록."""
    import logging as _logging

    notifier = AsyncMock()
    notifier.send_system_alert = AsyncMock()
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")
    signal = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(
        return_value=MagicMock(allowed=False, reason="손실 한도", risk_level="blocked")
    )
    engine._position_sizer.calculate = AsyncMock(return_value=_make_position_size())
    engine._eod_liquidator.is_entry_blocked.return_value = False

    with caplog.at_level(_logging.INFO, logger="modules.trading.engine"):
        await engine.process_screening_results([{"stock_code": "005930"}])

    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "engine_block" in m and "risk_blocked" in m and "005930" in m for m in messages
    )


@pytest.mark.asyncio
async def test_risk_blocked_triggers_telegram_alert():
    """risk_blocked 차단 시 텔레그램 send_system_alert 호출."""
    notifier = AsyncMock()
    notifier.send_system_alert = AsyncMock()
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")
    signal = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(
        return_value=MagicMock(allowed=False, reason="손실 한도", risk_level="blocked")
    )
    engine._position_sizer.calculate = AsyncMock(return_value=_make_position_size())
    engine._eod_liquidator.is_entry_blocked.return_value = False

    await engine.process_screening_results([{"stock_code": "005930"}])

    notifier.send_system_alert.assert_awaited_once()
    call_args = notifier.send_system_alert.call_args
    assert call_args[0][0] == "risk_warning"


@pytest.mark.asyncio
async def test_quantity_zero_does_not_trigger_telegram_alert():
    """quantity_zero 차단은 로그만 남기고 텔레그램 알림 미발송."""
    notifier = AsyncMock()
    notifier.send_system_alert = AsyncMock()
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")
    signal = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(return_value=MagicMock(allowed=True))
    engine._position_sizer.calculate = AsyncMock(
        return_value=_make_position_size(quantity=0)
    )
    engine._eod_liquidator.is_entry_blocked.return_value = False

    await engine.process_screening_results([{"stock_code": "005930"}])

    notifier.send_system_alert.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_unhealthy_triggers_telegram_alert():
    """pipeline_unhealthy 차단은 send_system_alert 호출."""
    notifier = AsyncMock()
    notifier.send_system_alert = AsyncMock()
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")

    # redis.get override: pipeline_healthy=false
    async def _get(key):
        if key == "scheduler:pipeline_healthy":
            return "false"
        if key == "trading:mode":
            return "auto"
        return None

    engine._redis.get = AsyncMock(side_effect=_get)

    await engine.process_screening_results([{"stock_code": "005930"}])

    notifier.send_system_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_block_alert_deduped_within_5min():
    """동일 (stock_code, reason) 조합은 5분 내 재알림 방지."""
    notifier = AsyncMock()
    notifier.send_system_alert = AsyncMock()
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")
    signal = _make_signal()
    engine._signal_generator.generate_signals = AsyncMock(return_value=[signal])
    engine._risk_manager.can_trade = AsyncMock(
        return_value=MagicMock(allowed=False, reason="손실 한도", risk_level="blocked")
    )
    engine._position_sizer.calculate = AsyncMock(return_value=_make_position_size())
    engine._eod_liquidator.is_entry_blocked.return_value = False

    # 두 번째 호출에서 dedup 키가 존재한다고 가정
    dedup_state = {"hit": False}

    async def _get(key):
        if key == "scheduler:pipeline_healthy":
            return "true"
        if key == "trading:mode":
            return "auto"
        if key.startswith("engine:block:dedup:"):
            if dedup_state["hit"]:
                return "1"
            dedup_state["hit"] = True
            return None
        return None

    engine._redis.get = AsyncMock(side_effect=_get)

    # 첫 호출 → 알림 1회
    await engine.process_screening_results([{"stock_code": "005930"}])
    # 두 번째 호출 → dedup으로 스킵
    await engine.process_screening_results([{"stock_code": "005930"}])

    assert notifier.send_system_alert.await_count == 1


# ---------------------------------------------------------------------------
# Phase 8 Sprint 2: breakout_tier 기반 size_ratio
# ---------------------------------------------------------------------------


def _make_signal_with_tier(tier: str, stock_code: str = "005930") -> TradeSignalData:
    """breakout_tier를 포함한 TradeSignalData."""
    return TradeSignalData(
        stock_code=stock_code,
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=0.72,
        reason={"breakout_tier": tier, "momentum_score": 0.5},
        entry_price=73000,
        stop_loss=71540,
        take_profit=75190,
    )


@pytest.mark.asyncio
async def test_prev_close_tier_applies_half_size_ratio():
    """breakout_tier='prev_close' → position_sizer.calculate에 size_ratio=0.5 전달."""
    engine = _make_engine(trading_mode="auto")
    signal = _make_signal_with_tier("prev_close")
    _setup_engine_basics(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930"}])

    engine._position_sizer.calculate.assert_called_once()
    _, kwargs = engine._position_sizer.calculate.call_args
    assert kwargs["size_ratio"] == 0.5


@pytest.mark.asyncio
async def test_prev_high_tier_keeps_size_ratio_1_0():
    """breakout_tier='prev_high' → size_ratio=1.0 유지."""
    engine = _make_engine(trading_mode="auto")
    signal = _make_signal_with_tier("prev_high")
    _setup_engine_basics(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930"}])

    _, kwargs = engine._position_sizer.calculate.call_args
    assert kwargs["size_ratio"] == 1.0


@pytest.mark.asyncio
async def test_gap_open_tier_keeps_size_ratio_1_0():
    """breakout_tier='gap_open' → size_ratio=1.0 유지."""
    engine = _make_engine(trading_mode="auto")
    signal = _make_signal_with_tier("gap_open")
    _setup_engine_basics(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930"}])

    _, kwargs = engine._position_sizer.calculate.call_args
    assert kwargs["size_ratio"] == 1.0


@pytest.mark.asyncio
async def test_candidate_position_size_ratio_overrides_when_smaller():
    """candidate.position_size_ratio=0.3 + prev_close tier → min(0.3, 0.5) = 0.3."""
    engine = _make_engine(trading_mode="auto")
    signal = _make_signal_with_tier("prev_close")
    _setup_engine_basics(engine, signal)

    candidate = {"stock_code": "005930", "position_size_ratio": 0.3}
    await engine.process_screening_results([candidate])

    _, kwargs = engine._position_sizer.calculate.call_args
    assert kwargs["size_ratio"] == 0.3


@pytest.mark.asyncio
async def test_missing_breakout_tier_defaults_to_prev_high_sizing():
    """reason에 breakout_tier 없으면 prev_high 기본값으로 size_ratio=1.0."""
    engine = _make_engine(trading_mode="auto")
    signal = _make_signal()  # reason에 breakout_tier 없음
    _setup_engine_basics(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930"}])

    _, kwargs = engine._position_sizer.calculate.call_args
    assert kwargs["size_ratio"] == 1.0


@pytest.mark.asyncio
async def test_auto_mode_sends_notification():
    """auto 모드 주문 시 notifier.send_notification("자동 주문 알림" 포함) 발송."""
    notifier = AsyncMock()
    notifier.send_notification = AsyncMock()
    engine = _make_engine(notifier_manager=notifier, trading_mode="auto")
    signal = _make_signal()
    _setup_engine_basics(engine, signal)

    await engine.process_screening_results([{"stock_code": "005930"}])

    # submit_order 호출
    engine._order_manager.submit_order.assert_called_once()
    # send_notification 호출 + 텍스트에 "자동 주문 알림" 포함
    notifier.send_notification.assert_called_once()
    call_args = notifier.send_notification.call_args
    text_arg = call_args[0][0] if call_args[0] else call_args[1].get("text", "")
    assert "자동 주문 알림" in text_arg
