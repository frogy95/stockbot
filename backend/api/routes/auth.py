import logging
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.config import settings
from core.redis import redis_client
from api.deps import get_current_user, UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_FAIL_KEY = "login:fail_count"
_FAIL_MAX = 5
_LOCK_TTL = 15 * 60


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _create_token(trading_env: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)
    payload = {
        "sub": "admin",
        "exp": expire,
        "trading_env": trading_env,
    }
    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def _make_token_response(trading_env: str) -> TokenResponse:
    return TokenResponse(
        access_token=_create_token(trading_env),
        expires_in=settings.JWT_EXPIRY_HOURS * 3600,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    if not settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 설정되지 않았습니다",
        )

    fail_count_raw = await redis_client.get(_FAIL_KEY)
    fail_count = int(fail_count_raw) if fail_count_raw else 0

    if fail_count >= _FAIL_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="로그인 시도 횟수 초과. 15분 후 다시 시도하세요",
        )

    if req.password != settings.ADMIN_PASSWORD:
        await redis_client.set(_FAIL_KEY, str(fail_count + 1), ttl=_LOCK_TTL)
        logger.warning("로그인 실패 (%d/%d)", fail_count + 1, _FAIL_MAX)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 올바르지 않습니다",
        )

    await redis_client.delete(_FAIL_KEY)
    return _make_token_response(settings.TRADING_ENV)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(user: UserInfo = Depends(get_current_user)):
    return _make_token_response(user.trading_env)


@router.get("/me", response_model=UserInfo)
async def get_me(user: UserInfo = Depends(get_current_user)):
    return user
