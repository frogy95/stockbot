"""스케줄러 08:30 KIS 재시도 job 테스트."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import CollectorScheduler, PIPELINE_STATUS_KEY
from modules.collector.models import CollectionResult
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

    with patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock()) as mock_collect:
        await scheduler._premarket_retry()

        # premarket이 이미 성공 상태이므로 _run_kis_daily_collect가 호출되면 안 됨
        mock_collect.assert_not_called()


@pytest.mark.asyncio
async def test_retry_executes_when_premarket_failed():
    """premarket.status == 'failed'일 때 KIS 재수집 실행 → 성공 시 _update_step_status 호출."""
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
        null_counts={"close_price": 0, "volume": 0},
    )

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=success_result)),
        patch.object(scheduler, "_update_step_status", new=AsyncMock()) as mock_update,
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
    ):
        await scheduler._premarket_retry()

        # _update_step_status("premarket", "success", ...) 호출 확인
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == "premarket"
        assert call_args[0][1] == "success"


@pytest.mark.asyncio
async def test_retry_kis_success_updates_status():
    """KIS 재시도 성공 시 pipeline_status가 success로 업데이트되어야 한다."""
    fake_redis = FakeRedis()
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler = _make_scheduler(fake_redis=fake_redis, telegram_bot=mock_bot)

    # premarket 실패 상태
    pipeline_status = {
        "premarket": {
            "status": "failed",
            "error": "KIS 수집 실패",
        }
    }
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps(pipeline_status))

    kis_result = CollectionResult(
        collected=2900,
        total_target=2900,
        null_counts={"close_price": 0, "volume": 0},
    )

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
    ):
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
