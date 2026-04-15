"""Task 3 테스트: eod_liquidator.liquidate_all이 Redis trailing_highs 키를 정리."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.trading.eod_liquidator import EodLiquidator
from modules.trading.position_manager import REDIS_TRAILING_HIGHS_KEY


@pytest.mark.asyncio
async def test_liquidate_all_deletes_trailing_highs_redis():
    """liquidate_all 완료 후 Redis `trailing_highs` 키 전체 삭제."""
    session = AsyncMock()
    # 활성 포지션 없음 → 빠르게 종료하지만 trailing_highs 정리는 수행되어야 함
    scalars = MagicMock()
    scalars.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=execute_result)

    @asynccontextmanager
    async def factory():
        yield session

    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock(return_value=True)

    liquidator = EodLiquidator(
        session_factory=factory,
        rest_client=AsyncMock(),
        redis_client=mock_redis,
    )

    await liquidator.liquidate_all()

    deleted_keys = [c.args[0] for c in mock_redis.delete.await_args_list if c.args]
    assert REDIS_TRAILING_HIGHS_KEY in deleted_keys
