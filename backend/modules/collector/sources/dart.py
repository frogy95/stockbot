"""DART 재무 수집기 — corp_code 매핑 + 재무 기초 데이터 수집."""

import logging
import zipfile
import io
from datetime import date, datetime

import httpx
from lxml import etree
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.corp_code import CorpCode
from core.models.financial_data import FinancialData
from modules.collector.models import CollectionResult

logger = logging.getLogger(__name__)

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
FINANCIAL_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

# 분기별 보고서 코드
REPRT_CODE = {1: "11013", 2: "11012", 3: "11014", 4: "11011"}


class DartCollector:
    """DART 공시 기반 재무 데이터 수집기."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session

    async def fetch_corp_code_zip(self) -> bytes:
        """DART에서 corp_code ZIP 파일을 다운로드하여 bytes로 반환한다."""
        params = {"crtfc_key": settings.DART_API_KEY}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(CORP_CODE_URL, params=params)
            resp.raise_for_status()
            return resp.content

    def parse_corp_code_xml(self, xml_bytes: bytes) -> list[dict]:
        """ZIP 내부의 XML bytes를 파싱하여 기업 코드 레코드 목록을 반환한다.

        stock_code가 빈 문자열(공백)이면 None으로 처리 (비상장 법인).
        modify_date는 YYYYMMDD 형식을 date 객체로 변환한다.
        """
        records = []
        try:
            root = etree.fromstring(xml_bytes)
            # <result><list>...</list>...</result> 구조
            for item in root.findall(".//list"):
                corp_code_el = item.find("corp_code")
                corp_name_el = item.find("corp_name")
                stock_code_el = item.find("stock_code")
                modify_date_el = item.find("modify_date")

                if corp_code_el is None or corp_name_el is None:
                    continue

                corp_code_val = (corp_code_el.text or "").strip()
                corp_name_val = (corp_name_el.text or "").strip()

                # 빈 문자열이면 비상장 → None
                raw_stock_code = (stock_code_el.text or "").strip() if stock_code_el is not None else ""
                stock_code_val = raw_stock_code if raw_stock_code else None

                # YYYYMMDD → date
                modify_date_val: date | None = None
                if modify_date_el is not None:
                    raw_date = (modify_date_el.text or "").strip()
                    if raw_date:
                        try:
                            modify_date_val = datetime.strptime(raw_date, "%Y%m%d").date()
                        except ValueError:
                            pass

                records.append({
                    "corp_code": corp_code_val,
                    "corp_name": corp_name_val,
                    "stock_code": stock_code_val,
                    "modify_date": modify_date_val,
                })
        except Exception:
            logger.exception("corp_code XML 파싱 실패")

        return records

    async def save_corp_codes(self, records: list[dict]) -> int:
        """CorpCode 테이블에 upsert하고 저장 건수를 반환한다."""
        if not records:
            return 0

        saved = 0
        for record in records:
            try:
                stmt = pg_insert(CorpCode).values(
                    corp_code=record["corp_code"],
                    corp_name=record["corp_name"],
                    stock_code=record["stock_code"],
                    modify_date=record["modify_date"],
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["corp_code"],
                    set_={
                        "corp_name": stmt.excluded.corp_name,
                        "stock_code": stmt.excluded.stock_code,
                        "modify_date": stmt.excluded.modify_date,
                    },
                )
                await self._db.execute(stmt)
                saved += 1
            except Exception:
                logger.exception("corp_code 저장 실패: %s", record.get("corp_code", "?"))

        await self._db.commit()
        logger.info("corp_code upsert 완료: %d건", saved)
        return saved

    async def fetch_financial(
        self, corp_code: str, year: str, reprt_code: str
    ) -> dict | None:
        """DART fnlttSinglAcntAll API를 호출하여 재무 데이터를 반환한다.

        status가 "000"이면 매출액/영업이익/당기순이익을 파싱하고,
        그렇지 않으면 None을 반환한다.
        """
        params = {
            "crtfc_key": settings.DART_API_KEY,
            "corp_code": corp_code,
            "bsns_year": year,
            "reprt_code": reprt_code,
            "fs_div": "CFS",  # 연결재무제표 우선
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(FINANCIAL_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.exception("DART 재무 API 호출 실패: corp_code=%s", corp_code)
            return None

        if data.get("status") != "000":
            logger.debug(
                "DART 재무 API 비정상 응답: corp_code=%s status=%s",
                corp_code,
                data.get("status"),
            )
            return None

        items = data.get("list", [])
        result: dict = {"revenue": None, "operating_profit": None, "net_income": None}

        keyword_map = {
            "매출액": "revenue",
            "영업이익": "operating_profit",
            "당기순이익": "net_income",
        }

        for item in items:
            account_nm = (item.get("account_nm") or "").strip()
            for keyword, field in keyword_map.items():
                if keyword in account_nm and result[field] is None:
                    raw_amount = (item.get("thstrm_amount") or "").replace(",", "").strip()
                    if raw_amount:
                        try:
                            result[field] = int(raw_amount)
                        except ValueError:
                            pass
                    break

        return result

    async def collect_financials(self, stock_codes: list[str]) -> CollectionResult:
        """종목코드 리스트를 받아 재무 데이터를 수집하고 DB에 저장한다.

        - DB에서 stock_code → corp_code 매핑 조회
        - ETF/비상장(매핑 없음) 종목은 스킵
        - 현재 연도 기준 직전 연도 연간 보고서(11011) 수집
        """
        total_target = len(stock_codes)
        if not stock_codes:
            return CollectionResult(collected=0, total_target=0)

        # stock_code → corp_code 매핑 조회
        result = await self._db.execute(
            select(CorpCode.stock_code, CorpCode.corp_code).where(
                CorpCode.stock_code.in_(stock_codes)
            )
        )
        mapping: dict[str, str] = {row.stock_code: row.corp_code for row in result.fetchall()}

        # 매핑된 종목만
        target_codes = [sc for sc in stock_codes if sc in mapping]
        skipped = total_target - len(target_codes)

        # 직전 연도 연간 보고서
        target_year = str(datetime.now().year - 1)
        target_reprt = REPRT_CODE[4]  # 연간: "11011"
        fiscal_year_int = int(target_year)
        fiscal_quarter_int = 4

        collected = 0
        failed = 0
        for stock_code in target_codes:
            corp_code = mapping[stock_code]
            try:
                financial = await self.fetch_financial(corp_code, target_year, target_reprt)
                if financial is None:
                    failed += 1
                    continue

                stmt = pg_insert(FinancialData).values(
                    stock_code=stock_code,
                    fiscal_year=fiscal_year_int,
                    fiscal_quarter=fiscal_quarter_int,
                    revenue=financial.get("revenue"),
                    operating_profit=financial.get("operating_profit"),
                    net_income=financial.get("net_income"),
                    source="dart",
                )
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_financial_data_stock_year_quarter",
                    set_={
                        "revenue": stmt.excluded.revenue,
                        "operating_profit": stmt.excluded.operating_profit,
                        "net_income": stmt.excluded.net_income,
                    },
                )
                await self._db.execute(stmt)
                collected += 1
            except Exception:
                logger.exception("재무 데이터 저장 실패: stock_code=%s", stock_code)
                failed += 1

        if collected:
            await self._db.commit()

        logger.info("DART 재무 수집 완료: %d건 (실패: %d, 스킵: %d)", collected, failed, skipped)
        return CollectionResult(collected=collected, failed=failed, skipped=skipped, total_target=total_target)
