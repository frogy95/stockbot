"""수집 상태 조회 / 수동 트리거 API."""

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from core.redis import redis_client
from modules.collector.scheduler import PIPELINE_RUNNING_KEY

router = APIRouter(tags=["collector"])


@router.get("/collector/status")
async def get_collector_status(request: Request):
    """수집 스케줄러 상태 조회."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"running": False, "message": "스케줄러 미초기화"}
    return scheduler.get_status()


@router.post("/collector/trigger/premarket")
async def trigger_premarket(background_tasks: BackgroundTasks, request: Request):
    """수동 장전 수집 트리거 (백그라운드 실행, /collector/status 로 완료 확인)."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    background_tasks.add_task(scheduler.trigger_premarket)
    return {"triggered": True, "message": "수집 시작됨. /api/v1/collector/status 에서 last_premarket 확인"}


@router.post("/collector/trigger/kis-daily/{target_date}")
async def trigger_kis_daily(target_date: str, background_tasks: BackgroundTasks, request: Request):
    """수동 KIS 일봉 수집 트리거 (특정 날짜 지정, 백그라운드 실행).

    target_date: YYYYMMDD 형식 (예: 20260402)
    """
    if len(target_date) != 8 or not target_date.isdigit():
        raise HTTPException(status_code=400, detail="target_date는 YYYYMMDD 형식이어야 합니다")
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    background_tasks.add_task(scheduler.trigger_kis_daily, target_date)
    return {
        "triggered": True,
        "target_date": target_date,
        "message": f"KIS 일봉 수집({target_date}) 시작됨. /api/v1/collector/pipeline-status 에서 확인",
    }


@router.post("/collector/trigger/etf")
async def trigger_etf(background_tasks: BackgroundTasks, request: Request):
    """수동 ETF 수집 트리거 (백그라운드 실행)."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    background_tasks.add_task(scheduler.trigger_etf)
    return {"triggered": True, "message": "ETF 수집 시작됨. /api/v1/collector/status 에서 last_etf 확인"}


@router.post("/collector/trigger/etf-master")
async def trigger_etf_master(background_tasks: BackgroundTasks, request: Request):
    """수동 ETF 마스터 갱신 트리거 (백그라운드 실행)."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    background_tasks.add_task(scheduler.trigger_etf_master)
    return {"triggered": True, "message": "ETF 마스터 갱신 시작됨. /api/v1/collector/status 에서 last_etf_master 확인"}


@router.post("/collector/trigger/dart")
async def trigger_dart(background_tasks: BackgroundTasks, request: Request):
    """수동 DART 재무 수집 트리거 (1차 스크리닝 통과 종목 대상, 백그라운드 실행)."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    background_tasks.add_task(scheduler.trigger_dart)
    return {"triggered": True, "message": "DART 수집 시작됨. /api/v1/collector/status 에서 last_dart 확인"}


@router.post("/collector/trigger/sentiment")
async def trigger_sentiment(background_tasks: BackgroundTasks, request: Request):
    """수동 네이버 센티멘트 수집 트리거 (1차 스크리닝 통과 종목 대상, 백그라운드 실행)."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    background_tasks.add_task(scheduler.trigger_sentiment)
    return {"triggered": True, "message": "센티멘트 수집 시작됨. /api/v1/collector/status 에서 last_sentiment 확인"}


@router.post("/collector/trigger/market-open")
async def trigger_market_open(background_tasks: BackgroundTasks, request: Request):
    """수동 market_open 트리거 (WS 연결 + 2차 스크리닝 활성화)."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    background_tasks.add_task(scheduler.trigger_market_open)
    return {"triggered": True, "message": "market_open 시작됨. /api/v1/kis/status 에서 ws_connected 확인"}


@router.post("/collector/trigger/market-open-recovery")
async def trigger_market_open_recovery(background_tasks: BackgroundTasks, request: Request):
    """수동 market_open_recovery 트리거 (WS 미연결 시 복구)."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}
    background_tasks.add_task(scheduler.trigger_market_open_recovery)
    return {"triggered": True, "message": "market_open_recovery 시작됨. /api/v1/kis/status 에서 ws_connected 확인"}


