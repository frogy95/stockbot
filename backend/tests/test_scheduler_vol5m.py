"""Phase 6.1 Sprint 1 — scheduler 5분봉 집계 연동 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import CollectorScheduler
from modules.collector.sources.kis_realtime import ExecutionData


def _make_scheduler(volume_aggregator=None):
    """테스트용 CollectorScheduler 생성 (volume_aggregator 주입 가능)."""
    mock_db_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx

    ws_manager = MagicMock()
    ws_manager.count = 0

    ws_client = MagicMock()
    ws_client.set_on_data = MagicMock()
    ws_client.set_on_ws_failure = MagicMock()
    ws_client.set_on_reconnect_success = MagicMock()

    redis = AsyncMock()
    redis.set = AsyncMock()

    trade_strength = MagicMock()
    trade_strength.add_execution = MagicMock()

    return CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=trade_strength,
        ws_client=ws_client,
        redis=redis,
        volume_aggregator=volume_aggregator,
    )


def _execution_sample() -> ExecutionData:
    return ExecutionData(
        stock_code="062040",
        time="131700",
        price=169900,
        change_sign="2",
        change=12000,
        change_rate=7.6,
        volume=1080,
        acml_volume=1080856,
        sell_or_buy="2",
    )


@pytest.mark.asyncio
async def test_process_realtime_data_calls_aggregator():
    """H0STCNT0 수신 시 aggregate_execution이 호출된다."""
    aggregator = AsyncMock()
    scheduler = _make_scheduler(volume_aggregator=aggregator)
    execution = _execution_sample()

    with (
        patch(
            "modules.collector.scheduler.parse_raw_message",
            return_value=("H0STCNT0", "0", "body"),
        ),
        patch(
            "modules.collector.scheduler.parse_execution",
            return_value=execution,
        ),
    ):
        await scheduler._process_realtime_data("H0STCNT0", "raw")

    aggregator.aggregate_execution.assert_awaited_once_with(
        execution.stock_code,
        execution.time,
        execution.volume,
        execution.sell_or_buy,
    )


@pytest.mark.asyncio
async def test_process_realtime_data_aggregator_failure_ignored():
    """aggregate_execution이 예외를 던져도 나머지 처리가 정상 완료된다."""
    aggregator = AsyncMock()
    aggregator.aggregate_execution = AsyncMock(side_effect=RuntimeError("Redis down"))
    scheduler = _make_scheduler(volume_aggregator=aggregator)
    execution = _execution_sample()

    with (
        patch(
            "modules.collector.scheduler.parse_raw_message",
            return_value=("H0STCNT0", "0", "body"),
        ),
        patch(
            "modules.collector.scheduler.parse_execution",
            return_value=execution,
        ),
    ):
        # 예외가 전파되지 않아야 함
        await scheduler._process_realtime_data("H0STCNT0", "raw")

    # Redis 캐시 set과 체결강도 add_execution은 aggregator 예외와 무관하게 수행됨
    scheduler._redis.set.assert_awaited()
    scheduler._trade_strength.add_execution.assert_called_once()
    # aggregator는 호출은 되었음
    aggregator.aggregate_execution.assert_awaited_once()


@pytest.mark.asyncio
async def test_aggregator_none_skips():
    """volume_aggregator=None이면 기존 동작 유지(호출 안 함)."""
    scheduler = _make_scheduler(volume_aggregator=None)
    execution = _execution_sample()

    with (
        patch(
            "modules.collector.scheduler.parse_raw_message",
            return_value=("H0STCNT0", "0", "body"),
        ),
        patch(
            "modules.collector.scheduler.parse_execution",
            return_value=execution,
        ),
    ):
        # 예외 없이 정상 완료
        await scheduler._process_realtime_data("H0STCNT0", "raw")

    # 기존 동작 (Redis set, 체결강도 업데이트)는 그대로 수행
    scheduler._redis.set.assert_awaited()
    scheduler._trade_strength.add_execution.assert_called_once()
