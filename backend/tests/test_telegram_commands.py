"""텔레그램 조회 명령어 테스트."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.notifier.commands import CommandHandler


@pytest.fixture
def mock_deps():
    session_factory = MagicMock()
    session = AsyncMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    redis_client = AsyncMock()
    telegram_bot = MagicMock()
    telegram_bot.send_notification = AsyncMock()

    return session_factory, session, redis_client, telegram_bot


@pytest.fixture
def handler(mock_deps):
    session_factory, _, redis_client, telegram_bot = mock_deps
    return CommandHandler(session_factory, redis_client, telegram_bot)


@pytest.mark.asyncio
async def test_status_command(handler, mock_deps):
    """/status 명령어: 활성 포지션 요약."""
    _, session, _, _ = mock_deps

    # 포지션 없음
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    result = await handler.handle_status(12345)
    assert "활성 포지션 없음" in result


@pytest.mark.asyncio
async def test_status_command_with_positions(handler, mock_deps):
    """/status 명령어: 포지션 있을 때."""
    _, session, _, _ = mock_deps

    pos = MagicMock()
    pos.stock_code = "005930"
    pos.quantity = 10
    pos.avg_price = 73000
    pos.current_price = 74000
    pos.unrealized_pnl = 10000

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pos]
    session.execute = AsyncMock(return_value=mock_result)

    result = await handler.handle_status(12345)
    assert "005930" in result


@pytest.mark.asyncio
async def test_today_command(handler, mock_deps):
    """/today 명령어: 오늘 손익 요약."""
    _, session, _, _ = mock_deps

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    result = await handler.handle_today(12345)
    assert "거래 기록 없음" in result


@pytest.mark.asyncio
async def test_mode_command(handler, mock_deps):
    """/mode 명령어: 현재 모드 표시."""
    result = await handler.handle_mode(12345)
    assert "모드" in result


@pytest.mark.asyncio
async def test_help_command(handler, mock_deps):
    """/help 명령어: 명령어 목록."""
    result = await handler.handle_help(12345)
    assert "/status" in result
    assert "/today" in result
    assert "/mode" in result
    assert "/help" in result


@pytest.mark.asyncio
async def test_dispatch_unknown_command(handler):
    """알 수 없는 명령어 -> help 반환."""
    result = await handler.dispatch("/unknown", 12345)
    assert "/help" in result
