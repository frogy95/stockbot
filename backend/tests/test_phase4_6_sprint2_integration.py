"""Phase 4.6 Sprint 2 통합 테스트.

trading_calendar, KODEX 필터, DB 후검증, scheduler 파이프라인 통합을 검증한다.
"""

import json
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from core.trading_calendar import get_latest_trading_day, get_prev_trading_day, is_trading_day
from modules.collector.models import CollectionResult, ValidationResult
from modules.collector.validator import CollectionValidator
from modules.collector.sources.kis_collector import KISCollector
from modules.collector.sources.data_go_kr import DataGoKrCollector
from tests.conftest import FakeRedis


# 1. trading_calendar + _is_within_t2 통합
class TestTradingCalendarIntegration:
    """trading_calendar가 validator._is_within_t2에 올바르게 통합되는지 검증."""

    def test_holiday_is_within_t2(self):
        """공휴일(1/1) 전후 데이터가 T-2 판정에 공휴일을 반영하는지 확인."""
        validator = CollectionValidator()
        # 1/2(금) 기준: T-2 거래일 = 12/30(화) (12/31 수 → T-1, 12/30 화 → T-2, 1/1 건너뜀)
        with patch("modules.collector.validator.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 2, 10, 0, tzinfo=CollectionValidator._is_within_t2.__func__.__code__.co_consts[0] if False else __import__("datetime").timezone(__import__("datetime").timedelta(hours=9)))
            mock_dt.strptime = datetime.strptime

            # 12/31 → T-1이므로 T-2 이내
            assert validator._is_within_t2("20251231") is True
            # 12/30 → T-2이므로 T-2 이내
            assert validator._is_within_t2("20251230") is True
            # 12/29 → T-3이므로 T-2 초과
            assert validator._is_within_t2("20251229") is False


# 2. KODEX 필터 통합
class TestKodexFilterIntegration:
    """KODEX 필터가 ETF 수집 대상을 올바르게 제한하는지 검증."""

    @pytest.mark.asyncio
    async def test_kodex_filter_with_mixed_etfs(self):
        """KODEX 5종 + 비KODEX 3종 → KODEX 5종만 반환."""
        kodex_codes = ["069500", "252670", "229200", "102110", "091170"]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = kodex_codes
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mock_rest = MagicMock()
        mock_rest.get_stock_price = AsyncMock(return_value=MagicMock(
            price=40000, open_price=39800, high=40500, low=39500,
            volume=3000000, change_rate=1.27,
        ))

        collector = KISCollector(mock_rest, mock_db)
        result = await collector.collect_etf_prices(etf_codes=None)

        assert result.total_target == 5
        assert result.collected == 5

        # SQL 쿼리에 KODEX 필터 확인
        select_stmt = mock_db.execute.call_args_list[0].args[0]
        compiled = str(select_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "KODEX" in compiled


# 3. ETF 수집 + 검증 통합
class TestEtfCollectValidationIntegration:
    """KODEX ~280종목 기준으로 validate_etf_collect 50% 임계값 검증."""

    def test_kodex_50_percent_threshold(self):
        """280종목 중 140종목 이상 수집 시 통과."""
        validator = CollectionValidator()

        result_pass = CollectionResult(collected=140, total_target=280)
        assert validator.validate_etf_collect(result_pass).passed is True

        result_fail = CollectionResult(collected=139, total_target=280)
        assert validator.validate_etf_collect(result_fail).passed is False


# 4. DB 후검증 통합
class TestDbValidationIntegration:
    """validate_premarket_db / validate_etf_db가 정상 DB 상태에서 passed 반환."""

    @pytest.mark.asyncio
    async def test_premarket_db_validation_pass(self):
        """충분한 건수 + 낮은 null 비율 → passed."""
        validator = CollectionValidator()
        mock_session = AsyncMock()

        mock_session.execute.side_effect = [
            MagicMock(scalar_one=MagicMock(return_value=2000)),  # total_count
            MagicMock(scalar_one=MagicMock(return_value=50)),    # null_count (2.5%)
        ]

        result = await validator.validate_premarket_db(mock_session)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_etf_db_validation_pass(self):
        """140건 이상 → passed."""
        validator = CollectionValidator()
        mock_session = AsyncMock()

        mock_session.execute.side_effect = [
            MagicMock(scalar_one=MagicMock(return_value=280)),
        ]

        result = await validator.validate_etf_db(mock_session)
        assert result.passed is True


# 5. scheduler 파이프라인 통합
class TestSchedulerPipelineIntegration:
    """premarket → primary_screen → etf → dart → sentiment 순서 + pipeline_healthy 판정."""

    @pytest.mark.asyncio
    async def test_full_pipeline_healthy(self):
        """전체 파이프라인 실행 후 pipeline_healthy 판정."""
        from modules.collector.scheduler import (
            CollectorScheduler,
            PIPELINE_HEALTHY_KEY,
            PIPELINE_STATUS_KEY,
        )

        fake_redis = FakeRedis()

        mock_db_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_session_ctx

        scheduler = CollectorScheduler(
            session_factory=mock_session_factory,
            rest_client=MagicMock(),
            ws_manager=MagicMock(count=0),
            trade_strength=MagicMock(),
            ws_client=MagicMock(),
            redis=fake_redis,
            primary_screener=MagicMock(
                screen=AsyncMock(return_value=[]),
                save_results=AsyncMock(return_value=0),
            ),
        )

        # 각 수집기 mock
        with (
            patch("modules.collector.scheduler.DataGoKrCollector") as MockDataGoKr,
            patch("modules.collector.scheduler.KISCollector") as MockKIS,
            patch("modules.collector.scheduler.KISMasterCollector") as MockMaster,
        ):
            MockDataGoKr.return_value.collect_all = AsyncMock(
                return_value=CollectionResult(
                    collected=2800,
                    data_date=datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d"),
                    null_counts={"close_price": 0, "volume": 0},
                )
            )
            MockMaster.return_value.collect = AsyncMock(
                return_value={"etf_count": 500, "etn_count": 50, "source": "kis", "sanity_passed": True}
            )
            MockKIS.return_value.collect_etf_prices = AsyncMock(
                return_value=CollectionResult(collected=280, total_target=280)
            )

            # DB 후검증 mock
            with patch.object(scheduler._validator, "validate_premarket_db", new_callable=AsyncMock) as mock_pre_db:
                mock_pre_db.return_value = ValidationResult(passed=True, severity="info")
                with patch.object(scheduler._validator, "validate_etf_db", new_callable=AsyncMock) as mock_etf_db:
                    mock_etf_db.return_value = ValidationResult(passed=True, severity="info")
                    await scheduler.run_premarket_pipeline()

        # pipeline_healthy 확인
        healthy = await fake_redis.get(PIPELINE_HEALTHY_KEY)
        assert healthy == "true"


# 6. 날짜 폴백 + 공휴일
class TestDateFallbackWithHoliday:
    """공휴일(1/1)에 data_go_kr 수집 시 전일(12/31)로 폴백."""

    def test_trading_dates_skip_holiday(self):
        """1/2(금) 기준 _get_trading_dates()의 첫 날짜가 12/31(수)인지 확인."""
        # 1/2 → yesterday = 1/1(신정, 공휴일) → get_latest_trading_day → 12/31
        with patch("modules.collector.sources.data_go_kr.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 2, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
            mock_dt.strptime = datetime.strptime

            dates = DataGoKrCollector._get_trading_dates(3)

        assert dates[0] == "20251231"  # 1/1 건너뜀 → 12/31
        # 모든 날짜가 거래일인지 확인
        for d in dates:
            parsed = datetime.strptime(d, "%Y%m%d").date()
            assert is_trading_day(parsed) is True
