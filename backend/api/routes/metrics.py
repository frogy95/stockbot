"""Phase 8.5 Sprint 1 — 관측성 metrics API 4종."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import UserInfo, get_current_user, get_db, get_redis
from core.config import settings
from core.metrics_keys import (
    SECONDARY_SCORE_PREFIX,
    SHADOW_STAGE_PREFIX,
    SHADOW_TRACKED_STAGES,
    STRATEGY_STAGE_PREFIX,
    TOP_REJECT_KEY,
)
from core.models.metrics import (
    ScreeningMetricsDaily,
    StrategyMetricsDaily,
    VirtualSignal,
)
from core.redis import RedisClient

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(get_current_user)],
)


class ScoreBucketStat(BaseModel):
    bucket: str
    count_today: int
    count_7d_avg: float


class ScoreHistogramResponse(BaseModel):
    date: str
    buckets: list[ScoreBucketStat]


class StageHeatmapCell(BaseModel):
    stage: str
    hour_min: str
    count: int


class StageHeatmapResponse(BaseModel):
    date: str
    cells: list[StageHeatmapCell]


class TopRejectItem(BaseModel):
    recorded_at: str | None = None
    stage: str
    stock_code: str | None = None
    breakout_ref: int | None = None
    current_price: int | None = None
    detail: dict[str, Any] | None = None


class TopRejectsResponse(BaseModel):
    items: list[TopRejectItem]


class VirtualSignalItem(BaseModel):
    id: int
    observed_at: str
    stock_code: str
    stock_name: str | None
    virtual_stage: str
    breakout_ref: int | None
    current_price: int | None
    gap_rate: float | None
    prev_close: int | None
    would_execute: bool
    detail: dict[str, Any] | None


class VirtualSignalsResponse(BaseModel):
    items: list[VirtualSignalItem]


class ShadowStageCell(BaseModel):
    stage: str
    hour_min: str
    pass_count: int
    fail_count: int
    pass_rate: float | None  # 표본 0이면 None


class ShadowHeatmapResponse(BaseModel):
    date: str
    stages: list[str]
    cells: list[ShadowStageCell]


def _today_kst() -> date:
    return datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()


@router.get("/score-histogram", response_model=ScoreHistogramResponse)
async def score_histogram(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
) -> ScoreHistogramResponse:
    today = _today_kst()
    today_s = today.isoformat()

    # 오늘: Redis 카운터에서 읽기
    prefix = f"{SECONDARY_SCORE_PREFIX}:{today_s}:"
    keys = await redis.scan_keys(f"{prefix}*")
    today_counts: dict[str, int] = {}
    for k in keys:
        raw = await redis.get(k)
        if raw is None:
            continue
        try:
            today_counts[k[len(prefix):]] = int(raw)
        except (TypeError, ValueError):
            continue

    # 지난 N일: DB 평균
    start = today - timedelta(days=days)
    rows = (
        await session.execute(
            select(
                ScreeningMetricsDaily.bucket,
                func.avg(ScreeningMetricsDaily.count),
            )
            .where(
                ScreeningMetricsDaily.metric_date >= start,
                ScreeningMetricsDaily.metric_date < today,
            )
            .group_by(ScreeningMetricsDaily.bucket)
        )
    ).all()
    avg_map = {bucket: float(avg or 0) for bucket, avg in rows}

    all_buckets = sorted(set(today_counts) | set(avg_map))
    return ScoreHistogramResponse(
        date=today_s,
        buckets=[
            ScoreBucketStat(
                bucket=b,
                count_today=today_counts.get(b, 0),
                count_7d_avg=round(avg_map.get(b, 0.0), 2),
            )
            for b in all_buckets
        ],
    )


@router.get("/stage-heatmap", response_model=StageHeatmapResponse)
async def stage_heatmap(
    date_param: str | None = Query(None, alias="date"),
    session: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
) -> StageHeatmapResponse:
    today = _today_kst()
    target: date
    if date_param in (None, "today"):
        target = today
    else:
        target = date.fromisoformat(date_param)

    cells: list[StageHeatmapCell] = []
    if target == today:
        prefix = f"{STRATEGY_STAGE_PREFIX}:{target.isoformat()}:"
        keys = await redis.scan_keys(f"{prefix}*")
        for k in keys:
            raw = await redis.get(k)
            if raw is None:
                continue
            try:
                count = int(raw)
            except (TypeError, ValueError):
                continue
            suffix = k[len(prefix):]
            parts = suffix.rsplit(":", 2)
            if len(parts) < 3:
                continue
            stage = parts[0]
            hour_min = f"{parts[1]}:{parts[2]}"
            cells.append(StageHeatmapCell(stage=stage, hour_min=hour_min, count=count))
    else:
        rows = (
            await session.execute(
                select(
                    StrategyMetricsDaily.stage,
                    StrategyMetricsDaily.hour_min_bucket,
                    StrategyMetricsDaily.count,
                ).where(StrategyMetricsDaily.metric_date == target)
            )
        ).all()
        cells = [
            StageHeatmapCell(stage=s, hour_min=h, count=int(c)) for s, h, c in rows
        ]

    return StageHeatmapResponse(date=target.isoformat(), cells=cells)


@router.get("/top-rejects", response_model=TopRejectsResponse)
async def top_rejects(
    limit: int = Query(5, ge=1, le=50),
    redis: RedisClient = Depends(get_redis),
) -> TopRejectsResponse:
    raw_items = await redis.lrange(TOP_REJECT_KEY, 0, limit - 1)
    items: list[TopRejectItem] = []
    for raw in raw_items:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        items.append(
            TopRejectItem(
                recorded_at=data.get("recorded_at"),
                stage=data.get("stage", "unknown"),
                stock_code=data.get("stock_code"),
                breakout_ref=data.get("breakout_ref"),
                current_price=data.get("current_price"),
                detail=data.get("detail"),
            )
        )
    return TopRejectsResponse(items=items)


@router.get("/shadow-heatmap", response_model=ShadowHeatmapResponse)
async def shadow_heatmap(
    date_param: str | None = Query(None, alias="date"),
    redis: RedisClient = Depends(get_redis),
) -> ShadowHeatmapResponse:
    """Phase 8.5 Sprint 1.5 — 각 필터 독립 평가(shadow)의 pass/fail heatmap.

    Sprint 1의 stage-heatmap과 의미가 다름:
    - stage-heatmap: 실제 주문 경로의 short-circuit 결과 (첫 실패 stage만 기록)
    - shadow-heatmap: 각 필터를 독립 평가 — short-circuit 무관하게 모든 stage 표본 확보
    """
    today = _today_kst()
    target: date
    if date_param in (None, "today"):
        target = today
    else:
        target = date.fromisoformat(date_param)

    # Redis 키 스캔 (DB fallback 없음 — Redis 7일 TTL 만으로 관찰, 과거일자 쿼리는 빈 셀 반환)
    prefix = f"{SHADOW_STAGE_PREFIX}:{target.isoformat()}:"
    keys = await redis.scan_keys(f"{prefix}*")
    # (stage, hour_min) → {"pass": n, "fail": n}
    aggregate: dict[tuple[str, str], dict[str, int]] = {}
    for k in keys:
        suffix = k[len(prefix):]
        # {stage}:{outcome}:{hh}:{mm}
        parts = suffix.rsplit(":", 3)
        if len(parts) < 4:
            continue
        stage, outcome, hh, mm = parts
        if outcome not in ("pass", "fail"):
            continue
        raw = await redis.get(k)
        if raw is None:
            continue
        try:
            count = int(raw)
        except (TypeError, ValueError):
            continue
        hour_min = f"{hh}:{mm}"
        bucket = aggregate.setdefault((stage, hour_min), {"pass": 0, "fail": 0})
        bucket[outcome] += count

    cells: list[ShadowStageCell] = []
    for (stage, hour_min), counts in sorted(aggregate.items()):
        total = counts["pass"] + counts["fail"]
        pass_rate = counts["pass"] / total if total > 0 else None
        cells.append(
            ShadowStageCell(
                stage=stage,
                hour_min=hour_min,
                pass_count=counts["pass"],
                fail_count=counts["fail"],
                pass_rate=pass_rate,
            )
        )

    return ShadowHeatmapResponse(
        date=target.isoformat(),
        stages=list(SHADOW_TRACKED_STAGES),
        cells=cells,
    )


@router.get("/virtual-signals", response_model=VirtualSignalsResponse)
async def virtual_signals(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_db),
) -> VirtualSignalsResponse:
    tz = ZoneInfo(settings.MARKET_TIMEZONE)
    cutoff = datetime.now(tz) - timedelta(days=days)
    rows = (
        await session.execute(
            select(VirtualSignal)
            .where(VirtualSignal.observed_at >= cutoff)
            .order_by(VirtualSignal.observed_at.desc())
            .limit(500)
        )
    ).scalars().all()

    items = [
        VirtualSignalItem(
            id=r.id,
            observed_at=r.observed_at.isoformat(),
            stock_code=r.stock_code,
            stock_name=r.stock_name,
            virtual_stage=r.virtual_stage,
            breakout_ref=r.breakout_ref,
            current_price=r.current_price,
            gap_rate=float(r.gap_rate) if r.gap_rate is not None else None,
            prev_close=r.prev_close,
            would_execute=r.would_execute,
            detail=r.detail,
        )
        for r in rows
    ]
    return VirtualSignalsResponse(items=items)
