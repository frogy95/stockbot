"""OrderManager 단위 테스트 — DB/KIS API 의존 없이 모킹으로 구현."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from core.clients.kis_rest import OrderResponse
from modules.trading.order_manager import OrderManager
from modules.trading.position_sizer import PositionSize
from modules.trading.strategy import TradeSignalData


# ---------------------------------------------------------------------------
# 헬퍼 팩토리
# ---------------------------------------------------------------------------


def _make_signal(
    stock_code: str = "005930",
    signal_type: str = "buy",
    entry_price: int = 50_000,
) -> TradeSignalData:
    return TradeSignalData(
        stock_code=stock_code,
        signal_type=signal_type,
        strategy_name="test_strategy",
        confidence=0.8,
        reason={},
        entry_price=entry_price,
        stop_loss=48_000,
        take_profit=53_000,
    )


def _make_position_size(quantity: int = 10) -> PositionSize:
    return PositionSize(
        invest_amount=500_000,
        quantity=quantity,
        is_leverage=False,
        size_pct=10.0,
    )


def _make_order_mock(order_id: int = 1, stock_code: str = "005930") -> MagicMock:
    """Order 모델 인스턴스를 흉내내는 MagicMock."""
    order = MagicMock()
    order.id = order_id
    order.stock_code = stock_code
    order.order_type = "buy"
    order.quantity = 10
    order.price = 50_000
    order.order_no = None
    order.status = "submitted"
    return order


def _make_session_factory(order_obj=None):
    """AsyncMock 기반 세션 팩토리를 생성한다."""
    session = AsyncMock()

    # execute → scalar_one_or_none 체인 설정
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = order_obj
    session.execute = AsyncMock(return_value=result_mock)

    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield session

    return factory, session


def _make_rest_client(
    order_no: str = "ORD001",
    fill_qty: int = 10,
) -> AsyncMock:
    """KISRestClient를 흉내내는 AsyncMock."""
    client = AsyncMock()
    client.place_order = AsyncMock(
        return_value=OrderResponse(
            order_no=order_no,
            stock_code="005930",
            message="주문 완료",
        )
    )
    client.cancel_order = AsyncMock(return_value={})
    client.get_order_status = AsyncMock(
        return_value={
            "output1": [{"tot_ccld_qty": str(fill_qty)}]
        }
    )
    return client


def _make_throttler() -> AsyncMock:
    throttler = AsyncMock()
    throttler.acquire = AsyncMock()
    return throttler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    return redis


@pytest.fixture
def mock_session_factory():
    order = _make_order_mock()
    factory, session = _make_session_factory(order)
    return factory, session


# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------


class TestSubmitOrder:
    """submit_order 기본 동작 테스트."""

    @pytest.mark.asyncio
    async def test_submit_order_creates_record_and_enqueues(self, mock_redis):
        """submit_order: DB 레코드 생성 후 큐에 enqueue."""
        factory, session = _make_session_factory()

        # refresh 후 order.id를 1로 설정
        created_order = _make_order_mock(order_id=1)

        async def _refresh(obj):
            obj.id = 1

        session.refresh = AsyncMock(side_effect=_refresh)

        client = _make_rest_client()
        throttler = _make_throttler()

        manager = OrderManager(factory, client, mock_redis, throttler)

        signal = _make_signal()
        pos_size = _make_position_size()

        order = await manager.submit_order(signal, pos_size)

        # DB commit 호출 확인
        session.commit.assert_called_once()
        session.add.assert_called_once()

        # 큐에 enqueue 확인
        assert manager._queue.qsize() == 1


class TestMarketOrderFill:
    """TC-1: 시장가 주문 실행 + 즉시 체결."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_market_order_immediately_filled(self, mock_sleep, mock_redis):
        """모의거래에서 시장가 주문 후 즉시 체결 → status="filled"."""
        order = _make_order_mock(order_id=1)
        factory, session = _make_session_factory(order)

        client = _make_rest_client(order_no="ORD001", fill_qty=10)
        throttler = _make_throttler()

        manager = OrderManager(factory, client, mock_redis, throttler)

        with patch("modules.trading.order_manager.settings") as mock_settings:
            mock_settings.TRADING_ENV = "paper"
            await manager._execute_order(1)

        # 시장가 주문 호출 확인
        call_args = client.place_order.call_args[0][0]
        assert call_args.order_division == "01"
        assert call_args.price == 0

        # 체결 폴링 후 status 업데이트 확인 — commit 최소 2회 (order_no 업데이트 + status 업데이트)
        assert session.commit.call_count >= 2