@router.post("/collector/trigger/dart-corp-code")
async def trigger_dart_corp_code():
    """DART corp_code ZIP 초기화 (최초 1회 실행 필요, 동기 실행)."""
    from core.database import get_session_factory
    from modules.collector.sources.dart import DartCollector
    import zipfile, io

    try:
        factory = get_session_factory()
        async with factory() as db_session:
            collector = DartCollector(db_session)
            zip_bytes = await collector.fetch_corp_code_zip()
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                xml_bytes = z.read("CORPCODE.xml")
            records = collector.parse_corp_code_xml(xml_bytes)
            saved = await collector.save_corp_codes(records)
        return {"ok": True, "corp_codes_saved": saved}
    except Exception as e:
        return {"ok": False, "error": str(e), "error_type": type(e).__name__}


@router.get("/collector/probe/data-go-kr")
async def probe_data_go_kr():
    """공공데이터포털 API 연결 진단 (1페이지, DB 저장 없음)."""
    import httpx
    from core.config import settings
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
    if today.weekday() == 5:
        bas_dt = (today - timedelta(days=1)).strftime("%Y%m%d")
    elif today.weekday() == 6:
        bas_dt = (today - timedelta(days=2)).strftime("%Y%m%d")
    else:
        bas_dt = today.strftime("%Y%m%d")

    url = (
        "https://apis.data.go.kr/1160100/service/"
        "GetStockSecuritiesInfoService/getStockPriceInfo"
    )
    params = {
        "serviceKey": settings.DATA_GO_KR_API_KEY,
        "resultType": "json",
        "numOfRows": 5,
        "pageNo": 1,
        "basDt": bas_dt,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        body = data.get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        return {
            "ok": True,
            "bas_dt": bas_dt,
            "total_count": body.get("totalCount"),
            "items_returned": len(items),
            "first_item": items[0] if items else None,
            "api_key_set": bool(settings.DATA_GO_KR_API_KEY),
        }
    except Exception as e:
        return {"ok": False, "bas_dt": bas_dt, "error": str(e)}


@router.get("/collector/pipeline-status")
async def get_pipeline_status(request: Request):
    """파이프라인 단계별 상태 + pipeline_healthy 조회."""
    scheduler = getattr(request.app.state, "collector_scheduler", None)
    pipeline_status = {}
    if scheduler is not None:
        pipeline_status = await scheduler.get_pipeline_status()
    pipeline_healthy = await redis_client.get("scheduler:pipeline_healthy")
    return {"pipeline_status": pipeline_status, "pipeline_healthy": pipeline_healthy}


@router.post("/collector/trigger/premarket-pipeline", status_code=202)
async def trigger_premarket_pipeline(background_tasks: BackgroundTasks, request: Request):
    """장전 파이프라인 수동 트리거 (BackgroundTasks로 비동기 실행).

    실행 중 중복 요청은 409로 거부한다.
    락 확인 직후 즉시 Redis에 락을 선점하여 동시 요청의 race condition을 방지한다.
    """
    running = await redis_client.get(PIPELINE_RUNNING_KEY)
    if running == "true":
        raise HTTPException(status_code=409, detail="파이프라인이 이미 실행 중입니다")

    scheduler = getattr(request.app.state, "collector_scheduler", None)
    if scheduler is None:
        return {"triggered": False, "message": "스케줄러 미초기화"}

    # 락을 즉시 선점 — BackgroundTask 실행 전 동시 요청 차단
    await redis_client.set(PIPELINE_RUNNING_KEY, "true", ttl=600)
    background_tasks.add_task(scheduler.run_premarket_pipeline)
    return {
        "triggered": True,
        "message": "파이프라인 시작됨. GET /api/v1/collector/pipeline-status 에서 확인",
    }


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
