"""Phase 8.5 Sprint 1 — Task 6: metrics API 라우터 검증."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch

from main import create_app

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


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {_make_token()}"}


async def _call(app, auth_headers, path: str):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.deps.settings") as mock_settings:
                mock_settings.JWT_SECRET = _JWT_SECRET
                mock_settings.TRADING_ENV = "paper"
                return await client.get(path, headers=auth_headers)


@pytest.mark.asyncio
async def test_score_histogram_200(app, auth_headers):
    resp = await _call(app, auth_headers, "/api/v1/metrics/score-histogram?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert "date" in body
    assert isinstance(body["buckets"], list)


@pytest.mark.asyncio
async def test_stage_heatmap_200(app, auth_headers):
    resp = await _call(app, auth_headers, "/api/v1/metrics/stage-heatmap?date=today")
    assert resp.status_code == 200
    body = resp.json()
    assert "date" in body
    assert isinstance(body["cells"], list)


@pytest.mark.asyncio
async def test_top_rejects_200(app, auth_headers):
    resp = await _call(app, auth_headers, "/api/v1/metrics/top-rejects?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_virtual_signals_200(app, auth_headers):
    resp = await _call(app, auth_headers, "/api/v1/metrics/virtual-signals?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_override_status_active_via_circuit_breaker(app, auth_headers):
    """Hotfix A — G3 단독 발동 시 triggered_at=None이어도 is_active=True여야 한다."""
    from api.deps import get_redis
    from core.override_keys import PHASE86_CIRCUIT_BREAKER_KEY, PHASE86_ROLLBACK_KEY

    class FakeRedis:
        def __init__(self, store: dict):
            self._store = store

        async def get(self, key):
            return self._store.get(key)

    store = {
        PHASE86_CIRCUIT_BREAKER_KEY: "true",
        "settings:override:SECONDARY_POOL_FALLBACK_ENABLED": "False",
    }
    app.dependency_overrides[get_redis] = lambda: FakeRedis(store)
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                with patch("api.deps.settings") as mock_settings:
                    mock_settings.JWT_SECRET = _JWT_SECRET
                    mock_settings.TRADING_ENV = "paper"
                    resp = await client.get(
                        "/api/v1/metrics/override-status", headers=auth_headers
                    )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_active"] is True, "G3 단독 발동에서 is_active=True 기대"
        assert body["triggered_at"] is None
        assert "SECONDARY_POOL_FALLBACK_ENABLED" in body["affected_keys"]
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_virtual_signals_stock_code_filter(app, auth_headers):
    """stock_code 쿼리 파라미터 적용 시 해당 종목 items만 반환되어야 한다."""
    resp = await _call(
        app, auth_headers, "/api/v1/metrics/virtual-signals?days=7&stock_code=187870"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["items"], list)
    for item in body["items"]:
        assert item["stock_code"] == "187870"


@pytest.mark.asyncio
async def test_shadow_heatmap_200(app, auth_headers):
    resp = await _call(app, auth_headers, "/api/v1/metrics/shadow-heatmap?date=today")
    assert resp.status_code == 200
    body = resp.json()
    assert "date" in body
    assert isinstance(body["stages"], list)
    assert len(body["stages"]) == 8  # SHADOW_TRACKED_STAGES
    assert isinstance(body["cells"], list)


@pytest.mark.asyncio
async def test_metrics_requires_auth(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics/score-histogram")
    assert resp.status_code == 401
