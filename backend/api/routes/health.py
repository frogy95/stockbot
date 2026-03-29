from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from core.database import get_engine
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
