"""스케줄 의존성 체인 + pipeline_healthy 플래그 테스트."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import CollectorScheduler
from modules.collector.models import CollectionResult
from modules.collector.sources.data_go_kr import DataGoKrCollector
from tests.conftest import FakeRedis


def _make_scheduler(fake_redis=None):
    """테스트용 CollectorScheduler 생성."""
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

    redis = fake_redis if fake_redis is not None else FakeRedis()

    scheduler = CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis,
    )
    return scheduler


@pytest.mark.asyncio
async def test_primary_screen_skips_when_premarket_failed():
    """premarket 상태가 'failed'이면 _primary_screen이 스킵 반환."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)

    # premarket failed 상태 설정
    pipeline_status = {"premarket": {"status": "failed", "error": "timeout"}}
    await redis.set("scheduler:pipeline_status", json.dumps(pipeline_status))

    scheduler._primary_screener = AsyncMock()  # screener가 있어야 job 실행됨

    result = await scheduler._primary_screen()

    # skipped 반환 + screener는 호출되지 않음
    assert result.get("skipped") is True
    scheduler._primary_screener.screen.assert_not_called()

    # pipeline_status에 primary_screen이 skipped로 기록됨
    saved = json.loads(await redis.get("scheduler:pipeline_status"))
    assert saved["primary_screen"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_dart_skips_when_primary_screen_failed():
    """primary_screen 상태가 'failed'이면 _dart_collect가 스킵."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)

    pipeline_status = {"primary_screen": {"status": "failed"}}
    await redis.set("scheduler:pipeline_status", json.dumps(pipeline_status))

    result = await scheduler._dart_collect()

    assert result == 0  # 스킵 시 0 반환

    saved = json.loads(await redis.get("scheduler:pipeline_status"))
    assert saved["dart"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_sentiment_skips_when_primary_screen_failed():
    """primary_screen 상태가 'failed'이면 _sentiment_collect가 스킵."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)

    pipeline_status = {"primary_screen": {"status": "failed"}}
    await redis.set("scheduler:pipeline_status", json.dumps(pipeline_status))

    result = await scheduler._sentiment_collect()

    assert result == 0

    saved = json.loads(await redis.get("scheduler:pipeline_status"))
    assert saved["sentiment"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_etf_skips_when_etf_master_failed():
    """etf_master 상태가 'failed'이면 _etf_collect가 스킵."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)

    pipeline_status = {"etf_master": {"status": "failed"}}
    await redis.set("scheduler:pipeline_status", json.dumps(pipeline_status))

    result = await scheduler._etf_collect()

    assert result == 0

    saved = json.loads(await redis.get("scheduler:pipeline_status"))
    assert saved["etf"]["status"] == "skipped"


@pytest.mark.asyncio
async def test_pipeline_healthy_true_when_core_succeed():
    """premarket + primary_screen 모두 'success'이면 pipeline_healthy가 'true'."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)

    # premarket 성공 후 primary_screen 성공
    pipeline_status = {"premarket": {"status": "success"}}
    await redis.set("scheduler:pipeline_status", json.dumps(pipeline_status))

    await scheduler._update_step_status("primary_screen", "success")

    healthy = await redis.get("scheduler:pipeline_healthy")
    assert healthy == "true"


@pytest.mark.asyncio
async def test_pipeline_healthy_false_on_init():
    """premarket 시작 시 pipeline_healthy가 'false'로 초기화."""
    redis = FakeRedis()
    await redis.set("scheduler:pipeline_healthy", "true")  # 이전 값이 true라도
    scheduler = _make_scheduler(redis)

    with patch("modules.collector.scheduler.DataGoKrCollector") as MockCollector:
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(return_value=CollectionResult(collected=2800, data_date=DataGoKrCollector._latest_trading_date(), null_counts={"close_price": 0, "volume": 0}))
        MockCollector.return_value = mock_instance

        await scheduler._premarket_collect()

    # premarket 시작 시 false로 초기화됨
    healthy = await redis.get("scheduler:pipeline_healthy")
    # premarket 성공 시에도 primary_screen이 아직 안 돼서 false여야 함
    assert healthy == "false"


@pytest.mark.asyncio
async def test_get_pipeline_status():
    """get_pipeline_status() 반환 JSON 구조 검증."""
    redis = FakeRedis()
    scheduler = _make_scheduler(redis)

    pipeline_data = {
        "premarket": {"status": "success", "timestamp": "2026-04-01T08:01:00"},
        "primary_screen": {"status": "success", "timestamp": "2026-04-01T08:11:00"},
    }
    await redis.set("scheduler:pipeline_status", json.dumps(pipeline_data))

    result = await scheduler.get_pipeline_status()

    assert "premarket" in result
    assert result["premarket"]["status"] == "success"
    assert "primary_screen" in result
