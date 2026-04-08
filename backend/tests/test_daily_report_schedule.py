"""일일 마감 리포트 스케줄 연결 테스트 — _market_close 호출 시 send_daily_report 발송 확인."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.collector.scheduler import CollectorScheduler

pytestmark = pytest.mark.asyncio


def _make_scheduler() -> CollectorScheduler:
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
        redis=AsyncMock(),
    )


async def test_market_close_calls_send_daily_report():
    """_market_close 호출 시 notifier_manager.send_daily_report가 호출되어야 한다."""
    scheduler = _make_scheduler()

    mock_notifier = MagicMock()
    mock_notifier.send_daily_report = AsyncMock()
    scheduler.set_notifier_manager(mock_notifier)

    await scheduler._market_close()

    mock_notifier.send_daily_report.assert_awaited_once()


async def test_market_close_skips_report_when_notifier_is_none():
    """notifier_manager가 None이면 에러 없이 스킵되어야 한다."""
    scheduler = _make_scheduler()
    # set_notifier_manager를 호출하지 않음 → _notifier_manager는 None

    # 예외 없이 정상 실행되어야 함
    await scheduler._market_close()
