import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from core.database import get_engine, get_session_factory
from core.redis import redis_client

router = APIRouter()


@router.get("/health")
async def health_check():
    db_status = "disconnected"
    redis_status = "disconnected"

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        pass

    try:
        if await redis_client.ping():
            redis_status = "connected"
    except Exception:
        pass

    status = "healthy" if db_status == "connected" and redis_status == "connected" else "unhealthy"
    status_code = 200 if status == "healthy" else 503

    return JSONResponse(
        content={"status": status, "database": db_status, "redis": redis_status},
        status_code=status_code,
    )


@router.get("/health/readiness")
async def readiness_check(request: Request):
    """준비 상태 확인: DB + Redis + 스케줄러 + pipeline_healthy 4가지 모두 정상이면 200."""
    db_status = "disconnected"
    redis_status = "disconnected"
    pipeline_status = "unknown"

    async def _check_db() -> None:
        nonlocal db_status
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception:
            pass

    async def _check_redis() -> None:
        nonlocal redis_status
        try:
            if await redis_client.ping():
                redis_status = "connected"
        except Exception:
            pass

    async def _check_pipeline() -> None:
        nonlocal pipeline_status
        try:
            healthy_val = await redis_client.get("scheduler:pipeline_healthy")
            pipeline_status = "healthy" if healthy_val == "true" else "unhealthy"
        except Exception:
            pass

    await asyncio.gather(_check_db(), _check_redis(), _check_pipeline())

    scheduler = getattr(request.app.state, "collector_scheduler", None)
    scheduler_status = "running" if scheduler is not None and getattr(scheduler, "is_running", False) else "not_running"

    all_ok = (
        db_status == "connected"
        and redis_status == "connected"
        and scheduler_status == "running"
        and pipeline_status == "healthy"
    )
    status_code = 200 if all_ok else 503

    return JSONResponse(
        content={
            "status": "ready" if all_ok else "not_ready",
            "database": db_status,
            "redis": redis_status,
            "scheduler": scheduler_status,
            "pipeline": pipeline_status,
        },
        status_code=status_code,
    )


@router.get("/health/db-stats")
async def db_stats():
    """DB 테이블 기본 통계 (디버그용)."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            stocks = (await session.execute(text("SELECT COUNT(*) FROM stocks"))).scalar()
            market_data = (await session.execute(text("SELECT COUNT(*) FROM market_data"))).scalar()
            latest_date = (await session.execute(
                text("SELECT MAX(data_date) FROM market_data")
            )).scalar()
            screening = (await session.execute(
                text("SELECT COUNT(*) FROM screening_results")
            )).scalar()
        corp_codes = (await session.execute(text("SELECT COUNT(*) FROM corp_codes"))).scalar()
        financial_data = (await session.execute(text("SELECT COUNT(*) FROM financial_data"))).scalar()
        news_sentiment = (await session.execute(text("SELECT COUNT(*) FROM news_sentiments"))).scalar()
        return {
            "stocks_count": stocks,
            "market_data_count": market_data,
            "market_data_latest_date": str(latest_date) if latest_date else None,
            "screening_results_count": screening,
            "corp_codes_count": corp_codes,
            "financial_data_count": financial_data,
            "news_sentiment_count": news_sentiment,
        }
    except Exception as e:
        return {"error": str(e)}
