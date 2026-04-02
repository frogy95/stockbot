from datetime import datetime, timedelta, timezone

from modules.collector.models import CollectionResult, ValidationResult

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

    @staticmethod
    def _null_ratio(result: CollectionResult, field_name: str) -> float:
        if result.collected == 0:
            return 1.0
        if not result.null_counts:
            return 0.0
        return result.null_counts.get(field_name, 0) / result.collected

    @staticmethod
    def _is_within_t2(data_date: str) -> bool:
        """data_date(YYYYMMDD)가 오늘(KST) 기준 T-2 영업일 이내인지 판정 (주말 건너뜀)."""
        today = datetime.now(KST).date()
        target = datetime.strptime(data_date, "%Y%m%d").date()

        # 오늘부터 역순으로 영업일 2일 전까지 계산
        biz_days_back = 0
        current = today
        while biz_days_back < 2:
            current -= timedelta(days=1)
            if current.weekday() < 5:  # 월~금
                biz_days_back += 1

        return target >= current
