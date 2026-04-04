"""ETF 마스터 스케줄러 + API 엔드포인트 테스트."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from modules.collector.scheduler import CollectorScheduler


def _make_scheduler() -> CollectorScheduler:
    mock_db_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=mock_session_ctx)

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
        redis=AsyncMock(),
    )


# ── 스케줄러 job 등록 ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_etf_master_collect_job_registered_at_0810():
    """etf_master_collect는 체인 파이프라인(premarket_pipeline, 08:00)으로 통합됨을 확인."""
    scheduler = _make_scheduler()
    await scheduler.start()

    job_ids = [job["id"] for job in scheduler.get_status()["next_jobs"]]
    assert "premarket_pipeline" in job_ids
    assert "etf_master_collect" not in job_ids

    from apscheduler.triggers.cron import CronTrigger
    job = scheduler._scheduler.get_job("premarket_pipeline")
    assert job is not None
    trigger = job.trigger
    assert isinstance(trigger, CronTrigger)
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields["hour"] == "8"
    assert fields["minute"] == "0"

    await scheduler.stop()


@pytest.mark.asyncio
async def test_etf_collect_job_at_0815():
    """etf_collect는 체인 파이프라인으로 통합되어 개별 job이 등록되지 않음을 확인."""
    scheduler = _make_scheduler()
    await scheduler.start()

    job = scheduler._scheduler.get_job("etf_collect")
    assert job is None  # 개별 job 없음, premarket_pipeline 체인 내에서 처리

    pipeline_job = scheduler._scheduler.get_job("premarket_pipeline")
    assert pipeline_job is not None

    await scheduler.stop()


@pytest.mark.asyncio
async def test_get_status_includes_last_etf_master():
    """get_status()에 last_etf_master 필드 포함 확인."""
    scheduler = _make_scheduler()
    status = scheduler.get_status()
    assert "last_etf_master" in status


@pytest.mark.asyncio
async def test_trigger_etf_master_calls_collect():
    """trigger_etf_master() 호출 시 KISMasterCollector.collect() 실행 확인."""
    scheduler = _make_scheduler()

    fake_result = {"etf_count": 10, "etn_count": 2, "source": "mst", "sanity_passed": True}

    from unittest.mock import patch, AsyncMock as AM
    with patch("modules.collector.scheduler.KISMasterCollector") as MockCollector:
        mock_instance = MagicMock()
        mock_instance.collect = AM(return_value=fake_result)
        MockCollector.return_value = mock_instance

        result = await scheduler.trigger_etf_master()

    assert result["etf_count"] == 10
    mock_instance.collect.assert_called_once()


# ── API 엔드포인트 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trigger_etf_master_api():
    """POST /api/v1/collector/trigger/etf-master 엔드포인트 동작 확인."""
    from fastapi.testclient import TestClient
    from main import app

    mock_scheduler = MagicMock()
    mock_scheduler.trigger_etf_master = AsyncMock(
        return_value={"etf_count": 5, "etn_count": 1, "source": "mst", "sanity_passed": True}
    )

    app.state.collector_scheduler = mock_scheduler

    with TestClient(app) as client:
        resp = client.post("/api/v1/collector/trigger/etf-master")

    assert resp.status_code == 200
    data = resp.json()
    assert data["triggered"] is True
