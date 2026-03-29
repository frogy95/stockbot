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
