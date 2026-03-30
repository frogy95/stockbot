"""승인 토큰 관리 테스트 — ApprovalManager (Redis 기반)."""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from core.config import settings
from core.redis import RedisClient
from modules.notifier.approval import ApprovalManager
from modules.trading.strategy import TradeSignalData


@pytest_asyncio.fixture
async def redis_client():
    client = RedisClient(settings.redis_url)
    await client.connect()
    yield client
    await client.disconnect()


@pytest_asyncio.fixture
async def approval_manager(redis_client):
    return ApprovalManager(redis_client)


@pytest.fixture
def sample_signal():
    return TradeSignalData(
        stock_code="005930",
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=0.85,
        reason={"rsi": 72, "volume_surge": True},
        entry_price=73000,
        stop_loss=71540,
        take_profit=75190,
    )


@pytest.mark.asyncio
async def test_create_approval(approval_manager, sample_signal, redis_client):
    """create_approval: UUID4 토큰 생성, Redis 키 저장, TTL 설정."""
    token = await approval_manager.create_approval(sample_signal, quantity=10, timeout_sec=30)

    assert len(token) == 36  # UUID4 형식
    stored = await redis_client.get(f"approval:{token}")
    assert stored is not None
    ttl_val = await redis_client.ttl(f"approval:{token}")
    assert 0 < ttl_val <= 30

    await redis_client.delete(f"approval:{token}")


@pytest.mark.asyncio
async def test_validate_approval(approval_manager, sample_signal, redis_client):
    """validate_approval: 유효 토큰 -> signal_data 반환 + 토큰 삭제 (일회용)."""
    token = await approval_manager.create_approval(sample_signal, quantity=10, timeout_sec=30)

    result = await approval_manager.validate_approval(token)
    assert result is not None
    assert result["signal"]["stock_code"] == "005930"
    assert result["quantity"] == 10

    # 일회용: 두 번째 검증 시 None
    result2 = await approval_manager.validate_approval(token)
    assert result2 is None


@pytest.mark.asyncio
async def test_validate_approval_invalid(approval_manager):
    """validate_approval: 존재하지 않는 토큰 -> None."""
    result = await approval_manager.validate_approval("nonexistent-token")
    assert result is None


@pytest.mark.asyncio
async def test_validate_approval_expired(approval_manager, sample_signal):
    """validate_approval: TTL 만료 후 -> None."""
    token = await approval_manager.create_approval(sample_signal, quantity=5, timeout_sec=1)
    await asyncio.sleep(1.5)

    result = await approval_manager.validate_approval(token)
    assert result is None


@pytest.mark.asyncio
async def test_get_pending_count(approval_manager, sample_signal, redis_client):
    """get_pending_count: 대기 중 승인 개수."""
    tokens = []
    for _ in range(3):
        t = await approval_manager.create_approval(sample_signal, quantity=10, timeout_sec=30)
        tokens.append(t)

    count = await approval_manager.get_pending_count()
    assert count >= 3

    for t in tokens:
        await redis_client.delete(f"approval:{t}")
