"""Phase 6.2 Sprint 1 — 장전 수집 단순화 검증 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import CollectorScheduler
from modules.collector.models import CollectionResult
from tests.conftest import FakeRedis


def _make_scheduler(fake_redis=None, telegram_bot=None):
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
    ws_client.set_on_ws_failure = MagicMock()
    ws_client.set_on_reconnect_success = MagicMock()
    ws_client.connected = False

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
async def test_premarket_collect_calls_kis_directly():
    """_premarket_collect()가 _run_kis_daily_collect()를 호출하고 DataGoKrCollector를 호출하지 않는다."""
    scheduler = _make_scheduler()

    kis_result = CollectionResult(collected=2800, total_target=2800, null_counts={"close_price": 0, "volume": 0})

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)) as mock_kis,
        patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal,
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        result = await scheduler._premarket_collect()

    mock_kis.assert_awaited_once()
    MockPortal.return_value.collect_all.assert_not_called()
    assert result == 2800


@pytest.mark.asyncio
async def test_premarket_collect_success_updates_status():
    """KIS 수집 성공 시 premarket status="success" 확인."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis=fake_redis)

    kis_result = CollectionResult(collected=2800, total_target=2800, null_counts={"close_price": 0, "volume": 0})

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        result = await scheduler._premarket_collect()

    assert result == 2800
    status = await scheduler._get_pipeline_status()
    assert status["premarket"]["status"] == "success"


@pytest.mark.asyncio
async def test_premarket_collect_failure_updates_status():
    """KIS 수집 예외 시 premarket status="failed" + 알림 발송 확인."""
    fake_redis = FakeRedis()
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler = _make_scheduler(fake_redis=fake_redis, telegram_bot=mock_bot)

    with patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(side_effect=Exception("KIS API 오류"))):
        result = await scheduler._premarket_collect()

    assert result == 0
    status = await scheduler._get_pipeline_status()
    assert status["premarket"]["status"] == "failed"

    mock_bot.send_notification.assert_called()
    message = mock_bot.send_notification.call_args[0][0]
    assert "[장애]" in message


@pytest.mark.asyncio
async def test_portal_supplement_collect_calls_data_go_kr():
    """_portal_supplement_collect()가 DataGoKrCollector.collect_all()을 호출하는지 검증."""
    scheduler = _make_scheduler()

    portal_result = CollectionResult(collected=2800, total_target=2800)

    with (
        patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal,
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
    ):
        MockPortal.return_value.collect_all = AsyncMock(return_value=portal_result)
        await scheduler._portal_supplement_collect()

    MockPortal.return_value.collect_all.assert_called_once()


@pytest.mark.asyncio
async def test_portal_supplement_collect_skips_non_trading_day():
    """비거래일 스킵 확인."""
    scheduler = _make_scheduler()

    with (
        patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal,
        patch("modules.collector.scheduler.is_trading_day", return_value=False),
    ):
        await scheduler._portal_supplement_collect()

    MockPortal.return_value.collect_all.assert_not_called()


@pytest.mark.asyncio
async def test_portal_supplement_collect_failure_logs_warning():
    """포털 예외 시 경고 로그만 (장애 아님, 알림 없음)."""
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler = _make_scheduler(telegram_bot=mock_bot)

    with (
        patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal,
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
    ):
        MockPortal.return_value.collect_all = AsyncMock(side_effect=Exception("포털 연결 실패"))
        await scheduler._portal_supplement_collect()

    # 장애 알림 없음 (포털은 보조 수집)
    mock_bot.send_notification.assert_not_called()


@pytest.mark.asyncio
async def test_start_registers_portal_supplement_job():
    """start() 호출 후 portal_supplement job 등록 확인."""
    scheduler = _make_scheduler()
    scheduler._scheduler.start = MagicMock()

    await scheduler.start()

    job_ids = [job.id for job in scheduler._scheduler.get_jobs()]
    assert "portal_supplement" in job_ids
