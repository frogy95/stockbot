"""WS 구독 매니저 테스트."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from modules.collector.ws_manager import WSSubscriptionManager


def _make_mock_ws(connected: bool = True, ws_is_none: bool = False):
    """Mock KISWebSocketClient."""
    mock = MagicMock()
    mock._ws = None if ws_is_none else MagicMock()
    mock.connected = connected
    mock.subscribe = AsyncMock()
    mock.unsubscribe = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_subscribe_stock():
    """종목 구독 추가."""
    ws = _make_mock_ws()
    mgr = WSSubscriptionManager(ws, max_subscriptions=35)

    result = await mgr.subscribe("005930")

    assert result is True
    assert mgr.count == 1
    # 체결 + 호가 2개 tr_id
    assert ws.subscribe.call_count == 2


@pytest.mark.asyncio
async def test_unsubscribe_stock():
    """종목 구독 해제."""
    ws = _make_mock_ws()
    mgr = WSSubscriptionManager(ws, max_subscriptions=35)

    await mgr.subscribe("005930")
    result = await mgr.unsubscribe("005930")

    assert result is True
    assert mgr.count == 0


@pytest.mark.asyncio
async def test_max_subscription_limit():
    """35종목 상한 초과 시 거부."""
    ws = _make_mock_ws()
    mgr = WSSubscriptionManager(ws, max_subscriptions=3)

    await mgr.subscribe("001", priority=1.0)
    await mgr.subscribe("002", priority=2.0)
    await mgr.subscribe("003", priority=3.0)

    # 우선순위 0은 가장 낮은 종목(001, 1.0)보다 낮으므로 거부
    result = await mgr.subscribe("004", priority=0.0)

    assert result is False
    assert mgr.count == 3


@pytest.mark.asyncio
async def test_subscribe_duplicate():
    """중복 구독 시 무시."""
    ws = _make_mock_ws()
    mgr = WSSubscriptionManager(ws, max_subscriptions=35)

    await mgr.subscribe("005930")
    initial_call_count = ws.subscribe.call_count

    result = await mgr.subscribe("005930")

    assert result is True
    assert mgr.count == 1
    # 추가 WS subscribe 호출 없음
    assert ws.subscribe.call_count == initial_call_count


@pytest.mark.asyncio
async def test_replace_lowest_priority():
    """상한 초과 시 우선순위 기반 로테이션."""
    ws = _make_mock_ws()
    mgr = WSSubscriptionManager(ws, max_subscriptions=2)

    await mgr.subscribe("001", priority=1.0)
    await mgr.subscribe("002", priority=3.0)

    # 우선순위 2.0 > 001의 1.0 → 001 교체
    result = await mgr.subscribe("003", priority=2.0)

    assert result is True
    assert mgr.count == 2
    assert "001" not in mgr.get_subscribed_stocks()
    assert "003" in mgr.get_subscribed_stocks()


@pytest.mark.asyncio
async def test_concurrent_subscribe():
    """asyncio.Lock으로 동시 구독 경쟁 조건 방지."""
    ws = _make_mock_ws()
    mgr = WSSubscriptionManager(ws, max_subscriptions=2)

    # 동시에 3개 구독 시도 (동일 우선순위 → 로테이션 불가)
    results = await asyncio.gather(
        mgr.subscribe("001", priority=1.0),
        mgr.subscribe("002", priority=1.0),
        mgr.subscribe("003", priority=1.0),
    )

    # Lock이 직렬화하므로 2개만 성공, 1개는 상한 초과로 실패
    assert sum(results) == 2
    assert mgr.count == 2


@pytest.mark.asyncio
async def test_ws_none_guard():
    """_ws가 None일 때 에러 없이 False 반환 (미해결 #3)."""
    ws = _make_mock_ws(connected=False, ws_is_none=True)
    mgr = WSSubscriptionManager(ws, max_subscriptions=35)

    result_sub = await mgr.subscribe("005930")
    result_unsub = await mgr.unsubscribe("005930")

    assert result_sub is False
    assert result_unsub is False


@pytest.mark.asyncio
async def test_get_subscribed_stocks():
    """현재 구독 종목 목록 조회."""
    ws = _make_mock_ws()
    mgr = WSSubscriptionManager(ws, max_subscriptions=35)

    await mgr.subscribe("005930")
    await mgr.subscribe("035720")

    stocks = mgr.get_subscribed_stocks()
    assert set(stocks) == {"005930", "035720"}


@pytest.mark.asyncio
async def test_ws_manager_guard_or_condition():
    """한쪽만 비정상이어도 구독 차단 (or 조건 검증)."""
    # Case 1: _ws 유효하지만 connected=False
    ws1 = _make_mock_ws(connected=False, ws_is_none=False)
    mgr1 = WSSubscriptionManager(ws1, max_subscriptions=35)
    result1 = await mgr1.subscribe("005930")
    assert result1 is False

    # Case 2: _ws=None이지만 connected=True (비정상 상태)
    ws2 = _make_mock_ws(connected=True, ws_is_none=True)
    mgr2 = WSSubscriptionManager(ws2, max_subscriptions=35)
    result2 = await mgr2.subscribe("005930")
    assert result2 is False

    # Case 3: unsubscribe도 동일하게 차단
    ws3 = _make_mock_ws(connected=False, ws_is_none=False)
    mgr3 = WSSubscriptionManager(ws3, max_subscriptions=35)
    result3 = await mgr3.unsubscribe("005930")
    assert result3 is False


@pytest.mark.asyncio
async def test_unsubscribe_all():
    """전체 구독 해제."""
    ws = _make_mock_ws()
    mgr = WSSubscriptionManager(ws, max_subscriptions=35)

    await mgr.subscribe("005930")
    await mgr.subscribe("035720")
    await mgr.unsubscribe_all()

    assert mgr.count == 0
