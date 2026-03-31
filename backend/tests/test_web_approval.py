"""웹 승인/거부 API 테스트."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import get_current_user, UserInfo
from main import create_app


@pytest.fixture
def app():
    """lifespan 비활성화 테스트 앱."""
    test_app = create_app()
    test_app.router.lifespan_context = None
    test_app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="admin", trading_env="paper"
    )
    yield test_app
    test_app.dependency_overrides.clear()


def _make_engine(approve_result: bool = True, reject_result: bool = True):
    engine = MagicMock()
    engine.approve_signal = AsyncMock(return_value=approve_result)
    engine.reject_signal = AsyncMock(return_value=reject_result)
    return engine


@pytest.mark.asyncio
async def test_approve_valid_token(app):
    """POST /signals/{token}/approve -- 유효 토큰 -> 200 + approved."""
    app.state.trading_engine = _make_engine(approve_result=True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/trading/signals/valid-token/approve")

    assert resp.status_code == 200
    assert resp.json()["result"] == "approved"


@pytest.mark.asyncio
async def test_reject_valid_token(app):
    """POST /signals/{token}/reject -- 유효 토큰 -> 200 + rejected."""
    app.state.trading_engine = _make_engine(reject_result=True)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/trading/signals/valid-token/reject")

    assert resp.status_code == 200
    assert resp.json()["result"] == "rejected"


@pytest.mark.asyncio
async def test_approve_expired_token(app):
    """POST /signals/{token}/approve -- 만료/없는 토큰 -> 404."""
    app.state.trading_engine = _make_engine(approve_result=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/v1/trading/signals/expired-token/approve")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_pending_empty(app):
    """GET /signals/pending -- approval_manager 없으면 빈 배열."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/trading/signals/pending")

    assert resp.status_code == 200
    data = resp.json()
    assert data["pending"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_get_pending_with_items(app):
    """GET /signals/pending -- approval_manager 있으면 항목 포함."""
    token = "abc-token"
    pending_item = {
        "token": token,
        "signal": {
            "stock_code": "005930",
            "signal_type": "BUY",
            "strategy_name": "momentum",
            "confidence": 0.9,
            "entry_price": 70000,
            "stop_loss": 68000,
            "take_profit": 73000,
        },
        "quantity": 5,
        "expires_in_sec": 45,
    }

    mgr = MagicMock()
    mgr.list_pending = AsyncMock(return_value=[pending_item])
    app.state.approval_manager = mgr

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/trading/signals/pending")

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert len(data["pending"]) == 1
    item = data["pending"][0]
    assert item["token"] == token
    assert item["signal"]["stock_code"] == "005930"
    assert item["expires_in_sec"] == 45
