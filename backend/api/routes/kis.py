from fastapi import APIRouter, HTTPException, Request

from core.clients.kis_rest import KISDataError

router = APIRouter(prefix="/kis", tags=["kis"])


@router.get("/status")
async def kis_status(request: Request):
    env = getattr(request.app.state, "kis_env", None)
    token_manager = getattr(request.app.state, "kis_token_manager", None)
    ws = getattr(request.app.state, "kis_ws", None)

    token_valid = False
    if token_manager:
        try:
            token = await token_manager.get_access_token()
            token_valid = bool(token)
        except Exception:
            pass

    return {
        "environment": env.name if env else "unknown",
        "token_valid": token_valid,
        "ws_connected": ws.connected if ws else False,
        "ws_subscriptions": ws.subscription_count if ws else 0,
    }


@router.get("/price/{stock_code}")
async def kis_price(stock_code: str, request: Request):
    rest_client = getattr(request.app.state, "kis_rest", None)
    if not rest_client:
        raise HTTPException(status_code=503, detail="KIS REST 클라이언트 미초기화")

    try:
        price = await rest_client.get_stock_price(stock_code)
        return price.model_dump()
    except KISDataError as e:
        raise HTTPException(status_code=400, detail=str(e))
