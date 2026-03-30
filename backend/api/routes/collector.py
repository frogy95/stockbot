"""수집 상태 조회 / 수동 트리거 API."""

import json

from fastapi import APIRouter, Request

from core.redis import redis_client

router = APIRouter(tags=["collector"])


@router.get("/collector/status")
async def get_collector_status(request: Request):
    """수집 스케줄러 상태 조회."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"running": False, "message": "스케줄러 미초기화"}
    return scheduler.get_status()


@router.post("/collector/trigger/premarket")
async def trigger_premarket(request: Request):
    """수동 장전 수집 트리거."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    result = await scheduler.trigger_premarket()
    return {"triggered": True, "result": result}


@router.post("/collector/trigger/etf")
async def trigger_etf(request: Request):
    """수동 ETF 수집 트리거."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    result = await scheduler.trigger_etf()
    return {"triggered": True, "result": result}


@router.post("/collector/trigger/dart")
async def trigger_dart(request: Request):
    """수동 DART 재무 수집 트리거 (1차 스크리닝 통과 종목 대상)."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    result = await scheduler.trigger_dart()
    return {"triggered": True, "result": result}


@router.post("/collector/trigger/sentiment")
async def trigger_sentiment(request: Request):
    """수동 네이버 센티멘트 수집 트리거 (1차 스크리닝 통과 종목 대상)."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    result = await scheduler.trigger_sentiment()
    return {"triggered": True, "result": result}


@router.get("/collector/realtime/{stock_code}")
async def get_realtime_data(stock_code: str, request: Request):
    """Redis에서 실시간 시세 조회."""
    execution_raw = await redis_client.get(f"realtime:{stock_code}:execution")
    orderbook_raw = await redis_client.get(f"realtime:{stock_code}:orderbook")

    execution = json.loads(execution_raw) if execution_raw else None
    orderbook = json.loads(orderbook_raw) if orderbook_raw else None

    # 체결강도
    trade_strength_calc = getattr(request.app.state, "trade_strength", None)
    trade_strength = 50.0
    if trade_strength_calc:
        trade_strength = trade_strength_calc.get_strength(stock_code)

    return {
        "execution": execution,
        "orderbook": orderbook,
        "trade_strength": trade_strength,
    }