class TestLimitOrderFallback:
    """TC-2: 최우선 지정가 → 3초 후 미체결 → 시장가 폴백."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_limit_order_unfilled_falls_back_to_market(self, mock_sleep, mock_redis):
        """실전 환경: 지정가 미체결 → 취소 → 시장가 재주문."""
        order = _make_order_mock(order_id=1)
        factory, session = _make_session_factory(order)

        client = AsyncMock()
        # 지정가 주문 응답
        client.place_order = AsyncMock(
            side_effect=[
                OrderResponse(order_no="LIMIT001", stock_code="005930", message="OK"),
                OrderResponse(order_no="MKT001", stock_code="005930", message="OK"),
            ]
        )
        client.cancel_order = AsyncMock(return_value={})
        # get_order_status: 처음엔 미체결, 두 번째 이후 체결
        client.get_order_status = AsyncMock(
            side_effect=[
                {"output1": [{"tot_ccld_qty": "0"}]},    # 지정가 미체결 확인
                {"output1": [{"tot_ccld_qty": "10"}]},   # 시장가 체결 (첫 번째 폴)
            ]
        )

        throttler = _make_throttler()

        manager = OrderManager(factory, client, mock_redis, throttler)

        with patch("modules.trading.order_manager.settings") as mock_settings:
            mock_settings.TRADING_ENV = "live"
            await manager._execute_order(1)

        # place_order 2회 호출 확인
        assert client.place_order.call_count == 2

        # 첫 번째 place_order: 지정가("05")
        first_order = client.place_order.call_args_list[0][0][0]
        assert first_order.order_division == "05"

        # 두 번째 place_order: 시장가("01")
        second_order = client.place_order.call_args_list[1][0][0]
        assert second_order.order_division == "01"

        # cancel_order 호출 확인
        client.cancel_order.assert_called_once()
        cancel_args = client.cancel_order.call_args[0]
        assert cancel_args[0] == "LIMIT001"

        # asyncio.sleep 호출: 3초 대기가 포함되어야 함
        sleep_calls = [c[0][0] for c in mock_sleep.call_args_list]
        assert 3.0 in sleep_calls


class TestPollFillStatus:
    """TC-3: 체결 폴링 (2초 x 최대 15회)."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_poll_fills_on_third_attempt(self, mock_sleep, mock_redis):
        """3번째 폴링에서 체결 확인 → True 반환."""
        factory, _ = _make_session_factory()
        client = AsyncMock()
        client.get_order_status = AsyncMock(
            side_effect=[
                {"output1": [{"tot_ccld_qty": "0"}]},
                {"output1": [{"tot_ccld_qty": "0"}]},
                {"output1": [{"tot_ccld_qty": "10"}]},
            ]
        )
        throttler = _make_throttler()
        manager = OrderManager(factory, client, mock_redis, throttler)

        result = await manager._poll_fill_status("ORD001", max_polls=15, interval=2.0)

        assert result is True
        assert client.get_order_status.call_count == 3
        # 3번의 sleep(2.0) 호출 확인
        assert mock_sleep.call_count == 3
        for c in mock_sleep.call_args_list:
            assert c[0][0] == 2.0


