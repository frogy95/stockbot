"""Hotfix C — scheduler가 should_*=False 시에도 execute_*를 호출해야 self-clear 분기가 동작한다.

이전 결함: `if result.should_rollback:` 가드로 인해 execute_rollback이 발동 시에만 호출됨 →
한 번 발동된 phase86:rollback:active(또는 circuit_breaker:active)가 TTL(24h)까지 영원히 잔존.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_phase86_g2_self_clear_called_when_should_rollback_false():
    """should_rollback=False여도 execute_rollback이 호출되어야 한다 (self-clear 경로 보장)."""
    from modules.collector.scheduler import CollectorScheduler

    scheduler = CollectorScheduler.__new__(CollectorScheduler)
    scheduler._redis = MagicMock()
    scheduler._session_factory = MagicMock()
    scheduler._notifier_manager = None
    scheduler._load_daily_signal_count = AsyncMock(return_value=2)
    scheduler._load_daily_fallback_triggered = AsyncMock(return_value=0)
    scheduler._load_daily_fallback_signal_count = AsyncMock(return_value=0)
    scheduler._load_daily_primary_candidates = AsyncMock(return_value=20)
    scheduler._load_daily_tier_count = AsyncMock(return_value=2)

    with patch("modules.safety.auto_rollback.AutoRollbackEvaluator") as MockEval, \
         patch("modules.collector.scheduler.is_trading_day", return_value=True):
        mock_eval = MockEval.return_value
        mock_eval.evaluate = AsyncMock(
            return_value=MagicMock(should_rollback=False, triggered=[])
        )
        mock_eval.execute_rollback = AsyncMock()

        await scheduler._evaluate_phase86_g2()

        mock_eval.execute_rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_phase86_g3_self_clear_called_when_should_trigger_false():
    """should_trigger=False여도 execute가 호출되어야 한다 (self-clear 경로 보장)."""
    from modules.collector.scheduler import CollectorScheduler

    scheduler = CollectorScheduler.__new__(CollectorScheduler)
    scheduler._redis = MagicMock()
    scheduler._session_factory = MagicMock()
    scheduler._notifier_manager = None

    with patch("modules.safety.circuit_breaker.CircuitBreaker") as MockBreaker, \
         patch("modules.collector.scheduler.is_trading_day", return_value=True):
        mock_breaker = MockBreaker.return_value
        mock_breaker.evaluate = AsyncMock(
            return_value=MagicMock(should_trigger=False, reason="above_threshold")
        )
        mock_breaker.execute = AsyncMock()

        await scheduler._evaluate_phase86_g3()

        mock_breaker.execute.assert_awaited_once()
