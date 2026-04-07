"""매매 관련 API 라우터 — 리스크 상태, 포지션, 매매 이력, 신호, 주문, 엔진 상태 조회."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_user
from core.config import settings
from core.models.trading import Order, PositionRecord, TradeHistory, TradeSignal

router = APIRouter(
    prefix="/trading",
    tags=["trading"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/risk-status")
async def get_risk_status(request: Request):
    """현재 리스크 상태 요약."""
    risk_manager = request.app.state.risk_manager
    return await risk_manager.get_risk_status()


@router.get("/positions")
async def get_positions(session: AsyncSession = Depends(get_db)):
    """활성 포지션 목록."""
    result = await session.execute(select(PositionRecord))
    positions = result.scalars().all()

    return [
        {
            "id": p.id,
            "stock_code": p.stock_code,
            "quantity": p.quantity,
            "avg_price": int(p.avg_price),
            "current_price": int(p.current_price),
            "unrealized_pnl": p.unrealized_pnl,
            "stop_loss": int(p.stop_loss),
            "take_profit": int(p.take_profit),
            "trailing_activated": p.trailing_activated,
            "entry_time": p.entry_time.isoformat() if p.entry_time else None,
            "strategy_name": p.strategy_name,
        }
        for p in positions
    ]


@router.get("/history")
async def get_history(
    session: AsyncSession = Depends(get_db),
    target_date: date = Query(default=None),
):
    """매매 이력 조회 (날짜 필터)."""
    if target_date is None:
        target_date = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()

    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    stmt = select(TradeHistory).where(
        TradeHistory.exit_time >= day_start,
        TradeHistory.exit_time <= day_end,
    )
    result = await session.execute(stmt)
    histories = result.scalars().all()

    return [
        {
            "id": h.id,
            "stock_code": h.stock_code,
            "strategy_name": h.strategy_name,
            "entry_price": int(h.entry_price),
            "exit_price": int(h.exit_price),
            "quantity": h.quantity,
            "realized_pnl": h.realized_pnl,
            "pnl_rate": float(h.pnl_rate),
            "holding_duration_sec": h.holding_duration_sec,
            "exit_reason": h.exit_reason,
            "entry_time": h.entry_time.isoformat() if h.entry_time else None,
            "exit_time": h.exit_time.isoformat() if h.exit_time else None,
        }
        for h in histories
    ]


@router.get("/signals")
async def get_signals(
    session: AsyncSession = Depends(get_db),
    target_date: date = Query(default=None),
    status: str = Query(default=None),
):
    """매매 신호 목록 조회."""
    stmt = select(TradeSignal)

    if target_date:
        day_start = datetime.combine(target_date, time.min)
        day_end = datetime.combine(target_date, time.max)
        stmt = stmt.where(
            TradeSignal.created_at >= day_start,
            TradeSignal.created_at <= day_end,
        )

    if status:
        stmt = stmt.where(TradeSignal.status == status)

    result = await session.execute(stmt)
    signals = result.scalars().all()

    return [
        {
            "id": s.id,
            "stock_code": s.stock_code,
            "signal_type": s.signal_type,
            "strategy_name": s.strategy_name,
            "confidence": float(s.confidence) if s.confidence else None,
            "reason": s.reason,
            "entry_price": int(s.entry_price),
            "stop_loss": int(s.stop_loss),
            "take_profit": int(s.take_profit),
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in signals
    ]


@router.get("/orders")
async def get_orders(
    session: AsyncSession = Depends(get_db),
    target_date: date = Query(default=None),
    status: str = Query(default=None),
):
    """주문 목록 조회."""
    stmt = select(Order)

    if target_date:
        day_start = datetime.combine(target_date, time.min)
        day_end = datetime.combine(target_date, time.max)
        stmt = stmt.where(
            Order.created_at >= day_start,
            Order.created_at <= day_end,
        )

    if status:
        stmt = stmt.where(Order.status == status)

    result = await session.execute(stmt)
    orders = result.scalars().all()

    return [
        {
            "id": o.id,
            "signal_id": o.signal_id,
            "stock_code": o.stock_code,
            "order_type": o.order_type,
            "order_no": o.order_no,
            "quantity": o.quantity,
            "price": int(o.price),
            "order_division": o.order_division,
            "status": o.status,
            "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
            "filled_at": o.filled_at.isoformat() if o.filled_at else None,
        }
        for o in orders
    ]


@router.get("/signals/pending")
async def get_pending_signals(request: Request):
    """승인 대기 중인 매매 신호 목록 조회."""
    approval_manager = getattr(request.app.state, "approval_manager", None)
    if not approval_manager:
        return {"pending": [], "count": 0}

    items = await approval_manager.list_pending()
    return {"pending": items, "count": len(items)}


async def _handle_signal_action(token: str, request: Request, action: str) -> dict:
    engine = getattr(request.app.state, "trading_engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="매매 엔진이 초기화되지 않았습니다")
    method = engine.approve_signal if action == "approve" else engine.reject_signal
    success = await method(token)
    if not success:
        raise HTTPException(status_code=404, detail="유효하지 않거나 만료된 토큰입니다")
    return {"result": "approved" if action == "approve" else "rejected"}


@router.post("/signals/{token}/approve")
async def approve_signal(token: str, request: Request):
    """매매 신호 웹 승인."""
    return await _handle_signal_action(token, request, "approve")


@router.post("/signals/{token}/reject")
async def reject_signal(token: str, request: Request):
    """매매 신호 웹 거부."""
    return await _handle_signal_action(token, request, "reject")


@router.get("/engine-status")
async def get_engine_status(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """매매 엔진 상태 조회."""
    engine = getattr(request.app.state, "trading_engine", None)

    engine_status = {"is_running": False, "queue_size": 0, "monitor_active": False}
    if engine:
        engine_status = engine.get_status()

    result = await session.execute(select(func.count(PositionRecord.id)))
    active_positions = result.scalar_one()

    return {
        "running": engine_status["is_running"],
        "queue_size": engine_status["queue_size"],
        "active_positions": active_positions,
    }
