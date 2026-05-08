"""Phase 8.6 Sprint 3 — Task 4: portal_supplement / metrics_rollup 잡 점검.

진단 결과 (B)에 해당 — 두 잡은 CronTrigger로 올바르게 등록됐으나
함수 본문에서 _save_last_timestamp 호출이 누락되어
production에서 scheduler:last_portal_supplement / scheduler:last_metrics_rollup 키가
None으로 관측됐음. Task 4에서 누락 호출을 추가하여 수정.

검증 케이스:
1. portal_supplement 잡 cron hour=16, minute=0 KST 확인
2. metrics_rollup 잡 cron hour=16, minute=5 KST 확인
3. _portal_supplement_collect 실행 후 scheduler:last_portal_supplement Redis 키 적재
4. _rollup_daily_metrics 실행 후 scheduler:last_metrics_rollup Redis 키 적재
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from core.config import settings
from modules.collector.scheduler import CollectorScheduler


def _make_scheduler(redis) -> CollectorScheduler:
    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.unsubscribe_all = AsyncMock()
    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()
    # APScheduler가 실제로 start()를 부르지 않도록 mock
    scheduler = CollectorScheduler(
        session_factory=AsyncMock(),
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis,
    )
    return scheduler


# ---------------------------------------------------------------------------
# 헬퍼: start()를 mocking하여 잡 등록만 추출
# ---------------------------------------------------------------------------


async def _get_registered_jobs(redis) -> dict:
    """start() 내부에서 등록된 잡을 실제로 등록하되 스케줄러 start는 우회."""
    scheduler = _make_scheduler(redis)
    # APScheduler 내부 start만 막음
    with patch.object(scheduler._scheduler, "start", return_value=None):
        with patch.object(scheduler, "_load_state_from_redis", new=AsyncMock()):
            # realtime_screener가 None이면 secondary_screen 미등록 — 문제없음
            await scheduler.start()
    return {j.id: j for j in scheduler._scheduler.get_jobs()}


# ---------------------------------------------------------------------------
# 케이스 1: portal_supplement 잡 cron 16:00 KST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portal_supplement_job_registered_cron_1600():
    """portal_supplement 잡이 16:00 KST CronTrigger로 등록되어야 한다."""
    redis = AsyncMock()
    jobs = await _get_registered_jobs(redis)
    assert "portal_supplement" in jobs, "portal_supplement 잡 미등록"
    job = jobs["portal_supplement"]
    trigger = job.trigger
    # CronTrigger fields: hour, minute
    fields = {f.name: f for f in trigger.fields}
    assert str(fields["hour"]) == "16", f"예상 16:00 KST, 실제 hour={fields['hour']}"
    assert str(fields["minute"]) == "0", f"예상 16:00 KST, 실제 minute={fields['minute']}"


# ---------------------------------------------------------------------------
# 케이스 2: metrics_rollup 잡 cron 16:05 KST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_rollup_job_registered_cron_1605():
    """metrics_rollup 잡이 16:05 KST CronTrigger로 등록되어야 한다."""
    redis = AsyncMock()
    jobs = await _get_registered_jobs(redis)
    assert "metrics_rollup" in jobs, "metrics_rollup 잡 미등록"
    job = jobs["metrics_rollup"]
    trigger = job.trigger
    fields = {f.name: f for f in trigger.fields}
    assert str(fields["hour"]) == "16", f"예상 16:05 KST, 실제 hour={fields['hour']}"
    assert str(fields["minute"]) == "5", f"예상 16:05 KST, 실제 minute={fields['minute']}"


# ---------------------------------------------------------------------------
# 케이스 3: _portal_supplement_collect 실행 후 Redis 키 적재
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portal_supplement_collect_saves_timestamp_to_redis():
    """_portal_supplement_collect 성공 경로에서 scheduler:last_portal_supplement 키 적재."""
    redis = AsyncMock()

    scheduler = _make_scheduler(redis)

    # DataGoKrCollector.collect_all mock (성공, collected=5)
    collect_result = MagicMock()
    collect_result.collected = 5
    mock_collector = AsyncMock()
    mock_collector.collect_all = AsyncMock(return_value=collect_result)

    # session_factory context manager mock
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    scheduler._session_factory = MagicMock(return_value=mock_session_ctx)

    tz = ZoneInfo(settings.MARKET_TIMEZONE)
    fixed_now = datetime(2026, 5, 7, 16, 0, 0, tzinfo=tz)

    with patch("modules.collector.scheduler.is_trading_day", return_value=True), \
         patch("modules.collector.scheduler.DataGoKrCollector", return_value=mock_collector), \
         patch("modules.collector.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        await scheduler._portal_supplement_collect()

    # scheduler:last_portal_supplement 키가 set 호출됐는지 확인
    set_calls = redis.set.call_args_list
    assert any(
        call.args[0] == "scheduler:last_portal_supplement"
        for call in set_calls
    ), f"scheduler:last_portal_supplement 키가 Redis에 저장되지 않음. 실제 set 호출: {set_calls}"


# ---------------------------------------------------------------------------
# 케이스 4: _rollup_daily_metrics 실행 후 Redis 키 적재
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_rollup_saves_timestamp_to_redis():
    """_rollup_daily_metrics 성공 경로에서 scheduler:last_metrics_rollup 키 적재."""
    tz = ZoneInfo(settings.MARKET_TIMEZONE)
    fixed_now = datetime(2026, 5, 7, 16, 5, 0, tzinfo=tz)

    # Redis mock: scan_keys는 빈 리스트 반환 (빈 데이터도 성공 경로 통과)
    redis = AsyncMock()
    redis.scan_keys = AsyncMock(return_value=[])
    redis.set = AsyncMock()

    scheduler = _make_scheduler(redis)

    # session_factory mock (빈 커밋)
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    scheduler._session_factory = MagicMock(return_value=mock_session_ctx)

    with patch("modules.collector.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        await scheduler._rollup_daily_metrics()

    set_calls = redis.set.call_args_list
    assert any(
        call.args[0] == "scheduler:last_metrics_rollup"
        for call in set_calls
    ), f"scheduler:last_metrics_rollup 키가 Redis에 저장되지 않음. 실제 set 호출: {set_calls}"
