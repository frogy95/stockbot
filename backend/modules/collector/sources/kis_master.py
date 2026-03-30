"""KIS 종목 마스터파일(.mst) 수집기 — ETF/ETN 종목 파싱 + stocks 테이블 적재."""

import asyncio
import io
import logging
import re
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.stock import Stock

logger = logging.getLogger(__name__)

MST_FILENAMES = {
    "kospi": "kospi_code.mst.zip",
    "kosdaq": "kosdaq_code.mst.zip",
}

SPOT_CHECK_CODES = {"069500", "122630", "114800", "252670", "102110"}

_CODE_SLICE = slice(0, 9)        # 종목코드 6자리 + 공백3
_NAME_SLICE = slice(21, 61)      # 종목명 40자
_SEC_TYPE_SLICE = slice(61, 63)  # 증권구분 2자
_MIN_LINE_LEN = 63               # 파싱 필수 최소 길이
_STOCK_CODE_RE = re.compile(r"^\d{6}$")

SEC_TYPE_ETF = "EF"
SEC_TYPE_ETN = "EN"


class KISMasterCollector:
    """KIS 종목 마스터파일 기반 ETF/ETN 수집기.

    KOSPI/KOSDAQ .mst.zip 병렬 다운로드 → CP949 줄바꿈 분리 파싱 → ETF/ETN 필터링
    → 메타데이터 보강 → sanity check → stocks 테이블 bulk upsert
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session

    async def collect(self) -> dict:
        """메인 오케스트레이션.

        반환: {"etf_count": int, "etn_count": int, "source": str, "sanity_passed": bool}
        """
        try:
            kospi_raw, kosdaq_raw = await asyncio.gather(
                self.download_mst("kospi"),
                self.download_mst("kosdaq"),
            )
        except Exception:
            logger.warning("mst 다운로드 실패 — 기존 DB ETF 유지")
            return await self._fallback_existing_db()

        all_records = self.parse_kospi_mst(kospi_raw) + self.parse_kosdaq_mst(kosdaq_raw)
        etf_list = self.enrich_etf_metadata(self.filter_etf(all_records))

        prev_count = await self._get_existing_etf_count()
        if not self.sanity_check(etf_list, prev_count):
            logger.warning("sanity check 실패 — 기존 DB ETF 유지")
            return await self._fallback_existing_db()

        etf_count = etn_count = 0
        for r in etf_list:
            if r["stock_type"] == "ETF":
                etf_count += 1
            else:
                etn_count += 1

        await self.sync_to_db(etf_list)
        logger.info("ETF 마스터 수집 완료: ETF=%d, ETN=%d", etf_count, etn_count)
        return {"etf_count": etf_count, "etn_count": etn_count, "source": "mst", "sanity_passed": True}

    async def download_mst(self, market: str, retry_delay: float = 10.0) -> bytes:
        """mst.zip 다운로드 후 압축 해제하여 mst 바이트 반환. 실패 시 3회 재시도."""
        url = f"{settings.KIS_MST_BASE_URL}/{MST_FILENAMES[market]}"
        mst_filename = MST_FILENAMES[market].replace(".zip", "")
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=60) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                        return zf.read(mst_filename)
                except Exception as e:
                    last_exc = e
                    logger.warning("mst 다운로드 실패 (%d/3): %s — %s", attempt + 1, market, e)
                    if attempt < 2:
                        await asyncio.sleep(retry_delay)

        raise last_exc  # type: ignore[misc]

    def parse_kospi_mst(self, data: bytes) -> list[dict]:
        return self._parse_mst(data, "KOSPI")

    def parse_kosdaq_mst(self, data: bytes) -> list[dict]:
        return self._parse_mst(data, "KOSDAQ")

    def filter_etf(self, records: list[dict]) -> list[dict]:
        result = []
        for r in records:
            sec = r.get("sec_type", "").strip()
            if sec == SEC_TYPE_ETF:
                result.append({**r, "stock_type": "ETF"})
            elif sec == SEC_TYPE_ETN:
                result.append({**r, "stock_type": "ETN"})
            elif sec:
                logger.debug("알 수 없는 증권구분: %s (종목=%s)", sec, r.get("stock_code"))
        return result

    def enrich_etf_metadata(self, records: list[dict]) -> list[dict]:
        for r in records:
            name = r.get("stock_name", "")
            etf_type, leverage_ratio = self._classify_leverage(name)
            r["etf_type"] = etf_type
            r["leverage_ratio"] = leverage_ratio
            r["underlying_index"] = self._extract_index(name)
        return records

    def sanity_check(self, etf_list: list[dict], prev_count: int | None = None) -> bool:
        """ETF 목록 품질 검증: 최소 200종목, spot-check 5종목, 전일 대비 ±10% 이내."""
        count = len(etf_list)
        if count < 200:
            logger.warning("sanity check 실패: 종목 수 부족 (%d < 200)", count)
            return False

        codes = {r["stock_code"] for r in etf_list}
        missing = SPOT_CHECK_CODES - codes
        if missing:
            logger.warning("sanity check 실패: spot-check 종목 누락 %s", missing)
            return False

        if prev_count and prev_count > 0:
            delta = abs(count - prev_count) / prev_count
            if delta > 0.10:
                logger.warning(
                    "sanity check 실패: 전일 대비 변동 %.1f%% (prev=%d, cur=%d)",
                    delta * 100, prev_count, count,
                )
                return False

        return True

    async def sync_to_db(self, etf_list: list[dict]) -> int:
        """ETF/ETN 종목을 stocks 테이블에 bulk upsert. 일반 주식 레코드 불변."""
        if not etf_list:
            return 0

        now_kst = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).isoformat()
        values = [
            {
                "stock_code": item["stock_code"],
                "stock_name": item["stock_name"],
                "market": "kr",
                "market_type": item.get("market_type", "KOSPI"),
                "stock_type": item["stock_type"],
                "is_active": True,
                "extra_data": {
                    "etf_type": item.get("etf_type", "normal"),
                    "leverage_ratio": item.get("leverage_ratio", 1),
                    "underlying_index": item.get("underlying_index", ""),
                    "source": "kis_mst",
                    "mst_updated_at": now_kst,
                },
            }
            for item in etf_list
        ]

        stmt = pg_insert(Stock).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_code"],
            set_={
                "stock_name": stmt.excluded.stock_name,
                "stock_type": stmt.excluded.stock_type,
                "market_type": stmt.excluded.market_type,
                "is_active": True,
                "extra_data": stmt.excluded.extra_data,
            },
        )
        await self._db.execute(stmt)
        await self._db.commit()
        return len(values)

    def _parse_mst(self, data: bytes, market_type: str) -> list[dict]:
        # 바이트 기반 슬라이싱: CP949에서 한글은 2바이트이므로
        # 디코딩 후 문자 슬라이싱 시 offset이 틀어짐. 각 필드를 개별 디코딩한다.
        records = []
        for line_bytes in data.split(b"\n"):
            line_bytes = line_bytes.rstrip(b"\r")
            if len(line_bytes) < _MIN_LINE_LEN:
                continue
            try:
                stock_code = line_bytes[_CODE_SLICE].decode("cp949").strip()
            except UnicodeDecodeError:
                continue
            if not _STOCK_CODE_RE.match(stock_code):
                continue
            try:
                stock_name = line_bytes[_NAME_SLICE].decode("cp949").strip()
                sec_type = line_bytes[_SEC_TYPE_SLICE].decode("cp949")
            except UnicodeDecodeError:
                logger.debug("mst 라인 디코딩 스킵 (code=%s)", stock_code)
                continue
            records.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "market_type": market_type,
                "sec_type": sec_type,
            })
        return records

    @staticmethod
    def _classify_leverage(name: str) -> tuple[str, int]:
        if "인버스2X" in name or "곱버스" in name or "인버스 2X" in name:
            return "inverse", -2
        if "인버스" in name:
            return "inverse", -1
        if "3X" in name or "3배" in name:
            return "leverage", 3
        if "레버리지" in name or "2X" in name or "2배" in name:
            return "leverage", 2
        return "normal", 1

    @staticmethod
    def _extract_index(name: str) -> str:
        mapping = {
            "KODEX 200": "KOSPI200",
            "TIGER 200": "KOSPI200",
            "나스닥100": "NASDAQ100",
            "S&P500": "SP500",
            "코스닥150": "KOSDAQ150",
        }
        for keyword, index in mapping.items():
            if keyword in name:
                return index
        return ""

    async def _get_existing_etf_count(self) -> int | None:
        try:
            result = await self._db.execute(
                select(func.count()).select_from(Stock).where(
                    Stock.stock_type.in_(["ETF", "ETN"])
                )
            )
            return result.scalar()
        except Exception:
            return None

    async def _fallback_existing_db(self) -> dict:
        count = await self._get_existing_etf_count() or 0
        return {"etf_count": count, "etn_count": 0, "source": "existing_db", "sanity_passed": False}
