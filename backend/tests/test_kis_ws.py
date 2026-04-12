"""KISWebSocketClient 단위 테스트."""

import asyncio
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.clients.kis_config import PAPER
from core.clients.kis_ws import KISWebSocketClient, MAX_RECONNECT_ATTEMPTS


# ── 공통 fixture ──────────────────────────────────────────


@pytest.fixture
def token_manager():
    """KISTokenManager mock."""
    tm = AsyncMock()
    tm.get_approval_key.return_value = "test-approval-key"
    return tm


@pytest.fixture
def ws_mock():
    """websockets.WebSocketClientProtocol mock."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock(side_effect=asyncio.CancelledError)
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def client(token_manager):
    """KISWebSocketClient 인스턴스."""
    return KISWebSocketClient(env=PAPER, token_manager=token_manager)


# ── connect 테스트 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_uses_approval_key(client, token_manager, ws_mock):
    """connect() 시 approval_key를 요청하고 WebSocket 연결한다."""
    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    token_manager.get_approval_key.assert_awaited_once()
    assert client.connected is True
    assert client._approval_key == "test-approval-key"

    # 정리
    await client.disconnect()


@pytest.mark.asyncio
async def test_connect_websocket_url(client, token_manager, ws_mock):
    """connect() 시 env.ws_url로 WebSocket 연결한다."""
    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock) as mock_connect:
        await client.connect()

    mock_connect.assert_awaited_once_with(PAPER.ws_url, ping_interval=30, ping_timeout=10, open_timeout=10)

    await client.disconnect()


# ── disconnect 테스트 ─────────────────────────────────────


@pytest.mark.asyncio
async def test_disconnect_closes_connection(client, token_manager, ws_mock):
    """disconnect() 시 WebSocket을 닫고 connected를 False로 설정한다."""
    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    await client.disconnect()

    ws_mock.close.assert_awaited_once()
    assert client.connected is False
    assert client._ws is None
    assert client._receive_task is None


# ── subscribe 테스트 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_message_format(client, token_manager, ws_mock):
    """subscribe() 시 올바른 구독 메시지를 전송한다."""
    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    await client.subscribe("005930", "H0STCNT0")

    # 전송된 메시지 검증
    sent_raw = ws_mock.send.call_args[0][0]
    sent = json.loads(sent_raw)

    assert sent["header"]["approval_key"] == "test-approval-key"
    assert sent["header"]["custtype"] == "P"
    assert sent["header"]["tr_type"] == "1"
    assert sent["header"]["content-type"] == "utf-8"
    assert sent["body"]["input"]["tr_id"] == "H0STCNT0"
    assert sent["body"]["input"]["tr_key"] == "005930"

    await client.disconnect()


@pytest.mark.asyncio
async def test_subscribe_adds_to_subscriptions(client, token_manager, ws_mock):
    """subscribe() 시 _subscriptions에 추가된다."""
    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    await client.subscribe("005930", "H0STCNT0")

    assert ("005930", "H0STCNT0") in client._subscriptions
    assert client.subscription_count == 1

    await client.disconnect()


# ── unsubscribe 테스트 ────────────────────────────────────


@pytest.mark.asyncio
async def test_unsubscribe_message_format(client, token_manager, ws_mock):
    """unsubscribe() 시 tr_type=2로 메시지를 전송한다."""
    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    # 먼저 구독
    await client.subscribe("005930", "H0STCNT0")
    # 구독 해제
    await client.unsubscribe("005930", "H0STCNT0")

    # 마지막 전송 메시지 검증 (unsubscribe)
    sent_raw = ws_mock.send.call_args[0][0]
    sent = json.loads(sent_raw)

    assert sent["header"]["tr_type"] == "2"
    assert sent["body"]["input"]["tr_id"] == "H0STCNT0"
    assert sent["body"]["input"]["tr_key"] == "005930"

    await client.disconnect()


@pytest.mark.asyncio
async def test_unsubscribe_removes_from_subscriptions(client, token_manager, ws_mock):
    """unsubscribe() 시 _subscriptions에서 제거된다."""
    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    await client.subscribe("005930", "H0STCNT0")
    assert client.subscription_count == 1

    await client.unsubscribe("005930", "H0STCNT0")
    assert client.subscription_count == 0
    assert ("005930", "H0STCNT0") not in client._subscriptions

    await client.disconnect()


# ── _on_message 테스트 ────────────────────────────────────


@pytest.mark.asyncio
async def test_on_message_json_logs_server_response(client, caplog):
    """JSON 메시지 수신 시 서버 응답을 로깅한다."""
    server_resp = json.dumps({"header": {"tr_id": "H0STCNT0"}, "body": {"msg": "OK"}})

    import logging
    with caplog.at_level(logging.INFO, logger="core.clients.kis_ws"):
        await client._on_message(server_resp)

    assert "서버 응답" in caplog.text


@pytest.mark.asyncio
async def test_on_message_pipe_data_calls_callback(client):
    """파이프 구분 메시지 수신 시 on_data 콜백을 호출한다."""
    callback = MagicMock()
    client.set_on_data(callback)

    pipe_msg = "H0STCNT0|001|005930|12345|67890"
    await client._on_message(pipe_msg)

    callback.assert_called_once_with("H0STCNT0", pipe_msg)


@pytest.mark.asyncio
async def test_on_message_pipe_data_no_callback(client):
    """콜백 미등록 시 파이프 메시지를 무시한다 (에러 없음)."""
    pipe_msg = "H0STCNT0|001|005930|12345"
    await client._on_message(pipe_msg)  # 에러 없이 통과


# ── set_on_data 테스트 ────────────────────────────────────


def test_set_on_data_registers_callback(client):
    """set_on_data()로 콜백을 등록한다."""
    callback = MagicMock()
    client.set_on_data(callback)
    assert client._on_data is callback


# ── subscription tracking 테스트 ──────────────────────────


@pytest.mark.asyncio
async def test_multiple_subscriptions(client, token_manager, ws_mock):
    """여러 종목 구독 시 모두 _subscriptions에 추적된다."""
    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    await client.subscribe("005930", "H0STCNT0")
    await client.subscribe("000660", "H0STCNT0")
    await client.subscribe("005930", "H0STASP0")

    assert client.subscription_count == 3
    assert ("005930", "H0STCNT0") in client._subscriptions
    assert ("000660", "H0STCNT0") in client._subscriptions
    assert ("005930", "H0STASP0") in client._subscriptions

    await client.disconnect()


# ── _reconnect 테스트 ─────────────────────────────────────


@pytest.mark.asyncio
async def test_reconnect_resubscribes(client, token_manager, ws_mock):
    """재연결 시 기존 구독을 복원하고 종목 간 딜레이가 삽입된다."""
    new_ws = AsyncMock()
    new_ws.send = AsyncMock()
    new_ws.recv = AsyncMock(side_effect=asyncio.CancelledError)
    new_ws.close = AsyncMock()

    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    # 구독 추가 (2개 종목)
    await client.subscribe("005930", "H0STCNT0")
    await client.subscribe("000660", "H0STCNT0")

    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    with (
        patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=new_ws),
        patch("core.clients.kis_ws.asyncio.sleep", side_effect=mock_sleep),
    ):
        await client._reconnect()

    # 재연결 후 구독 복원 확인 — send가 2번 호출됨 (2개 종목)
    assert new_ws.send.await_count == 2
    assert client.connected is True
    # 2개 종목: 첫 번째 이후 딜레이 1회 (마지막 종목은 딜레이 없음)
    delay_calls = [s for s in sleep_calls if s == PAPER.ws_reconnect_delay]
    assert len(delay_calls) == 1

    await client.disconnect()


@pytest.mark.asyncio
async def test_reconnect_exponential_backoff(client, token_manager):
    """재연결 실패 시 지수 백오프로 대기한다."""
    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    # 모든 연결 시도 실패
    with (
        patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, side_effect=Exception("연결 실패")),
        patch("core.clients.kis_ws.asyncio.sleep", side_effect=mock_sleep),
    ):
        await client._reconnect()

    # 7회 시도, 2/4/8/16/32/64/128초 대기
    assert len(sleep_calls) == MAX_RECONNECT_ATTEMPTS
    assert sleep_calls == [2, 4, 8, 16, 32, 64, 128]
    assert client.connected is False


@pytest.mark.asyncio
async def test_reconnect_max_attempts_exceeded(client, token_manager):
    """최대 재연결 횟수 초과 시 connected를 False로 설정한다."""
    with (
        patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, side_effect=Exception("연결 실패")),
        patch("core.clients.kis_ws.asyncio.sleep", new_callable=AsyncMock),
    ):
        await client._reconnect()

    assert client.connected is False


@pytest.mark.asyncio
async def test_reconnect_calls_failure_callback(client, token_manager):
    """최대 재연결 횟수 초과 시 on_ws_failure 콜백을 호출한다."""
    failure_callback = AsyncMock()
    client.set_on_ws_failure(failure_callback)

    with (
        patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, side_effect=Exception("연결 실패")),
        patch("core.clients.kis_ws.asyncio.sleep", new_callable=AsyncMock),
    ):
        await client._reconnect()

    assert client.connected is False
    failure_callback.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconnect_calls_success_callback(client, token_manager, ws_mock):
    """재연결 성공 시 on_reconnect_success 콜백을 호출한다."""
    new_ws = AsyncMock()
    new_ws.send = AsyncMock()
    new_ws.recv = AsyncMock(side_effect=asyncio.CancelledError)
    new_ws.close = AsyncMock()

    success_callback = AsyncMock()
    client.set_on_reconnect_success(success_callback)

    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    with (
        patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=new_ws),
        patch("core.clients.kis_ws.asyncio.sleep", new_callable=AsyncMock),
    ):
        await client._reconnect()

    assert client.connected is True
    success_callback.assert_awaited_once()

    await client.disconnect()


@pytest.mark.asyncio
async def test_receive_loop_logs_close_code(client, token_manager, ws_mock, caplog):
    """ConnectionClosed 예외에서 code/reason을 로깅한다."""
    from websockets.exceptions import ConnectionClosed
    from websockets.frames import Close
    import logging

    close_exc = ConnectionClosed(Close(1001, "going away"), None)
    ws_mock.recv = AsyncMock(side_effect=close_exc)

    # _reconnect를 no-op으로 모킹하여 재연결 없이 로그만 확인
    with (
        patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock),
        patch.object(client, "_reconnect", new_callable=AsyncMock),
        caplog.at_level(logging.WARNING, logger="core.clients.kis_ws"),
    ):
        await client.connect()
        if client._receive_task:
            try:
                await asyncio.wait_for(asyncio.shield(client._receive_task), timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

    assert "code=" in caplog.text or "reason=" in caplog.text

    await client.disconnect()


# ── Phase 6 Sprint 1 — ConcurrencyError / 좀비 / open_timeout / subscribe 가드 ──


@pytest.mark.asyncio
async def test_reconnect_cancels_existing_receive_task(client, token_manager, ws_mock):
    """_reconnect() 진입 시 기존 _receive_task를 cancel+await한다."""
    new_ws = AsyncMock()
    new_ws.send = AsyncMock()
    new_ws.recv = AsyncMock(side_effect=asyncio.CancelledError)
    new_ws.close = AsyncMock()

    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    old_task = client._receive_task
    assert old_task is not None

    with (
        patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=new_ws),
        patch("core.clients.kis_ws.asyncio.sleep", new_callable=AsyncMock),
    ):
        await client._reconnect()

    # 기존 task가 취소되고 새 task가 생성됨
    assert old_task.cancelled()
    assert client._receive_task is not None
    assert client._receive_task is not old_task

    await client.disconnect()


@pytest.mark.asyncio
async def test_reconnect_starts_receive_loop_on_subscription_failure(client, token_manager, ws_mock):
    """구독 복원 실패해도 _receive_task가 생성된다 (좀비 방지)."""
    new_ws = AsyncMock()
    new_ws.recv = AsyncMock(side_effect=asyncio.CancelledError)
    new_ws.close = AsyncMock()
    # subscribe 시 Exception 발생
    new_ws.send = AsyncMock(side_effect=Exception("구독 실패"))

    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock):
        await client.connect()

    # 구독 추가
    await client.subscribe("005930", "H0STCNT0")

    with (
        patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=new_ws),
        patch("core.clients.kis_ws.asyncio.sleep", new_callable=AsyncMock),
    ):
        await client._reconnect()

    # subscribe 실패에도 수신 루프 시작됨
    assert client._receive_task is not None
    assert client.connected is True

    await client.disconnect()


@pytest.mark.asyncio
async def test_ws_connect_open_timeout(client, token_manager, ws_mock):
    """connect()와 _reconnect() 모두 open_timeout=10을 전달한다."""
    with patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=ws_mock) as mock_connect:
        await client.connect()

    mock_connect.assert_awaited_once_with(
        PAPER.ws_url, ping_interval=30, ping_timeout=10, open_timeout=10,
    )

    new_ws = AsyncMock()
    new_ws.send = AsyncMock()
    new_ws.recv = AsyncMock(side_effect=asyncio.CancelledError)
    new_ws.close = AsyncMock()

    with (
        patch("core.clients.kis_ws.websockets.connect", new_callable=AsyncMock, return_value=new_ws) as mock_reconnect,
        patch("core.clients.kis_ws.asyncio.sleep", new_callable=AsyncMock),
    ):
        await client._reconnect()

    # _reconnect 내부 connect 호출에도 open_timeout=10 전달
    mock_reconnect.assert_awaited_with(
        PAPER.ws_url, ping_interval=30, ping_timeout=10, open_timeout=10,
    )

    await client.disconnect()


@pytest.mark.asyncio
async def test_ws_subscribe_none_guard(client):
    """_ws=None 상태에서 subscribe/unsubscribe 시 예외 없이 return."""
    assert client._ws is None

    # subscribe — 예외 없이 조용히 반환
    await client.subscribe("005930", "H0STCNT0")
    assert client.subscription_count == 0
    assert ("005930", "H0STCNT0") not in client._subscriptions

    # unsubscribe — 예외 없이 조용히 반환
    await client.unsubscribe("005930", "H0STCNT0")


# ── 초기 상태 테스트 ──────────────────────────────────────


def test_initial_state(client):
    """초기 상태가 올바른지 확인한다."""
    assert client.connected is False
    assert client.subscription_count == 0
    assert client._ws is None
    assert client._receive_task is None
    assert client._on_data is None
