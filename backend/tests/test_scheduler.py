"""수집 스케줄러 테스트."""

import json
import pytest
from datetime import datetime, timezone
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
    assert status["job_count"] == 8  # premarket_pipeline, market_open, market_close, market_open_recovery, premarket_retry, portal_supplement, metrics_rollup, auto_rollback_check

    job_ids = {j["id"] for j in status["next_jobs"]}
    assert "premarket_pipeline" in job_ids
    assert "market_open" in job_ids
    assert "market_close" in job_ids
    assert "market_open_recovery" in job_ids
    assert "premarket_retry" in job_ids
    assert "portal_supplement" in job_ids
    assert "metrics_rollup" in job_ids
    assert "auto_rollback_check" in job_ids
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
    """장전 수집 job이 KIS 일봉 수집 호출."""
    scheduler = _make_scheduler()

    kis_result = CollectionResult(collected=2800, total_target=2800, null_counts={"close_price": 0, "volume": 0})

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)) as mock_kis,
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        count = await scheduler._premarket_collect()

    assert count == 2800
    mock_kis.assert_awaited_once()


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

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._market_open()

    scheduler._ws_client.set_on_data.assert_called_once()
    scheduler._ws_client.connect.assert_called_once()


@pytest.mark.asyncio
async def test_market_close_job():
    """장후 WS 구독 해제."""
    scheduler = _make_scheduler()

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._market_close()

    scheduler._ws_manager.unsubscribe_all.assert_called_once()
    scheduler._ws_client.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_premarket():
    """수동 트리거."""
    scheduler = _make_scheduler()

    kis_result = CollectionResult(collected=2800, total_target=2800, null_counts={"close_price": 0, "volume": 0})

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)),
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
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
async def test_premarket_kis_success_no_extra_calls():
    """KIS 수집 성공 시 DataGoKrCollector 미호출."""
    scheduler = _make_scheduler(FakeRedis())

    kis_result = CollectionResult(
        collected=2800, total_target=3000,
        null_counts={"close_price": 0, "volume": 0},
    )

    with (
        patch.object(scheduler, "_run_kis_daily_collect", new=AsyncMock(return_value=kis_result)),
        patch("modules.collector.scheduler.DataGoKrCollector") as MockPortal,
        patch.object(scheduler, "_run_db_validation", new=AsyncMock()),
    ):
        await scheduler._premarket_collect()

    MockPortal.return_value.collect_all.assert_not_called()


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


# === Phase 8 Sprint 2 Task 8: 동시호가 no_data 가드 ===


def _build_scheduler_for_secondary(
    subscribed_codes: list[str], data_count: int, now_kst: datetime
):
    """_secondary_screen no_data 가드 테스트용 스케줄러 + realtime_screener mock."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(redis=fake_redis)

    # realtime_screener는 빈 결과 반환 (실제 screening 로직 우회)
    screener = MagicMock()
    screener.screen = AsyncMock(return_value=[])
    scheduler._realtime_screener = screener

    # primary codes 조회 mock — 비어있지 않아야 함수가 진입
    async def _get_codes(_db_session):
        return ["005930"] if subscribed_codes else []

    scheduler._get_latest_primary_codes = _get_codes

    scheduler._ws_manager.get_subscribed_stocks = MagicMock(
        return_value=subscribed_codes
    )

    # Redis에서 execution/orderbook 데이터: data_count만큼 채운다
    for i in range(data_count):
        if i >= len(subscribed_codes):
            break
        code = subscribed_codes[i]
        fake_redis._store[f"realtime:{code}:execution"] = "{}"
        fake_redis._store[f"realtime:{code}:orderbook"] = "{}"

    return scheduler


@pytest.mark.asyncio
async def test_secondary_screen_skips_no_data_guard_during_closing_auction():
    """동시호가(15:15 KST) 구간 — data_count=0이어도 no_data 카운터 증가 없음."""
    closing_auction_time = datetime(
        2026, 4, 22, 15, 15, 0, tzinfo=ZoneInfo("Asia/Seoul")
    )
    scheduler = _build_scheduler_for_secondary(
        subscribed_codes=["005930", "000660"], data_count=0, now_kst=closing_auction_time
    )
    scheduler._reconnect_ws = AsyncMock()
    # 초기 1회 no_data 이후 다시 호출해도 증가 안 해야 함
    scheduler._secondary_no_data_count = 1

    with patch("modules.collector.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = closing_auction_time
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        await scheduler._secondary_screen()

    # 동시호가 구간 — 카운터 0으로 초기화됨
    assert scheduler._secondary_no_data_count == 0
    scheduler._reconnect_ws.assert_not_called()


@pytest.mark.asyncio
async def test_secondary_screen_no_data_guard_active_during_regular_hours():
    """일반 장중(10:00 KST) — data_count=0이면 no_data 카운터 증가."""
    regular_hours = datetime(2026, 4, 22, 10, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    scheduler = _build_scheduler_for_secondary(
        subscribed_codes=["005930"], data_count=0, now_kst=regular_hours
    )
    scheduler._reconnect_ws = AsyncMock()

    with patch("modules.collector.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = regular_hours
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        await scheduler._secondary_screen()

    assert scheduler._secondary_no_data_count == 1
    scheduler._reconnect_ws.assert_not_called()  # 5회 누적 전까지는 재연결 없음


# === Phase 8 Sprint 2 Task 9: 재연결 알림 60초 dedup ===


@pytest.mark.asyncio
async def test_reconnect_alert_deduped_within_60s():
    """60초 내 2회 호출 → telegram.send_notification 1회만."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(redis=fake_redis)
    scheduler._telegram_bot = AsyncMock()
    scheduler._telegram_bot.send_notification = AsyncMock()

    sent_1 = await scheduler._send_reconnect_alert("test", 10)
    sent_2 = await scheduler._send_reconnect_alert("test", 10)

    assert sent_1 is True
    assert sent_2 is False
    assert scheduler._telegram_bot.send_notification.await_count == 1


