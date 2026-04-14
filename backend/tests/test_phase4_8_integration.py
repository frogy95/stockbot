"""Phase 4.8 통합 테스트 — 포털 실패 → KIS 보조 수집 → 스크리닝 폴백 시나리오."""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch

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
async def test_kis_success_no_alert():
    """KIS 수집 성공 → 장애 알림 없음, premarket=success."""
    fake_redis = FakeRedis()
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler = _make_scheduler(fake_redis)
    scheduler.set_telegram_bot(mock_bot)

    kis_result = CollectionResult(
        collected=2800, total_target=3000,
        null_counts={"close_price": 0, "volume": 0},
    )

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        await scheduler._premarket_collect()

    # 장애/긴급 알림 없음
    assert not mock_bot.send_notification.called

    status = await scheduler._get_pipeline_status()
    assert status["premarket"]["status"] == "success"


@pytest.mark.asyncio
async def test_kis_failure_pipeline_unhealthy():
    """KIS 수집 실패 → pipeline_healthy=false."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis)

    kis_result = CollectionResult(collected=100, failed=2400, total_target=2500, data_date="20260403")

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
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


@pytest.mark.asyncio
async def test_kis_success_then_retry_skip():
    """08:00 KIS 성공 → premarket=success → 08:30 재시도 스킵.

    실패 상태에서 재시도 성공 시 [복구] 알림 확인도 함께 검증.
    """
    import json
    from modules.collector.scheduler import PIPELINE_STATUS_KEY, STATE_TTL

    fake_redis = FakeRedis()
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler = _make_scheduler(fake_redis)
    scheduler.set_telegram_bot(mock_bot)

    kis_ok = CollectionResult(collected=2400, failed=100, total_target=2500, null_counts={"close_price": 0, "volume": 0})

    # 08:00: KIS 성공 → 장애 알림 없음
    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_ok)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        await scheduler._premarket_collect()

    assert not mock_bot.send_notification.called
    mock_bot.send_notification.reset_mock()

    # KIS 성공 → premarket="success" → retry 스킵 확인
    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._premarket_retry()

    # 실패 상태에서 재시도 성공 → [복구] 알림 확인
    await fake_redis.set(
        PIPELINE_STATUS_KEY,
        json.dumps({"premarket": {"status": "failed"}}),
        ttl=STATE_TTL,
    )
    kis_retry_ok = CollectionResult(collected=2800, total_target=3000, null_counts={"close_price": 0, "volume": 0})
    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_retry_ok)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
    ):
        await scheduler._premarket_retry()

    retry_messages = [c[0][0] for c in mock_bot.send_notification.call_args_list]
    assert any("[복구]" in m for m in retry_messages)

    status = await scheduler._get_pipeline_status()
    assert status["premarket"]["status"] == "success"


@pytest.mark.asyncio
async def test_kis_fail_then_retry_fail():
    """08:00 KIS 실패 → [장애] 알림 → pipeline_healthy=false → 08:30 재시도 실패 → 상태 유지."""
    fake_redis = FakeRedis()
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler = _make_scheduler(fake_redis)
    scheduler.set_telegram_bot(mock_bot)

    kis_fail = CollectionResult(collected=0, total_target=0, data_date=None, null_counts={})

    # 08:00: KIS 실패
    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_fail)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        await scheduler._premarket_collect()

    messages = [c[0][0] for c in mock_bot.send_notification.call_args_list]
    assert any("[장애]" in m for m in messages)

    healthy = await fake_redis.get("scheduler:pipeline_healthy")
    assert healthy == "false"

    mock_bot.send_notification.reset_mock()

    # 08:30: 재시도도 실패 → 상태 유지
    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_fail)),
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
    ):
        await scheduler._premarket_retry()

    # 재시도 실패 → 복구 알림 없음, 상태 여전히 failed
    assert not any("[복구]" in c[0][0] for c in mock_bot.send_notification.call_args_list)
    status = await scheduler._get_pipeline_status()
    assert status["premarket"]["status"] == "failed"


@pytest.mark.asyncio
async def test_kis_success_no_retry_no_alert():
    """08:00 KIS 정상 → 재시도 스킵 → 알림 없음."""
    fake_redis = FakeRedis()
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler = _make_scheduler(fake_redis)
    scheduler.set_telegram_bot(mock_bot)

    kis_ok = CollectionResult(
        collected=2800, total_target=3000,
        null_counts={"close_price": 0, "volume": 0},
    )

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_ok)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        await scheduler._premarket_collect()

    # 장애 알림 없음
    assert not mock_bot.send_notification.called

    # 재시도 스킵 (premarket 이미 success)
    with patch("modules.collector.scheduler.DataGoKrCollector") as MockRetry:
        await scheduler._premarket_retry()
        MockRetry.return_value.collect_all.assert_not_called()
