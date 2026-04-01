"""스케줄러 Redis 상태 영속화 테스트."""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, call

from modules.collector.scheduler import CollectorScheduler


def _make_scheduler(redis_mock=None):
    """테스트용 CollectorScheduler 생성."""
    mock_db_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx

    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.unsubscribe_all = AsyncMock()

    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()

    redis = redis_mock if redis_mock is not None else AsyncMock()

    scheduler = CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis,
    )
    return scheduler


@pytest.mark.asyncio
async def test_init_loads_state_from_redis():
    """생성자에서 Redis에 저장된 _last_* 값을 start() 시점에 로드하는지 확인."""
    redis_mock = AsyncMock()
    iso_str = "2026-04-01T08:00:00+09:00"
    redis_mock.get = AsyncMock(return_value=iso_str)

    scheduler = _make_scheduler(redis_mock)
    await scheduler.start()

    # Redis에서 로드된 값이 datetime으로 복원되어야 함
    assert scheduler._last_premarket is not None
    assert isinstance(scheduler._last_premarket, datetime)

    await scheduler.stop()


@pytest.mark.asyncio
async def test_premarket_saves_to_redis():
    """_premarket_collect 성공 후 Redis에 저장되는지 확인."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()

    scheduler = _make_scheduler(redis_mock)

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "modules.collector.scheduler.DataGoKrCollector"
    ) as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(return_value=2800)
        MockCollector.return_value = mock_instance

        await scheduler._premarket_collect()

    # Redis set이 호출되어야 함
    assert redis_mock.set.called
    call_args_list = redis_mock.set.call_args_list
    keys_saved = [c.args[0] if c.args else c.kwargs.get("key", "") for c in call_args_list]
    assert any("scheduler:last_premarket" in k for k in keys_saved)

    # TTL 86400 확인
    premarket_call = next(
        c for c in call_args_list
        if (c.args and "scheduler:last_premarket" in c.args[0])
        or ("scheduler:last_premarket" in c.kwargs.get("key", ""))
    )
    ttl = premarket_call.kwargs.get("ttl") or (premarket_call.args[2] if len(premarket_call.args) > 2 else None)
    assert ttl == 86400


@pytest.mark.asyncio
async def test_get_status_includes_pipeline_status():
    """get_status() 반환값에 pipeline_status 키가 포함되는지 확인."""
    scheduler = _make_scheduler()

    status = scheduler.get_status()

    assert "pipeline_status" in status
