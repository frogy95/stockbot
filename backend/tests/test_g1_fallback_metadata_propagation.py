"""Phase 8.6 Sprint 1 — Task 3: G1 is_fallback 메타데이터 신호→주문 전파 검증.

4개 시나리오:
  1. SignalGenerator: candidate.is_fallback=True → TradeSignal.fallback=True + reason["fallback"]=True
  2. SignalGenerator: candidate normal → fallback=False
  3. OrderManager.submit_order: signal.fallback=True → Order.fallback=True
  4. M-F2 API: GET /api/v1/metrics/fallback-signal-rate 정상 응답
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from core.models.trading import Order, TradeSignal
from main import create_app
from modules.trading.order_manager import OrderManager
from modules.trading.position_sizer import PositionSize
from modules.trading.signal_generator import SignalGenerator
from modules.trading.strategy import (
    MarketSnapshot,
    RejectedSignal,
    Strategy,
    TradeSignalData,
)

_JWT_SECRET = "test-secret-key-32bytes-long-abc"


def _make_token() -> str:
    return pyjwt.encode(
        {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            "trading_env": "paper",
        },
        _JWT_SECRET,
        algorithm="HS256",
    )


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


class _StubStrategy(Strategy):
    """후보가 들어오면 무조건 신호를 생성하는 전략 스텁."""

    @property
    def name(self) -> str:
        return "stub_strategy"

    async def generate_signal(
        self, snapshot: MarketSnapshot
    ) -> TradeSignalData | RejectedSignal:
        return TradeSignalData(
            stock_code=snapshot.stock_code,
            signal_type="buy",
            strategy_name=self.name,
            confidence=0.8,
            reason={"breakout_tier": "prev_high"},
            entry_price=snapshot.current_price or 50_000,
            stop_loss=int((snapshot.current_price or 50_000) * 0.98),
            take_profit=int((snapshot.current_price or 50_000) * 1.03),
        )


def _make_candidate(stock_code: str = "005930", *, is_fallback: bool = False) -> dict:
    return {
        "stock_code": stock_code,
        "stock_name": "삼성전자",
        "stock_type": "STOCK",
        "current_price": 50_000,
        "open_price": 49_500,
        "high": 50_500,
        "low": 49_400,
        "prev_close": 49_500,
        "prev_high": 50_000,
        "volume": 1_000_000,
        "prev_volume": 800_000,
        "change_rate": 1.0,
        "trade_strength": 100.0,
        "total_bid_volume": 5000,
        "total_ask_volume": 5000,
        "recent_highs": [49_500, 49_800, 50_000],
        "recent_lows": [49_000, 49_200, 49_300],
        "recent_closes": [49_300, 49_500, 49_500],
        "is_fallback": is_fallback,
    }


def _make_session_factory_capture():
    """session.add()로 들어오는 객체를 캡처하는 팩토리."""
    added: list = []

    session = AsyncMock()
    # dup 체크용 select() → scalars().first() = None
    dup_result = MagicMock()
    dup_scalars = MagicMock()
    dup_scalars.first.return_value = None
    dup_result.scalars.return_value = dup_scalars
    session.execute = AsyncMock(return_value=dup_result)
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.commit = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield session

    return factory, added


# ---------------------------------------------------------------------------
# 시나리오 1·2: SignalGenerator 메타데이터 전파
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signal_generator_propagates_is_fallback_true_to_trade_signal():
    """candidate.is_fallback=True → TradeSignal.fallback=True + reason["fallback"]=True"""
    factory, added = _make_session_factory_capture()
    redis = AsyncMock()
    generator = SignalGenerator(factory, redis, _StubStrategy())

    candidate = _make_candidate(is_fallback=True)
    signals = await generator.generate_signals([candidate])

    assert len(signals) == 1
    assert signals[0].fallback is True

    # DB 기록 검증
    persisted = [obj for obj in added if isinstance(obj, TradeSignal)]
    assert len(persisted) == 1
    assert persisted[0].fallback is True, "DB 컬럼 fallback=True 누락"
    assert persisted[0].reason.get("fallback") is True, "reason JSON 폴백 키 누락"


@pytest.mark.asyncio
async def test_signal_generator_defaults_fallback_false_for_regular_candidate():
    """일반 후보 → TradeSignal.fallback=False"""
    factory, added = _make_session_factory_capture()
    redis = AsyncMock()
    generator = SignalGenerator(factory, redis, _StubStrategy())

    candidate = _make_candidate(is_fallback=False)
    signals = await generator.generate_signals([candidate])

    assert len(signals) == 1
    assert signals[0].fallback is False

    persisted = [obj for obj in added if isinstance(obj, TradeSignal)]
    assert len(persisted) == 1
    assert persisted[0].fallback is False
    assert persisted[0].reason.get("fallback", False) is False


# ---------------------------------------------------------------------------
# 시나리오 3: OrderManager.submit_order 메타데이터 승계
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_order_manager_propagates_fallback_from_signal_to_order():
    """signal.fallback=True → orders.fallback=True 승계"""
    added: list = []
    session = AsyncMock()
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 1))
    session.execute = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield session

    rest_client = AsyncMock()
    redis = AsyncMock()
    throttler = AsyncMock()

    manager = OrderManager(factory, rest_client, redis, throttler)
    signal = TradeSignalData(
        stock_code="005930",
        signal_type="buy",
        strategy_name="stub_strategy",
        confidence=0.8,
        reason={"fallback": True},
        entry_price=50_000,
        stop_loss=49_000,
        take_profit=51_500,
        fallback=True,
    )
    position_size = PositionSize(
        invest_amount=500_000, quantity=10, is_leverage=False, size_pct=10.0
    )

    await manager.submit_order(signal, position_size)

    orders = [obj for obj in added if isinstance(obj, Order)]
    assert len(orders) == 1
    assert orders[0].fallback is True, "Order.fallback=True 승계 실패"


@pytest.mark.asyncio
async def test_order_manager_default_fallback_false():
    """signal.fallback=False(기본) → orders.fallback=False"""
    added: list = []
    session = AsyncMock()
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 1))

    @asynccontextmanager
    async def factory():
        yield session

    manager = OrderManager(factory, AsyncMock(), AsyncMock(), AsyncMock())
    signal = TradeSignalData(
        stock_code="005930",
        signal_type="buy",
        strategy_name="stub_strategy",
        confidence=0.8,
        reason={},
        entry_price=50_000,
        stop_loss=49_000,
        take_profit=51_500,
    )
    position_size = PositionSize(
        invest_amount=500_000, quantity=10, is_leverage=False, size_pct=10.0
    )

    await manager.submit_order(signal, position_size)

    orders = [obj for obj in added if isinstance(obj, Order)]
    assert orders[0].fallback is False


# ---------------------------------------------------------------------------
# 시나리오 4: M-F2 API
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {_make_token()}"}


@pytest.mark.asyncio
async def test_m_f2_fallback_signal_rate_endpoint_responds(app, auth_headers):
    """M-F2 API: 정상 JSON 응답 (date, fallback_signals, fallback_triggered_codes, rate)."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.deps.settings") as mock_settings:
                mock_settings.JWT_SECRET = _JWT_SECRET
                mock_settings.TRADING_ENV = "paper"

                resp = await client.get(
                    "/api/v1/metrics/fallback-signal-rate",
                    headers=auth_headers,
                )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    for field in ("date", "fallback_signals", "fallback_triggered_codes", "rate"):
        assert field in data, f"필드 누락: {field}"
    # 분모 0 fail-safe — 데이터 없을 시 rate=null 허용
    assert data["rate"] is None or isinstance(data["rate"], (int, float))


@pytest.mark.asyncio
async def test_m_f2_endpoint_requires_auth(app):
    """인증 없이 접근 불가."""
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics/fallback-signal-rate")

    assert resp.status_code == 401
