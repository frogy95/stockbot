"""매매 관련 API 라우터 — 리스크 상태, 포지션, 매매 이력 조회."""

from datetime import date, datetime, time

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from core.database import get_session_factory
from core.models.trading import PositionRecord, TradeHistory

router = APIRouter(prefix="/trading", tags=["trading"])


@router.get("/risk-status")
async def get_risk_status(request: Request):
    """현재 리스크 상태 요약."""
    risk_manager = request.app.state.risk_manager
    return await risk_manager.get_risk_status()


@router.get("/positions")
async def get_positions():
    """활성 포지션 목록."""
    factory = get_session_factory()
    async with factory() as session:
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
async def get_history(target_date: date = Query(default=None)):
    """매매 이력 조회 (날짜 필터)."""
    if target_date is None:
        target_date = date.today()

    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    factory = get_session_factory()
    async with factory() as session:
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
