"""매매 엔진 pipeline_healthy 차단 테스트."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from modules.trading.engine import TradingEngine

def _make_engine(redis_return_value):
    """TradingEngine mock 생성.

    redis_return_value: pipeline_healthy 키에 대한 반환값.
    safe_mode:active 키는 항상 None 반환 (safe_mode 게이트 차단 방지).
    """
    signal_generator = AsyncMock()
    signal_generator.generate_signals = AsyncMock(return_value=[])

    order_manager = AsyncMock()
    order_manager.start = AsyncMock()
    order_manager.stop = AsyncMock()
    order_manager.get_queue_size = MagicMock(return_value=0)

    position_manager = AsyncMock()
    risk_manager = AsyncMock()
    position_sizer = AsyncMock()

    eod_liquidator = MagicMock()
    eod_liquidator.is_entry_blocked = MagicMock(return_value=False)

    redis_client = AsyncMock()

    async def _redis_get(key: str):
        # safe_mode:active 는 None 반환 — safe_mode 게이트 통과 허용
        if key == "safe_mode:active":
            return None
        return redis_return_value

    redis_client.get = _redis_get

    return TradingEngine(
        signal_generator=signal_generator,
        order_manager=order_manager,
        position_manager=position_manager,
        risk_manager=risk_manager,
        position_sizer=position_sizer,
        eod_liquidator=eod_liquidator,
        redis_client=redis_client,
    )

@pytest.mark.asyncio
async def test_engine_blocks_when_pipeline_unhealthy():
    """pipeline_healthy가 None 또는 'false'이면 신호 생성 없이 조기 반환."""
    for val in [None, "false"]:
        engine = _make_engine(redis_return_value=val)
        await engine.process_screening_results([{"stock_code": "005930"}])
        engine._signal_generator.generate_signals.assert_not_called()

@pytest.mark.asyncio
async def test_engine_proceeds_when_pipeline_healthy():
    """pipeline_healthy가 'true'이면 signal_generator.generate_signals 호출."""
    engine = _make_engine(redis_return_value="true")
    await engine.process_screening_results([{"stock_code": "005930"}])
    engine._signal_generator.generate_signals.assert_called_once()
