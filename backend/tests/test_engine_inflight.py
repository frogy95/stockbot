"""Task 3 테스트: engine._execute_exit in-flight 중복 매도 방지."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.trading.engine import TradingEngine


INFLIGHT_PREFIX = "exit:inflight:"


def _make_engine(rest_client: AsyncMock, redis_store: dict | None = None):
    """간단한 TradingEngine 생성: Redis mock은 dict-backed."""
    store: dict[str, str] = dict(redis_store or {})
    mock_redis = AsyncMock()

    async def _get(key):
        return store.get(key)

    async def _set(key, value, ttl=None):
        store[key] = value

    async def _delete(key):
        return store.pop(key, None) is not None

    mock_redis.get = AsyncMock(side_effect=_get)
    mock_redis.set = AsyncMock(side_effect=_set)
    mock_redis.delete = AsyncMock(side_effect=_delete)

    session = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=execute_result)

    @asynccontextmanager
    async def factory():
        yield session

    engine = TradingEngine(
        signal_generator=AsyncMock(),
        order_manager=AsyncMock(),
        position_manager=AsyncMock(),
        risk_manager=AsyncMock(),
        position_sizer=AsyncMock(),
        eod_liquidator=MagicMock(),
        redis_client=mock_redis,
        notifier_manager=AsyncMock(),
        session_factory=factory,
        rest_client=rest_client,
    )
    return engine, mock_redis, store


def _exit_info(stock_code: str = "005930") -> dict:
    return {
        "stock_code": stock_code,
        "quantity": 10,
        "exit_reason": "stop_loss",
        "position_id": 1,
    }


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_execute_exit_sets_inflight_flag(mock_sleep):
    """_execute_exit 진입 시 Redis inflight 키가 설정되고 성공 시 삭제."""
    rest_client = AsyncMock()
    order_resp = MagicMock()
    order_resp.order_no = "SELL001"
    rest_client.place_order = AsyncMock(return_value=order_resp)
    rest_client.get_order_status = AsyncMock(
        return_value={"output1": [{"tot_ccld_qty": "10", "tot_ccld_amt": "730000"}]}
    )

    engine, mock_redis, store = _make_engine(rest_client)

    await engine._execute_exit(_exit_info("005930"))

    inflight_key = f"{INFLIGHT_PREFIX}005930"
    # set 호출 시 TTL이 명시적으로 전달됐는지 확인
    set_calls = [c for c in mock_redis.set.await_args_list if c.args and c.args[0] == inflight_key]
    assert len(set_calls) == 1
    assert set_calls[0].kwargs.get("ttl") == 30 or (len(set_calls[0].args) >= 3 and set_calls[0].args[2] == 30)

    # 청산 완료 후 키 삭제
    delete_calls = [c.args[0] for c in mock_redis.delete.await_args_list if c.args]
    assert inflight_key in delete_calls
    # 최종적으로 키가 남아있지 않음
    assert inflight_key not in store


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_execute_exit_skips_if_inflight(mock_sleep):
    """이미 inflight 플래그가 있는 종목은 매도 주문 발송하지 않음."""
    rest_client = AsyncMock()
    rest_client.place_order = AsyncMock()

    inflight_key = f"{INFLIGHT_PREFIX}005930"
    engine, mock_redis, store = _make_engine(
        rest_client, redis_store={inflight_key: "1"}
    )

    await engine._execute_exit(_exit_info("005930"))

    # place_order 호출되면 안 됨
    rest_client.place_order.assert_not_called()
    # close_position도 호출되면 안 됨
    engine._position_manager.close_position.assert_not_called()
    # 기존 inflight 플래그는 유지 (다른 루프에서 관리)
    assert store.get(inflight_key) == "1"


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_execute_exit_clears_inflight_on_place_order_failure(mock_sleep):
    """place_order 예외 발생 시에도 inflight 플래그가 삭제되어 재시도 가능."""
    rest_client = AsyncMock()
    rest_client.place_order = AsyncMock(side_effect=Exception("KIS 일시 장애"))

    engine, mock_redis, store = _make_engine(rest_client)

    await engine._execute_exit(_exit_info("005930"))

    inflight_key = f"{INFLIGHT_PREFIX}005930"
    assert inflight_key not in store


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_execute_exit_clears_inflight_on_polling_timeout(mock_sleep):
    """체결 폴링 3회 모두 미체결 시에도 inflight 플래그가 삭제됨 (다음 루프 재시도)."""
    rest_client = AsyncMock()
    order_resp = MagicMock()
    order_resp.order_no = "SELL001"
    rest_client.place_order = AsyncMock(return_value=order_resp)
    rest_client.get_order_status = AsyncMock(
        return_value={"output1": [{"tot_ccld_qty": "0", "tot_ccld_amt": "0"}]}
    )

    engine, mock_redis, store = _make_engine(rest_client)

    await engine._execute_exit(_exit_info("005930"))

    inflight_key = f"{INFLIGHT_PREFIX}005930"
    assert inflight_key not in store
    engine._position_manager.close_position.assert_not_called()
