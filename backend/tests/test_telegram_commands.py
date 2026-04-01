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


@pytest.mark.asyncio
async def test_pipeline_command_no_scheduler(mock_deps):
    """/pipeline: 스케줄러 미주입 시 경고 반환."""
    session_factory, _, redis_client, telegram_bot = mock_deps
    handler = CommandHandler(session_factory, redis_client, telegram_bot, collector_scheduler=None)

    result = await handler.handle_pipeline(12345)
    assert "스케줄러 미초기화" in result


@pytest.mark.asyncio
async def test_pipeline_command_with_status(mock_deps):
    """/pipeline: 단계별 상태 포함."""
    import json
    from modules.collector.scheduler import PIPELINE_STATUS_KEY, PIPELINE_HEALTHY_KEY
    from tests.conftest import FakeRedis

    session_factory, _, _, telegram_bot = mock_deps
    fake_redis = FakeRedis()
    await fake_redis.set(PIPELINE_HEALTHY_KEY, "true")
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps({
        "premarket": {"status": "success", "timestamp": "2026-04-02T08:01:00+09:00"},
        "primary_screen": {"status": "success", "timestamp": "2026-04-02T08:11:00+09:00"},
    }))

    mock_scheduler = MagicMock()
    mock_scheduler.get_pipeline_status = AsyncMock(return_value={
        "premarket": {"status": "success", "timestamp": "2026-04-02T08:01:00+09:00"},
        "primary_screen": {"status": "success", "timestamp": "2026-04-02T08:11:00+09:00"},
    })

    handler = CommandHandler(session_factory, fake_redis, telegram_bot, collector_scheduler=mock_scheduler)
    result = await handler.handle_pipeline(12345)

    assert "파이프라인" in result
    assert "✅" in result
    assert "/recover" in result


@pytest.mark.asyncio
async def test_recover_command_starts_pipeline(mock_deps):
    """/recover: 파이프라인 실행 중 아닐 때 복구 시작."""
    from tests.conftest import FakeRedis

    session_factory, _, _, telegram_bot = mock_deps
    fake_redis = FakeRedis()

    mock_scheduler = MagicMock()
    mock_scheduler.run_premarket_pipeline = AsyncMock(return_value={"completed": True})

    handler = CommandHandler(session_factory, fake_redis, telegram_bot, collector_scheduler=mock_scheduler)
    result = await handler.handle_recover(12345)

    assert "복구 시작" in result
    assert "/pipeline" in result


@pytest.mark.asyncio
async def test_recover_command_rejects_duplicate(mock_deps):
    """/recover: 이미 실행 중이면 거부."""
    from modules.collector.scheduler import PIPELINE_RUNNING_KEY
    from tests.conftest import FakeRedis

    session_factory, _, _, telegram_bot = mock_deps
    fake_redis = FakeRedis()
    await fake_redis.set(PIPELINE_RUNNING_KEY, "true")

    mock_scheduler = MagicMock()
    handler = CommandHandler(session_factory, fake_redis, telegram_bot, collector_scheduler=mock_scheduler)
    result = await handler.handle_recover(12345)

    assert "이미 실행 중" in result


@pytest.mark.asyncio
async def test_help_includes_new_commands(mock_deps):
    """/help에 /pipeline, /recover 포함."""
    session_factory, _, redis_client, telegram_bot = mock_deps
    handler = CommandHandler(session_factory, redis_client, telegram_bot)

    result = await handler.handle_help(12345)
    assert "/pipeline" in result
    assert "/recover" in result
