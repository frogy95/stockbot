from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from core.models.settings import SystemSetting

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


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


@router.put("/{key}")
async def update_setting(
    key: str, body: SettingUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"설정 '{key}'을(를) 찾을 수 없습니다")
    row.value = body.value
    await db.commit()
    await db.refresh(row)
    return {
        "key": row.key,
        "value": row.value,
        "value_type": row.value_type,
        "category": row.category,
        "description": row.description,
    }
