"""DB 폴백 스크리닝 + 재시도 후 재실행 통합 테스트."""

import json
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import (
    CollectorScheduler,
    PIPELINE_RUNNING_KEY,
    PIPELINE_HEALTHY_KEY,
    PIPELINE_STATUS_KEY,
)
from modules.collector.models import CollectionResult, ValidationResult
from tests.conftest import FakeRedis


def _make_scheduler(fake_redis=None):
    """테스트용 CollectorScheduler 생성 (primary_screener 포함)."""
    mock_db_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory.return_value = mock_session_ctx

    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.subscribe = AsyncMock()
    ws_manager.unsubscribe_all = AsyncMock()

    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()

    primary_screener = AsyncMock()
    primary_screener.screen = AsyncMock(return_value=[])
    primary_screener.save_results = AsyncMock(return_value=0)

    redis = fake_redis if fake_redis is not None else FakeRedis()

    return CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis,
        primary_screener=primary_screener,
    )


async def _set_pipeline_status(redis: FakeRedis, status: dict) -> None:
    await redis.set(PIPELINE_STATUS_KEY, json.dumps(status))


@asynccontextmanager
async def _retry_patches(scheduler, portal_result, screen_result=None):
    """_premarket_retry 테스트 공통 패치 컨텍스트."""
    validation_ok = ValidationResult(passed=True, severity="info")
    with (
        patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector,
        patch.object(scheduler._validator, "validate_premarket", return_value=validation_ok),
        patch.object(scheduler._validator, "validate_premarket_db", AsyncMock(return_value=ValidationResult(passed=True))),
        patch.object(scheduler._validator, "cross_check_prices", AsyncMock(return_value=[])),
        patch.object(scheduler, "_primary_screen", AsyncMock(return_value=screen_result or {"candidates": 0, "passed": 0})) as mock_screen,
        patch.object(scheduler, "_dart_collect", AsyncMock(return_value=0)) as mock_dart,
        patch.object(scheduler, "_sentiment_collect", AsyncMock(return_value=0)) as mock_sentiment,
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
    ):
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(return_value=portal_result)
        MockCollector.return_value = mock_instance
        yield mock_screen, mock_dart, mock_sentiment


# ── _primary_screen DB 폴백 테스트 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_primary_screen_db_fallback_success():
    """premarket 'failed' + DB 데이터 충분 (T-1) → 스크리닝 진행, primary_screen 'success'."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)
    await _set_pipeline_status(redis, {"premarket": {"status": "failed"}})

    readiness_ok = ValidationResult(
        passed=True, severity="info",
        details={"total_count": 1800, "is_stale": False, "latest_date": "2026-04-05"},
    )
    with patch.object(scheduler._validator, "validate_screening_readiness", AsyncMock(return_value=readiness_ok)):
        result = await scheduler._primary_screen()

    assert result.get("skipped") is not True
    saved = json.loads(await redis.get(PIPELINE_STATUS_KEY))
    assert saved["primary_screen"]["status"] == "success"


@pytest.mark.asyncio
async def test_primary_screen_db_fallback_stale_alert():
    """premarket 'failed' + DB 데이터 T-2 → 스크리닝 진행 + 텔레그램 경고."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)
    mock_bot = AsyncMock()
    mock_bot.send_notification = AsyncMock()
    scheduler._telegram_bot = mock_bot

    await _set_pipeline_status(redis, {"premarket": {"status": "failed"}})

    readiness_stale = ValidationResult(
        passed=True, severity="warning",
        details={"total_count": 1600, "is_stale": True, "latest_date": "2026-04-03", "source_counts": {}},
    )
    with patch.object(scheduler._validator, "validate_screening_readiness", AsyncMock(return_value=readiness_stale)):
        await scheduler._primary_screen()

    mock_bot.send_notification.assert_called_once()
    call_arg = mock_bot.send_notification.call_args[0][0]
    assert "[경고]" in call_arg
    assert "T-2" in call_arg


