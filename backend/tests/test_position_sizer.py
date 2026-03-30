"""PositionSizer 단위 테스트 — DB 의존 없이 모킹으로 구현."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from modules.trading.position_sizer import PositionSize, PositionSizer


# ---------------------------------------------------------------------------
# 헬퍼: 가짜 session factory
# ---------------------------------------------------------------------------

_SENTINEL = object()


def _make_session_factory(execute_return=_SENTINEL):
    """AsyncMock 기반 세션 팩토리를 생성한다.

    ``execute_return`` 이 리스트이면 ``scalars().all()`` 에 사용하고,
    단일 객체(또는 None)이면 ``scalar_one_or_none()`` 에 사용한다.
    """
    session = AsyncMock()
    if execute_return is not _SENTINEL:
        result_mock = MagicMock()
        if isinstance(execute_return, list):
            result_mock.scalars.return_value.all.return_value = execute_return
        else:
            result_mock.scalar_one_or_none.return_value = execute_return
        session.execute.return_value = result_mock

    @asynccontextmanager
    async def factory():
        yield session

    return factory, session


def _make_setting(key: str, value: str):
    """SystemSetting 행을 흉내내는 간이 객체."""
    obj = MagicMock()
    obj.key = key
    obj.value = value
    return obj


def _make_stock(stock_name: str):
    """Stock 행을 흉내내는 간이 객체."""
    obj = MagicMock()
    obj.stock_name = stock_name
    return obj


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------

class TestPositionSizerCalculate:
    """투자금·수량 산출 테스트."""

    @pytest.mark.asyncio
    async def test_normal_stock_invest_amount(self):
        """일반 종목 투자금 계산: 잔고 1,000만원, 비율 10% → 투자금 100만원."""
        # load_settings: position_size_pct=10.0
        settings = [_make_setting("position_size_pct", "10.0")]
        factory, session = _make_session_factory(settings)

        sizer = PositionSizer(factory)
        await sizer.load_settings()

        # is_leverage → False (일반 종목)
        stock = _make_stock("삼성전자")
        lev_factory, lev_session = _make_session_factory(stock)
        sizer._session_factory = lev_factory

        result = await sizer.calculate(
            stock_code="005930", current_price=50_000, balance_amount=10_000_000
        )
        assert isinstance(result, PositionSize)
        assert result.invest_amount == 1_000_000
        assert result.is_leverage is False
        assert result.size_pct == 10.0

    @pytest.mark.asyncio
    async def test_leverage_etf_invest_amount(self):
        """레버리지 ETF 투자금 계산: 잔고 1,000만원, 비율 5% → 투자금 50만원."""
        settings = [
            _make_setting("position_size_pct", "10.0"),
            _make_setting("leverage_position_size_pct", "5.0"),
        ]
        factory, _ = _make_session_factory(settings)

        sizer = PositionSizer(factory)
        await sizer.load_settings()

        # is_leverage → True
        stock = _make_stock("KODEX 레버리지")
        lev_factory, _ = _make_session_factory(stock)
        sizer._session_factory = lev_factory

        result = await sizer.calculate(
            stock_code="122630", current_price=10_000, balance_amount=10_000_000
        )
        assert result.invest_amount == 500_000
        assert result.is_leverage is True
        assert result.size_pct == 5.0

    @pytest.mark.asyncio
    async def test_quantity_calculation(self):
        """수량 산출: 투자금 100만원, 현재가 50,000원 → 수량 20주."""
        factory, _ = _make_session_factory([])
        sizer = PositionSizer(factory)
        # 기본 비율 10% 사용

        stock = _make_stock("삼성전자")
        lev_factory, _ = _make_session_factory(stock)
        sizer._session_factory = lev_factory

        result = await sizer.calculate(
            stock_code="005930", current_price=50_000, balance_amount=10_000_000
        )
        assert result.quantity == 20

    @pytest.mark.asyncio
    async def test_quantity_truncation(self):
        """수량 산출 (단주 절사): 투자금 100만원, 현재가 33,000원 → 수량 30주."""
        factory, _ = _make_session_factory([])
        sizer = PositionSizer(factory)

        stock = _make_stock("LG에너지솔루션")
        lev_factory, _ = _make_session_factory(stock)
        sizer._session_factory = lev_factory

        result = await sizer.calculate(
            stock_code="373220", current_price=33_000, balance_amount=10_000_000
        )
        # 10,000,000 * 10% = 1,000,000 / 33,000 = 30.30… → 30
        assert result.quantity == 30

    @pytest.mark.asyncio
    async def test_zero_balance_returns_zero_quantity(self):
        """투자금 0 이하: 잔고 0 시 수량 0."""
        factory, _ = _make_session_factory([])
        sizer = PositionSizer(factory)

        stock = _make_stock("삼성전자")
        lev_factory, _ = _make_session_factory(stock)
        sizer._session_factory = lev_factory

        result = await sizer.calculate(
            stock_code="005930", current_price=50_000, balance_amount=0
        )
        assert result.invest_amount == 0
        assert result.quantity == 0

    @pytest.mark.asyncio
    async def test_zero_price_returns_zero_quantity(self):
        """현재가 0: 가격 0 시 수량 0 (ZeroDivisionError 방지)."""
        factory, _ = _make_session_factory([])
        sizer = PositionSizer(factory)

        stock = _make_stock("삼성전자")
        lev_factory, _ = _make_session_factory(stock)
        sizer._session_factory = lev_factory

        result = await sizer.calculate(
            stock_code="005930", current_price=0, balance_amount=10_000_000
        )
        assert result.quantity == 0


class TestIsLeverage:
    """레버리지 판별 테스트."""

    @pytest.mark.asyncio
    async def test_leverage_keyword_in_name(self):
        """stock_name에 '레버리지' 포함 시 True."""
        stock = _make_stock("KODEX 200선물인버스2X")
        factory, _ = _make_session_factory(stock)
        sizer = PositionSizer(factory)

        assert await sizer.is_leverage("252670") is True

    @pytest.mark.asyncio
    async def test_leverage_korean_keyword(self):
        """stock_name에 '레버리지' 포함 시 True."""
        stock = _make_stock("KODEX 코스닥150 레버리지")
        factory, _ = _make_session_factory(stock)
        sizer = PositionSizer(factory)

        assert await sizer.is_leverage("233740") is True

    @pytest.mark.asyncio
    async def test_normal_stock_not_leverage(self):
        """일반 종목은 False."""
        stock = _make_stock("삼성전자")
        factory, _ = _make_session_factory(stock)
        sizer = PositionSizer(factory)

        assert await sizer.is_leverage("005930") is False

    @pytest.mark.asyncio
    async def test_stock_not_found_returns_false(self):
        """종목이 없으면 False."""
        factory, _ = _make_session_factory(None)
        sizer = PositionSizer(factory)

        assert await sizer.is_leverage("999999") is False
