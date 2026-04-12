"""스케줄러 텔레그램 장애 알림 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import CollectorScheduler
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
async def test_premarket_failure_sends_telegram():
    """_premarket_collect 실패 시 telegram 알림 — 예외 경로에서 KIS 폴백도 실패하면 이중 실패 알림."""
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()

    scheduler = _make_scheduler(telegram_bot=mock_bot)

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(side_effect=Exception("API timeout"))
        MockCollector.return_value = mock_instance

        await scheduler._premarket_collect()

    mock_bot.send_notification.assert_called()
    # 예외 경로에서 KIS 폴백도 실패하면 이중 실패([긴급]) 또는 폴백 예외 시 [장애] 알림
    all_messages = [call[0][0] for call in mock_bot.send_notification.call_args_list]
    assert any("[긴급]" in msg or "[장애]" in msg for msg in all_messages)
    assert any("premarket" in msg for msg in all_messages)


@pytest.mark.asyncio
async def test_pipeline_recovery_success_sends_telegram():
    """run_premarket_pipeline 성공 완료 시 [복구 완료] 메시지 발송."""
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()

    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis=fake_redis, telegram_bot=mock_bot)

    # 모든 step을 성공시키는 mock
    with (
        patch("modules.collector.scheduler.DataGoKrCollector") as MockData,
        patch("modules.collector.scheduler.KISMasterCollector") as MockMaster,
        patch("modules.collector.scheduler.KISCollector") as MockKIS,
        patch.object(scheduler._validator, "cross_check_prices", new=AsyncMock(return_value=[])),
    ):
        MockData.return_value.collect_all = AsyncMock(return_value=CollectionResult(collected=2800, data_date=DataGoKrCollector._latest_trading_date(), null_counts={"close_price": 0, "volume": 0}))
        MockMaster.return_value.collect = AsyncMock(
            return_value={"etf_count": 700, "etn_count": 50, "source": "mst", "sanity_passed": True}
        )
        MockKIS.return_value.collect_etf_prices = AsyncMock(return_value=CollectionResult(collected=700, total_target=700))

        scheduler._primary_screener = AsyncMock()
        scheduler._primary_screener.screen = AsyncMock(return_value=[])
        scheduler._primary_screener.save_results = AsyncMock(return_value=0)

        await scheduler.run_premarket_pipeline()

    # 복구 알림이 발송됨
    assert mock_bot.send_notification.called
    messages = [call[0][0] for call in mock_bot.send_notification.call_args_list]
    assert any("[복구 완료]" in m for m in messages)


@pytest.mark.asyncio
async def test_no_telegram_when_bot_not_set():
    """_telegram_bot이 None이면 에러 없이 스킵."""
    scheduler = _make_scheduler(telegram_bot=None)  # bot 미설정

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(side_effect=Exception("network error"))
        MockCollector.return_value = mock_instance

        # 에러 없이 정상 완료되어야 함
        result = await scheduler._premarket_collect()

    assert result == 0  # 실패 시 0 반환


@pytest.mark.asyncio
async def test_kis_fallback_sends_info_alert():
    """포털 실패 → KIS 폴백 성공 시 [정보] 알림 발송."""
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()

    scheduler = _make_scheduler(telegram_bot=mock_bot)

    portal_result = CollectionResult(collected=100, total_target=2800, data_date=None, null_counts={})  # 수집 부족 → validation fail
    kis_result = CollectionResult(collected=2500, total_target=2800, data_date=None, null_counts={})  # 80% 이상 → validation pass

    with (
        patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal,
        patch.object(scheduler, "_run_kis_daily_fallback", new=AsyncMock(return_value=kis_result)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        MockPortal.return_value.collect_all = AsyncMock(return_value=portal_result)
        await scheduler._premarket_collect()

    mock_bot.send_notification.assert_called_once()
    message = mock_bot.send_notification.call_args[0][0]
    assert "[정보]" in message


@pytest.mark.asyncio
async def test_double_failure_sends_critical_alert():
    """포털 + KIS 모두 실패 시 [긴급] 알림 발송 + pipeline_healthy=false."""
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()

    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis=fake_redis, telegram_bot=mock_bot)

    portal_result = CollectionResult(collected=100, total_target=2800, data_date=None, null_counts={})  # validation fail
    kis_result = CollectionResult(collected=0, total_target=0, data_date=None, null_counts={})  # total_target=0 → fail

    with (
        patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal,
        patch.object(scheduler, "_run_kis_daily_fallback", new=AsyncMock(return_value=kis_result)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        MockPortal.return_value.collect_all = AsyncMock(return_value=portal_result)
        await scheduler._premarket_collect()

    mock_bot.send_notification.assert_called_once()
    message = mock_bot.send_notification.call_args[0][0]
    assert "[긴급]" in message

    healthy = await fake_redis.get("scheduler:pipeline_healthy")
    assert healthy == "false"
