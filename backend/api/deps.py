from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.redis import redis_client, RedisClient


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_redis() -> RedisClient:
    return redis_client
