"""settings 테이블 초기 시드 데이터 적재 (21개 항목)"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from core.models.settings import SystemSetting

SEED_DATA = [
    ("trading_env", "paper", "string", "system", "거래 환경 (paper/live)"),
    ("max_loss_per_trade_pct", "-2.0", "float", "risk", "건당 최대 손실률 (%)"),
    ("max_profit_per_trade_pct", "3.0", "float", "risk", "건당 익절 기준 (%)"),
    ("trailing_stop_pct", "-1.0", "float", "risk", "트레일링 스탑 (고점 대비 %)"),
    ("daily_max_loss_pct", "-3.0", "float", "risk", "일일 최대 손실률 (%)"),
    ("monthly_max_loss_pct", "-10.0", "float", "risk", "월간 최대 손실률 (%)"),
    ("position_size_pct", "10.0", "float", "risk", "건당 투자 비율 (%)"),
    ("max_position_count", "5", "int", "risk", "최대 동시 포지션 수"),
    ("leverage_etf_loss_pct", "-1.5", "float", "risk", "레버리지 ETF 손절률 (%)"),
    ("leverage_etf_size_pct", "7.0", "float", "risk", "레버리지 ETF 투자 비율 (%)"),
    ("force_close_start", "15:00", "string", "trading", "강제 청산 시작 시각"),
    ("force_close_end", "15:20", "string", "trading", "강제 청산 종료 시각"),
    ("trading_start", "09:30", "string", "trading", "본매매 시작 시각"),
    ("trading_end", "14:30", "string", "trading", "본매매 종료 시각"),
    ("no_entry_start", "09:00", "string", "trading", "신규 진입 금지 시작"),
    ("no_entry_end", "09:30", "string", "trading", "신규 진입 금지 종료"),
    ("approval_timeout_trading", "30", "int", "trading", "장중 승인 타임아웃 (초)"),
    ("approval_timeout_closing", "15", "int", "trading", "마감 전 승인 타임아웃 (초)"),
    ("approval_timeout_default", "60", "int", "trading", "기본 승인 타임아웃 (초)"),
    ("emergency_stop_enabled", "true", "bool", "risk", "비상 정지 활성화"),
    ("data_collection_start", "08:00", "string", "schedule", "장전 데이터 수집 시작"),
]


async def seed() -> int:
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    count = 0
    async with factory() as session:
        for key, value, value_type, category, description in SEED_DATA:
            existing = await session.execute(
                select(SystemSetting).where(SystemSetting.key == key)
            )
            row = existing.scalar_one_or_none()
            if row:
                row.value = value
                row.value_type = value_type
                row.category = category
                row.description = description
            else:
                session.add(
                    SystemSetting(
                        key=key,
                        value=value,
                        value_type=value_type,
                        category=category,
                        description=description,
                    )
                )
            count += 1
        await session.commit()

    await engine.dispose()
    return count


async def main():
    count = await seed()
    print(f"{count}개 설정 시드 완료")


if __name__ == "__main__":
    asyncio.run(main())
