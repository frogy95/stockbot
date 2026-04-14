"""스케줄러 파이프라인 통합 테스트 — 성공/실패/복구 시나리오."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.collector.scheduler import (
    CollectorScheduler,
    PIPELINE_STATUS_KEY,
    PIPELINE_HEALTHY_KEY,
    CORE_STEPS,
)
from modules.collector.models import CollectionResult
from modules.collector.sources.data_go_kr import DataGoKrCollector
from tests.conftest import FakeRedis


def _premarket_result(collected: int = 2800) -> CollectionResult:
    return CollectionResult(
        collected=collected,
        total_target=collected,
        null_counts={"close_price": 0, "volume": 0},
    )


def _etf_result(collected: int = 700, total_target: int = 700) -> CollectionResult:
    return CollectionResult(collected=collected, total_target=total_target)


def _make_scheduler(fake_redis: FakeRedis | None = None):
    """테스트용 CollectorScheduler 생성."""
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

    redis = fake_redis if fake_redis is not None else FakeRedis()

    scheduler = CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis,
    )

    # 1차 스크리너 설정 (의존성 체인 테스트를 위해)
    mock_screener = AsyncMock()
    mock_screener.screen = AsyncMock(return_value=[])
    mock_screener.save_results = AsyncMock(return_value=0)
    scheduler._primary_screener = mock_screener

    return scheduler



@pytest.mark.asyncio
async def test_full_pipeline_success_flow():
    """전체 파이프라인 성공 시 모든 step이 'success'이고 pipeline_healthy = 'true'."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis)

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=_premarket_result())),
        patch("modules.collector.scheduler.KISMasterCollector") as MockMaster,
        patch("modules.collector.scheduler.KISCollector") as MockKIS,
    ):
        MockMaster.return_value.collect = AsyncMock(
            return_value={"etf_count": 700, "etn_count": 50, "source": "mst", "sanity_passed": True}
        )
        MockKIS.return_value.collect_etf_prices = AsyncMock(return_value=_etf_result())

        # 전체 파이프라인 실행
        await scheduler._premarket_collect()
        await scheduler._etf_master_collect()
        await scheduler._primary_screen()
        await scheduler._etf_collect()
        await scheduler._dart_collect()
        await scheduler._sentiment_collect()

    # 모든 step 상태 확인
    pipeline_status = json.loads(await fake_redis.get(PIPELINE_STATUS_KEY))
    for step in CORE_STEPS:
        assert pipeline_status[step]["status"] == "success", f"{step} should be success"

    # pipeline_healthy = "true"
    healthy = await fake_redis.get(PIPELINE_HEALTHY_KEY)
    assert healthy == "true"


@pytest.mark.asyncio
async def test_premarket_failure_cascades():
    """premarket 실패 → primary_screen/dart/sentiment 스킵 → pipeline_healthy = 'false'."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis)

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(side_effect=Exception("API 장애"))),
        patch("modules.collector.scheduler.KISMasterCollector") as MockMaster,
        patch("modules.collector.scheduler.KISCollector") as MockKIS,
    ):
        # etf_master는 독립 → 성공
        MockMaster.return_value.collect = AsyncMock(
            return_value={"etf_count": 700, "etn_count": 50, "source": "mst", "sanity_passed": True}
        )
        MockKIS.return_value.collect_etf_prices = AsyncMock(return_value=_etf_result())

        await scheduler._premarket_collect()      # 실패
        await scheduler._etf_master_collect()     # 성공 (독립)
        await scheduler._primary_screen()         # 스킵 (premarket 실패)
        await scheduler._etf_collect()            # 성공 (etf_master 성공)
        await scheduler._dart_collect()           # 스킵 (primary_screen 스킵)
        await scheduler._sentiment_collect()      # 스킵 (primary_screen 스킵)

    pipeline_status = json.loads(await fake_redis.get(PIPELINE_STATUS_KEY))
    assert pipeline_status["premarket"]["status"] == "failed"
    assert pipeline_status["primary_screen"]["status"] == "skipped"
    assert pipeline_status["dart"]["status"] == "skipped"
    assert pipeline_status["sentiment"]["status"] == "skipped"
    assert pipeline_status["etf_master"]["status"] == "success"

    # pipeline_healthy는 false (CORE_STEPS 미완료)
    healthy = await fake_redis.get(PIPELINE_HEALTHY_KEY)
    assert healthy != "true"


@pytest.mark.asyncio
async def test_manual_pipeline_recovers():
    """premarket 실패 후 run_premarket_pipeline 호출 → 성공 시 pipeline_healthy = 'true'."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(fake_redis)

    # 1단계: premarket 실패 시뮬레이션
    with patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(side_effect=Exception("초기 장애"))):
        await scheduler._premarket_collect()

    healthy_before = await fake_redis.get(PIPELINE_HEALTHY_KEY)
    assert healthy_before != "true"

    # 2단계: 수동 복구 실행
    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=_premarket_result())),
        patch("modules.collector.scheduler.KISMasterCollector") as MockMaster,
        patch("modules.collector.scheduler.KISCollector") as MockKIS,
    ):
        MockMaster.return_value.collect = AsyncMock(
            return_value={"etf_count": 700, "etn_count": 50, "source": "mst", "sanity_passed": True}
        )
        MockKIS.return_value.collect_etf_prices = AsyncMock(return_value=_etf_result())

        result = await scheduler.run_premarket_pipeline()

    assert result["completed"] is True

    healthy_after = await fake_redis.get(PIPELINE_HEALTHY_KEY)
    assert healthy_after == "true"

    # pipeline_running 락이 해제됨
    running = await fake_redis.get("scheduler:pipeline_running")
    assert running != "true"
