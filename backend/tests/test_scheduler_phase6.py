"""Phase 6 Sprint 1 — scheduler 치명적 버그 수정 테스트."""

from datetime import date
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import CollectorScheduler


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
    ws_client.set_on_ws_failure = MagicMock()
    ws_client.set_on_reconnect_success = MagicMock()
    ws_client.connected = False

    return CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis if redis is not None else AsyncMock(),
    )


@pytest.mark.asyncio
async def test_market_open_failure_sends_telegram():
    """_market_open() 예외 시 텔레그램 알림 발송."""
    scheduler = _make_scheduler()
    telegram = AsyncMock()
    scheduler._telegram_bot = telegram
    scheduler._ws_client.connect = AsyncMock(side_effect=Exception("WS 연결 실패"))

    # is_trading_day = True 로 mock (거래일)
    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._market_open()

    # _send_failure_alert 를 통해 텔레그램 알림 발송 확인
    telegram.send_notification.assert_awaited()
    call_msg = telegram.send_notification.call_args[0][0]
    assert "장애" in call_msg
    assert "market_open" in call_msg


@pytest.mark.asyncio
async def test_market_open_recovery_checks_connected():
    """connected=False + count>0 일 때 recovery 실행."""
    scheduler = _make_scheduler()
    telegram = AsyncMock()
    scheduler._telegram_bot = telegram

    # ws_manager.count > 0이지만 ws_client.connected = False
    scheduler._ws_manager.count = 5
    scheduler._ws_client.connected = False

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._market_open_recovery()

    # connected=False이므로 _market_open이 호출됨 (connect가 호출됨)
    scheduler._ws_client.connect.assert_awaited()


@pytest.mark.asyncio
async def test_market_open_recovery_skips_when_connected():
    """connected=True 일 때 recovery 스킵."""
    scheduler = _make_scheduler()
    scheduler._ws_client.connected = True
    scheduler._ws_manager.count = 5

    await scheduler._market_open_recovery()

    # 이미 연결된 상태이므로 connect 미호출
    scheduler._ws_client.connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduled_pipeline_skips_non_trading_day():
    """비거래일에 파이프라인 스킵."""
    scheduler = _make_scheduler()
    redis_mock = AsyncMock()
    scheduler._redis = redis_mock

    with patch("modules.collector.scheduler.is_trading_day", return_value=False):
        await scheduler._run_scheduled_pipeline()

    # Redis에 PIPELINE_RUNNING_KEY 설정하지 않음 (파이프라인 미실행)
    redis_mock.get.assert_not_awaited()
    redis_mock.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_market_open_skips_non_trading_day():
    """비거래일에 _market_open 스킵."""
    scheduler = _make_scheduler()

    with patch("modules.collector.scheduler.is_trading_day", return_value=False):
        await scheduler._market_open()

    # WS 연결 시도 없음
    scheduler._ws_client.connect.assert_not_awaited()
