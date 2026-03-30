"""텔레그램 봇 테스트 — 외부 API 호출 없이 로직만 검증한다."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from modules.notifier.telegram_bot import TelegramBot
from modules.trading.strategy import TradeSignalData


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_signal() -> TradeSignalData:
    """테스트용 매매 신호 데이터."""
    return TradeSignalData(
        stock_code="005930",
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=0.85,
        reason={"rsi": 72, "volume_surge": True},
        entry_price=73000,
        stop_loss=71540,
        take_profit=75190,
    )


@pytest.fixture
def mock_approval_manager() -> MagicMock:
    """ApprovalManager 목업."""
    return MagicMock()


@pytest.fixture
def telegram_bot(mock_approval_manager) -> TelegramBot:
    """TelegramBot 인스턴스 (실제 Bot 호출 없음)."""
    bot = TelegramBot.__new__(TelegramBot)
    # 내부 Bot 인스턴스를 목업으로 교체
    bot._bot = AsyncMock()
    bot._authorized_chat_id = 123456789
    bot._approval_manager = mock_approval_manager
    return bot


# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------

def test_format_signal_message(telegram_bot, sample_signal):
    """format_signal_message: 신호 데이터를 HTML 메시지와 인라인 키보드로 포맷팅한다."""
    token = "test-token-uuid"
    text, keyboard = telegram_bot.format_signal_message(sample_signal, quantity=10, token=token)

    # HTML 메시지 내용 검증
    assert "005930" in text
    assert "매수" in text
    assert "10" in text  # 수량
    assert "73,000" in text  # 진입가 (천 단위 구분)
    assert "85%" in text  # 신뢰도 퍼센트
    assert "momentum_breakout" in text
    assert "rsi" in text  # 근거 포함

    # 인라인 버튼 구성 검증
    buttons = keyboard.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].callback_data == f"approve:{token}"
    assert buttons[1].callback_data == f"reject:{token}"
    assert "승인" in buttons[0].text
    assert "거부" in buttons[1].text


def test_format_fill_message(telegram_bot):
    """format_fill_message: 체결 데이터를 HTML 메시지로 포맷팅한다."""
    text = telegram_bot.format_fill_message(
        stock_code="005930",
        quantity=10,
        price=73000,
        order_type="buy",
    )

    assert "005930" in text
    assert "매수" in text
    assert "10" in text
    assert "73,000" in text
    # 총금액 = 10 * 73,000 = 730,000
    assert "730,000" in text


def test_format_fill_message_sell(telegram_bot):
    """format_fill_message: 매도 방향도 정확히 포맷팅한다."""
    text = telegram_bot.format_fill_message(
        stock_code="035720",
        quantity=5,
        price=50000,
        order_type="sell",
    )

    assert "매도" in text
    assert "250,000" in text  # 5 * 50,000


def test_format_daily_report(telegram_bot):
    """format_daily_report: 일일 리포트 HTML 포맷팅을 검증한다."""
    stats = {
        "total_trades": 5,
        "realized_pnl": 150000,
        "win_rate": 0.6,
        "positions": ["005930: 매수 10주", "035720: 매수 5주"],
    }
    text = telegram_bot.format_daily_report(stats)

    assert "5건" in text
    assert "150,000" in text  # 실현 손익
    assert "60%" in text  # 승률
    assert "005930" in text  # 포지션 항목
    assert "035720" in text


def test_format_daily_report_empty_positions(telegram_bot):
    """format_daily_report: 포지션이 없을 때 '보유 포지션 없음' 출력."""
    stats = {
        "total_trades": 0,
        "realized_pnl": 0,
        "win_rate": 0.0,
        "positions": [],
    }
    text = telegram_bot.format_daily_report(stats)

    assert "보유 포지션 없음" in text


def test_format_daily_report_negative_pnl(telegram_bot):
    """format_daily_report: 손실(음수) 손익도 올바르게 표시한다."""
    stats = {
        "total_trades": 3,
        "realized_pnl": -50000,
        "win_rate": 0.33,
        "positions": [],
    }
    text = telegram_bot.format_daily_report(stats)

    assert "-50,000" in text


def test_build_approval_keyboard(telegram_bot, sample_signal):
    """format_signal_message의 인라인 키보드 구성을 상세 검증한다."""
    token = "approval-uuid-1234"
    _, keyboard = telegram_bot.format_signal_message(sample_signal, quantity=1, token=token)

    rows = keyboard.inline_keyboard
    assert len(rows) == 1  # 한 줄에 두 버튼

    approve_btn, reject_btn = rows[0]
    assert approve_btn.callback_data == f"approve:{token}"
    assert reject_btn.callback_data == f"reject:{token}"


def test_parse_callback_data(telegram_bot):
    """parse_callback_data: 콜백 문자열에서 action과 token을 올바르게 파싱한다."""
    action, token = telegram_bot.parse_callback_data("approve:some-uuid-1234")
    assert action == "approve"
    assert token == "some-uuid-1234"

    action, token = telegram_bot.parse_callback_data("reject:another-uuid-5678")
    assert action == "reject"
    assert token == "another-uuid-5678"


def test_parse_callback_data_with_colon_in_token(telegram_bot):
    """parse_callback_data: 토큰 내부에 콜론이 있어도 action만 분리한다."""
    action, token = telegram_bot.parse_callback_data("approve:part1:part2")
    assert action == "approve"
    assert token == "part1:part2"


def test_is_authorized_chat(telegram_bot):
    """is_authorized: 화이트리스트 chat_id 검증."""
    # 허용된 chat_id
    assert telegram_bot.is_authorized(123456789) is True

    # 허용되지 않은 chat_id
    assert telegram_bot.is_authorized(999999999) is False
    assert telegram_bot.is_authorized(0) is False
