"""Phase 8.6 Sprint 4 — backtest API 라우터 (admin 가드)."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import UserInfo, get_current_user, get_db
from core.config import settings
from core.models.backtest import BacktestRun, BacktestSignalMetric, LiveGateStatus

router = APIRouter(tags=["backtest"])


# ---------------------------------------------------------------------------
# admin 가드 헬퍼
# ---------------------------------------------------------------------------


def require_backtest_admin(current: UserInfo = Depends(get_current_user)) -> UserInfo:
    """BACKTEST_ADMIN_USERNAME 이 None 이거나 현재 사용자명과 불일치하면 403."""
    if (
        settings.BACKTEST_ADMIN_USERNAME is None
        or current.username != settings.BACKTEST_ADMIN_USERNAME
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="backtest admin only",
        )
    return current


# ---------------------------------------------------------------------------
# 응답 모델
# ---------------------------------------------------------------------------


class BacktestRunResponse(BaseModel):
    run_id: str
    period_start: date
    period_end: date
    n_trading_days: int
    regime_box_days: int
    regime_trend_days: int
    status: str
    error: str | None
    started_at: str
    completed_at: str | None
    created_at: str


class BacktestRunListResponse(BaseModel):
    runs: list[BacktestRunResponse]


class BacktestSignalMetricResponse(BaseModel):
    tier: str
    pass_rate_simulated: float
    pass_rate_actual: float | None
    ks_statistic: float | None
    ks_pvalue: float | None
    bootstrap_ci_lower: float | None
    bootstrap_ci_upper: float | None
    recorded_at: str


class BacktestRunDetailResponse(BaseModel):
    run: BacktestRunResponse
    metrics: list[BacktestSignalMetricResponse]


class LiveGateStatusResponse(BaseModel):
    evaluated_at: str | None
    g_bt1_passed: bool
    g_bt2_passed: bool
    g_bt3_passed: bool
    all_passed: bool
    details: dict[str, Any] | None


class KSTrendPoint(BaseModel):
    run_id: str
    period_end: date
    ks_pvalue: float | None


class KSTrendResponse(BaseModel):
    tier: str
    points: list[KSTrendPoint]


class RunTriggerResponse(BaseModel):
    run_id: str
    status: str


class BackfillResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


class _RunBody(BaseModel):
    period_end: date
    n_days: int = 60


class _BackfillBody(BaseModel):
    start_date: date
    end_date: date


def _fmt(dt: Any) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _to_run_response(run: BacktestRun) -> BacktestRunResponse:
    return BacktestRunResponse(
        run_id=run.run_id,
        period_start=run.period_start,
        period_end=run.period_end,
        n_trading_days=run.n_trading_days,
        regime_box_days=run.regime_box_days,
        regime_trend_days=run.regime_trend_days,
        status=run.status,
        error=run.error,
        started_at=_fmt(run.started_at),
        completed_at=_fmt(run.completed_at),
        created_at=_fmt(run.created_at),
    )


async def _run_walkforward(run_id: str, period_end: date, n_days: int) -> None:
    """BackgroundTasks 콜백 — WalkForwardRunner.run 실행."""
    from core.database import get_session_factory
    from modules.backtest.walkforward import WalkForwardRunner

    session_factory = get_session_factory()
    async with session_factory() as session:
        runner = WalkForwardRunner(session=session)
        await runner.run(run_id=run_id, period_end=period_end, n_days=n_days)


async def _run_backfill(rest_client, start_date: date, end_date: date) -> None:
    """BackgroundTasks 콜백 — historical_loader.backfill_missing_daily 실행."""
    from core.database import get_session_factory
    from modules.backtest.historical_loader import backfill_missing_daily

    session_factory = get_session_factory()
    async with session_factory() as session:
        await backfill_missing_daily(
            session, start_date=start_date, end_date=end_date, rest_client=rest_client
        )


@router.post("/run", response_model=RunTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    body: _RunBody,
    background_tasks: BackgroundTasks,
    _: UserInfo = Depends(require_backtest_admin),
) -> RunTriggerResponse:
    """walk-forward 백테스트 실행 트리거 (BackgroundTasks 비동기)."""
    run_id = str(uuid.uuid4())
    background_tasks.add_task(_run_walkforward, run_id, body.period_end, body.n_days)
    return RunTriggerResponse(run_id=run_id, status="running")


@router.get("/runs", response_model=BacktestRunListResponse)
async def list_runs(
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_backtest_admin),
) -> BacktestRunListResponse:
    """최근 백테스트 실행 목록 (period_end DESC)."""
    rows = (
        await session.execute(
            select(BacktestRun).order_by(BacktestRun.period_end.desc()).limit(limit)
        )
    ).scalars().all()
    return BacktestRunListResponse(runs=[_to_run_response(r) for r in rows])


@router.get("/runs/{run_id}", response_model=BacktestRunDetailResponse)
async def get_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_backtest_admin),
) -> BacktestRunDetailResponse:
    """단일 실행 상세 + tier별 BacktestSignalMetric 포함."""
    run = (
        await session.execute(select(BacktestRun).where(BacktestRun.run_id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    metrics_rows = (
        await session.execute(
            select(BacktestSignalMetric).where(BacktestSignalMetric.run_id == run_id)
        )
    ).scalars().all()
    metrics = [
        BacktestSignalMetricResponse(
            tier=m.tier,
            pass_rate_simulated=m.pass_rate_simulated,
            pass_rate_actual=m.pass_rate_actual,
            ks_statistic=m.ks_statistic,
            ks_pvalue=m.ks_pvalue,
            bootstrap_ci_lower=m.bootstrap_ci_lower,
            bootstrap_ci_upper=m.bootstrap_ci_upper,
            recorded_at=_fmt(m.recorded_at),
        )
        for m in metrics_rows
    ]
    return BacktestRunDetailResponse(run=_to_run_response(run), metrics=metrics)


@router.get("/distribution-check", response_model=KSTrendResponse)
async def distribution_check(
    tier: str = Query("prev_high"),
    session: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_backtest_admin),
) -> KSTrendResponse:
    """최근 7개 BacktestRun 의 지정 tier KS p-value 시계열 반환."""
    run_rows = (
        await session.execute(
            select(BacktestRun.run_id, BacktestRun.period_end)
            .order_by(BacktestRun.period_end.desc())
            .limit(7)
        )
    ).all()

    if not run_rows:
        return KSTrendResponse(tier=tier, points=[])

    run_id_list = [r[0] for r in run_rows]
    metric_rows = (
        await session.execute(
            select(BacktestSignalMetric).where(
                BacktestSignalMetric.run_id.in_(run_id_list),
                BacktestSignalMetric.tier == tier,
            )
        )
    ).scalars().all()
    metric_map = {m.run_id: m for m in metric_rows}

    points = [
        KSTrendPoint(
            run_id=run_id_val,
            period_end=period_end_val,
            ks_pvalue=metric_map[run_id_val].ks_pvalue if run_id_val in metric_map else None,
        )
        for run_id_val, period_end_val in reversed(run_rows)
    ]

    return KSTrendResponse(tier=tier, points=points)


@router.get("/live-gate-status", response_model=LiveGateStatusResponse)
async def get_live_gate_status(
    session: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_backtest_admin),
) -> LiveGateStatusResponse:
    """최신 LiveGateStatus row 반환. row 없으면 기본값(all False) 응답."""
    row = (
        await session.execute(
            select(LiveGateStatus).order_by(LiveGateStatus.evaluated_at.desc()).limit(1)
        )
    ).scalar_one_or_none()

    if row is None:
        return LiveGateStatusResponse(
            evaluated_at=None,
            g_bt1_passed=False,
            g_bt2_passed=False,
            g_bt3_passed=False,
            all_passed=False,
            details=None,
        )

    return LiveGateStatusResponse(
        evaluated_at=_fmt(row.evaluated_at),
        g_bt1_passed=row.g_bt1_passed,
        g_bt2_passed=row.g_bt2_passed,
        g_bt3_passed=row.g_bt3_passed,
        all_passed=row.all_passed,
        details=row.details,
    )


@router.post("/backfill-daily", response_model=BackfillResponse, status_code=status.HTTP_202_ACCEPTED)
async def backfill_daily(
    body: _BackfillBody,
    background_tasks: BackgroundTasks,
    request: Request,
    _: UserInfo = Depends(require_backtest_admin),
) -> BackfillResponse:
    """historical_loader.backfill_missing_daily 트리거 (BackgroundTasks 비동기)."""
    rest_client = getattr(request.app.state, "kis_inquiry", None)
    if rest_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KIS 조회 클라이언트 미초기화 (app.state.kis_inquiry 부재)",
        )
    background_tasks.add_task(_run_backfill, rest_client, body.start_date, body.end_date)
    return BackfillResponse(status="running")
