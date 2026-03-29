import pytest
import pytest_asyncio

from core.redis import RedisClient
from core.config import settings


@pytest_asyncio.fixture
async def redis():
    client = RedisClient(settings.redis_url)
    await client.connect()
    yield client
    await client.delete("test:key")
    await client.delete("test:ttl")
    await client.delete("test:get_or_set")
    await client.disconnect()


@pytest.mark.asyncio
async def test_ping(redis: RedisClient):
    assert await redis.ping() is True


@pytest.mark.asyncio
async def test_get_set_delete(redis: RedisClient):
    await redis.set("test:key", "hello")
    val = await redis.get("test:key")
    assert val == "hello"

    deleted = await redis.delete("test:key")
    assert deleted is True

    val = await redis.get("test:key")
    assert val is None


@pytest.mark.asyncio
async def test_set_with_ttl(redis: RedisClient):
    await redis.set("test:ttl", "expires", ttl=60)
    val = await redis.get("test:ttl")
    assert val == "expires"


@pytest.mark.asyncio
async def test_get_or_set(redis: RedisClient):
    async def factory():
        return "computed"

    val = await redis.get_or_set("test:get_or_set", factory, ttl=60)
    assert val == "computed"

    # 캐시 히트 — factory 호출 안 됨
    async def should_not_call():
        raise AssertionError("factory should not be called on cache hit")

    val = await redis.get_or_set("test:get_or_set", should_not_call, ttl=60)
    assert val == "computed"
