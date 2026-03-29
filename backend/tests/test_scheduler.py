"""수집 스케줄러 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import CollectorScheduler


def _make_scheduler():
    """테스트용 CollectorScheduler 생성."""
    data_go_kr = AsyncMock()
    data_go_kr.collect_all = AsyncMock(return_value=2800)

    kis_collector = AsyncMock()
    kis_collector.collect_etf_prices = AsyncMock(return_value=20)

    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.unsubscribe_all = AsyncMock()

    trade_strength = MagicMock()
    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()

    redis = AsyncMock()

    scheduler = CollectorScheduler(
        data_go_kr=data_go_kr,
        kis_collector=kis_collector,
        ws_manager=ws_manager,
        trade_strength=trade_strength,
        ws_client=ws_client,
        redis=redis,
    )
    return scheduler


@pytest.mark.asyncio
async def test_scheduler_registers_jobs():
    """초기화 시 장전/장중/장후 job 등록 확인."""
    scheduler = _make_scheduler()
    await scheduler.start()

    status = scheduler.get_status()
    assert status["running"] is True
    assert status["job_count"] == 4

    job_ids = {j["id"] for j in status["next_jobs"]}
    assert "premarket_collect" in job_ids
    assert "etf_collect" in job_ids
    assert "market_open" in job_ids
    assert "market_close" in job_ids

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
    count = await scheduler._premarket_collect()

    assert count == 2800
    scheduler._data_go_kr.collect_all.assert_called_once()


@pytest.mark.asyncio
async def test_etf_job():
    """ETF 수집 job."""
    scheduler = _make_scheduler()
    count = await scheduler._etf_collect()

    assert count == 20
    scheduler._kis_collector.collect_etf_prices.assert_called_once()


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
    result = await scheduler.trigger_premarket()

    assert result == {"stocks_collected": 2800}


@pytest.mark.asyncio
async def test_trigger_etf():
    """수동 ETF 트리거."""
    scheduler = _make_scheduler()
    result = await scheduler.trigger_etf()

    assert result == {"etfs_collected": 20}
