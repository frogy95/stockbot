from fastapi import APIRouter
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
        return {
            "stocks_count": stocks,
            "market_data_count": market_data,
            "market_data_latest_date": str(latest_date) if latest_date else None,
            "screening_results_count": screening,
        }
    except Exception as e:
        return {"error": str(e)}
