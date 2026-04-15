"""engine 가격 갱신 + 청산 실행 + 모니터 루프 테스트."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.engine import TradingEngine

KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _make_redis(price_data: dict[str, dict] | None = None) -> AsyncMock:
    """Redis mock — realtime:{code}:execution 키에 가격 데이터 설정."""
    mock_redis = AsyncMock()
    store = {}
    if price_data:
        for code, data in price_data.items():
            store[f"realtime:{code}:execution"] = json.dumps(data)

    async def _get(key: str) -> str | None:
        return store.get(key)

    mock_redis.get = AsyncMock(side_effect=_get)
    mock_redis.set = AsyncMock()
    return mock_redis


def _make_session_factory(stock_codes=None):
    """포지션 조회용 세션 팩토리 mock.

    _collect_price_updates에서 select(PositionRecord.stock_code)를 실행하면
    result.scalars().all()이 stock_code 문자열 리스트를 반환한다.
    """
    session = AsyncMock()
    result_mock = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = stock_codes or []
    result_mock.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result_mock)

    @asynccontextmanager
    async def factory():
        yield session

    return factory


def _make_engine(
    redis_data: dict[str, dict] | None = None,
    stock_codes: list[str] | None = None,
    rest_client: AsyncMock | None = None,
) -> TradingEngine:
    """테스트용 TradingEngine 생성."""
    mock_redis = _make_redis(redis_data)
    session_factory = _make_session_factory(stock_codes)

    if rest_client is None:
        rest_client = AsyncMock()

    engine = TradingEngine(
        signal_generator=AsyncMock(),
        order_manager=AsyncMock(),
        position_manager=AsyncMock(),
        risk_manager=AsyncMock(),
        position_sizer=AsyncMock(),
        eod_liquidator=MagicMock(),
        redis_client=mock_redis,
        notifier_manager=AsyncMock(),
        session_factory=session_factory,
        rest_client=rest_client,
    )
    engine._order_manager.get_queue_size.return_value = 0
    return engine


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------


class TestCollectPriceUpdatesFromRedis:
    """Redis WS 데이터에서 가격 수집."""

    @pytest.mark.asyncio
    async def test_collect_price_updates_from_redis(self):
        """Redis realtime:{code}:execution 키에서 current_price 수집."""
        stock_codes = ["005930", "000660"]
        redis_data = {
            "005930": {"current_price": 73000, "volume": 1000},
            "000660": {"current_price": 150000, "volume": 500},
        }
        engine = _make_engine(redis_data=redis_data, stock_codes=stock_codes)

        result = await engine._collect_price_updates()

        assert result == {"005930": 73000, "000660": 150000}


class TestCollectPriceUpdatesRestFallback:
    """Redis 미스 시 REST 폴백."""

    @pytest.mark.asyncio
    async def test_collect_price_updates_rest_fallback(self):
        """Redis에 없는 종목은 rest_client.get_stock_price로 폴백."""
        stock_codes = ["005930"]
        # Redis에 데이터 없음
        rest_client = AsyncMock()
        price_result = MagicMock()
        price_result.price = 73000
        rest_client.get_stock_price = AsyncMock(return_value=price_result)

        engine = _make_engine(stock_codes=stock_codes, rest_client=rest_client)

        result = await engine._collect_price_updates()

        assert result == {"005930": 73000}
        rest_client.get_stock_price.assert_called_once_with("005930")


class TestMonitorLoopCallsUpdatePrices:
    """_monitor_positions_loop가 update_prices 호출."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_monitor_loop_calls_update_prices(self, mock_sleep):
        """모니터 루프가 가격 수집 → update_prices 호출."""
        stock_codes = ["005930"]
        redis_data = {"005930": {"current_price": 73000}}
        engine = _make_engine(redis_data=redis_data, stock_codes=stock_codes)
        engine._position_manager.check_exit_conditions = AsyncMock(return_value=[])

        # 장 시간 내로 시뮬레이션
        market_time = datetime(2026, 4, 15, 10, 0, 0, tzinfo=KST)

        # 1회만 실행 후 종료
        call_count = {"n": 0}
        original_running = True

        async def stop_after_one(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 1:
                engine._running = False

        mock_sleep.side_effect = stop_after_one

        engine._running = True
        with patch("modules.trading.engine.datetime") as mock_dt:
            mock_dt.now.return_value = market_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await engine._monitor_positions_loop(interval=5.0)

        engine._position_manager.update_prices.assert_called_once()


class TestMonitorLoopExecutesExit:
    """청산 조건 충족 시 _execute_exit 호출."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_monitor_loop_executes_exit(self, mock_sleep):
        """check_exit_conditions 결과에 대해 _execute_exit 호출."""
        stock_codes = ["005930"]
        redis_data = {"005930": {"current_price": 73000}}
        engine = _make_engine(redis_data=redis_data, stock_codes=stock_codes)

        exit_info = {
            "stock_code": "005930",
            "quantity": 10,
            "exit_reason": "stop_loss",
            "position_id": 1,
        }
        engine._position_manager.check_exit_conditions = AsyncMock(return_value=[exit_info])
        engine._execute_exit = AsyncMock()

        call_count = {"n": 0}

        async def stop_after_one(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 1:
                engine._running = False

        mock_sleep.side_effect = stop_after_one

        engine._running = True
        market_time = datetime(2026, 4, 15, 10, 0, 0, tzinfo=KST)
        with patch("modules.trading.engine.datetime") as mock_dt:
            mock_dt.now.return_value = market_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await engine._monitor_positions_loop(interval=5.0)

        engine._execute_exit.assert_called_once_with(exit_info)


class TestMonitorLoopMarketHoursGuard:
    """장 시간 외에는 가격 갱신/청산 미실행."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_monitor_loop_market_hours_guard(self, mock_sleep):
        """장 시간(09:00~15:30) 외에는 update_prices 미호출."""
        stock_codes = ["005930"]
        redis_data = {"005930": {"current_price": 73000}}
        engine = _make_engine(redis_data=redis_data, stock_codes=stock_codes)
        engine._position_manager.check_exit_conditions = AsyncMock(return_value=[])

        # 장 시간 외 (08:30)
        off_market_time = datetime(2026, 4, 15, 8, 30, 0, tzinfo=KST)

        call_count = {"n": 0}

        async def stop_after_one(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 1:
                engine._running = False

        mock_sleep.side_effect = stop_after_one

        engine._running = True
        with patch("modules.trading.engine.datetime") as mock_dt:
            mock_dt.now.return_value = off_market_time
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await engine._monitor_positions_loop(interval=5.0)

        engine._position_manager.update_prices.assert_not_called()


class TestExecuteExitPlacesSellOrder:
    """_execute_exit 시장가 매도 + 폴링 + close_position."""

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_execute_exit_places_sell_order(self, mock_sleep):
        """시장가 매도 주문 + 체결 폴링 + close_position 호출."""
        rest_client = AsyncMock()
        # place_order 응답
        order_resp = MagicMock()
        order_resp.order_no = "SELL001"
        rest_client.place_order = AsyncMock(return_value=order_resp)
        # get_order_status: 체결
        rest_client.get_order_status = AsyncMock(
            return_value={
                "output1": [{"tot_ccld_qty": "10", "tot_ccld_amt": "730000"}]
            }
        )

        engine = _make_engine(rest_client=rest_client)

        exit_info = {
            "stock_code": "005930",
            "quantity": 10,
            "exit_reason": "stop_loss",
            "position_id": 1,
        }
        await engine._execute_exit(exit_info)

        # 시장가 매도 주문 호출
        rest_client.place_order.assert_called_once()
        order_req = rest_client.place_order.call_args[0][0]
        assert order_req.order_type == "sell"
        assert order_req.order_division == "01"
        assert order_req.price == 0

        # close_position 호출
        engine._position_manager.close_position.assert_called_once_with(
            1, 73000, "stop_loss"
        )
