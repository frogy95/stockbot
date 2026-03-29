import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.clients.kis_config import PAPER
from core.clients.token_manager import KISTokenManager, KISAuthError


def make_redis_mock(cache=None):
    """Redis mock: get/set/delete/ttl 지원"""
    store = cache if cache is not None else {}
    ttl_store = {}
    redis = AsyncMock()

    async def mock_get(key):
        return store.get(key)

    async def mock_set(key, value, ttl=None):
        store[key] = value
        if ttl:
            ttl_store[key] = ttl

    async def mock_delete(key):
        return store.pop(key, None) is not None

    async def mock_ttl(key):
        return ttl_store.get(key, -1)

    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock(side_effect=mock_set)
    redis.delete = AsyncMock(side_effect=mock_delete)
    redis.ttl = AsyncMock(side_effect=mock_ttl)

    return redis, store, ttl_store


def make_http_mock(responses):
    """httpx.AsyncClient mock: 응답 목록을 순서대로 반환"""
    http = AsyncMock()
    call_count = {"n": 0}

    async def mock_post(url, **kwargs):
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        resp = responses[idx]
        mock_resp = MagicMock()
        mock_resp.status_code = resp.get("status_code", 200)
        mock_resp.json.return_value = resp.get("json", {})
        mock_resp.raise_for_status = MagicMock()
        if resp.get("status_code", 200) >= 400:
            from httpx import HTTPStatusError, Request, Response

            mock_resp.raise_for_status.side_effect = HTTPStatusError(
                "error", request=MagicMock(), response=mock_resp
            )
        return mock_resp

    http.post = AsyncMock(side_effect=mock_post)
    http.aclose = AsyncMock()
    return http


@pytest.mark.asyncio
async def test_get_access_token_cache_miss():
    """캐시 미스 시 한투 OAuth API 호출 후 Redis에 저장"""
    redis, store, _ = make_redis_mock()
    http = make_http_mock(
        [{"json": {"access_token": "test-token-123", "expires_in": 86400}}]
    )

    manager = KISTokenManager(env=PAPER, redis=redis)
    manager._http = http

    token = await manager.get_access_token()

    assert token == "test-token-123"
    assert http.post.call_count == 1
    assert redis.set.call_count == 1


@pytest.mark.asyncio
async def test_get_access_token_cache_hit():
    """캐시 히트 시 API 호출 없이 Redis에서 토큰 반환"""
    redis, store, _ = make_redis_mock({"kis:paper:access_token": "cached-token"})
    http = make_http_mock([])

    manager = KISTokenManager(env=PAPER, redis=redis)
    manager._http = http

    token = await manager.get_access_token()

    assert token == "cached-token"
    assert http.post.call_count == 0


@pytest.mark.asyncio
async def test_get_approval_key():
    """WebSocket approval_key 발급 + Redis 캐싱"""
    redis, store, _ = make_redis_mock()
    http = make_http_mock([{"json": {"approval_key": "ws-key-abc"}}])

    manager = KISTokenManager(env=PAPER, redis=redis)
    manager._http = http

    key = await manager.get_approval_key()

    assert key == "ws-key-abc"
    assert redis.set.call_count == 1


@pytest.mark.asyncio
async def test_get_hashkey():
    """hashkey 발급 (캐싱 없음, 매번 호출)"""
    redis, store, _ = make_redis_mock()
    http = make_http_mock(
        [{"json": {"HASH": "hash-value-1"}}, {"json": {"HASH": "hash-value-2"}}]
    )

    manager = KISTokenManager(env=PAPER, redis=redis)
    manager._http = http

    h1 = await manager.get_hashkey({"key": "val"})
    h2 = await manager.get_hashkey({"key": "val2"})

    assert h1 == "hash-value-1"
    assert h2 == "hash-value-2"
    assert http.post.call_count == 2
    assert redis.set.call_count == 0


@pytest.mark.asyncio
async def test_refresh_token():
    """기존 토큰 무시하고 강제 재발급"""
    redis, store, _ = make_redis_mock({"kis:paper:access_token": "old-token"})
    http = make_http_mock(
        [{"json": {"access_token": "new-token-456", "expires_in": 86400}}]
    )

    manager = KISTokenManager(env=PAPER, redis=redis)
    manager._http = http

    token = await manager.refresh_token()

    assert token == "new-token-456"
    assert redis.delete.call_count == 1
    assert http.post.call_count == 1


@pytest.mark.asyncio
async def test_should_refresh_when_ttl_low():
    """Redis TTL 기반으로 만료 2시간 전이면 True"""
    redis, _, ttl_store = make_redis_mock({"kis:paper:access_token": "token"})
    ttl_store["kis:paper:access_token"] = 3600  # 1시간 남음 (< 7200)

    manager = KISTokenManager(env=PAPER, redis=redis)

    assert await manager._should_refresh() is True


@pytest.mark.asyncio
async def test_should_refresh_when_ttl_high():
    """TTL이 충분하면 False"""
    redis, _, ttl_store = make_redis_mock({"kis:paper:access_token": "token"})
    ttl_store["kis:paper:access_token"] = 20000

    manager = KISTokenManager(env=PAPER, redis=redis)

    assert await manager._should_refresh() is False


@pytest.mark.asyncio
async def test_auth_error_on_http_failure():
    """토큰 발급 실패(HTTP 에러) 시 KISAuthError 예외"""
    redis, _, _ = make_redis_mock()
    http = make_http_mock([{"status_code": 500, "json": {"error": "server error"}}])

    manager = KISTokenManager(env=PAPER, redis=redis)
    manager._http = http

    with pytest.raises(KISAuthError):
        await manager.get_access_token()


@pytest.mark.asyncio
async def test_rate_limit_retry():
    """토큰 발급 Rate Limit 실패(EGW00133) 시 재시도"""
    redis, _, _ = make_redis_mock()
    http = make_http_mock(
        [
            {"json": {"msg_cd": "EGW00133", "msg1": "초당 거래건수를 초과"}},
            {"json": {"access_token": "retry-token", "expires_in": 86400}},
        ]
    )

    manager = KISTokenManager(env=PAPER, redis=redis)
    manager._http = http
    manager._RATE_LIMIT_WAIT = 0.01  # 테스트 시 대기 시간 최소화

    token = await manager.get_access_token()

    assert token == "retry-token"
    assert http.post.call_count == 2