@pytest.mark.asyncio
async def test_primary_screen_db_fallback_insufficient():
    """premarket 'failed' + DB 데이터 부족 → 스크리닝 스킵."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)
    await _set_pipeline_status(redis, {"premarket": {"status": "failed"}})

    readiness_fail = ValidationResult(
        passed=False, failure_type="data_insufficient",
        failure_reason="DB 스크리닝 데이터 부족: 500 < 1500",
    )
    with patch.object(scheduler._validator, "validate_screening_readiness", AsyncMock(return_value=readiness_fail)):
        result = await scheduler._primary_screen()

    assert result.get("skipped") is True
    saved = json.loads(await redis.get(PIPELINE_STATUS_KEY))
    assert saved["primary_screen"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_primary_screen_db_fallback_exception():
    """DB 검증 자체 예외 → 안전하게 스킵."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)
    await _set_pipeline_status(redis, {"premarket": {"status": "failed"}})

    with patch.object(
        scheduler._validator, "validate_screening_readiness",
        AsyncMock(side_effect=Exception("DB 연결 오류")),
    ):
        result = await scheduler._primary_screen()

    assert result.get("skipped") is True
    saved = json.loads(await redis.get(PIPELINE_STATUS_KEY))
    assert saved["primary_screen"]["status"] == "skipped"


# ── _premarket_retry 후속 재실행 테스트 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_premarket_retry_triggers_rerun():
    """포털 재시도 성공 + primary_screen 'skipped' → 스크리닝 + dart + sentiment 재실행."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)
    await _set_pipeline_status(redis, {
        "premarket": {"status": "failed"},
        "primary_screen": {"status": "skipped"},
    })

    portal_result = CollectionResult(collected=1800, data_date="20260405")
    async with _retry_patches(scheduler, portal_result) as (mock_screen, mock_dart, mock_sentiment):
        await scheduler._premarket_retry()

    mock_screen.assert_called_once()
    mock_dart.assert_called_once()
    mock_sentiment.assert_called_once()


@pytest.mark.asyncio
async def test_premarket_retry_no_rerun_when_screen_success():
    """포털 재시도 성공 + primary_screen 이미 'success' → 재실행 안 함."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)
    await _set_pipeline_status(redis, {
        "premarket": {"status": "failed"},
        "primary_screen": {"status": "success"},
    })

    portal_result = CollectionResult(collected=1800, data_date="20260405")
    async with _retry_patches(scheduler, portal_result) as (mock_screen, mock_dart, mock_sentiment):
        await scheduler._premarket_retry()

    mock_screen.assert_not_called()


@pytest.mark.asyncio
async def test_premarket_retry_rerun_blocked_by_running_lock():
    """재실행 시 PIPELINE_RUNNING_KEY 존재 → 재실행 스킵."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)
    await _set_pipeline_status(redis, {
        "premarket": {"status": "failed"},
        "primary_screen": {"status": "skipped"},
    })
    await redis.set(PIPELINE_RUNNING_KEY, "manual")

    portal_result = CollectionResult(collected=1800, data_date="20260405")
    async with _retry_patches(scheduler, portal_result) as (mock_screen, mock_dart, mock_sentiment):
        await scheduler._premarket_retry()

    mock_screen.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_healthy_stays_false_on_db_fallback():
    """DB 폴백 스크리닝 성공해도 pipeline_healthy=false 유지."""
    redis = FakeRedis()
    await redis.set(PIPELINE_HEALTHY_KEY, "false")
    scheduler = _make_scheduler(redis)
    await _set_pipeline_status(redis, {"premarket": {"status": "failed"}})

    readiness_ok = ValidationResult(
        passed=True, severity="info",
        details={"total_count": 1800, "is_stale": False, "latest_date": "2026-04-05"},
    )
    with patch.object(scheduler._validator, "validate_screening_readiness", AsyncMock(return_value=readiness_ok)):
        await scheduler._primary_screen()

    # premarket이 "success"가 아니므로 _are_core_steps_healthy()가 False → healthy 전환 없음
    healthy = await redis.get(PIPELINE_HEALTHY_KEY)
    assert healthy == "false"
