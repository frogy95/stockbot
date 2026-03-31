from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db, UserInfo
from core.config import settings
from core.models.trading import PositionRecord, TradeHistory

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    today_pnl: int
    today_pnl_rate: float
    today_trade_count: int
    active_positions: int
    unrealized_pnl: int
    trading_env: str
    engine_running: bool
    risk_status: dict[str, Any]


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    request: Request,
    session: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(get_current_user),
):
    today = date.today()
    today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)

    # 오늘 거래 이력 집계
    history_result = await session.execute(
        select(
            func.coalesce(func.sum(TradeHistory.realized_pnl), 0),
            func.coalesce(func.avg(TradeHistory.pnl_rate), 0.0),
            func.count(TradeHistory.id),
        ).where(TradeHistory.exit_time >= today_start)
    )
    today_pnl, today_pnl_rate, today_trade_count = history_result.one()

    # 활성 포지션 집계
    pos_result = await session.execute(
        select(
            func.count(PositionRecord.id),
            func.coalesce(func.sum(PositionRecord.unrealized_pnl), 0),
        )
    )
    active_positions, unrealized_pnl = pos_result.one()

    # 엔진 상태
    engine = getattr(request.app.state, "trading_engine", None)
    engine_running = engine.get_status()["is_running"] if engine else False

    # 리스크 상태
    risk_manager = getattr(request.app.state, "risk_manager", None)
    risk_status = await risk_manager.get_risk_status() if risk_manager else {}

    return DashboardSummary(
        today_pnl=int(today_pnl),
        today_pnl_rate=float(today_pnl_rate),
        today_trade_count=int(today_trade_count),
        active_positions=int(active_positions),
        unrealized_pnl=int(unrealized_pnl),
        trading_env=settings.TRADING_ENV,
        engine_running=engine_running,
        risk_status=risk_status,
    )
