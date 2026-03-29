"""스크리닝 결과 조회 / 수동 트리거 API."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from core.models.screening_result import ScreeningResult

router = APIRouter(tags=["screening"])


@router.get("/screening/primary")
async def get_primary_results(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """최신 1차 스크리닝 결과 조회."""
    results, screened_at = await _get_latest_results(db, "primary")
    return {
        "results": results,
        "screened_at": screened_at,
        "total": len(results),
    }


@router.get("/screening/secondary")
async def get_secondary_results(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """최신 2차 스크리닝 결과 조회."""
    results, screened_at = await _get_latest_results(db, "secondary")
    return {
        "results": results,
        "screened_at": screened_at,
        "total": len(results),
    }


@router.post("/screening/trigger/primary")
async def trigger_primary(request: Request):
    """수동 1차 스크리닝 트리거."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    result = await scheduler.trigger_primary_screening()
    return {"triggered": True, "result": result}


@router.post("/screening/trigger/secondary")
async def trigger_secondary(request: Request):
    """수동 2차 스크리닝 트리거."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    result = await scheduler.trigger_secondary_screening()
    return {"triggered": True, "result": result}


@router.get("/screening/status")
async def get_screening_status(request: Request):
    """스크리닝 상태 조회."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"message": "스케줄러 미초기화"}
    return scheduler.get_screening_status()


async def _get_latest_results(
    db: AsyncSession, screening_type: str
) -> tuple[list[dict], str | None]:
    """screening_results에서 최신 배치 결과 조회."""
    latest_at_q = select(func.max(ScreeningResult.screened_at)).where(
        ScreeningResult.screening_type == screening_type
    )
    latest_at_result = await db.execute(latest_at_q)
    latest_at: datetime | None = latest_at_result.scalar()

    if latest_at is None:
        return [], None

    stmt = (
        select(ScreeningResult)
        .where(
            ScreeningResult.screening_type == screening_type,
            ScreeningResult.screened_at == latest_at,
        )
        .order_by(ScreeningResult.rank)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "stock_code": r.stock_code,
            "screening_type": r.screening_type,
            "score": float(r.score) if r.score else None,
            "rank": r.rank,
            "factors": r.factors,
            "is_hot": r.is_hot,
            "status": r.status,
        }
        for r in rows
    ], latest_at.isoformat()
