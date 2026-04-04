"""수집 스케줄러 테스트."""

import json
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from modules.collector.scheduler import CollectorScheduler, PIPELINE_STATUS_KEY
from modules.collector.models import CollectionResult
from modules.collector.sources.data_go_kr import DataGoKrCollector
from tests.conftest import FakeRedis


def _make_scheduler(redis=None):
    """테스트용 CollectorScheduler 생성. redis=None이면 AsyncMock 사용."""
    mock_db_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx

    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.unsubscribe_all = AsyncMock()

    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()

    return CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis if redis is not None else AsyncMock(),
    )


@pytest.mark.asyncio
async def test_scheduler_registers_jobs():
    """초기화 시 장전/장중/장후 job 등록 확인."""
    scheduler = _make_scheduler()
    await scheduler.start()

    status = scheduler.get_status()
    assert status["running"] is True
    assert status["job_count"] == 5  # premarket_pipeline, market_open, market_close, market_open_recovery, premarket_retry

    job_ids = {j["id"] for j in status["next_jobs"]}
    assert "premarket_pipeline" in job_ids
    assert "market_open" in job_ids
    assert "market_close" in job_ids
    assert "market_open_recovery" in job_ids
    assert "premarket_retry" in job_ids
    # 개별 장전 job은 더 이상 등록되지 않음
    assert "premarket_collect" not in job_ids
    assert "etf_master_collect" not in job_ids
    assert "primary_screen" not in job_ids
    assert "etf_collect" not in job_ids
    assert "dart_collect" not in job_ids
    assert "sentiment_collect" not in job_ids

    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_start_stop():
    """시작/종료 정상 동작."""
    scheduler = _make_scheduler()

    await scheduler.start()
    assert scheduler.get_status()["running"] is True

    await scheduler.stop()
    assert scheduler.get_status()["running"] is False


@pytest.mark.asyncio
async def test_premarket_job():
    """장전 수집 job이 공공데이터포털 수집 호출."""
    scheduler = _make_scheduler()

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(return_value=CollectionResult(collected=2800, data_date=DataGoKrCollector._latest_trading_date(), null_counts={"close_price": 0, "volume": 0}))
        MockCollector.return_value = mock_instance

        count = await scheduler._premarket_collect()

    assert count == 2800
    mock_instance.collect_all.assert_called_once()


@pytest.mark.asyncio
async def test_etf_job():
    """ETF 수집 job — etf_master 선행 성공 상태를 전제한다."""
    fake_redis = FakeRedis()
    # etf_master 성공 상태를 미리 설정
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps({"etf_master": {"status": "success"}}))

    mock_db_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx

    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_client = MagicMock()

    scheduler = CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=fake_redis,
    )

    with patch("modules.collector.scheduler.KISCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_etf_prices = AsyncMock(return_value=CollectionResult(collected=20, total_target=20))
        MockCollector.return_value = mock_instance

        count = await scheduler._etf_collect()

    assert count == 20
    mock_instance.collect_etf_prices.assert_called_once()


@pytest.mark.asyncio
async def test_market_open_job():
    """장중 시작 시 WS 연결."""
    scheduler = _make_scheduler()
    await scheduler._market_open()

    scheduler._ws_client.set_on_data.assert_called_once()
    scheduler._ws_client.connect.assert_called_once()


@pytest.mark.asyncio
async def test_market_close_job():
    """장후 WS 구독 해제."""
    scheduler = _make_scheduler()
    await scheduler._market_close()

    scheduler._ws_manager.unsubscribe_all.assert_called_once()
    scheduler._ws_client.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_premarket():
    """수동 트리거."""
    scheduler = _make_scheduler()

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(return_value=CollectionResult(collected=2800, data_date=DataGoKrCollector._latest_trading_date(), null_counts={"close_price": 0, "volume": 0}))
        MockCollector.return_value = mock_instance

        result = await scheduler.trigger_premarket()

    assert result == {"stocks_collected": 2800}


@pytest.mark.asyncio
async def test_trigger_etf():
    """수동 ETF 트리거 — etf_master 선행 성공 상태를 전제한다."""
    fake_redis = FakeRedis()
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps({"etf_master": {"status": "success"}}))

    mock_db_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx

    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_client = MagicMock()

    scheduler = CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=fake_redis,
    )

    with patch("modules.collector.scheduler.KISCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_etf_prices = AsyncMock(return_value=CollectionResult(collected=20, total_target=20))
        MockCollector.return_value = mock_instance

        result = await scheduler.trigger_etf()

    assert result == {"etfs_collected": 20}


@pytest.mark.asyncio
async def test_premarket_calls_db_validation():
    """장전 수집 성공 후 DB 후검증이 호출되는지 확인."""
    scheduler = _make_scheduler()

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(return_value=CollectionResult(
            collected=2800, data_date=DataGoKrCollector._latest_trading_date(),
            null_counts={"close_price": 0, "volume": 0},
        ))
        MockCollector.return_value = mock_instance

        with patch.object(scheduler._validator, "validate_premarket_db", new_callable=AsyncMock) as mock_db_val:
            from modules.collector.models import ValidationResult
            mock_db_val.return_value = ValidationResult(passed=True, severity="info")
            await scheduler._premarket_collect()
            mock_db_val.assert_called_once()


@pytest.mark.asyncio
async def test_etf_calls_db_validation():
    """ETF 수집 성공 후 DB 후검증이 호출되는지 확인."""
    fake_redis = FakeRedis()
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps({"etf_master": {"status": "success"}}))

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
    )

    with patch("modules.collector.scheduler.KISCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_etf_prices = AsyncMock(
            return_value=CollectionResult(collected=20, total_target=20)
        )
        MockCollector.return_value = mock_instance

        with patch.object(scheduler._validator, "validate_etf_db", new_callable=AsyncMock) as mock_db_val:
            from modules.collector.models import ValidationResult
            mock_db_val.return_value = ValidationResult(passed=True, severity="info")
            await scheduler._etf_collect()
            mock_db_val.assert_called_once()


