from collections.abc import Callable, Awaitable

import redis.asyncio as aioredis

from core.config import settings


class RedisClient:
    def __init__(self, url: str):
        self._url = url
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._redis = aioredis.from_url(self._url, decode_responses=True)

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def ping(self) -> bool:
        if not self._redis:
            return False
        return await self._redis.ping()

    async def get(self, key: str) -> str | None:
        if not self._redis:
            return None
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if not self._redis:
            return
        if ttl:
            await self._redis.set(key, value, ex=ttl)
        else:
            await self._redis.set(key, value)

    async def delete(self, key: str) -> bool:
        if not self._redis:
            return False
        return bool(await self._redis.delete(key))

    async def ttl(self, key: str) -> int:
        if not self._redis:
            return -2
        return await self._redis.ttl(key)

    async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        """카운터 증분. ttl 제공 시 최초 생성(값==amount)에만 만료 적용."""
        if not self._redis:
            return 0
        new_value = await self._redis.incrby(key, amount)
        if ttl is not None and new_value == amount:
            await self._redis.expire(key, ttl)
        return int(new_value)

    async def mget(self, keys: list[str]) -> list[str | None]:
        if not self._redis or not keys:
            return []
        return await self._redis.mget(keys)

    async def lpush(self, key: str, value: str) -> int:
        if not self._redis:
            return 0
        return int(await self._redis.lpush(key, value))

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        if not self._redis:
            return
        await self._redis.ltrim(key, start, stop)

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        if not self._redis:
            return []
        return list(await self._redis.lrange(key, start, stop))

    async def scan_keys(self, pattern: str) -> list[str]:
        """패턴에 매칭되는 키 목록을 반환한다 (SCAN 사용)."""
        if not self._redis:
            return []
        keys = []
        async for key in self._redis.scan_iter(match=pattern):
            keys.append(key)
        return keys

    async def hset(self, key: str, field: str, value: str) -> None:
        if not self._redis:
            return
        await self._redis.hset(key, field, value)

    async def hget(self, key: str, field: str) -> str | None:
        if not self._redis:
            return None
        return await self._redis.hget(key, field)

    async def hdel(self, key: str, field: str) -> bool:
        if not self._redis:
            return False
        return bool(await self._redis.hdel(key, field))

    async def hgetall(self, key: str) -> dict[str, str]:
        if not self._redis:
            return {}
        return await self._redis.hgetall(key)

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[str]],
        ttl: int | None = None,
    ) -> str:
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await factory()
        await self.set(key, value, ttl=ttl)
        return value


redis_client = RedisClient(settings.redis_url)
