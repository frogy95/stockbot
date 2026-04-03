"""Phase 4.8 통합 테스트 — 포털 실패 → KIS 보조 수집 → 스크리닝 폴백 시나리오."""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.models import CollectionResult
from modules.collector.scheduler import PIPELINE_HEALTHY_KEY
from modules.screening.screener import PrimaryScreener
from tests.conftest import FakeRedis
from tests.test_scheduler import _make_scheduler


@pytest.mark.asyncio
async def test_portal_fail_kis_fallback_screening():
    """포털 실패 → KIS 보조 수집 → 스크리닝 정상 동작."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis)

    portal_result = CollectionResult(collected=50, total_target=3000, data_date="20260403", null_counts={})
    kis_result = CollectionResult(collected=2400, failed=100, total_target=2500, data_date="20260403")

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal, \
         patch("modules.collector.scheduler.KISDailyCollector") as MockKIS:
        MockPortal.return_value.collect_all = AsyncMock(return_value=portal_result)
        MockKIS.return_value.collect_all = AsyncMock(return_value=kis_result)

        await scheduler._premarket_collect()

    MockKIS.return_value.collect_all.assert_called_once()

    status = await scheduler._get_pipeline_status()
    assert status["premarket"]["status"] == "success"

    screener = PrimaryScreener()
    today_prev = {
        "005930": {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "stock_type": "STOCK",
            "market_type": "KOSPI",
            "volume": 5_000_000,
            "prev_volume": 2_000_000,
            "market_cap": 350_000_000_000_000,
            "change_rate": 2.5,
            "close_price": 70_000,
            "high_price": 72_000,
            "low_price": 69_000,
        }
    }
    with patch.object(screener, "_fetch_today_and_prev", new_callable=AsyncMock) as mock_fetch, \
         patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mock_recent:
        mock_fetch.return_value = today_prev
        mock_recent.return_value = {}

        session = AsyncMock()
        result = await screener.screen(session)

    assert len(result) >= 1


@pytest.mark.asyncio
async def test_portal_success_no_fallback():
    """포털 정상 → KIS 보조 수집 미호출."""
    from modules.collector.sources.data_go_kr import DataGoKrCollector
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis)

    portal_result = CollectionResult(
        collected=2800, total_target=3000,
        data_date=DataGoKrCollector._latest_trading_date(),
        null_counts={"close_price": 0, "volume": 0},
    )

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal, \
         patch("modules.collector.scheduler.KISDailyCollector") as MockKIS:
        MockPortal.return_value.collect_all = AsyncMock(return_value=portal_result)

        await scheduler._premarket_collect()

    MockKIS.return_value.collect_all.assert_not_called()


@pytest.mark.asyncio
async def test_dual_failure_pipeline_unhealthy():
    """포털 + KIS 모두 실패 → pipeline_healthy=false."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis)

    portal_result = CollectionResult(collected=50, total_target=3000, data_date="20260403", null_counts={})
    kis_result = CollectionResult(collected=100, failed=2400, total_target=2500, data_date="20260403")

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal, \
         patch("modules.collector.scheduler.KISDailyCollector") as MockKIS:
        MockPortal.return_value.collect_all = AsyncMock(return_value=portal_result)
        MockKIS.return_value.collect_all = AsyncMock(return_value=kis_result)

        await scheduler._premarket_collect()

    healthy = await fake_redis.get(PIPELINE_HEALTHY_KEY)
    assert healthy == "false"

    status = await scheduler._get_pipeline_status()
    assert status["premarket"]["status"] == "failed"


@pytest.mark.asyncio
async def test_kis_daily_market_cap_estimation():
    """KIS 보조 데이터에 market_cap=None일 때 listed_shares 기반 추정이 스크리닝에 적용."""
    screener = PrimaryScreener()

    today = date.today()
    today_row_with_listed_shares = {
        "stock_code": "005930",
        "data_date": today,
        "stock_name": "삼성전자",
        "stock_type": "STOCK",
        "market_type": "KOSPI",
        "volume": 5_000_000,
        "market_cap": None,
        "listed_shares": 5_969_782_550,
        "change_rate": Decimal("2.5"),
        "close_price": 70_000,
        "high_price": 72_000,
        "low_price": 69_000,
        "open_price": 70_000,
    }

    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = [today_row_with_listed_shares]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    result = await screener._fetch_today_and_prev(session)

    assert "005930" in result
    expected = 5_969_782_550 * 70_000
    assert result["005930"]["market_cap"] == expected
    assert result["005930"]["market_cap"] > 30_000_000_000
