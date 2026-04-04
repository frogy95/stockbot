import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.market_data import MarketData
from core.trading_calendar import get_prev_trading_day
from modules.collector.models import CollectionResult, ValidationResult

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class CollectionValidator:

    def validate_premarket(self, result: CollectionResult) -> ValidationResult:
        details: dict = {}

        # 수집 건수 >= 1500
        if result.collected < 1500:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"수집 건수 부족: {result.collected} < 1500",
                details={"collected": result.collected},
            )

        # null_ratio(close_price) < 5%
        close_ratio = self._null_ratio(result, "close_price")
        details["close_price_null_ratio"] = close_ratio
        if close_ratio >= 0.05:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"close_price null 비율 초과: {close_ratio:.1%} >= 5%",
                details=details,
            )

        # null_ratio(volume) < 5%
        volume_ratio = self._null_ratio(result, "volume")
        details["volume_null_ratio"] = volume_ratio
        if volume_ratio >= 0.05:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"volume null 비율 초과: {volume_ratio:.1%} >= 5%",
                details=details,
            )

        # data_date within T-2
        if result.data_date and not self._is_within_t2(result.data_date):
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"데이터 기준일 T-2 초과: {result.data_date}",
                details=details,
            )

        return ValidationResult(passed=True, severity="info", details=details)

    def validate_etf_master(
        self, result: CollectionResult, sanity_passed: bool
    ) -> ValidationResult:
        if not sanity_passed:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason="ETF 마스터 sanity check 실패",
                details={"collected": result.collected},
            )
        return ValidationResult(passed=True, severity="info")

    def validate_etf_collect(self, result: CollectionResult) -> ValidationResult:
        if result.total_target == 0:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason="ETF 수집 대상 0건",
            )
        ratio = result.collected / result.total_target
        if ratio < 0.5:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"ETF 수집률 부족: {ratio:.0%} < 50%",
                details={"collected": result.collected, "total_target": result.total_target},
            )
        return ValidationResult(passed=True, severity="info")

    def validate_primary_screen(self, result: CollectionResult) -> ValidationResult:
        if result.collected == 0:
            return ValidationResult(
                passed=True,
                severity="warning",
                details={"collected": 0},
            )
        return ValidationResult(passed=True, severity="info")

    def validate_dart(self, result: CollectionResult) -> ValidationResult:
        if result.total_target == 0:
            return ValidationResult(
                passed=True,
                severity="warning",
                details={"collected": 0, "total_target": 0},
            )
        ratio = result.collected / result.total_target
        if ratio < 0.5:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"corp_code 매핑률 부족: {ratio:.0%} < 50%",
                details={"collected": result.collected, "total_target": result.total_target},
            )
        return ValidationResult(passed=True, severity="info")

    def validate_kis_daily(self, result: CollectionResult) -> ValidationResult:
        if result.total_target == 0:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason="KIS 보조 수집 대상 0건",
            )
        ratio = result.collected / result.total_target
        if ratio < 0.8:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"KIS 보조 수집률 부족: {ratio:.0%} < 80%",
                details={"collected": result.collected, "total_target": result.total_target},
            )
        return ValidationResult(passed=True, severity="info")

    def validate_sentiment(self, result: CollectionResult) -> ValidationResult:
        if result.total_target == 0:
            return ValidationResult(
                passed=True,
                severity="warning",
                details={"collected": 0, "total_target": 0},
            )
        ratio = result.collected / result.total_target
        if ratio < 0.7:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"감성 분석 수집 성공률 부족: {ratio:.0%} < 70%",
                details={"collected": result.collected, "total_target": result.total_target},
            )
        return ValidationResult(passed=True, severity="info")

    async def validate_premarket_db(self, session: AsyncSession) -> ValidationResult:
        """DB에 적재된 장전 데이터 건수 + null 비율 검증."""
        today = datetime.now(KST).date()
        boundary = get_prev_trading_day(today, n=2)

        # 전체 건수
        total_stmt = select(func.count()).select_from(MarketData).where(
            MarketData.data_date >= boundary,
            MarketData.source == "data_go_kr",
        )
        total_result = await session.execute(total_stmt)
        total_count = total_result.scalar_one()

        if total_count < 1500:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"DB 장전 데이터 건수 부족: {total_count} < 1500",
                details={"total_count": total_count, "boundary_date": str(boundary)},
            )

        # close_price null 건수
        null_stmt = select(func.count()).select_from(MarketData).where(
            MarketData.data_date >= boundary,
            MarketData.source == "data_go_kr",
            MarketData.close_price.is_(None),
        )
        null_result = await session.execute(null_stmt)
        null_count = null_result.scalar_one()

        null_ratio = null_count / total_count
        if null_ratio >= 0.05:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"DB close_price null 비율 초과: {null_ratio:.1%} >= 5%",
                details={
                    "total_count": total_count,
                    "null_count": null_count,
                    "null_ratio": null_ratio,
                },
            )

        return ValidationResult(
            passed=True,
            severity="info",
            details={
                "total_count": total_count,
                "null_count": null_count,
                "null_ratio": null_ratio,
                "boundary_date": str(boundary),
            },
        )

    async def cross_check_prices(self, session: AsyncSession, data_date: date) -> list[dict]:
        """포털(data_go_kr) vs KIS(kis_daily) 종가를 in-memory join하여 1% 초과 괴리 종목 반환.

        Returns:
            괴리 종목 목록. 각 항목: {"stock_code", "portal_close", "kis_close", "divergence_pct"}
        """
        portal_stmt = select(MarketData.stock_code, MarketData.close_price).where(
            MarketData.data_date == data_date,
            MarketData.source == "data_go_kr",
            MarketData.close_price.is_not(None),
        )
        kis_stmt = select(MarketData.stock_code, MarketData.close_price).where(
            MarketData.data_date == data_date,
            MarketData.source == "kis_daily",
            MarketData.close_price.is_not(None),
        )

        portal_result = await session.execute(portal_stmt)
        kis_result = await session.execute(kis_stmt)

        portal_map: dict = {row[0]: row[1] for row in portal_result.all()}
        kis_map: dict = {row[0]: row[1] for row in kis_result.all()}

        divergent_stocks: list[dict] = []
        for stock_code in portal_map.keys() & kis_map.keys():
            portal_close = portal_map[stock_code]
            kis_close = kis_map[stock_code]
            if portal_close == 0:
                continue
            divergence_pct = float(abs(portal_close - kis_close) / portal_close * 100)
            if divergence_pct > 1.0:
                divergent_stocks.append({
                    "stock_code": stock_code,
                    "portal_close": portal_close,
                    "kis_close": kis_close,
                    "divergence_pct": divergence_pct,
                })

        if divergent_stocks:
            logger.warning("데이터 cross-check 괴리 발견: %s", divergent_stocks)

        return divergent_stocks

    async def validate_etf_db(self, session: AsyncSession) -> ValidationResult:
        """DB에 적재된 ETF 시세 건수 검증."""
        today = datetime.now(KST).date()

        stmt = select(func.count()).select_from(MarketData).where(
            MarketData.data_date == today,
            MarketData.source == "kis_rest",
        )
        result = await session.execute(stmt)
        count = result.scalar_one()

        if count < 140:
            return ValidationResult(
                passed=False,
                failure_type="permanent",
                failure_reason=f"DB ETF 시세 건수 부족: {count} < 140",
                details={"count": count, "data_date": str(today)},
            )

        return ValidationResult(
            passed=True,
            severity="info",
            details={"count": count, "data_date": str(today)},
        )

    @staticmethod
    def _null_ratio(result: CollectionResult, field_name: str) -> float:
        if result.collected == 0:
            return 1.0
        if not result.null_counts:
            return 0.0
        return result.null_counts.get(field_name, 0) / result.collected

    @staticmethod
    def _is_within_t2(data_date: str) -> bool:
        """data_date(YYYYMMDD)가 오늘(KST) 기준 T-2 영업일 이내인지 판정 (주말/공휴일 건너뜀)."""
        today = datetime.now(KST).date()
        target = datetime.strptime(data_date, "%Y%m%d").date()
        boundary = get_prev_trading_day(today, n=2)
        return target >= boundary
