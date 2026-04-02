"""한투 REST ETF 수집기 — ETF 개별 시세 조회 + DB 저장."""

import logging
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.clients.kis_rest import KISRestClient, StockPrice
from core.models.market_data import MarketData
from core.models.stock import Stock
from modules.collector.models import CollectionResult

logger = logging.getLogger(__name__)


class KISCollector:
    """한투 REST API 기반 ETF 시세 수집기."""

    def __init__(self, rest_client: KISRestClient, db_session: AsyncSession) -> None:
        self._rest = rest_client
        self._db = db_session

    async def collect_etf_prices(self, etf_codes: list[str] | None = None) -> CollectionResult:
        """ETF 개별 시세 수집. CollectionResult 반환."""
        if etf_codes is None:
            etf_codes = await self._get_etf_codes()

        collected = 0
        failed = 0
        null_counts: dict[str, int] = {}
        for code in etf_codes:
            try:
                price = await self._rest.get_stock_price(code)
                if price.price == 0:
                    null_counts["close_price_zero"] = null_counts.get("close_price_zero", 0) + 1
                    logger.warning("ETF 종가 0 감지: %s", code)
                    continue
                await self._save_etf_price(code, price)
                await self._db.commit()
                collected += 1
            except Exception:
                await self._db.rollback()
                failed += 1
                logger.exception("ETF 시세 수집 실패: %s", code)

        logger.info("ETF 수집 완료: %d/%d (실패: %d)", collected, len(etf_codes), failed)
        return CollectionResult(
            collected=collected,
            failed=failed,
            total_target=len(etf_codes),
            null_counts=null_counts if null_counts else None,
        )

    async def _get_etf_codes(self) -> list[str]:
        """stocks 테이블에서 KODEX ETF 종목코드 조회."""
        result = await self._db.execute(
            select(Stock.stock_code).where(
                Stock.stock_type == "ETF",
                Stock.is_active.is_(True),
                Stock.stock_name.startswith("KODEX"),
            )
        )
        codes = list(result.scalars().all())
        logger.info("KODEX ETF 수집 대상: %d종목", len(codes))
        return codes

    async def _save_etf_price(self, stock_code: str, price: StockPrice) -> None:
        """market_data 테이블에 ETF 시세 저장."""
        today = date.today()

        stmt = pg_insert(MarketData).values(
            stock_code=stock_code,
            data_date=today,
            open_price=price.open_price,
            high_price=price.high,
            low_price=price.low,
            close_price=price.price,
            volume=price.volume,
            change_rate=price.change_rate,
            source="kis_rest",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_code", "data_date", "source"],
            set_={
                "close_price": stmt.excluded.close_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "volume": stmt.excluded.volume,
                "change_rate": stmt.excluded.change_rate,
                "updated_at": func.now(),
            },
        )
        await self._db.execute(stmt)
