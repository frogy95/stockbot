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
async def test_metrics_requires_auth(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics/score-histogram")
    assert resp.status_code == 401
