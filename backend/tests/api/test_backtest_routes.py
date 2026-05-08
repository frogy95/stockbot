"""Phase 8.6 Sprint 4 — backtest API 라우터 테스트."""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import UserInfo, get_current_user, get_db
from core.models.backtest import BacktestRun, BacktestSignalMetric, LiveGateStatus
from main import create_app


# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def app_no_auth(mock_session):
    """인증 override 없이 lifespan 비활성화 앱 — 인증 테스트용."""
    test_app = create_app()
    test_app.router.lifespan_context = None

    async def override_get_db():
        yield mock_session

    test_app.dependency_overrides[get_db] = override_get_db
    yield test_app
    test_app.dependency_overrides.clear()


def _make_app_with_user(mock_session, username: str):
    """지정 username 으로 인증된 앱 반환."""
    test_app = create_app()
    test_app.router.lifespan_context = None

    async def override_get_db():
        yield mock_session

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username=username, trading_env="paper"
    )
    return test_app


def _fake_run(run_id: str = "run-abc") -> BacktestRun:
    now = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    run = MagicMock(spec=BacktestRun)
    run.run_id = run_id
    run.period_start = date(2026, 3, 1)
    run.period_end = date(2026, 5, 1)
    run.n_trading_days = 42
    run.regime_box_days = 20
    run.regime_trend_days = 22
    run.status = "completed"
    run.error = None
    run.started_at = now
    run.completed_at = now
    run.created_at = now
    return run


def _fake_metric(run_id: str = "run-abc", tier: str = "prev_high") -> BacktestSignalMetric:
    now = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    m = MagicMock(spec=BacktestSignalMetric)
    m.run_id = run_id
    m.tier = tier
    m.pass_rate_simulated = 0.6
    m.pass_rate_actual = 0.55
    m.ks_statistic = 0.1
    m.ks_pvalue = 0.3
    m.bootstrap_ci_lower = 0.48
    m.bootstrap_ci_upper = 0.62
    m.recorded_at = now
    return m


def _fake_gate() -> LiveGateStatus:
    now = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    g = MagicMock(spec=LiveGateStatus)
    g.evaluated_at = now
    g.g_bt1_passed = True
    g.g_bt2_passed = True
    g.g_bt3_passed = False
    g.all_passed = False
    g.details = {"g_bt1": "ok", "g_bt2": "ok", "g_bt3": "fail"}
    return g


