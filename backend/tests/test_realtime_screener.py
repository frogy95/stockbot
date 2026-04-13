"""2차 스크리닝 엔진 테스트 (Redis/DB 모킹 — 순수 로직 검증)."""
from __future__ import annotations

import json
from datetime import datetime, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.screening.filters import SecondaryFilters
from modules.screening.realtime_screener import RealtimeScreener
from modules.screening.scorer import FactorScorer
from modules.collector.trade_strength import TradeStrengthCalculator


# ---------------------------------------------------------------------------
# 헬퍼: Redis mock 데이터 생성
# ---------------------------------------------------------------------------

def _make_execution_data(
    current_price: int = 50_000,
    volume: int = 200_000,
    prev_volume: int = 50_000,
    change_rate: float = 3.0,
    trade_strength: float = 150.0,
) -> str:
    """Redis realtime:{code}:execution 저장 형식 (KIS CTTR 포함)."""
    return json.dumps({
        "current_price": current_price,
        "volume": volume,
        "prev_volume": prev_volume,
        "change_rate": change_rate,
        "trade_strength": trade_strength,
    })


def _make_orderbook_data(
    total_bid_volume: int = 100_000,
    total_ask_volume: int = 80_000,
) -> str:
    """Redis realtime:{code}:orderbook 저장 형식."""
    return json.dumps({
        "total_bid_volume": total_bid_volume,
        "total_ask_volume": total_ask_volume,
    })


def _make_screener(
    filters: SecondaryFilters | None = None,
    scorer: FactorScorer | None = None,
    redis_client: AsyncMock | None = None,
    trade_calc: TradeStrengthCalculator | None = None,
) -> RealtimeScreener:
    """테스트용 RealtimeScreener 인스턴스 생성."""
    return RealtimeScreener(
        filters=filters or SecondaryFilters(),
        scorer=scorer or FactorScorer(),
        redis_client=redis_client or AsyncMock(),
        trade_strength_calc=trade_calc or TradeStrengthCalculator(),
    )


# ---------------------------------------------------------------------------
# 시초가 구간 테스트
# ---------------------------------------------------------------------------

