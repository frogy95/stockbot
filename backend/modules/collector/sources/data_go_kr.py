"""공공데이터포털 수집기 — 전 종목 일괄 OHLCV/시총/상장주식수 수집."""

import logging
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.market_data import MarketData
from core.models.stock import Stock

logger = logging.getLogger(__name__)

BASE_URL = (
    "https://apis.data.go.kr/1160100/service/"
    "GetStockSecuritiesInfoService/getStockPriceInfo"
)
DEFAULT_NUM_ROWS = 500
MAX_RETRIES = 3
RETRY_DELAY = 30  # 초


class DataGoKrCollector:
    """공공데이터포털 주식시세정보 수집기."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session

    @staticmethod
    def _latest_trading_date() -> str:
        """가장 최근 거래일(평일)을 YYYYMMDD 문자열로 반환한다. 오늘이 평일이면 오늘, 주말이면 직전 금요일."""
        today = date.today()
        # 월요일=0, 일요일=6
        if today.weekday() == 5:   # 토요일
            return (today - timedelta(days=1)).strftime("%Y%m%d")
        if today.weekday() == 6:   # 일요일
            return (today - timedelta(days=2)).strftime("%Y%m%d")
        return today.strftime("%Y%m%d")

    async def collect_all(self, retry_delay: float = RETRY_DELAY) -> int:
        """전 종목 일괄 수집. 수집된 종목 수를 반환한다."""
        bas_dt = self._latest_trading_date()
        logger.info("공공데이터포털 수집 기준일: %s", bas_dt)
        total_collected = 0
        page = 1

        while True:
            items = await self._fetch_page(page, DEFAULT_NUM_ROWS, retry_delay, bas_dt)
            if not items:
                break

            for item in items:
                try:
                    await self._upsert_stock(item)
                    await self._save_market_data(item)
                    total_collected += 1
                except Exception:
                    logger.exception("종목 저장 실패: %s", item.get("srtnCd", "?"))

            await self._db.commit()

            if len(items) < DEFAULT_NUM_ROWS:
                break
            page += 1

        logger.info("공공데이터포털 수집 완료: %d종목", total_collected)
        return total_collected

    async def _fetch_page(
        self, page: int, num_rows: int, retry_delay: float = RETRY_DELAY, bas_dt: str | None = None
    ) -> list[dict]:
        """단일 페이지 호출. 실패 시 최대 3회 재시도."""
        params = {
            "serviceKey": settings.DATA_GO_KR_API_KEY,
            "resultType": "json",
            "numOfRows": num_rows,
            "pageNo": page,
        }
        if bas_dt:
            params["basDt"] = bas_dt

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(BASE_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                items = (
                    data.get("response", {})
                    .get("body", {})
                    .get("items", {})
                    .get("item", [])
                )
                return items if isinstance(items, list) else []

            except Exception:
                logger.warning(
                    "공공데이터포털 페이지 %d 호출 실패 (%d/%d)",
                    page, attempt + 1, MAX_RETRIES,
                )
                if attempt < MAX_RETRIES - 1:
                    import asyncio
                    await asyncio.sleep(retry_delay)

        logger.error("공공데이터포털 페이지 %d 최종 실패", page)
        return []

    async def _upsert_stock(self, item: dict) -> None:
        """stocks 테이블 upsert."""
        stock_code = item.get("srtnCd", "").strip()
        if not stock_code:
            return

        market_type = item.get("mrktCtg", "KOSPI").strip()
        stock_type = "ETF" if item.get("srtnCd", "").startswith("4") else "STOCK"

        stmt = pg_insert(Stock).values(
            stock_code=stock_code,
            stock_name=item.get("itmsNm", "").strip(),
            market="kr",
            market_type=market_type,
            stock_type=stock_type,
            is_active=True,
            listed_shares=self._parse_int(item.get("lstgStCnt")),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_code"],
            set_={
                "stock_name": stmt.excluded.stock_name,
                "market_type": stmt.excluded.market_type,
                "listed_shares": stmt.excluded.listed_shares,
                "is_active": True,
            },
        )
        await self._db.execute(stmt)

    async def _save_market_data(self, item: dict) -> None:
        """market_data 테이블 insert (중복 시 무시)."""
        stock_code = item.get("srtnCd", "").strip()
        if not stock_code:
            return

        data_date = self._parse_date(item.get("basDt", ""))
        if not data_date:
            return

        stmt = pg_insert(MarketData).values(
            stock_code=stock_code,
            data_date=data_date,
            open_price=self._parse_int(item.get("mkp")),
            high_price=self._parse_int(item.get("hipr")),
            low_price=self._parse_int(item.get("lopr")),
            close_price=self._parse_int(item.get("clpr")),
            volume=self._parse_int(item.get("trqu")),
            market_cap=self._parse_int(item.get("mrktTotAmt")),
            listed_shares=self._parse_int(item.get("lstgStCnt")),
            change_rate=self._parse_float(item.get("fltRt")),
            source="data_go_kr",
        )
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_market_data_stock_code_data_date_source"
            if False  # constraint 이름은 SQLAlchemy UniqueConstraint에서 자동 생성
            else None,
            index_elements=["stock_code", "data_date", "source"],
        )
        await self._db.execute(stmt)

    @staticmethod
    def _parse_int(value) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_date(value: str) -> date | None:
        if not value:
            return None
        try:
            return datetime.strptime(value.strip(), "%Y%m%d").date()
        except ValueError:
            return None
