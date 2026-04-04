"""스케줄러 08:30 포털 재시도 job 테스트."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import CollectorScheduler, PIPELINE_STATUS_KEY
from modules.collector.models import CollectionResult
from modules.collector.sources.data_go_kr import DataGoKrCollector
from tests.conftest import FakeRedis


def _make_scheduler(fake_redis: FakeRedis | None = None, telegram_bot=None):
    """테스트용 CollectorScheduler 생성."""
    mock_db_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx

    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.subscribe = AsyncMock()
    ws_manager.unsubscribe_all = AsyncMock()

    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()

    redis = fake_redis if fake_redis is not None else FakeRedis()

    scheduler = CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis,
    )
    if telegram_bot is not None:
        scheduler.set_telegram_bot(telegram_bot)
    return scheduler


@pytest.mark.asyncio
async def test_retry_job_registered():
    """start() 호출 후 premarket_retry job이 scheduler에 등록되어야 한다."""
    scheduler = _make_scheduler()

    # APScheduler가 실제로 시작되지 않도록 mock
    scheduler._scheduler.start = MagicMock()

    await scheduler.start()

    job_ids = [job.id for job in scheduler._scheduler.get_jobs()]
    assert "premarket_retry" in job_ids


@pytest.mark.asyncio
async def test_retry_skipped_when_premarket_success():
    """pipeline_status에서 premarket.status == 'success'이면 재시도 스킵 (early return)."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis=fake_redis)

    # premarket 성공 상태로 Redis 설정
    pipeline_status = {"premarket": {"status": "success"}}
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps(pipeline_status))

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(return_value=CollectionResult(collected=2800))
        MockCollector.return_value = mock_instance

        await scheduler._premarket_retry()

        # premarket이 이미 성공 상태이므로 collect_all이 호출되면 안 됨
        mock_instance.collect_all.assert_not_called()


@pytest.mark.asyncio
async def test_retry_executes_when_premarket_failed():
    """premarket.status == 'failed'일 때 포털 재수집 실행 → 성공 시 _update_step_status 호출."""
    fake_redis = FakeRedis()
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler = _make_scheduler(fake_redis=fake_redis, telegram_bot=mock_bot)

    # premarket 실패 상태로 Redis 설정
    pipeline_status = {"premarket": {"status": "failed"}}
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps(pipeline_status))

    success_result = CollectionResult(
        collected=2800,
        total_target=2800,
        data_date=DataGoKrCollector._latest_trading_date(),
        null_counts={"close_price": 0, "volume": 0},
    )

    with (
        patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector,
        patch.object(scheduler, "_update_step_status", new=AsyncMock()) as mock_update,
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(return_value=success_result)
        MockCollector.return_value = mock_instance

        await scheduler._premarket_retry()

        # collect_all 호출 확인
        mock_instance.collect_all.assert_called_once()

        # _update_step_status("premarket", "success", ...) 호출 확인
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == "premarket"
        assert call_args[0][1] == "success"


@pytest.mark.asyncio
async def test_retry_portal_success_overrides_kis():
    """재시도 성공 시 포털 데이터 기준으로 step status가 업데이트되어야 한다."""
    fake_redis = FakeRedis()
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler = _make_scheduler(fake_redis=fake_redis, telegram_bot=mock_bot)

    # premarket 실패 상태 + KIS 폴백으로 success였던 상황 시뮬레이션
    pipeline_status = {
        "premarket": {
            "status": "failed",
            "error": "포털 실패",
        }
    }
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps(pipeline_status))

    portal_result = CollectionResult(
        collected=2900,
        total_target=2900,
        data_date=DataGoKrCollector._latest_trading_date(),
        null_counts={"close_price": 0, "volume": 0},
    )

    with (
        patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector,
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(return_value=portal_result)
        MockCollector.return_value = mock_instance

        await scheduler._premarket_retry()

    # Redis의 pipeline_status에서 premarket이 success로 업데이트되었는지 확인
    raw = await fake_redis.get(PIPELINE_STATUS_KEY)
    updated_status = json.loads(raw)
    assert updated_status["premarket"]["status"] == "success"
    assert updated_status["premarket"].get("collected_count") == 2900

    # [복구] 알림 발송 확인
    mock_bot.send_notification.assert_called_once()
    message = mock_bot.send_notification.call_args[0][0]
    assert "[복구]" in message