class TestNoSignalPeriod:
    """09:00~09:30 시초가 구간 내에서는 빈 리스트 반환."""

    @pytest.mark.asyncio
    async def test_before_0930_returns_empty(self):
        """09:30 이전에는 빈 리스트 반환."""
        screener = _make_screener()
        session = AsyncMock()

        # 09:15 시점 모킹
        mock_now = datetime(2026, 3, 29, 9, 15, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = await screener.screen(["005930", "000660"], session)

        assert result == []

    @pytest.mark.asyncio
    async def test_at_0900_returns_empty(self):
        """09:00 정각에도 빈 리스트 반환."""
        screener = _make_screener()
        session = AsyncMock()

        mock_now = datetime(2026, 3, 29, 9, 0, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = await screener.screen(["005930"], session)

        assert result == []

    @pytest.mark.asyncio
    async def test_after_0930_proceeds(self):
        """09:30 이후에는 정상 진행 (빈 후보여도 빈 리스트)."""
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=None)
        screener = _make_screener(redis_client=redis_mock)
        session = AsyncMock()

        mock_now = datetime(2026, 3, 29, 9, 31, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = await screener.screen([], session)

        assert result == []


# ---------------------------------------------------------------------------
# 체결강도 필터 테스트
# ---------------------------------------------------------------------------

class TestTradeStrengthFilter:
    """체결강도(KIS CTTR) 120+ 통과, 미달 제외."""

    @pytest.mark.asyncio
    async def test_trade_strength_pass(self):
        """체결강도 150 → 통과 (KIS CTTR 기준, 기본값)."""
        trade_calc = TradeStrengthCalculator(window_seconds=300)

        redis_mock = AsyncMock()

        async def mock_get(key: str):
            if key == "realtime:005930:execution":
                return _make_execution_data(trade_strength=150.0)
            if key == "realtime:005930:orderbook":
                return _make_orderbook_data()
            return None

        redis_mock.get = AsyncMock(side_effect=mock_get)

        screener = _make_screener(redis_client=redis_mock, trade_calc=trade_calc)
        session = AsyncMock()

        # DB에서 stock 정보 + market_data 조회 모킹
        mock_now = datetime(2026, 3, 29, 10, 0, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt, \
             patch.object(screener, "_get_stock_info", new_callable=AsyncMock) as mock_stock, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mock_market:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_stock.return_value = {
                "005930": {"stock_name": "삼성전자", "stock_type": "STOCK"},
            }
            mock_market.return_value = {
                "005930": [
                    {"close_price": 49000, "high_price": 50000, "low_price": 48000},
                    {"close_price": 49500, "high_price": 50500, "low_price": 48500},
                    {"close_price": 50000, "high_price": 51000, "low_price": 49000},
                    {"close_price": 50500, "high_price": 51500, "low_price": 49500},
                    {"close_price": 51000, "high_price": 52000, "low_price": 50000},
                ],
            }

            # save_results 모킹
            with patch.object(screener, "save_results", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = 1
                result = await screener.screen(["005930"], session)

        assert len(result) == 1
        assert result[0]["stock_code"] == "005930"
        assert result[0]["trade_strength"] == 150.0

    @pytest.mark.asyncio
    async def test_trade_strength_fail(self):
        """체결강도 100 → 제외 (KIS CTTR 기준 120 미달)."""
        trade_calc = TradeStrengthCalculator(window_seconds=300)

        redis_mock = AsyncMock()

        async def mock_get(key: str):
            if key == "realtime:005930:execution":
                return _make_execution_data(trade_strength=100.0)
            if key == "realtime:005930:orderbook":
                return _make_orderbook_data()
            return None

        redis_mock.get = AsyncMock(side_effect=mock_get)

        screener = _make_screener(redis_client=redis_mock, trade_calc=trade_calc)
        session = AsyncMock()

        mock_now = datetime(2026, 3, 29, 10, 0, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt, \
             patch.object(screener, "_get_stock_info", new_callable=AsyncMock) as mock_stock:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_stock.return_value = {
                "005930": {"stock_name": "삼성전자", "stock_type": "STOCK"},
            }

            result = await screener.screen(["005930"], session)

        assert result == []


# ---------------------------------------------------------------------------
# 호가잔량 비율 필터 테스트
# ---------------------------------------------------------------------------

class TestOrderbookRatioFilter:
    """호가잔량 비율 1.2+ 통과, 미달 제외."""

    @pytest.mark.asyncio
    async def test_orderbook_ratio_pass(self):
        """bid/ask = 100000/80000 = 1.25 → 통과."""
        trade_calc = TradeStrengthCalculator(window_seconds=300)

        redis_mock = AsyncMock()

        async def mock_get(key: str):
            if key == "realtime:005930:execution":
                return _make_execution_data()
            if key == "realtime:005930:orderbook":
                return _make_orderbook_data(total_bid_volume=100_000, total_ask_volume=80_000)
            return None

        redis_mock.get = AsyncMock(side_effect=mock_get)

        screener = _make_screener(redis_client=redis_mock, trade_calc=trade_calc)
        session = AsyncMock()

        mock_now = datetime(2026, 3, 29, 10, 0, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt, \
             patch.object(screener, "_get_stock_info", new_callable=AsyncMock) as mock_stock, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mock_market, \
             patch.object(trade_calc, "get_strength", return_value=80.0):
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_stock.return_value = {
                "005930": {"stock_name": "삼성전자", "stock_type": "STOCK"},
            }
            mock_market.return_value = {
                "005930": [
                    {"close_price": 49000, "high_price": 50000, "low_price": 48000},
                    {"close_price": 49500, "high_price": 50500, "low_price": 48500},
                    {"close_price": 50000, "high_price": 51000, "low_price": 49000},
                    {"close_price": 50500, "high_price": 51500, "low_price": 49500},
                    {"close_price": 51000, "high_price": 52000, "low_price": 50000},
                ],
            }

            with patch.object(screener, "save_results", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = 1
                result = await screener.screen(["005930"], session)

        assert len(result) == 1
        assert result[0]["orderbook_ratio"] == pytest.approx(1.25, rel=0.01)

    @pytest.mark.asyncio
    async def test_orderbook_ratio_fail(self):
        """bid/ask = 80000/100000 = 0.8 → 제외."""
        trade_calc = TradeStrengthCalculator(window_seconds=300)

        redis_mock = AsyncMock()

        async def mock_get(key: str):
            if key == "realtime:005930:execution":
                return _make_execution_data()
            if key == "realtime:005930:orderbook":
                return _make_orderbook_data(total_bid_volume=80_000, total_ask_volume=100_000)
            return None

        redis_mock.get = AsyncMock(side_effect=mock_get)

        screener = _make_screener(redis_client=redis_mock, trade_calc=trade_calc)
        session = AsyncMock()

        mock_now = datetime(2026, 3, 29, 10, 0, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt, \
             patch.object(screener, "_get_stock_info", new_callable=AsyncMock) as mock_stock, \
             patch.object(trade_calc, "get_strength", return_value=80.0):
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_stock.return_value = {
                "005930": {"stock_name": "삼성전자", "stock_type": "STOCK"},
            }

            result = await screener.screen(["005930"], session)

        assert result == []


# ---------------------------------------------------------------------------
# Redis 데이터 없는 종목 스킵
# ---------------------------------------------------------------------------

class TestRedisDataMissing:
    """Redis 데이터 없는 종목은 스킵."""

    @pytest.mark.asyncio
    async def test_no_execution_data_skips(self):
        """execution 데이터 없으면 스킵."""
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=None)

        screener = _make_screener(redis_client=redis_mock)
        session = AsyncMock()

        mock_now = datetime(2026, 3, 29, 10, 0, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt, \
             patch.object(screener, "_get_stock_info", new_callable=AsyncMock) as mock_stock:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_stock.return_value = {
                "005930": {"stock_name": "삼성전자", "stock_type": "STOCK"},
            }

            result = await screener.screen(["005930"], session)

        assert result == []

    @pytest.mark.asyncio
    async def test_no_orderbook_data_skips(self):
        """orderbook 데이터 없으면 스킵."""
        redis_mock = AsyncMock()

        async def mock_get(key: str):
            if key == "realtime:005930:execution":
                return _make_execution_data()
            return None

        redis_mock.get = AsyncMock(side_effect=mock_get)

        screener = _make_screener(redis_client=redis_mock)
        session = AsyncMock()

        mock_now = datetime(2026, 3, 29, 10, 0, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt, \
             patch.object(screener, "_get_stock_info", new_callable=AsyncMock) as mock_stock:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_stock.return_value = {
                "005930": {"stock_name": "삼성전자", "stock_type": "STOCK"},
            }

            result = await screener.screen(["005930"], session)

        assert result == []


# ---------------------------------------------------------------------------
# 스코어링 통합 테스트
# ---------------------------------------------------------------------------

class TestScoringIntegration:
    """2차 스크리닝 통과 종목에 팩터 스코어링 적용."""

    @pytest.mark.asyncio
    async def test_scoring_with_realtime_factors(self):
        """실시간 체결강도/호가잔량이 팩터에 반영되어 스코어 갱신."""
        trade_calc = TradeStrengthCalculator(window_seconds=300)

        redis_mock = AsyncMock()

        async def mock_get(key: str):
            code = key.split(":")[1]
            if ":execution" in key:
                if code == "005930":
                    return _make_execution_data(volume=200_000, prev_volume=50_000)
                if code == "000660":
                    return _make_execution_data(volume=300_000, prev_volume=60_000)
            if ":orderbook" in key:
                if code == "005930":
                    return _make_orderbook_data(total_bid_volume=120_000, total_ask_volume=80_000)
                if code == "000660":
                    return _make_orderbook_data(total_bid_volume=150_000, total_ask_volume=100_000)
            return None

        redis_mock.get = AsyncMock(side_effect=mock_get)

        screener = _make_screener(redis_client=redis_mock, trade_calc=trade_calc)
        session = AsyncMock()

        mock_now = datetime(2026, 3, 29, 10, 0, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt, \
             patch.object(screener, "_get_stock_info", new_callable=AsyncMock) as mock_stock, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mock_market, \
             patch.object(trade_calc, "get_strength", return_value=85.0):
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_stock.return_value = {
                "005930": {"stock_name": "삼성전자", "stock_type": "STOCK"},
                "000660": {"stock_name": "SK하이닉스", "stock_type": "STOCK"},
            }
            mock_market.return_value = {
                "005930": [
                    {"close_price": 49000, "high_price": 50000, "low_price": 48000},
                    {"close_price": 49500, "high_price": 50500, "low_price": 48500},
                    {"close_price": 50000, "high_price": 51000, "low_price": 49000},
                    {"close_price": 50500, "high_price": 51500, "low_price": 49500},
                    {"close_price": 51000, "high_price": 52000, "low_price": 50000},
                ],
                "000660": [
                    {"close_price": 99000, "high_price": 100000, "low_price": 98000},
                    {"close_price": 99500, "high_price": 100500, "low_price": 98500},
                    {"close_price": 100000, "high_price": 101000, "low_price": 99000},
                    {"close_price": 100500, "high_price": 101500, "low_price": 99500},
                    {"close_price": 101000, "high_price": 102000, "low_price": 100000},
                ],
            }

            with patch.object(screener, "save_results", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = 2
                result = await screener.screen(["005930", "000660"], session)

        assert len(result) == 2

        # 필수 키 확인
        for item in result:
            assert "stock_code" in item
            assert "stock_name" in item
            assert "stock_type" in item
            assert "score" in item
            assert "rank" in item
            assert "factors" in item
            assert "is_passed" in item
            assert "trade_strength" in item
            assert "orderbook_ratio" in item

        # rank 순서 확인
        assert result[0]["rank"] == 1
        assert result[1]["rank"] == 2

        # 체결강도/호가잔량이 팩터에 반영됨
        for item in result:
            assert "trade_strength_factor" in item["factors"]
            assert "orderbook_ratio_factor" in item["factors"]

    @pytest.mark.asyncio
    async def test_mixed_pass_and_fail(self):
        """2종목 중 1종목만 필터 통과."""
        trade_calc = TradeStrengthCalculator(window_seconds=300)

        redis_mock = AsyncMock()

        async def mock_get(key: str):
            code = key.split(":")[1]
            if ":execution" in key:
                return _make_execution_data()
            if ":orderbook" in key:
                if code == "005930":
                    # 통과: bid/ask = 1.25
                    return _make_orderbook_data(total_bid_volume=100_000, total_ask_volume=80_000)
                if code == "000660":
                    # 미달: bid/ask = 0.8
                    return _make_orderbook_data(total_bid_volume=80_000, total_ask_volume=100_000)
            return None

        redis_mock.get = AsyncMock(side_effect=mock_get)

        screener = _make_screener(redis_client=redis_mock, trade_calc=trade_calc)
        session = AsyncMock()

        mock_now = datetime(2026, 3, 29, 10, 0, 0)
        with patch("modules.screening.realtime_screener.datetime") as mock_dt, \
             patch.object(screener, "_get_stock_info", new_callable=AsyncMock) as mock_stock, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mock_market, \
             patch.object(trade_calc, "get_strength", return_value=80.0):
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_stock.return_value = {
                "005930": {"stock_name": "삼성전자", "stock_type": "STOCK"},
                "000660": {"stock_name": "SK하이닉스", "stock_type": "STOCK"},
            }
            mock_market.return_value = {
                "005930": [
                    {"close_price": 49000, "high_price": 50000, "low_price": 48000},
                    {"close_price": 49500, "high_price": 50500, "low_price": 48500},
                    {"close_price": 50000, "high_price": 51000, "low_price": 49000},
                    {"close_price": 50500, "high_price": 51500, "low_price": 49500},
                    {"close_price": 51000, "high_price": 52000, "low_price": 50000},
                ],
            }

            with patch.object(screener, "save_results", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = 1
                result = await screener.screen(["005930", "000660"], session)

        assert len(result) == 1
        assert result[0]["stock_code"] == "005930"


# ---------------------------------------------------------------------------
# save_results 테스트
# ---------------------------------------------------------------------------

class TestSaveResults:
    """screening_results 테이블에 2차 스크리닝 결과 저장."""

    @pytest.mark.asyncio
    async def test_save_secondary_results(self):
        screener = _make_screener()
        session = AsyncMock()
        session.commit = AsyncMock()

        results = [
            {
                "stock_code": "005930",
                "score": 85.0,
                "rank": 1,
                "factors": {"volume_factor": 90.0},
                "is_passed": True,
                "trade_strength": 80.0,
                "orderbook_ratio": 1.25,
            },
        ]

        count = await screener.save_results(session, results)
        assert count == 1
        assert session.add.call_count == 1
        session.commit.assert_awaited_once()