@pytest.mark.asyncio
async def test_reconnect_alert_sent_after_dedup_key_expires():
    """dedup 키 삭제 후 재발송 허용 (TTL 만료 시뮬레이션)."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(redis=fake_redis)
    scheduler._telegram_bot = AsyncMock()
    scheduler._telegram_bot.send_notification = AsyncMock()

    await scheduler._send_reconnect_alert("a", 5)
    # TTL 만료 시뮬레이션 — 키 제거
    fake_redis._store.pop("ws:reconnect:notified", None)
    await scheduler._send_reconnect_alert("b", 5)

    assert scheduler._telegram_bot.send_notification.await_count == 2


# === Phase 8 Sprint 2 Task 10: 일일 리포트 당일 1회 잠금 ===


@pytest.mark.asyncio
async def test_market_close_sends_daily_report_once_per_day():
    """_market_close 2회 연속 호출 → send_daily_report 1회만."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(redis=fake_redis)
    scheduler._notifier_manager = AsyncMock()
    scheduler._notifier_manager.send_daily_report = AsyncMock()

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._market_close()
        await scheduler._market_close()

    assert scheduler._notifier_manager.send_daily_report.await_count == 1


@pytest.mark.asyncio
async def test_market_close_resends_daily_report_on_next_day():
    """다른 날짜 키는 발송 허용 (lock은 날짜별)."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(redis=fake_redis)
    scheduler._notifier_manager = AsyncMock()
    scheduler._notifier_manager.send_daily_report = AsyncMock()

    # 어제 날짜로 lock 선점
    fake_redis._store["scheduler:daily_report:sent:20260421"] = "1"

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._market_close()  # 오늘은 2026-04-22 기준

    # 오늘 발송은 허용
    assert scheduler._notifier_manager.send_daily_report.await_count == 1


@pytest.mark.asyncio
async def test_market_close_does_not_set_lock_on_failure():
    """send_daily_report 예외 시 lock 미설정 → 재시도 가능."""
    fake_redis = FakeRedis()
    scheduler = _make_scheduler(redis=fake_redis)
    scheduler._notifier_manager = AsyncMock()
    scheduler._notifier_manager.send_daily_report = AsyncMock(
        side_effect=Exception("boom")
    )

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._market_close()

    # lock이 설정되지 않았으므로 다음 시도 가능
    today_str = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
    assert fake_redis._store.get(f"scheduler:daily_report:sent:{today_str}") is None


# === Phase 8.5 Sprint 2 Task 5: 자동 롤백 검사 ===


def _make_scheduler_with_session(session_factory, redis=None):
    """session_factory를 직접 주입하는 테스트용 스케줄러 팩토리."""
    ws_manager = MagicMock()
    ws_manager.count = 0
    ws_manager.unsubscribe_all = AsyncMock()
    ws_client = MagicMock()
    ws_client.connect = AsyncMock()
    ws_client.disconnect = AsyncMock()
    ws_client.set_on_data = MagicMock()
    return CollectorScheduler(
        session_factory=session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis if redis is not None else FakeRedis(),
    )


def _make_session_factory_with_counts(today_count: int, prev_count: int):
    """DB에서 신호 건수를 반환하는 session_factory mock 생성.

    execute().scalar_one() 이 today_count, prev_count 순서로 반환되도록 설정.
    """
    mock_session = AsyncMock()

    # scalar_one()이 순서대로 today_count, prev_count를 반환
    mock_result_today = MagicMock()
    mock_result_today.scalar_one.return_value = today_count
    mock_result_prev = MagicMock()
    mock_result_prev.scalar_one.return_value = prev_count

    mock_session.execute = AsyncMock(
        side_effect=[mock_result_today, mock_result_prev]
    )

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value = mock_session_ctx
    return mock_session_factory


@pytest.mark.asyncio
async def test_auto_rollback_triggered_when_two_zero_days():
    """오늘 + 전 영업일 모두 신호 0건 → Redis override 설정 + Telegram 경고 발동."""
    fake_redis = FakeRedis()
    session_factory = _make_session_factory_with_counts(today_count=0, prev_count=0)
    scheduler = _make_scheduler_with_session(session_factory, redis=fake_redis)

    mock_notifier = AsyncMock()
    mock_notifier.send_system_alert = AsyncMock()
    scheduler._notifier_manager = mock_notifier

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._check_auto_rollback()

    # Redis override 키 설정 확인
    assert fake_redis._store.get("settings:override:MIN_VOLUME_FLOOR_MODE") == "legacy"
    assert fake_redis._store.get("settings:override:SECONDARY_POOL_FALLBACK_ENABLED") == "False"
    # Telegram 알림 발송 확인
    mock_notifier.send_system_alert.assert_awaited_once()
    call_args = mock_notifier.send_system_alert.call_args
    assert call_args[0][0] == "auto_rollback"
    assert "자동 롤백 발동" in call_args[0][1]


@pytest.mark.asyncio
async def test_auto_rollback_not_triggered_if_any_signal_exists():
    """전 영업일에 신호 1건 이상 → 롤백 발동 안 함."""
    fake_redis = FakeRedis()
    session_factory = _make_session_factory_with_counts(today_count=0, prev_count=1)
    scheduler = _make_scheduler_with_session(session_factory, redis=fake_redis)

    mock_notifier = AsyncMock()
    mock_notifier.send_system_alert = AsyncMock()
    scheduler._notifier_manager = mock_notifier

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._check_auto_rollback()

    # Redis override 키 미설정 확인
    assert fake_redis._store.get("settings:override:MIN_VOLUME_FLOOR_MODE") is None
    assert fake_redis._store.get("settings:override:SECONDARY_POOL_FALLBACK_ENABLED") is None
    mock_notifier.send_system_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_rollback_skipped_on_non_trading_day():
    """비거래일에는 롤백 검사 자체를 스킵."""
    fake_redis = FakeRedis()
    session_factory = _make_session_factory_with_counts(today_count=0, prev_count=0)
    scheduler = _make_scheduler_with_session(session_factory, redis=fake_redis)

    with patch("modules.collector.scheduler.is_trading_day", return_value=False):
        await scheduler._check_auto_rollback()

    # 비거래일 → DB 조회도 없고 Redis 변경도 없음
    assert fake_redis._store.get("settings:override:MIN_VOLUME_FLOOR_MODE") is None


def test_override_respected_by_resolve_min_volume_floor():
    """redis_override_mode='legacy' → 0.5 반환 (pure 함수 검증)."""
    from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor
    from unittest.mock import MagicMock

    # 간단한 snapshot mock
    snapshot = MagicMock()
    snapshot.current_price = 50000
    snapshot.prev_close = 45000

    result = _resolve_min_volume_floor(
        snapshot,
        tier="gap_open",
        gap_rate=0.1,
        breakout_ref=46000.0,
        redis_override_mode="legacy",
    )

    assert result == 0.5


def test_override_not_set_uses_settings_mode():
    """redis_override_mode=None → settings.MIN_VOLUME_FLOOR_MODE 사용."""
    from modules.trading.strategies.momentum_breakout import _resolve_min_volume_floor
    from unittest.mock import MagicMock, patch

    snapshot = MagicMock()
    snapshot.current_price = 50000
    snapshot.prev_close = 45000

    # settings.MIN_VOLUME_FLOOR_MODE = "legacy" 로 패치
    with patch(
        "modules.trading.strategies.momentum_breakout.settings"
    ) as mock_settings:
        mock_settings.MIN_VOLUME_FLOOR_MODE = "legacy"
        mock_settings.MIN_VOLUME_FLOOR_HARD = 0.3

        result = _resolve_min_volume_floor(
            snapshot,
            tier="gap_open",
            gap_rate=0.1,
            breakout_ref=46000.0,
            redis_override_mode=None,
        )

    assert result == 0.5
