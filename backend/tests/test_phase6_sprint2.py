"""Phase 6 Sprint 2 — 복원력 강화 테스트."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import httpx

from modules.collector.sources.kis_daily_collector import KISDailyCollector
from modules.collector.scheduler import CollectorScheduler


# ── KIS 일봉 수집기 재시도 테스트 ──────────────────────────


def _make_rest_mock():
    """KISRestClient mock."""
    return MagicMock()


def _make_db_session():
    """AsyncSession mock."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=["005930"])))))
    db.commit = AsyncMock()
    return db


def _make_http_error(status_code: int) -> httpx.HTTPStatusError:
    """httpx.HTTPStatusError를 생성한다."""
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


@pytest.mark.asyncio
async def test_kis_daily_collector_retries_on_500():
    """HTTP 500 시 3회 재시도 후 성공."""
    rest = _make_rest_mock()
    db = _make_db_session()
    collector = KISDailyCollector(rest, db)

    # 1회 실패(500), 2회째 성공
    price_mock = MagicMock()
    price_mock.data_date = "20260410"
    price_mock.open_price = 100
    price_mock.high_price = 110
    price_mock.low_price = 90
    price_mock.close_price = 105
    price_mock.volume = 1000
    price_mock.change_rate = 5.0

    rest.get_daily_price = AsyncMock(
        side_effect=[_make_http_error(500), [price_mock]]
    )

    with patch("modules.collector.sources.kis_daily_collector.asyncio.sleep", new_callable=AsyncMock):
        result = await collector._fetch_with_retry("005930", "20260410")

    assert result == [price_mock]
    assert rest.get_daily_price.call_count == 2


@pytest.mark.asyncio
async def test_kis_daily_collector_retries_on_429():
    """HTTP 429 시 재시도 + 백오프."""
    rest = _make_rest_mock()
    db = _make_db_session()
    collector = KISDailyCollector(rest, db)

    price_mock = MagicMock()
    price_mock.data_date = "20260410"
    rest.get_daily_price = AsyncMock(
        side_effect=[_make_http_error(429), _make_http_error(429), [price_mock]]
    )

    sleep_calls = []

    async def mock_sleep(seconds):
        sleep_calls.append(seconds)

    with patch("modules.collector.sources.kis_daily_collector.asyncio.sleep", side_effect=mock_sleep):
        result = await collector._fetch_with_retry("005930", "20260410")

    assert result == [price_mock]
    assert rest.get_daily_price.call_count == 3
    # 백오프: 2초, 4초
    assert sleep_calls == [2, 4]


@pytest.mark.asyncio
async def test_kis_daily_collector_no_retry_on_400():
    """HTTP 400 시 즉시 실패 (재시도 안 함)."""
    rest = _make_rest_mock()
    db = _make_db_session()
    collector = KISDailyCollector(rest, db)

    rest.get_daily_price = AsyncMock(side_effect=_make_http_error(400))

    with pytest.raises(httpx.HTTPStatusError):
        await collector._fetch_with_retry("005930", "20260410")

    # 400은 재시도 대상이 아니므로 1회만 호출
    assert rest.get_daily_price.call_count == 1


# ── scheduler recovery 단계적 재시도 테스트 ──────────────────


def _make_scheduler(redis=None):
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
    ws_client.set_on_ws_failure = MagicMock()
    ws_client.set_on_reconnect_success = MagicMock()
    ws_client.connected = False

    return CollectorScheduler(
        session_factory=mock_session_factory,
        rest_client=MagicMock(),
        ws_manager=ws_manager,
        trade_strength=MagicMock(),
        ws_client=ws_client,
        redis=redis if redis is not None else AsyncMock(),
    )


