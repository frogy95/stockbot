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
from core.settings_override import resolve_override
from core.models.metrics import (
    ScreeningMetricsDaily,
    StrategyMetricsDaily,
    VirtualSignal,
)
from core.models.trading import TradeSignal
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
    limit: int = Query(5, ge=1, le=5),
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


class FallbackStatsResponse(BaseModel):
    date: str
    triggered_count: int
    codes: list[str]


@router.get("/fallback-stats", response_model=FallbackStatsResponse)
async def get_fallback_stats(
    date_param: str | None = Query(None, alias="date"),
    redis: RedisClient = Depends(get_redis),
) -> FallbackStatsResponse:
    """Phase 8.5 Sprint 2 — 폴백 발동 통계.

    Redis 키:
      - metrics:fallback:triggered:{today}: 폴백 발동 횟수 (incr)
      - metrics:fallback:code:{code}:{today}: 종목별 폴백 발동 횟수 (incr)
    """
    today = _today_kst()
    target_s = date_param if date_param not in (None, "today") else today.isoformat()

    triggered_key = f"metrics:fallback:triggered:{target_s}"
    triggered_count = int(await redis.get(triggered_key) or 0)

    # metrics:fallback:code:{code}:{today} 패턴으로 종목 코드 수집
    code_prefix = "metrics:fallback:code:"
    pattern = f"{code_prefix}*:{target_s}"
    keys = await redis.scan_keys(pattern)
    codes: list[str] = []
    for k in keys:
        # 키 형식: metrics:fallback:code:{code}:{date}
        suffix = k[len(code_prefix):]
        # suffix = "{code}:{date}"
        parts = suffix.rsplit(":", 1)
        if len(parts) == 2 and parts[1] == target_s:
            codes.append(parts[0])
    codes.sort()

    return FallbackStatsResponse(
        date=target_s,
        triggered_count=triggered_count,
        codes=codes,
    )


class FallbackSignalRateResponse(BaseModel):
    date: str
    fallback_signals: int
    fallback_triggered_codes: int
    rate: float | None  # 분모=0 시 None


@router.get("/fallback-signal-rate", response_model=FallbackSignalRateResponse)
async def get_fallback_signal_rate(
    date_param: str | None = Query(None, alias="date"),
    session: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
) -> FallbackSignalRateResponse:
    """Phase 8.6 Sprint 1 — G1 M-F2: 일별 폴백 신호율.

    분자: trade_signals.fallback=True 신호 수 (해당 날짜)
    분모: 그날 폴백 발동 종목 수 (Redis `metrics:fallback:code:*:{date}`)
    rate = 분자 / 분모 (분모=0 시 None — fail-safe)
    """
    today = _today_kst()
    target_s = date_param if date_param not in (None, "today") else today.isoformat()
    target = date.fromisoformat(target_s)

    # 분자 — DB
    tz = ZoneInfo(settings.MARKET_TIMEZONE)
    start = datetime.combine(target, datetime.min.time(), tzinfo=tz)
    end = start + timedelta(days=1)
    fallback_signals = int(
        (
            await session.execute(
                select(func.count(TradeSignal.id)).where(
                    TradeSignal.fallback.is_(True),
                    TradeSignal.created_at >= start,
                    TradeSignal.created_at < end,
                )
            )
        ).scalar()
        or 0
    )

    keys = await redis.scan_keys(f"metrics:fallback:code:*:{target_s}")
    fallback_triggered_codes = len(keys)

    rate = (
        round(fallback_signals / fallback_triggered_codes, 4)
        if fallback_triggered_codes
        else None
    )

    return FallbackSignalRateResponse(
        date=target_s,
        fallback_signals=fallback_signals,
        fallback_triggered_codes=fallback_triggered_codes,
        rate=rate,
    )


class OverrideStatusResponse(BaseModel):
    is_active: bool
    triggered_at: str | None
    reason: str | None
    affected_keys: list[str]


@router.get("/override-status", response_model=OverrideStatusResponse)
async def get_override_status(
    redis: RedisClient = Depends(get_redis),
) -> OverrideStatusResponse:
    """Phase 8.5 Sprint 2.5 — 자동 롤백 발동 상태 조회.

    Redis `settings:override:triggered_at`이 존재하면 is_active=True.
    `settings:override:reason`은 발동 사유.
    """
    triggered_at = await resolve_override(redis, "triggered_at", default=None)
    reason = await resolve_override(redis, "reason", default=None)
    return OverrideStatusResponse(
        is_active=triggered_at is not None,
        triggered_at=triggered_at,
        reason=reason,
        affected_keys=["MIN_VOLUME_FLOOR_MODE", "SECONDARY_POOL_FALLBACK_ENABLED"],
    )


class Phase86StatusResponse(BaseModel):
    rollback_active: bool  # phase86:rollback:active (G2)
    circuit_breaker_active: bool  # phase86:circuit_breaker:active (G3)
    fallback_share: float | None  # 오늘 R4 비율 (분모=0 시 None)
    fallback_signals: int
    primary_candidates: int


@router.get("/phase86-status", response_model=Phase86StatusResponse)
async def get_phase86_status(
    session: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
) -> Phase86StatusResponse:
    """Phase 8.6 Sprint 1 — G2(R1~R4)/G3 활성 상태 + R4 분자/분모 스냅샷."""
    rollback_active = (await redis.get("phase86:rollback:active")) is not None
    circuit_active = (await redis.get("phase86:circuit_breaker:active")) is not None

    today = _today_kst()
    tz = ZoneInfo(settings.MARKET_TIMEZONE)
    start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
    end = start + timedelta(days=1)
    fallback_signals = int(
        (
            await session.execute(
                select(func.count(TradeSignal.id)).where(
                    TradeSignal.fallback.is_(True),
                    TradeSignal.created_at >= start,
                    TradeSignal.created_at < end,
                )
            )
        ).scalar()
        or 0
    )
    primary_raw = await redis.get(f"screener:candidates:primary:{today.isoformat()}")
    primary_candidates = int(primary_raw or 0)
    denom = fallback_signals + primary_candidates
    share = round(fallback_signals / denom, 4) if denom > 0 else None

    return Phase86StatusResponse(
        rollback_active=rollback_active,
        circuit_breaker_active=circuit_active,
        fallback_share=share,
        fallback_signals=fallback_signals,
        primary_candidates=primary_candidates,
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
