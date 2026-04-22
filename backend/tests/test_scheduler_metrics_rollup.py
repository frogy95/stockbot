"""Phase 8.5 Sprint 1 — Task 5: 16:05 메트릭 일별 집계 배치 검증."""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from core.models.metrics import ScreeningMetricsDaily, StrategyMetricsDaily
from modules.collector.scheduler import CollectorScheduler


@pytest.fixture
def engine():
    return create_async_engine(settings.database_url)


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _today_str() -> str:
    return datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date().isoformat()


def _today() -> date:
    return datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()


def _make_scheduler(redis, session_factory):
    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.unsubscribe_all = AsyncMock()
    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()
    return CollectorScheduler(
        session_factory=session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis,
    )


class FakeRedis:
    def __init__(self, values: dict[str, str]):
        self.values = dict(values)

    async def scan_keys(self, pattern: str) -> list[str]:
        import fnmatch
        return [k for k in self.values.keys() if fnmatch.fnmatch(k, pattern)]

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


async def _cleanup(session_factory, today):
    async with session_factory() as session:
        await session.execute(
            delete(ScreeningMetricsDaily).where(ScreeningMetricsDaily.metric_date == today)
        )
        await session.execute(
            delete(StrategyMetricsDaily).where(StrategyMetricsDaily.metric_date == today)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_rollup_inserts_and_upserts(session_factory):
    today = _today()
    today_s = _today_str()
    await _cleanup(session_factory, today)

    redis = FakeRedis({
        f"metrics:secondary:score:{today_s}:>=75": "5",
        f"metrics:secondary:score:{today_s}:70-80": "3",
        f"metrics:secondary:score:{today_s}:40-50": "10",
        f"metrics:strategy:stage:{today_s}:min_volume_floor:09:30": "7",
        f"metrics:strategy:stage:{today_s}:breakout:10:00": "2",
        f"metrics:strategy:stage:{today_s}:pass:11:20": "1",
    })

    scheduler = _make_scheduler(redis, session_factory)
    await scheduler._rollup_daily_metrics()

    async with session_factory() as session:
        screening = (
            await session.execute(
                select(ScreeningMetricsDaily).where(ScreeningMetricsDaily.metric_date == today)
            )
        ).scalars().all()
        strategy = (
            await session.execute(
                select(StrategyMetricsDaily).where(StrategyMetricsDaily.metric_date == today)
            )
        ).scalars().all()

    assert len(screening) == 3
    assert len(strategy) == 3
    bucket_map = {r.bucket: r.count for r in screening}
    assert bucket_map == {">=75": 5, "70-80": 3, "40-50": 10}
    stage_map = {(r.stage, r.hour_min_bucket): r.count for r in strategy}
    assert stage_map == {
        ("min_volume_floor", "09:30"): 7,
        ("breakout", "10:00"): 2,
        ("pass", "11:20"): 1,
    }

    # 재실행 (UPSERT) — count 갱신
    redis.values[f"metrics:secondary:score:{today_s}:>=75"] = "12"
    redis.values[f"metrics:strategy:stage:{today_s}:min_volume_floor:09:30"] = "20"
    await scheduler._rollup_daily_metrics()

    async with session_factory() as session:
        screening = (
            await session.execute(
                select(ScreeningMetricsDaily).where(
                    ScreeningMetricsDaily.metric_date == today,
                    ScreeningMetricsDaily.bucket == ">=75",
                )
            )
        ).scalars().all()
        strategy = (
            await session.execute(
                select(StrategyMetricsDaily).where(
                    StrategyMetricsDaily.metric_date == today,
                    StrategyMetricsDaily.stage == "min_volume_floor",
                )
            )
        ).scalars().all()

    assert len(screening) == 1 and screening[0].count == 12
    assert len(strategy) == 1 and strategy[0].count == 20

    await _cleanup(session_factory, today)


@pytest.mark.asyncio
async def test_rollup_empty_keys_no_error(session_factory):
    """빈 Redis 상태에서도 예외 없음."""
    redis = FakeRedis({})
    scheduler = _make_scheduler(redis, session_factory)
    await scheduler._rollup_daily_metrics()


@pytest.mark.asyncio
async def test_rollup_swallows_exceptions(session_factory):
    """집계 실패해도 예외 전파 금지 (스케줄러 중단 방지)."""
    redis = MagicMock()
    redis.scan_keys = AsyncMock(side_effect=RuntimeError("redis down"))
    scheduler = _make_scheduler(redis, session_factory)
    # 예외가 전파되지 않아야 함
    await scheduler._rollup_daily_metrics()
