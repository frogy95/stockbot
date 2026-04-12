"""체인 파이프라인 동작 검증 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import CollectorScheduler, PIPELINE_RUNNING_KEY, STATE_TTL
from tests.conftest import FakeRedis


def _make_scheduler(redis=None):
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

    return CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis if redis is not None else AsyncMock(),
    )


@pytest.mark.asyncio
async def test_chain_pipeline_registered_at_0800():
    """start() 후 premarket_pipeline job이 08:00에 등록되고 개별 장전 job이 없는지 확인."""
    scheduler = _make_scheduler()
    await scheduler.start()

    job_ids = {j["id"] for j in scheduler.get_status()["next_jobs"]}
    assert "premarket_pipeline" in job_ids
    assert "premarket_collect" not in job_ids
    assert "etf_master_collect" not in job_ids
    assert "primary_screen" not in job_ids
    assert "etf_collect" not in job_ids
    assert "dart_collect" not in job_ids
    assert "sentiment_collect" not in job_ids

    await scheduler.stop()


@pytest.mark.asyncio
async def test_run_scheduled_pipeline_acquires_lock():
    """_run_scheduled_pipeline() 호출 시 락 선점 후 run_premarket_pipeline이 호출되는지 확인."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis=redis)

    scheduler.run_premarket_pipeline = AsyncMock(return_value={"completed": True, "pipeline_status": {}})

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._run_scheduled_pipeline()

    scheduler.run_premarket_pipeline.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_scheduled_pipeline_skips_when_locked():
    """PIPELINE_RUNNING_KEY가 이미 존재하면 run_premarket_pipeline이 호출되지 않는지 확인."""
    redis = FakeRedis()
    await redis.set(PIPELINE_RUNNING_KEY, "manual")
    scheduler = _make_scheduler(redis=redis)

    scheduler.run_premarket_pipeline = AsyncMock(return_value={"completed": True, "pipeline_status": {}})

    await scheduler._run_scheduled_pipeline()

    scheduler.run_premarket_pipeline.assert_not_awaited()


@pytest.mark.asyncio
async def test_chain_pipeline_logs_duration(caplog):
    """_run_scheduled_pipeline() 호출 후 소요 시간 로깅이 출력되는지 확인."""
    import logging
    redis = FakeRedis()
    scheduler = _make_scheduler(redis=redis)

    scheduler.run_premarket_pipeline = AsyncMock(return_value={"completed": True, "pipeline_status": {}})

    with (
        caplog.at_level(logging.INFO, logger="modules.collector.scheduler"),
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
    ):
        await scheduler._run_scheduled_pipeline()

    assert any("장전 파이프라인 시작" in r.message for r in caplog.records)
    assert any("장전 파이프라인 종료" in r.message and "소요" in r.message for r in caplog.records)
