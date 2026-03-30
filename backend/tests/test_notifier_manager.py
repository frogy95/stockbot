"""NotifierManager 테스트 — TelegramBot과 ApprovalManager는 mock 처리."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from modules.notifier.manager import NotifierManager
from modules.trading.strategy import TradeSignalData

# ── pytest-asyncio strict 모드 설정 ─────────────────────────────────────────
pytestmark = pytest.mark.asyncio


# ── 공통 픽스처 ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_signal():
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
def mock_telegram():
    """TelegramBot mock 객체."""
    bot = MagicMock()
    bot.send_signal_alert = AsyncMock(return_value=9001)  # message_id
    bot.send_notification = AsyncMock(return_value=9002)
    bot.edit_message = AsyncMock()
    bot.format_fill_message = MagicMock(return_value="체결 알림 텍스트")
    bot.format_daily_report = MagicMock(return_value="일일 리포트 텍스트")
    return bot


@pytest.fixture
def mock_approval():
    """ApprovalManager mock 객체."""
    mgr = MagicMock()
    mgr.create_approval = AsyncMock(return_value="test-token-uuid")
    mgr.validate_approval = AsyncMock(
        return_value={
            "signal": {
                "stock_code": "005930",
                "signal_type": "buy",
                "strategy_name": "momentum_breakout",
                "confidence": 0.85,
                "reason": {"rsi": 72},
                "entry_price": 73000,
                "stop_loss": 71540,
                "take_profit": 75190,
            },
            "quantity": 10,
        }
    )
    return mgr


@pytest.fixture
def mock_session_factory():
    """SQLAlchemy async session_factory mock."""
    return MagicMock()


@pytest_asyncio.fixture
async def manager(mock_telegram, mock_approval, mock_session_factory):
    """NotifierManager 인스턴스 (의존성 전부 mock)."""
    return NotifierManager(mock_telegram, mock_approval, mock_session_factory)


# ── 테스트 케이스 ─────────────────────────────────────────────────────────────

async def test_notify_signal(manager, mock_approval, mock_telegram, sample_signal):
    """신호 발생 시 승인 토큰 생성 + 텔레그램 발송 호출 확인."""
    token = await manager.notify_signal(sample_signal, quantity=10, timeout_sec=60)

    # 승인 토큰 생성 호출 확인
    mock_approval.create_approval.assert_awaited_once_with(sample_signal, 10, 60)

    # 텔레그램 신호 알림 발송 호출 확인
    mock_telegram.send_signal_alert.assert_awaited_once_with(sample_signal, 10, "test-token-uuid")

    # 반환된 토큰과 pending_messages 등록 확인
    assert token == "test-token-uuid"
    assert manager._pending_messages[token] == 9001


async def test_notify_fill(manager, mock_telegram):
    """체결 시 텔레그램 알림 발송 확인."""
    await manager.notify_fill(
        stock_code="005930",
        quantity=10,
        price=73000,
        order_type="buy",
    )

    # format_fill_message 호출 확인
    mock_telegram.format_fill_message.assert_called_once_with("005930", 10, 73000, "buy")

    # send_notification 발송 확인
    mock_telegram.send_notification.assert_awaited_once_with("체결 알림 텍스트")


async def test_notify_rejection(manager, mock_approval, mock_telegram, sample_signal):
    """거부 시 메시지 수정 확인."""
    # pending 메시지 사전 등록
    token = "reject-token"
    manager._pending_messages[token] = 9999

    result = await manager.handle_approval(token, action="reject")

    # validate_approval 호출 확인
    mock_approval.validate_approval.assert_awaited_once_with(token)

    # 메시지 수정 — 거부 텍스트 확인
    mock_telegram.edit_message.assert_awaited_once_with(9999, "❌ 거부됨")

    # pending_messages에서 제거 확인
    assert token not in manager._pending_messages

    # 결과 반환 확인
    assert result is not None
    assert result["action"] == "reject"
    assert result["quantity"] == 10


async def test_notify_timeout(manager, mock_telegram, sample_signal):
    """승인 만료 시 메시지 수정 + pending 제거 확인."""
    token = "timeout-token"
    manager._pending_messages[token] = 8888

    await manager.notify_timeout(token)

    # 메시지 수정 호출 확인
    mock_telegram.edit_message.assert_awaited_once_with(8888, "⏰ 승인 시간 만료")

    # pending_messages에서 제거 확인
    assert token not in manager._pending_messages


async def test_notify_timeout_missing_token(manager, mock_telegram, caplog):
    """pending에 없는 토큰으로 timeout 호출 시 경고 로그 + 에러 미발생 확인."""
    import logging

    with caplog.at_level(logging.WARNING, logger="modules.notifier.manager"):
        await manager.notify_timeout("nonexistent-token")

    # edit_message 호출 안됨
    mock_telegram.edit_message.assert_not_awaited()

    # 경고 로그 확인
    assert any("pending 메시지 없음" in r.message for r in caplog.records)


async def test_send_daily_report(manager, mock_telegram):
    """일일 리포트 데이터 조합 + 발송 확인."""
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock

    from core.models.trading import TradeHistory

    # TradeHistory 레코드 mock 생성
    def make_record(pnl: int) -> MagicMock:
        r = MagicMock(spec=TradeHistory)
        r.realized_pnl = pnl
        r.exit_time = datetime.now(tz=timezone.utc)
        return r

    records = [make_record(5000), make_record(-2000), make_record(3000)]

    # scalars().all() 체인 mock
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = records

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def fake_factory():
        yield mock_session

    await manager.send_daily_report(session_factory=fake_factory)

    # format_daily_report 호출 인수 확인
    call_args = mock_telegram.format_daily_report.call_args
    stats = call_args[0][0]
    assert stats["total_trades"] == 3
    assert stats["realized_pnl"] == 6000  # 5000 - 2000 + 3000
    assert abs(stats["win_rate"] - 0.6666) < 0.01  # 2/3 승 (0.0~1.0 범위)

    # send_notification 발송 확인
    mock_telegram.send_notification.assert_awaited_once_with("일일 리포트 텍스트")