def _make_scalars(items: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    result.scalar_one_or_none.return_value = items[0] if items else None
    return result


# ---------------------------------------------------------------------------
# 1. 비인증 요청 → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(app_no_auth):
    """Authorization 헤더 없이 요청 시 401 응답."""
    async with AsyncClient(
        transport=ASGITransport(app=app_no_auth), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/backtest/runs")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. BACKTEST_ADMIN_USERNAME=None → 인증된 사용자도 403 (lockdown)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lockdown_when_admin_username_none(mock_session):
    """BACKTEST_ADMIN_USERNAME=None 이면 인증된 사용자도 403."""
    app = _make_app_with_user(mock_session, username="admin")

    with patch("core.config.settings.BACKTEST_ADMIN_USERNAME", None):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/backtest/runs")

    assert resp.status_code == 403
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. BACKTEST_ADMIN_USERNAME=admin, 현재 사용자=other → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_admin_user_gets_403(mock_session):
    """현재 사용자명이 admin 과 다르면 403."""
    app = _make_app_with_user(mock_session, username="other")

    with patch("core.config.settings.BACKTEST_ADMIN_USERNAME", "admin"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/backtest/runs")

    assert resp.status_code == 403
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4 & 5. POST /run → 202 + run_id 반환 + BackgroundTasks 호출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_run_returns_run_id(mock_session):
    """admin 사용자가 POST /run 하면 202 + run_id 포함 응답."""
    app = _make_app_with_user(mock_session, username="admin")

    with patch("core.config.settings.BACKTEST_ADMIN_USERNAME", "admin"), \
         patch("api.routes.backtest._run_walkforward") as mock_bg:
        mock_bg.return_value = None
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/backtest/run",
                json={"period_end": "2026-05-01", "n_days": 60},
            )

    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "running"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_run_run_id_passed_to_background(mock_session):
    """POST /run 응답 run_id가 _run_walkforward 첫 번째 인자로 전달되어야 한다 (S4-M1 회귀)."""
    app = _make_app_with_user(mock_session, username="admin")
    captured_args = []

    def capture_bg(*args, **kwargs):
        captured_args.extend(args)
        return None

    with patch("core.config.settings.BACKTEST_ADMIN_USERNAME", "admin"), \
         patch("api.routes.backtest._run_walkforward", side_effect=capture_bg):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/backtest/run",
                json={"period_end": "2026-05-01", "n_days": 60},
            )

    assert resp.status_code == 202
    returned_run_id = resp.json()["run_id"]
    # BackgroundTasks.add_task(fn, run_id, period_end, n_days) 순서 검증
    # captured_args[0] 이 add_task 로 전달된 첫 번째 위치 인자 (run_id)
    assert len(captured_args) >= 1
    assert captured_args[0] == returned_run_id, (
        f"응답 run_id({returned_run_id})와 백그라운드 태스크에 전달된 run_id({captured_args[0]})가 불일치"
    )
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. GET /runs → 최근 실행 목록
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_runs(mock_session):
    """GET /runs 는 BacktestRun 목록을 반환한다."""
    run = _fake_run()
    mock_session.execute = AsyncMock(return_value=_make_scalars([run]))

    app = _make_app_with_user(mock_session, username="admin")

    with patch("core.config.settings.BACKTEST_ADMIN_USERNAME", "admin"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/backtest/runs?limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert len(data["runs"]) == 1
    assert data["runs"][0]["run_id"] == "run-abc"
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. GET /runs/{run_id} → 상세 + metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_run_detail(mock_session):
    """GET /runs/{run_id} 는 run 정보 + tier metric 4종 포함 응답."""
    run = _fake_run("run-xyz")
    metrics = [_fake_metric("run-xyz", tier) for tier in ["gap_open", "prev_high", "prev_close", "volume_surge"]]

    call_count = 0

    async def side_effect(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # BacktestRun 조회
            return _make_scalars([run])
        else:
            # BacktestSignalMetric 조회
            return _make_scalars(metrics)

    mock_session.execute = side_effect

    app = _make_app_with_user(mock_session, username="admin")

    with patch("core.config.settings.BACKTEST_ADMIN_USERNAME", "admin"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/backtest/runs/run-xyz")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run"]["run_id"] == "run-xyz"
    assert len(data["metrics"]) == 4
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. GET /live-gate-status → LiveGateStatus row 또는 기본값
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_gate_status_with_row(mock_session):
    """DB에 LiveGateStatus row 가 있으면 실제 값 반환."""
    gate = _fake_gate()
    mock_session.execute = AsyncMock(return_value=_make_scalars([gate]))

    app = _make_app_with_user(mock_session, username="admin")

    with patch("core.config.settings.BACKTEST_ADMIN_USERNAME", "admin"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/backtest/live-gate-status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["g_bt1_passed"] is True
    assert data["all_passed"] is False
    assert data["details"] is not None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_live_gate_status_default_when_no_row(mock_session):
    """DB에 LiveGateStatus row 없으면 기본값(all False) 반환."""
    mock_session.execute = AsyncMock(return_value=_make_scalars([]))

    app = _make_app_with_user(mock_session, username="admin")

    with patch("core.config.settings.BACKTEST_ADMIN_USERNAME", "admin"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/backtest/live-gate-status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["g_bt1_passed"] is False
    assert data["g_bt2_passed"] is False
    assert data["all_passed"] is False
    assert data["evaluated_at"] is None
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 9. POST /backfill-daily → 202 + BackgroundTasks 호출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_daily_returns_running(mock_session):
    """POST /backfill-daily 는 202 + status=running 반환."""
    app = _make_app_with_user(mock_session, username="admin")

    with patch("core.config.settings.BACKTEST_ADMIN_USERNAME", "admin"), \
         patch("api.routes.backtest._run_backfill") as mock_bg:
        mock_bg.return_value = None
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/backtest/backfill-daily",
                json={"start_date": "2026-03-01", "end_date": "2026-05-01"},
            )

    assert resp.status_code == 202
    assert resp.json()["status"] == "running"
    app.dependency_overrides.clear()
