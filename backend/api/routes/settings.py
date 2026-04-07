from datetime import datetime, timezone, time as dt_time
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_user, UserInfo
from core.config import settings
from core.models.audit_log import AuditLog
from core.models.settings import SystemSetting
from core.models.trading import PositionRecord

_KST = ZoneInfo(settings.MARKET_TIMEZONE)
_MARKET_OPEN = dt_time(9, 0)
_MARKET_CLOSE = dt_time(15, 30)

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(get_current_user)],
)


class SettingUpdate(BaseModel):
    value: str


class ModeSwitchRequest(BaseModel):
    target_env: str
    password: str


class TradingModeRequest(BaseModel):
    target_mode: Literal["manual", "semi-auto", "auto"]
    password: str


def _is_market_hours() -> bool:
    """현재 KST 시각이 평일 장중(09:00~15:30)이면 True."""
    now_kst = datetime.now(timezone.utc).astimezone(_KST)
    if now_kst.weekday() >= 5:  # 토요일(5)/일요일(6)은 장외
        return False
    return _MARKET_OPEN <= now_kst.time() <= _MARKET_CLOSE


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("")
async def get_settings(
    category: str | None = None, db: AsyncSession = Depends(get_db)
):
    query = select(SystemSetting)
    if category:
        query = query.where(SystemSetting.category == category)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        {
            "key": row.key,
            "value": row.value,
            "value_type": row.value_type,
            "category": row.category,
            "description": row.description,
        }
        for row in rows
    ]


@router.get("/{key}")
async def get_setting(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"설정 '{key}'을(를) 찾을 수 없습니다")
    return {
        "key": row.key,
        "value": row.value,
        "value_type": row.value_type,
        "category": row.category,
        "description": row.description,
    }


@router.put("/mode")
async def switch_trading_mode(
    body: ModeSwitchRequest,
    request: Request,
    current_user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """거래 모드 전환 (비밀번호 재확인 + 장중 차단 + 포지션 체크)."""
    if body.password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="비밀번호가 올바르지 않습니다")

    if _is_market_hours():
        raise HTTPException(status_code=423, detail="장중(09:00~15:30)에는 모드를 전환할 수 없습니다")

    position_count_result = await db.execute(select(func.count(PositionRecord.id)))
    if position_count_result.scalar_one() > 0:
        raise HTTPException(status_code=409, detail="활성 포지션이 있어 전환할 수 없습니다")

    setting_result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "trading_env")
    )
    row = setting_result.scalar_one_or_none()
    old_value = row.value if row else None

    if row:
        row.value = body.target_env
    else:
        db.add(SystemSetting(key="trading_env", value=body.target_env, value_type="str", category="trading"))

    db.add(AuditLog(
        action="mode_switch",
        target_key="trading_env",
        old_value=old_value,
        new_value=body.target_env,
        actor=current_user.username,
        ip_address=_get_client_ip(request),
    ))
    await db.commit()

    switched_at = datetime.now(timezone.utc).isoformat()
    return {"trading_env": body.target_env, "switched_at": switched_at}


@router.put("/trading-mode")
async def switch_trading_mode_setting(
    body: TradingModeRequest,
    request: Request,
    current_user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """매매 모드 전환 (manual/semi-auto/auto). auto 전환 시 포지션 체크 + 장중 차단."""
    if body.password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="비밀번호가 올바르지 않습니다")

    if _is_market_hours():
        raise HTTPException(status_code=423, detail="장중(09:00~15:30)에는 모드를 전환할 수 없습니다")

    # auto로 전환 시에만 활성 포지션 체크 (semi-auto/manual로의 전환은 허용)
    if body.target_mode == "auto":
        position_count_result = await db.execute(select(func.count(PositionRecord.id)))
        if position_count_result.scalar_one() > 0:
            raise HTTPException(status_code=409, detail="활성 포지션이 있어 자동 모드로 전환할 수 없습니다")

    setting_result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "trading_mode")
    )
    row = setting_result.scalar_one_or_none()
    old_value = row.value if row else None

    if row:
        row.value = body.target_mode
    else:
        db.add(SystemSetting(
            key="trading_mode",
            value=body.target_mode,
            value_type="string",
            category="trading",
            description="매매 모드 (manual/semi-auto/auto)",
        ))

    db.add(AuditLog(
        action="trading_mode_switch",
        target_key="trading_mode",
        old_value=old_value,
        new_value=body.target_mode,
        actor=current_user.username,
        ip_address=_get_client_ip(request),
    ))
    await db.commit()

    switched_at = datetime.now(timezone.utc).isoformat()
    return {"trading_mode": body.target_mode, "switched_at": switched_at}


@router.put("/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    request: Request,
    current_user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"설정 '{key}'을(를) 찾을 수 없습니다")

    if row.category == "risk" and _is_market_hours():
        lock_result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "risk_lock_during_trading")
        )
        lock_row = lock_result.scalar_one_or_none()
        if lock_row and lock_row.value.lower() == "true":
            raise HTTPException(status_code=423, detail="장중에는 리스크 설정을 변경할 수 없습니다")

    old_value = row.value
    row.value = body.value
    db.add(AuditLog(
        action="setting_update",
        target_key=key,
        old_value=old_value,
        new_value=body.value,
        actor=current_user.username,
        ip_address=_get_client_ip(request),
    ))
    await db.commit()
    await db.refresh(row)
    return {
        "key": row.key,
        "value": row.value,
        "value_type": row.value_type,
        "category": row.category,
        "description": row.description,
    }
