from collections.abc import AsyncGenerator

import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_session
from core.redis import redis_client, RedisClient

_bearer = HTTPBearer(auto_error=False)


class UserInfo(BaseModel):
    username: str
    trading_env: str


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_redis() -> RedisClient:
    return redis_client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserInfo:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 필요합니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = pyjwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=["HS256"],
        )
        username: str = payload.get("sub", "admin")
        trading_env: str = payload.get("trading_env", settings.TRADING_ENV)
        return UserInfo(username=username, trading_env=trading_env)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
