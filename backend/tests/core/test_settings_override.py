import pytest
from unittest.mock import AsyncMock

from core.settings_override import resolve_override, OVERRIDE_PREFIX
from core.config import settings as _settings


@pytest.mark.asyncio
async def test_resolve_override_returns_default_when_disabled(monkeypatch):
    monkeypatch.setattr(_settings, "SETTINGS_OVERRIDE_ENABLED", False)
    redis = AsyncMock()
    redis.get.return_value = "legacy"
    result = await resolve_override(redis, "MIN_VOLUME_FLOOR_MODE", default="dynamic")
    assert result == "dynamic"
    redis.get.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_override_returns_redis_value(monkeypatch):
    monkeypatch.setattr(_settings, "SETTINGS_OVERRIDE_ENABLED", True)
    redis = AsyncMock()
    redis.get.return_value = "legacy"
    result = await resolve_override(redis, "MIN_VOLUME_FLOOR_MODE", default="dynamic")
    assert result == "legacy"
    redis.get.assert_awaited_once_with(f"{OVERRIDE_PREFIX}MIN_VOLUME_FLOOR_MODE")


@pytest.mark.asyncio
async def test_resolve_override_returns_default_when_redis_none(monkeypatch):
    monkeypatch.setattr(_settings, "SETTINGS_OVERRIDE_ENABLED", True)
    result = await resolve_override(None, "KEY", default="fallback")
    assert result == "fallback"


@pytest.mark.asyncio
async def test_resolve_override_returns_default_on_missing_key(monkeypatch):
    monkeypatch.setattr(_settings, "SETTINGS_OVERRIDE_ENABLED", True)
    redis = AsyncMock()
    redis.get.return_value = None
    result = await resolve_override(redis, "KEY", default="fallback")
    assert result == "fallback"


@pytest.mark.asyncio
async def test_resolve_override_fallback_on_cast_error(monkeypatch):
    monkeypatch.setattr(_settings, "SETTINGS_OVERRIDE_ENABLED", True)
    redis = AsyncMock()
    redis.get.return_value = "not_an_int"
    result = await resolve_override(redis, "KEY", default=42, cast=int)
    assert result == 42


@pytest.mark.asyncio
async def test_resolve_override_fallback_on_redis_error(monkeypatch):
    monkeypatch.setattr(_settings, "SETTINGS_OVERRIDE_ENABLED", True)
    redis = AsyncMock()
    redis.get.side_effect = RuntimeError("redis down")
    result = await resolve_override(redis, "KEY", default="safe")
    assert result == "safe"


@pytest.mark.asyncio
async def test_resolve_override_cast_bool():
    redis = AsyncMock()
    redis.get.return_value = "False"
    result = await resolve_override(
        redis, "BOOL", default=True,
        cast=lambda s: s.lower() not in ("false", "0", "no"),
    )
    assert result is False
