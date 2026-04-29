"""WS 안정화 통합 테스트 — 환경별 구독 제한 + 2차 스크리닝 WS 가드 + 체결강도 웜업."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.clients.kis_config import PAPER
from modules.collector.trade_strength import TradeStrengthCalculator


# ── TradeStrengthCalculator 웜업 테스트 ──────────────────


def test_trade_strength_warmup():
    """set_warmup 후 get_strength가 50.0을 반환하고, 만료 후 정상값 복귀."""
    tc = TradeStrengthCalculator()
    tc.set_warmup("005930", duration=5.0)

    # 웜업 중
    assert tc.get_strength("005930") == 50.0

    # 만료 시뮬레이션: now를 웜업 종료 이후로 전달
    future = time.time() + 10.0
    # 데이터 없으므로 여전히 50.0 (중립)
    assert tc.get_strength("005930", now=future) == 50.0
    # 웜업 키는 만료 후 삭제되어야 함
    assert "005930" not in tc._warmup_until


def test_trade_strength_set_warmup_all():
    """set_warmup_all이 현재 데이터가 있는 모든 종목에 웜업을 적용한다."""
    tc = TradeStrengthCalculator()
    now = time.time()
    # 두 종목에 데이터 추가
    tc.add_execution("005930", now, 100, "2")
    tc.add_execution("000660", now, 200, "1")

    tc.set_warmup_all(duration=5.0)

    assert tc.get_strength("005930") == 50.0
    assert tc.get_strength("000660") == 50.0


def test_trade_strength_reset_clears_warmup():
    """reset() 호출 시 _warmup_until 항목도 함께 제거된다."""
    tc = TradeStrengthCalculator()
    tc.set_warmup("005930", duration=60.0)
    assert "005930" in tc._warmup_until

    tc.reset("005930")
    assert "005930" not in tc._warmup_until


# ── CollectorScheduler 2차 스크리닝 WS 가드 테스트 ──────


def _make_scheduler():
    """최소 의존성으로 CollectorScheduler 인스턴스 생성."""
    from modules.collector.scheduler import CollectorScheduler

    session_factory = AsyncMock()
    rest_client = MagicMock()
    ws_client = MagicMock()
    ws_client.connected = False
    ws_manager = MagicMock()
    ws_manager.count = 0
    trade_strength = TradeStrengthCalculator()
    redis = AsyncMock()

    scheduler = CollectorScheduler(
        session_factory=session_factory,
        rest_client=rest_client,
        ws_manager=ws_manager,
        trade_strength=trade_strength,
        ws_client=ws_client,
        redis=redis,
    )
    return scheduler


@pytest.mark.asyncio
async def test_scheduler_secondary_screen_ws_guard():
    """WS 미연결 시 _secondary_screen이 스킵 결과를 반환한다."""
    scheduler = _make_scheduler()
    scheduler._ws_client.connected = False

    result = await scheduler._secondary_screen()

    assert result["skipped"] is True
    assert result["reason"] == "ws_disconnected"
    assert scheduler._secondary_skip_count == 1


@pytest.mark.asyncio
async def test_scheduler_secondary_screen_skip_counter():
    """연속 3회 스킵 시 텔레그램 경고를 발송하고, 이후 10회마다 재발송한다."""
    scheduler = _make_scheduler()
    scheduler._ws_client.connected = False

    mock_bot = AsyncMock()
    scheduler._telegram_bot = mock_bot

    # 3회 스킵 → 첫 경고 발송
    for _ in range(3):
        await scheduler._secondary_screen()

    assert scheduler._secondary_skip_count == 3
    assert mock_bot.send_notification.await_count == 1

    # 4~9회 스킵 → 추가 발송 없음
    for _ in range(6):
        await scheduler._secondary_screen()

    assert mock_bot.send_notification.await_count == 1

    # 10회 스킵 → 재발송
    await scheduler._secondary_screen()
    assert mock_bot.send_notification.await_count == 2


# ── WSSubscriptionManager 환경 기반 상한 테스트 ──────────


@pytest.mark.asyncio
async def test_ws_manager_env_max_subscriptions():
    """PAPER 환경에서 WSSubscriptionManager가 20종목 상한을 적용한다.

    기존 기대값(25)이 실제 PAPER.max_ws_subscriptions=20과 불일치하여 수정.
    """
    from modules.collector.ws_manager import WSSubscriptionManager
    from core.clients.kis_ws import KISWebSocketClient
    from core.clients.token_manager import KISTokenManager

    token_manager = AsyncMock(spec=KISTokenManager)
    ws_client = KISWebSocketClient(env=PAPER, token_manager=token_manager)

    manager = WSSubscriptionManager(ws_client, max_subscriptions=PAPER.max_ws_subscriptions)
    assert manager._max == 20

    ws_mock = AsyncMock()
    ws_mock.send = AsyncMock()
    ws_client._ws = ws_mock
    ws_client._connected = True
    ws_client._approval_key = "test-key"

    # 20종목 구독
    for i in range(20):
        code = f"{i:06d}"
        result = await manager.subscribe(code, priority=float(i))
        assert result is True, f"종목 {code} 구독 실패"

    assert manager.count == 20

    # 21번째 종목: 우선순위 낮으면 거부
    result = await manager.subscribe("999999", priority=0.0)
    assert result is False
    assert manager.count == 20
