"""KIS REST 일봉 보조 수집기 — 공공데이터포털 장전 수집 실패 시 폴백으로 동작한다."""

import asyncio
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.clients.kis_rest import DailyPrice, KISRestClient
from core.config import settings
from core.models.market_data import MarketData
from core.models.stock import Stock
from core.trading_calendar import get_prev_trading_day
from modules.collector.models import CollectionResult

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50
_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # 초 (2-4-8)
_RETRYABLE_STATUS_CODES = {500, 502, 503, 429}


class KISDailyCollector:
    """한투 REST 일봉 API 기반 전 종목 보조 수집기."""

    def __init__(self, rest_client: KISRestClient, db_session: AsyncSession) -> None:
        self._rest = rest_client
        self._db = db_session

    async def collect_all(self, target_date: str | None = None) -> CollectionResult:
        """전체 활성 주식 종목 일봉 수집. target_date가 None이면 전일(T-1)."""
        if target_date is None:
            prev_day = get_prev_trading_day(datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date(), n=1)
            target_date = prev_day.strftime("%Y%m%d")

        codes = await self._get_active_stock_codes()
        total = len(codes)
        collected = 0
        failed = 0

        for batch_start in range(0, total, _BATCH_SIZE):
            batch = codes[batch_start : batch_start + _BATCH_SIZE]
            for code in batch:
                try:
                    prices = await self._fetch_with_retry(code, target_date)
                    if prices:
                        await self._save_daily_price(code, prices[0])
                        collected += 1
                    else:
                        failed += 1
                        logger.warning("일봉 데이터 없음: %s %s", code, target_date)
                except Exception:
                    failed += 1
                    logger.exception("일봉 수집 실패: %s", code)
            await self._db.commit()

        logger.info("KIS 일봉 수집 완료: %d/%d (실패: %d)", collected, total, failed)
        return CollectionResult(
            collected=collected,
            failed=failed,
            total_target=total,
            data_date=target_date,
        )

    async def _fetch_with_retry(self, code: str, target_date: str) -> list:
        """KIS REST 일봉 조회 — 일시적 에러(500/502/503/429) 시 지수 백오프 재시도."""
        for attempt in range(_MAX_RETRIES):
            try:
                return await self._rest.get_daily_price(code, target_date, target_date)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES - 1:
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "일봉 수집 재시도: %s HTTP %d (%d/%d, %d초 대기)",
                        code, e.response.status_code, attempt + 1, _MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        return []

    async def _get_active_stock_codes(self) -> list[str]:
        result = await self._db.execute(
            select(Stock.stock_code).where(
                Stock.stock_type == "STOCK",
                Stock.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _save_daily_price(self, stock_code: str, price: DailyPrice) -> None:
        data_date = date(
            int(price.data_date[:4]),
            int(price.data_date[4:6]),
            int(price.data_date[6:8]),
        )

        stmt = pg_insert(MarketData).values(
            stock_code=stock_code,
            data_date=data_date,
            open_price=price.open_price,
            high_price=price.high_price,
            low_price=price.low_price,
            close_price=price.close_price,
            volume=price.volume,
            change_rate=price.change_rate,
            market_cap=None,
            source="kis_daily",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_code", "data_date", "source"],
            set_={
                "close_price": stmt.excluded.close_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "volume": stmt.excluded.volume,
                "change_rate": stmt.excluded.change_rate,
                "collected_at": func.now(),
            },
        )
        await self._db.execute(stmt)
