from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from modules.collector.models import CollectionResult
from modules.collector.validator import CollectionValidator, KST


@pytest.fixture
def validator():
    return CollectionValidator()


class TestValidatePremarket:
    def test_pass_sufficient_count_low_nulls(self, validator):
        result = CollectionResult(
            collected=2000,
            data_date=datetime.now(KST).strftime("%Y%m%d"),
            null_counts={"close_price": 10, "volume": 5},
        )
        v = validator.validate_premarket(result)
        assert v.passed is True
        assert v.severity == "info"

    def test_fail_insufficient_count(self, validator):
        result = CollectionResult(collected=1499, data_date=datetime.now(KST).strftime("%Y%m%d"))
        v = validator.validate_premarket(result)
        assert v.passed is False
        assert v.failure_type == "permanent"
        assert "1499" in v.failure_reason

    def test_fail_high_close_price_null_ratio(self, validator):
        result = CollectionResult(
            collected=2000,
            data_date=datetime.now(KST).strftime("%Y%m%d"),
            null_counts={"close_price": 100, "volume": 0},
        )
        v = validator.validate_premarket(result)
        assert v.passed is False
        assert "close_price" in v.failure_reason

    def test_fail_high_volume_null_ratio(self, validator):
        result = CollectionResult(
            collected=2000,
            data_date=datetime.now(KST).strftime("%Y%m%d"),
            null_counts={"close_price": 0, "volume": 100},
        )
        v = validator.validate_premarket(result)
        assert v.passed is False
        assert "volume" in v.failure_reason

    def test_fail_data_date_t3(self, validator):
        # T-3 이상 이전 날짜 (영업일 기준)
        today = datetime.now(KST).date()
        old_date = today - timedelta(days=7)  # 충분히 오래된 날짜
        result = CollectionResult(
            collected=2000,
            data_date=old_date.strftime("%Y%m%d"),
            null_counts={"close_price": 0, "volume": 0},
        )
        v = validator.validate_premarket(result)
        assert v.passed is False
        assert "T-2" in v.failure_reason


class TestValidateEtfMaster:
    def test_pass_sanity_ok(self, validator):
        result = CollectionResult(collected=500)
        v = validator.validate_etf_master(result, sanity_passed=True)
        assert v.passed is True

    def test_fail_sanity_failed(self, validator):
        result = CollectionResult(collected=500)
        v = validator.validate_etf_master(result, sanity_passed=False)
        assert v.passed is False
        assert v.failure_type == "permanent"


class TestValidateEtfCollect:
    def test_pass_above_50_percent(self, validator):
        result = CollectionResult(collected=50, total_target=100)
        v = validator.validate_etf_collect(result)
        assert v.passed is True

    def test_fail_below_50_percent(self, validator):
        result = CollectionResult(collected=49, total_target=100)
        v = validator.validate_etf_collect(result)
        assert v.passed is False
        assert v.failure_type == "permanent"


class TestValidatePrimaryScreen:
    def test_zero_is_warning(self, validator):
        result = CollectionResult(collected=0)
        v = validator.validate_primary_screen(result)
        assert v.passed is True
        assert v.severity == "warning"

    def test_nonzero_is_info(self, validator):
        result = CollectionResult(collected=5)
        v = validator.validate_primary_screen(result)
        assert v.passed is True
        assert v.severity == "info"


class TestValidateDart:
    def test_fail_mapping_below_50(self, validator):
        result = CollectionResult(collected=49, total_target=100)
        v = validator.validate_dart(result)
        assert v.passed is False

    def test_pass_mapping_above_50(self, validator):
        result = CollectionResult(collected=50, total_target=100)
        v = validator.validate_dart(result)
        assert v.passed is True

    def test_zero_total_is_warning(self, validator):
        result = CollectionResult(collected=0, total_target=0)
        v = validator.validate_dart(result)
        assert v.passed is True
        assert v.severity == "warning"


class TestValidateSentiment:
    def test_fail_below_70(self, validator):
        result = CollectionResult(collected=69, total_target=100)
        v = validator.validate_sentiment(result)
        assert v.passed is False

    def test_pass_above_70(self, validator):
        result = CollectionResult(collected=70, total_target=100)
        v = validator.validate_sentiment(result)
        assert v.passed is True

    def test_zero_total_is_warning(self, validator):
        result = CollectionResult(collected=0, total_target=0)
        v = validator.validate_sentiment(result)
        assert v.passed is True
        assert v.severity == "warning"


class TestValidateKisDaily:
    def test_pass_above_80_percent(self, validator):
        result = CollectionResult(collected=80, total_target=100)
        v = validator.validate_kis_daily(result)
        assert v.passed is True
        assert v.severity == "info"

    def test_fail_low_rate(self, validator):
        result = CollectionResult(collected=79, total_target=100)
        v = validator.validate_kis_daily(result)
        assert v.passed is False
        assert v.failure_type == "permanent"
        assert "80%" in v.failure_reason

    def test_pass_exact_threshold(self, validator):
        result = CollectionResult(collected=80, total_target=100)
        v = validator.validate_kis_daily(result)
        assert v.passed is True


class TestNullRatio:
    def test_zero_collected(self):
        result = CollectionResult(collected=0)
        assert CollectionValidator._null_ratio(result, "close_price") == 1.0

    def test_no_null_counts(self):
        result = CollectionResult(collected=100)
        assert CollectionValidator._null_ratio(result, "close_price") == 0.0

    def test_normal_ratio(self):
        result = CollectionResult(collected=100, null_counts={"close_price": 3})
        assert CollectionValidator._null_ratio(result, "close_price") == pytest.approx(0.03)