@pytest.mark.asyncio
async def test_premarket_fallback_to_kis_daily():
    """포털 수집 후 validation 실패 시 KIS 보조 수집 자동 호출."""
    scheduler = _make_scheduler(FakeRedis())

    portal_result = CollectionResult(collected=100, total_target=3000, data_date="20260403", null_counts={})
    kis_result = CollectionResult(collected=2400, failed=100, total_target=2500, data_date="20260403")

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal, \
         patch("modules.collector.scheduler.KISDailyCollector") as MockKIS:
        MockPortal.return_value.collect_all = AsyncMock(return_value=portal_result)
        MockKIS.return_value.collect_all = AsyncMock(return_value=kis_result)

        await scheduler._premarket_collect()

    MockKIS.return_value.collect_all.assert_called_once()


@pytest.mark.asyncio
async def test_premarket_fallback_kis_success():
    """KIS 보조 수집 성공 시 pipeline_status premarket이 success로 갱신."""
    scheduler = _make_scheduler(FakeRedis())

    portal_result = CollectionResult(collected=100, total_target=3000, data_date="20260403", null_counts={})
    kis_result = CollectionResult(collected=2400, failed=100, total_target=2500, data_date="20260403")

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal, \
         patch("modules.collector.scheduler.KISDailyCollector") as MockKIS:
        MockPortal.return_value.collect_all = AsyncMock(return_value=portal_result)
        MockKIS.return_value.collect_all = AsyncMock(return_value=kis_result)

        await scheduler._premarket_collect()

    status = await scheduler._get_pipeline_status()
    assert status.get("premarket", {}).get("status") == "success"


@pytest.mark.asyncio
async def test_premarket_fallback_kis_fail():
    """KIS 보조 수집도 실패 시 pipeline_status premarket이 failed로 유지."""
    scheduler = _make_scheduler(FakeRedis())

    portal_result = CollectionResult(collected=100, total_target=3000, data_date="20260403", null_counts={})
    kis_result = CollectionResult(collected=100, failed=2400, total_target=2500, data_date="20260403")

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal, \
         patch("modules.collector.scheduler.KISDailyCollector") as MockKIS:
        MockPortal.return_value.collect_all = AsyncMock(return_value=portal_result)
        MockKIS.return_value.collect_all = AsyncMock(return_value=kis_result)

        await scheduler._premarket_collect()

    status = await scheduler._get_pipeline_status()
    assert status.get("premarket", {}).get("status") == "failed"


@pytest.mark.asyncio
async def test_premarket_no_fallback_on_success():
    """포털 수집 성공 시 KIS 보조 수집 미호출."""
    scheduler = _make_scheduler(FakeRedis())

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
async def test_check_and_recover_market_open_during_market_hours():
    """장중(09:00~15:30) 재시작 시 _market_open 자동 호출."""
    scheduler = _make_scheduler()

    market_time = datetime(2026, 3, 31, 10, 30, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    with patch("modules.collector.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = market_time

        result = await scheduler.check_and_recover_market_open()

    assert result is True
    scheduler._ws_client.connect.assert_called_once()


@pytest.mark.asyncio
async def test_check_and_recover_market_open_before_market():
    """장전(09:00 이전) 재시작 시 _market_open 미호출."""
    scheduler = _make_scheduler()

    before_market = datetime(2026, 3, 31, 8, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    with patch("modules.collector.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = before_market

        result = await scheduler.check_and_recover_market_open()

    assert result is False
    scheduler._ws_client.connect.assert_not_called()


@pytest.mark.asyncio
async def test_check_and_recover_market_open_after_market():
    """장후(15:30 이후) 재시작 시 _market_open 미호출."""
    scheduler = _make_scheduler()

    after_market = datetime(2026, 3, 31, 16, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    with patch("modules.collector.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = after_market

        result = await scheduler.check_and_recover_market_open()

    assert result is False
    scheduler._ws_client.connect.assert_not_called()
