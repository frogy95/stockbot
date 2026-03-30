"""Redis 기반 일회용 승인 토큰 관리."""
from __future__ import annotations

import json
import uuid

from core.redis import RedisClient
from modules.trading.strategy import TradeSignalData


class ApprovalManager:
    """매매 승인 토큰의 생성·검증·만료를 관리한다."""

    def __init__(self, redis_client: RedisClient):
        self._redis = redis_client

    async def create_approval(
        self, signal: TradeSignalData, quantity: int, timeout_sec: int
    ) -> str:
        """승인 토큰을 생성하고 Redis에 저장한다."""
        token = str(uuid.uuid4())
        payload = json.dumps({
            "signal": signal.model_dump(),
            "quantity": quantity,
        })
        await self._redis.set(f"approval:{token}", payload, ttl=timeout_sec)
        return token

    async def validate_approval(self, token: str) -> dict | None:
        """토큰을 검증하고 데이터를 반환한다. 일회용이므로 검증 후 삭제."""
        data = await self._redis.get(f"approval:{token}")
        if data is None:
            return None
        await self._redis.delete(f"approval:{token}")
        return json.loads(data)

    async def cancel_approval(self, token: str) -> bool:
        """승인 토큰을 취소(삭제)한다."""
        return await self._redis.delete(f"approval:{token}")

    async def get_pending_count(self) -> int:
        """대기 중인 승인 토큰 개수를 반환한다."""
        keys = await self._redis.scan_keys("approval:*")
        return len(keys)
