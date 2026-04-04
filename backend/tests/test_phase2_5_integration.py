"""Phase 2.5 통합 테스트 — ETF 마스터 수집 파이프라인 전체 흐름."""

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from modules.collector.sources.kis_master import KISMasterCollector
from modules.collector.sources.kis_collector import KISCollector


from tests.test_kis_master import _make_mst_line, _make_mst_bytes


def _build_valid_mst() -> bytes:
    """sanity check 통과하는 mst 데이터 생성."""
    spot_codes = ["069500", "122630", "114800", "252670", "102110"]
    lines = [_make_mst_line(c, f"ETF_{c}", "EF") for c in spot_codes]
    lines += [_make_mst_line(f"{i:06d}", f"ETF_{i}", "EF") for i in range(250)]
    return _make_mst_bytes(lines)


def _new_session() -> AsyncSession:
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    return session


# ── 1. ETF 마스터 수집 전체 흐름 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_etf_master_pipeline():
    """mock mst → 파싱 → 필터 → 메타 → sanity → DB upsert 전체 흐름."""
    session = _new_session()
    collector = KISMasterCollector(session)

    mst_data = _build_valid_mst()

    async def fake_download(market: str, retry_delay: float = 10.0) -> bytes:
        return mst_data

    with patch.object(collector, "download_mst", side_effect=fake_download):
        result = await collector.collect()

    assert result["source"] == "mst"
    assert result["sanity_passed"] is True
    assert result["etf_count"] > 0
    session.execute.assert_called()
    session.commit.assert_called()


# ── 2. KISCollector ETF 코드 조회 연결 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_kis_collector_gets_etf_codes_after_master_load():
    """stocks에 ETF 적재 후 KISCollector._get_etf_codes()가 ETF 코드 반환."""
    session = AsyncMock(spec=AsyncSession)

    # stocks 테이블에 ETF 코드가 있다고 가정
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["069500", "122630"]
    session.execute = AsyncMock(return_value=mock_result)

    kis_collector = KISCollector(MagicMock(), session)
    codes = await kis_collector._get_etf_codes()

    assert "069500" in codes
    assert "122630" in codes


# ── 3. 다운로드 실패 시 기존 DB 유지 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_preserves_existing_db():
    """mst 다운로드 실패 시 기존 ETF 레코드 손실 없음 (DB 쓰기 없음)."""
    session = _new_session()
    session.execute.return_value.scalar.return_value = 5  # 기존 5개 ETF
    collector = KISMasterCollector(session)

    async def fail_download(market: str, retry_delay: float = 10.0) -> bytes:
        raise Exception("network error")

    with patch.object(collector, "download_mst", side_effect=fail_download):
        result = await collector.collect()

    assert result["source"] == "existing_db"
    assert result["sanity_passed"] is False
    # commit이 호출되지 않아야 함 (DB 변경 없음)
    session.commit.assert_not_called()


# ── 4. 시드 폴백: DB에 ETF 없음 + mst 실패 ────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_fallback_when_db_empty_and_mst_fails():
    """DB에 ETF 없음 + mst 실패 → seed_etfs() 호출 확인."""
    from scripts.seed_etf import SEED_ETFS

    session = AsyncMock(spec=AsyncSession)

    # 스케줄러의 _etf_master_collect에서 seed 폴백은 별도 처리이므로
    # 여기서는 seed_etfs 자체가 DB에 upsert 하는지 검증
    from scripts.seed_etf import seed_etfs
    count = await seed_etfs(session)

    assert count == len(SEED_ETFS)
    session.execute.assert_called_once()
    session.commit.assert_called_once()


# ── 5. 일반 주식 안전성 ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_to_db_does_not_touch_stocks():
    """ETF upsert가 stock_type='STOCK' 레코드에 영향 주지 않음."""
    session = _new_session()
    collector = KISMasterCollector(session)

    etf_list = [
        {
            "stock_code": "069500", "stock_name": "KODEX 200", "stock_type": "ETF",
            "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSPI200",
        }
    ]
    await collector.sync_to_db(etf_list)

    # execute가 호출됐는지 확인 (bulk upsert 1회)
    assert session.execute.call_count == 1
    # DELETE 쿼리가 없어야 함
    call_args = str(session.execute.call_args)
    assert "DELETE" not in call_args.upper()


# ── 6. 스케줄러 job 시간 순서 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scheduler_etf_master_before_etf_collect():
    """etf_master_collect → etf_collect 순서는 premarket_pipeline 체인 내에서 보장됨을 확인."""
    from modules.collector.scheduler import CollectorScheduler
    from apscheduler.triggers.cron import CronTrigger

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session_ctx)

    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.unsubscribe_all = AsyncMock()
    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()

    scheduler = CollectorScheduler(
        session_factory=mock_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=AsyncMock(),
    )
    await scheduler.start()

    # 개별 job 대신 08:00 단일 체인 파이프라인으로 통합됨
    assert scheduler._scheduler.get_job("etf_master_collect") is None
    assert scheduler._scheduler.get_job("etf_collect") is None
    pipeline_job = scheduler._scheduler.get_job("premarket_pipeline")
    assert pipeline_job is not None
    fields = {f.name: str(f) for f in pipeline_job.trigger.fields}
    assert fields["hour"] == "8"
    assert fields["minute"] == "0"

    await scheduler.stop()
