import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from core.config import settings
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


@router.get("/health/observation-daily")
async def observation_daily(
    date_param: str | None = Query(None, alias="date"),
):
    """Phase 8.5 5거래일 관찰용 — 6개 지표를 한 번에 반환.

    KST 기준 일별 집계.
    - M-S1/M-S2/M-S3: tier별 신호 수 (gap_open / prev_high / prev_close)
    - M-F1: 폴백 발동 횟수 + 종목 코드
    - M-R: 자동 롤백 발동 여부 + 사유
    인증 없음 (집계 카운터만 노출, 민감 정보 없음).
    """
    tz = ZoneInfo(settings.MARKET_TIMEZONE)
    target: date = (
        date.fromisoformat(date_param)
        if date_param and date_param != "today"
        else datetime.now(tz).date()
    )
    target_s = target.isoformat()

    # 1) tier별 신호 수 — trade_signals.reason->>'breakout_tier'
    factory = get_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT COALESCE(reason->>'breakout_tier', 'unknown') AS tier,
                           COUNT(*) AS n
                    FROM trade_signals
                    WHERE (created_at AT TIME ZONE :tz)::date = :d
                    GROUP BY tier
                    """
                ),
                {"tz": settings.MARKET_TIMEZONE, "d": target},
            )
        ).all()
    tier_counts = {tier: int(n) for tier, n in rows}
    signals = {
        "gap_open": tier_counts.get("gap_open", 0),
        "prev_high": tier_counts.get("prev_high", 0),
        "prev_close": tier_counts.get("prev_close", 0),
        "other": sum(
            n for t, n in tier_counts.items()
            if t not in ("gap_open", "prev_high", "prev_close")
        ),
        "total": sum(tier_counts.values()),
    }

    # 2) 폴백 발동 (Redis: metrics:fallback:triggered:{date})
    triggered_count = int(await redis_client.get(f"metrics:fallback:triggered:{target_s}") or 0)
    code_pattern = f"metrics:fallback:code:*:{target_s}"
    code_keys = await redis_client.scan_keys(code_pattern)
    fallback_codes: list[str] = []
    for k in code_keys:
        suffix = k[len("metrics:fallback:code:"):]
        parts = suffix.rsplit(":", 1)
        if len(parts) == 2 and parts[1] == target_s:
            fallback_codes.append(parts[0])
    fallback_codes.sort()

    # 3) 자동 롤백 (Redis: settings:override:{triggered_at,reason})
    rollback_at = await redis_client.get("settings:override:triggered_at")
    rollback_reason = await redis_client.get("settings:override:reason")

    return {
        "date": target_s,
        "signals": signals,
        "fallback": {
            "triggered_count": triggered_count,
            "codes": fallback_codes,
        },
        "rollback": {
            "is_active": rollback_at is not None,
            "triggered_at": rollback_at,
            "reason": rollback_reason,
        },
    }


@router.get("/health/ws-diag")
async def ws_diagnostic(request: Request):
    """WS + 실시간 데이터 진단 — 스케줄러 WS 상태 및 Redis 캐시 확인."""
    diag: dict = {}

    # 1) 스케줄러 WS 상태
    ws_client = getattr(request.app.state, "kis_ws", None)
    ws_manager = getattr(request.app.state, "ws_manager", None)
    diag["ws_connected"] = ws_client.connected if ws_client else False
    diag["ws_subscription_count"] = ws_manager.count if ws_manager else 0
    diag["ws_subscribed_stocks"] = ws_manager.get_subscribed_stocks()[:10] if ws_manager else []

    # 2) Redis 실시간 데이터 샘플 확인
    sample_codes = diag["ws_subscribed_stocks"][:5]
    realtime_check = {}
    for code in sample_codes:
        exec_data = await redis_client.get(f"realtime:{code}:execution")
        ob_data = await redis_client.get(f"realtime:{code}:orderbook")
        realtime_check[code] = {
            "execution": exec_data is not None,
            "orderbook": ob_data is not None,
        }
        if exec_data:
            import json as _json
            try:
                parsed = _json.loads(exec_data)
                realtime_check[code]["exec_price"] = parsed.get("price")
                realtime_check[code]["exec_time"] = parsed.get("time")
            except Exception:
                pass
    diag["realtime_data"] = realtime_check

    # 3) 2차 스크리닝 DB 결과 확인
    try:
        factory = get_session_factory()
        async with factory() as session:
            secondary_count = (await session.execute(
                text("SELECT COUNT(*) FROM screening_results WHERE screening_type = 'secondary'")
            )).scalar()
            diag["secondary_screening_total"] = secondary_count
    except Exception as e:
        diag["secondary_screening_total"] = f"error: {e}"

    return diag
