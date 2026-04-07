"""시스템 경고 알림 테스트 — send_system_alert 메서드 동작 확인."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.notifier.manager import NotifierManager

pytestmark = pytest.mark.asyncio


def _make_manager(bot=None) -> NotifierManager:
    """테스트용 NotifierManager 생성."""
    approval = MagicMock()
    session_factory = MagicMock()
    return NotifierManager(bot, approval, session_factory)


async def test_send_system_alert_emergency_stop():
    """send_system_alert('emergency_stop', ...) 호출 시 텔레그램 메시지가 발송되어야 한다."""
    mock_bot = MagicMock()
    mock_bot.format_system_alert = MagicMock(return_value="⛔ [비상 정지]\n손실 한도 초과")
    mock_bot.send_notification = AsyncMock()

    manager = _make_manager(bot=mock_bot)

    await manager.send_system_alert("emergency_stop", "손실 한도 초과")

    mock_bot.format_system_alert.assert_called_once_with("emergency_stop", "손실 한도 초과")
    mock_bot.send_notification.assert_awaited_once_with("⛔ [비상 정지]\n손실 한도 초과")


async def test_send_system_alert_pipeline_failure():
    """send_system_alert('pipeline_failure', ...) 호출 시 파이프라인 실패 포맷 메시지 발송."""
    mock_bot = MagicMock()
    expected_text = "<b>🚨 [파이프라인 실패]</b>\n수집 실패"
    mock_bot.format_system_alert = MagicMock(return_value=expected_text)
    mock_bot.send_notification = AsyncMock()

    manager = _make_manager(bot=mock_bot)

    await manager.send_system_alert("pipeline_failure", "수집 실패")

    mock_bot.format_system_alert.assert_called_once_with("pipeline_failure", "수집 실패")
    mock_bot.send_notification.assert_awaited_once_with(expected_text)


async def test_send_system_alert_skips_when_bot_is_none():
    """텔레그램 봇 미설정(None) 시 에러 없이 스킵되어야 한다."""
    manager = _make_manager(bot=None)

    # 예외 없이 정상 실행되어야 함
    await manager.send_system_alert("emergency_stop", "손실 한도 초과")


async def test_format_system_alert_emergency_stop():
    """format_system_alert('emergency_stop', ...) 결과가 올바른 HTML 포맷이어야 한다."""
    from modules.notifier.telegram_bot import TelegramBot

    # TelegramBot 내부 _bot 없이 포맷 메서드만 테스트
    bot = object.__new__(TelegramBot)

    result = bot.format_system_alert("emergency_stop", "일일 손실 4% 초과")

    assert "⛔" in result
    assert "[비상 정지]" in result
    assert "일일 손실 4% 초과" in result
    assert "<b>" in result


async def test_format_system_alert_pipeline_failure():
    """format_system_alert('pipeline_failure', ...) 결과가 올바른 HTML 포맷이어야 한다."""
    from modules.notifier.telegram_bot import TelegramBot

    bot = object.__new__(TelegramBot)

    result = bot.format_system_alert("pipeline_failure", "수집 단계 오류")

    assert "🚨" in result
    assert "[파이프라인 실패]" in result
    assert "수집 단계 오류" in result


async def test_format_system_alert_unknown_type():
    """알 수 없는 alert_type은 기본 포맷으로 처리되어야 한다."""
    from modules.notifier.telegram_bot import TelegramBot

    bot = object.__new__(TelegramBot)

    result = bot.format_system_alert("unknown_type", "상세 내용")

    assert "상세 내용" in result
