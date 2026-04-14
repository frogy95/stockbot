"""Phase 4.6 통합 테스트 — 도메인 분리 + 유효성 검증 통합 시나리오."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import (
    CollectorScheduler,
    PIPELINE_STATUS_KEY,
    PIPELINE_HEALTHY_KEY,
)
from modules.collector.models import CollectionResult
from modules.collector.sources.data_go_kr import DataGoKrCollector
from tests.conftest import FakeRedis


def _make_scheduler(fake_redis: FakeRedis | None = None, inquiry_client=None):
    """테스트용 CollectorScheduler 생성 (inquiry_client 지원)."""
    mock_db_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx

    rest_client = MagicMock()

    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.subscribe = AsyncMock()
    ws_manager.unsubscribe_all = AsyncMock()

    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()

    redis = fake_redis if fake_redis is not None else FakeRedis()

    scheduler = CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=rest_client,
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis,
        inquiry_client=inquiry_client,
    )

    mock_screener = AsyncMock()
    mock_screener.screen = AsyncMock(return_value=[])
    mock_screener.save_results = AsyncMock(return_value=0)
    scheduler._primary_screener = mock_screener

    return scheduler, rest_client


def _latest_date() -> str:
    return DataGoKrCollector._latest_trading_date()


# ── 1. 도메인 분리 확인 ──────────────────────────────────

@pytest.mark.asyncio
async def test_etf_collect_uses_inquiry_client():
    """ETF 수집이 inquiry_client를 KISCollector에 전달하는지 확인."""
    fake_redis = FakeRedis()
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps({"etf_master": {"status": "success"}}))

    inquiry_client = MagicMock()
    scheduler, rest_client = _make_scheduler(fake_redis, inquiry_client=inquiry_client)

    with patch("modules.collector.scheduler.KISCollector") as MockKIS:
        MockKIS.return_value.collect_etf_prices = AsyncMock(
            return_value=CollectionResult(collected=20, total_target=20)
        )
        await scheduler._etf_collect()

    # KISCollector가 inquiry_client로 생성되었는지 확인
    MockKIS.assert_called_once()
    actual_client = MockKIS.call_args[0][0]
    assert actual_client is inquiry_client
    assert actual_client is not rest_client


@pytest.mark.asyncio
async def test_etf_collect_falls_back_to_rest_client():
    """inquiry_client가 None이면 rest_client를 사용."""
    fake_redis = FakeRedis()
    await fake_redis.set(PIPELINE_STATUS_KEY, json.dumps({"etf_master": {"status": "success"}}))

    scheduler, rest_client = _make_scheduler(fake_redis, inquiry_client=None)

    with patch("modules.collector.scheduler.KISCollector") as MockKIS:
        MockKIS.return_value.collect_etf_prices = AsyncMock(
            return_value=CollectionResult(collected=20, total_target=20)
        )
        await scheduler._etf_collect()

    actual_client = MockKIS.call_args[0][0]
    assert actual_client is rest_client


# ── 2. premarket 유효성 검증 통합 ─────────────────────────

@pytest.mark.asyncio
async def test_premarket_validation_pass():
    """premarket 1500건+ → pipeline_status에 validation.passed=True."""
    fake_redis = FakeRedis()
    scheduler, _ = _make_scheduler(fake_redis)

    kis_result = CollectionResult(
        collected=2800, total_target=2800,
        null_counts={"close_price": 0, "volume": 0},
    )

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        count = await scheduler._premarket_collect()

    assert count == 2800

    pipeline_status = json.loads(await fake_redis.get(PIPELINE_STATUS_KEY))
    step = pipeline_status["premarket"]
    assert step["status"] == "success"
    assert step["collected_count"] == 2800
    assert step["validation"]["passed"] is True


@pytest.mark.asyncio
async def test_premarket_validation_fail_low_count():
    """premarket 100건 → validation.passed=False, status=failed."""
    fake_redis = FakeRedis()
    scheduler, _ = _make_scheduler(fake_redis)

    kis_result = CollectionResult(
        collected=100, total_target=2800,
        null_counts={"close_price": 0, "volume": 0},
    )

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        count = await scheduler._premarket_collect()

    assert count == 100

    pipeline_status = json.loads(await fake_redis.get(PIPELINE_STATUS_KEY))
    step = pipeline_status["premarket"]
    assert step["status"] == "failed"
    assert step["validation"]["passed"] is False
    assert step["validation"]["failure_type"] == "permanent"

    healthy = await fake_redis.get(PIPELINE_HEALTHY_KEY)
    assert healthy == "false"


# ── 3. 0건 수집 시 pipeline_healthy=false ──────────────────

@pytest.mark.asyncio
async def test_premarket_zero_collected():
    """premarket 0건 수집 → failed + pipeline_healthy 미설정."""
    fake_redis = FakeRedis()
    scheduler, _ = _make_scheduler(fake_redis)

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockData:
        MockData.return_value.collect_all = AsyncMock(
            return_value=CollectionResult(
                collected=0, data_date=_latest_date(),
                null_counts={"close_price": 0, "volume": 0},
            )
        )
        count = await scheduler._premarket_collect()

    assert count == 0

    pipeline_status = json.loads(await fake_redis.get(PIPELINE_STATUS_KEY))
    assert pipeline_status["premarket"]["status"] == "failed"

    healthy = await fake_redis.get(PIPELINE_HEALTHY_KEY)
    assert healthy == "false"


# ── 4. pipeline_status JSON 확장 확인 ──────────────────────

@pytest.mark.asyncio
async def test_pipeline_status_has_collected_count_and_validation():
    """pipeline_status entry에 collected_count, validation dict 존재."""
    fake_redis = FakeRedis()
    scheduler, _ = _make_scheduler(fake_redis)

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockData:
        MockData.return_value.collect_all = AsyncMock(
            return_value=CollectionResult(
                collected=2000, data_date=_latest_date(),
                null_counts={"close_price": 10, "volume": 5},
            )
        )
        await scheduler._premarket_collect()

    pipeline_status = json.loads(await fake_redis.get(PIPELINE_STATUS_KEY))
    step = pipeline_status["premarket"]

    assert "collected_count" in step
    assert "validation" in step
    assert "passed" in step["validation"]
    assert "severity" in step["validation"]
    assert "details" in step["validation"]


# ── 5. _are_core_steps_healthy가 validation도 확인 ────────

@pytest.mark.asyncio
async def test_core_steps_healthy_checks_validation():
    """status=success이지만 validation.passed=False → healthy=False."""
    pipeline_status = {
        "premarket": {
            "status": "success",
            "validation": {"passed": False, "failure_type": "permanent"},
        },
        "primary_screen": {"status": "success"},
    }
    assert CollectorScheduler._are_core_steps_healthy(pipeline_status) is False


@pytest.mark.asyncio
async def test_core_steps_healthy_passes_when_no_validation():
    """validation 키가 없으면 status만으로 판정 (하위호환)."""
    pipeline_status = {
        "premarket": {"status": "success"},
        "primary_screen": {"status": "success"},
    }
    assert CollectorScheduler._are_core_steps_healthy(pipeline_status) is True