class TestPollTimeout:
    """TC-4: 체결 폴링 30초 초과 → timeout."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_poll_timeout_after_max_polls(self, mock_sleep, mock_redis):
        """15회 폴링 후 미체결 → False 반환."""
        factory, _ = _make_session_factory()
        client = AsyncMock()
        # 항상 미체결
        client.get_order_status = AsyncMock(
            return_value={"output1": [{"tot_ccld_qty": "0"}]}
        )
        throttler = _make_throttler()
        manager = OrderManager(factory, client, mock_redis, throttler)

        result = await manager._poll_fill_status("ORD001", max_polls=15, interval=2.0)

        assert result is False
        assert client.get_order_status.call_count == 15
        assert mock_sleep.call_count == 15


class TestQueueSequential:
    """TC-5: 주문 큐 순차 실행."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_three_orders_processed_sequentially(self, mock_sleep, mock_redis):
        """3건의 주문이 순차적으로 처리된다."""
        execution_order = []

        # 주문 ID에 따라 다른 Order mock 반환
        orders = {
            1: _make_order_mock(order_id=1, stock_code="005930"),
            2: _make_order_mock(order_id=2, stock_code="000660"),
            3: _make_order_mock(order_id=3, stock_code="035720"),
        }

        session = AsyncMock()
        call_count = {"n": 0}

        async def side_effect_execute(stmt):
            # submit_order의 commit/refresh 호출 시에는 mock 재사용
            result_mock = MagicMock()
            result_mock.scalar_one_or_none.return_value = orders.get(
                call_count["n"] % 3 + 1
            )
            return result_mock

        session.execute = AsyncMock(side_effect=side_effect_execute)
        session.add = MagicMock()
        session.commit = AsyncMock()

        ids_assigned = [1, 2, 3]
        idx = {"i": 0}

        async def mock_refresh(obj):
            obj.id = ids_assigned[idx["i"] % 3]
            idx["i"] += 1

        session.refresh = AsyncMock(side_effect=mock_refresh)

        @asynccontextmanager
        async def factory():
            yield session

        original_execute_order = []

        client = AsyncMock()
        client.place_order = AsyncMock(
            return_value=OrderResponse(order_no="ORD", stock_code="005930", message="OK")
        )
        client.get_order_status = AsyncMock(
            return_value={"output1": [{"tot_ccld_qty": "10"}]}
        )
        throttler = _make_throttler()

        manager = OrderManager(factory, client, mock_redis, throttler)

        # _execute_order를 패치해 실행 순서 기록
        original_execute = manager._execute_order

        async def patched_execute(order_id: int):
            original_execute_order.append(order_id)

        manager._execute_order = patched_execute

        # 3건 submit
        signal1 = _make_signal(stock_code="005930")
        signal2 = _make_signal(stock_code="000660")
        signal3 = _make_signal(stock_code="035720")
        pos = _make_position_size()

        await manager.submit_order(signal1, pos)
        await manager.submit_order(signal2, pos)
        await manager.submit_order(signal3, pos)

        # 워커 시작 및 큐 소진 대기
        await manager.start()
        await manager._queue.join()
        await manager.stop()

        # 순차 처리 확인 (enqueue 순서와 동일)
        assert len(original_execute_order) == 3
        assert original_execute_order == sorted(original_execute_order)


class TestThrottlerCalled:
    """TC-6: 스로틀러 호출 확인."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_throttler_acquire_called_on_order(self, mock_sleep, mock_redis):
        """주문 실행 시 throttler.acquire()가 반드시 호출된다."""
        order = _make_order_mock(order_id=1)
        factory, session = _make_session_factory(order)

        client = _make_rest_client(order_no="ORD001", fill_qty=10)
        throttler = _make_throttler()

        manager = OrderManager(factory, client, mock_redis, throttler)

        with patch("modules.trading.order_manager.settings") as mock_settings:
            mock_settings.TRADING_ENV = "paper"
            await manager._execute_order(1)

        # throttler.acquire 최소 1회 이상 호출
        assert throttler.acquire.call_count >= 1


class TestPaperTradingMarketOnly:
    """TC-7: 모의거래 환경에서는 시장가만 사용."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_paper_env_uses_market_order_only(self, mock_sleep, mock_redis):
        """TRADING_ENV=paper 시 order_division="01"(시장가)만 사용."""
        order = _make_order_mock(order_id=1)
        factory, session = _make_session_factory(order)

        client = _make_rest_client(order_no="ORD001", fill_qty=10)
        throttler = _make_throttler()

        manager = OrderManager(factory, client, mock_redis, throttler)

        with patch("modules.trading.order_manager.settings") as mock_settings:
            mock_settings.TRADING_ENV = "paper"
            await manager._execute_order(1)

        # place_order 1회만 호출 (지정가 시도 없음)
        assert client.place_order.call_count == 1

        # 호출된 주문의 order_division이 "01"(시장가)인지 확인
        placed_order = client.place_order.call_args[0][0]
        assert placed_order.order_division == "01"
        assert placed_order.price == 0

        # cancel_order 호출 없음
        client.cancel_order.assert_not_called()