@pytest.mark.asyncio
async def test_recovery_three_stage_retry():
    """09:05/09:10/09:15 단계적 재시도 — 3회 모두 실패 시 긴급 알림."""
    scheduler = _make_scheduler()
    telegram = AsyncMock()
    scheduler._telegram_bot = telegram
    # connected는 항상 False (복구 실패 시나리오)
    type(scheduler._ws_client).connected = PropertyMock(return_value=False)

    with (
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
        patch("modules.collector.scheduler.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await scheduler._market_open_recovery()

    # 3회 시도
    assert scheduler._ws_client.connect.await_count == 3
    # 5분 간격 2번 대기 (3회 시도 사이 2번)
    assert mock_sleep.await_count == 2
    # 긴급 알림 확인
    last_call = telegram.send_notification.call_args_list[-1]
    assert "긴급" in last_call[0][0]
    assert "최종 실패" in last_call[0][0]


@pytest.mark.asyncio
async def test_recovery_skips_if_connected():
    """이미 연결된 상태에서 recovery 스킵."""
    scheduler = _make_scheduler()
    type(scheduler._ws_client).connected = PropertyMock(return_value=True)
    scheduler._ws_manager.count = 5

    with patch("modules.collector.scheduler.is_trading_day", return_value=True):
        await scheduler._market_open_recovery()

    scheduler._ws_client.connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_succeeds_on_second_attempt():
    """2회차에서 복구 성공."""
    scheduler = _make_scheduler()
    telegram = AsyncMock()
    scheduler._telegram_bot = telegram

    # 1회차: connected=False, 2회차: connected=True
    connected_values = [False, False, True]  # check, after 1st _market_open, after 2nd _market_open
    type(scheduler._ws_client).connected = PropertyMock(side_effect=connected_values)

    with (
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
        patch("modules.collector.scheduler.asyncio.sleep", new_callable=AsyncMock),
    ):
        await scheduler._market_open_recovery()

    # 2회 시도 후 성공
    assert scheduler._ws_client.connect.await_count == 2
    last_call = telegram.send_notification.call_args_list[-1]
    assert "복구 성공" in last_call[0][0]


@pytest.mark.asyncio
async def test_recovery_final_failure_alert():
    """3회 실패 시 텔레그램 긴급 알림."""
    scheduler = _make_scheduler()
    telegram = AsyncMock()
    scheduler._telegram_bot = telegram
    type(scheduler._ws_client).connected = PropertyMock(return_value=False)

    with (
        patch("modules.collector.scheduler.is_trading_day", return_value=True),
        patch("modules.collector.scheduler.asyncio.sleep", new_callable=AsyncMock),
    ):
        await scheduler._market_open_recovery()

    # 마지막 알림이 [긴급]
    all_msgs = [call[0][0] for call in telegram.send_notification.call_args_list]
    assert any("긴급" in msg for msg in all_msgs)


@pytest.mark.asyncio
async def test_market_close_skips_non_trading_day():
    """비거래일 market_close 스킵."""
    scheduler = _make_scheduler()

    with patch("modules.collector.scheduler.is_trading_day", return_value=False):
        await scheduler._market_close()

    scheduler._ws_manager.unsubscribe_all.assert_not_awaited()
    scheduler._ws_client.disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_premarket_retry_skips_non_trading_day():
    """비거래일 premarket_retry 스킵."""
    scheduler = _make_scheduler()
    redis_mock = AsyncMock()
    scheduler._redis = redis_mock

    with patch("modules.collector.scheduler.is_trading_day", return_value=False):
        await scheduler._premarket_retry()

    # 파이프라인 상태 조회 없음
    redis_mock.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_premarket_exception_triggers_kis_fallback():
    """_premarket_collect 예외 경로에서 KIS 폴백 실행."""
    scheduler = _make_scheduler()
    telegram = AsyncMock()
    scheduler._telegram_bot = telegram

    # DataGoKrCollector 예외 발생 시뮬레이션
    mock_fallback_result = MagicMock()
    mock_fallback_result.collected = 2500
    mock_fallback_result.failed = 100
    mock_fallback_result.total_target = 2600
    mock_fallback_result.data_date = "20260410"

    mock_validation = MagicMock()
    mock_validation.passed = True

    scheduler._run_kis_daily_fallback = AsyncMock(return_value=mock_fallback_result)
    scheduler._validator = MagicMock()
    scheduler._validator.validate_kis_daily.return_value = mock_validation
    scheduler._run_db_validation = AsyncMock()
    scheduler._update_step_status = AsyncMock()

    # DataGoKrCollector.collect_all이 예외 발생
    with patch("modules.collector.scheduler.DataGoKrCollector") as mock_collector_cls:
        mock_instance = AsyncMock()
        mock_instance.collect_all = AsyncMock(side_effect=Exception("포털 연결 실패"))
        mock_collector_cls.return_value = mock_instance

        result = await scheduler._premarket_collect()

    # KIS 폴백이 실행되어 2500건 수집
    scheduler._run_kis_daily_fallback.assert_awaited_once()
    assert result == 2500
