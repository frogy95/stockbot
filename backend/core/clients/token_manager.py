import asyncio
import logging

import httpx

from core.clients.kis_config import KISEnvironment

logger = logging.getLogger(__name__)

TOKEN_TTL = 82800  # 23시간
REFRESH_THRESHOLD = 7200  # 2시간


class KISAuthError(Exception):
    pass


class KISTokenManager:
    _RATE_LIMIT_WAIT = 60  # EGW00133 재시도 대기 (초)

    def __init__(self, env: KISEnvironment, redis):
        self._env = env
        self._redis = redis
        self._http: httpx.AsyncClient | None = None

    def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._env.base_url, timeout=30.0
            )
        return self._http

    def _token_key(self) -> str:
        return f"kis:{self._env.name}:access_token"

    def _approval_key_key(self) -> str:
        return f"kis:{self._env.name}:approval_key"

    async def get_access_token(self) -> str:
        cached = await self._redis.get(self._token_key())
        if cached:
            return cached

        token, expires_in = await self._request_token()
        ttl = min(expires_in - 600, TOKEN_TTL)
        await self._redis.set(self._token_key(), token, ttl=ttl)
        return token

    async def get_approval_key(self) -> str:
        cached = await self._redis.get(self._approval_key_key())
        if cached:
            return cached

        key = await self._request_approval_key()
        await self._redis.set(self._approval_key_key(), key, ttl=TOKEN_TTL)
        return key

    async def get_hashkey(self, body: dict) -> str:
        return await self._request_hashkey(body)

    async def refresh_token(self) -> str:
        await self._redis.delete(self._token_key())
        token, expires_in = await self._request_token()
        ttl = min(expires_in - 600, TOKEN_TTL)
        await self._redis.set(self._token_key(), token, ttl=ttl)
        return token

    async def _should_refresh(self) -> bool:
        remaining = await self._redis.ttl(self._token_key())
        return remaining < REFRESH_THRESHOLD

    async def _request_token(self) -> tuple[str, int]:
        http = self._ensure_http()
        body = {
            "grant_type": "client_credentials",
            "appkey": self._env.app_key,
            "appsecret": self._env.app_secret,
        }

        try:
            resp = await http.post("/oauth2/tokenP", json=body)
            data = resp.json()

            if data.get("msg_cd") == "EGW00133":
                logger.warning("토큰 발급 Rate Limit, %s초 후 재시도", self._RATE_LIMIT_WAIT)
                await asyncio.sleep(self._RATE_LIMIT_WAIT)
                resp = await http.post("/oauth2/tokenP", json=body)
                data = resp.json()

            resp.raise_for_status()

            if "access_token" not in data:
                raise KISAuthError(f"토큰 응답에 access_token 없음: {data}")

            return data["access_token"], data.get("expires_in", 86400)

        except httpx.HTTPStatusError as e:
            raise KISAuthError(f"토큰 발급 실패: {e}") from e

    async def _request_approval_key(self) -> str:
        http = self._ensure_http()
        body = {
            "grant_type": "client_credentials",
            "appkey": self._env.app_key,
            "secretkey": self._env.app_secret,
        }

        try:
            resp = await http.post("/oauth2/Approval", json=body)
            resp.raise_for_status()
            data = resp.json()

            if "approval_key" not in data:
                raise KISAuthError(f"approval_key 응답 누락: {data}")

            return data["approval_key"]

        except httpx.HTTPStatusError as e:
            raise KISAuthError(f"approval_key 발급 실패: {e}") from e

    async def _request_hashkey(self, body: dict) -> str:
        http = self._ensure_http()
        headers = {
            "Content-Type": "application/json",
            "appkey": self._env.app_key,
            "appsecret": self._env.app_secret,
        }

        try:
            resp = await http.post("/uapi/hashkey", json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()["HASH"]

        except httpx.HTTPStatusError as e:
            raise KISAuthError(f"hashkey 발급 실패: {e}") from e

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None
