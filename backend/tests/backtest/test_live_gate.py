"""LIVE 토글 게이트 G-Bt1·G-Bt2·G-Bt3 자동 평가 테스트 (Phase 8.6 Sprint 4 Task 5)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.backtest.live_gate import LiveGateEvaluator, run_weekly_backtest_and_gate_assess


def _make_session_factory(session: MagicMock) -> MagicMock:
    factory = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    factory.return_value = cm
    return factory


def _make_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _stub_gate_methods(gate: LiveGateEvaluator, *, g1: dict, g2: dict, g3: dict) -> None:
    gate._eval_gbt1 = AsyncMock(return_value=g1)
    gate._eval_gbt2 = AsyncMock(return_value=g2)
    gate._eval_gbt3 = AsyncMock(return_value=g3)


# ---------- G-Bt1 ----------


@pytest.mark.asyncio
async def test_gbt1_pass_gap_within_threshold():
    """가장 최근 BacktestRun metric의 sim/actual 격차가 10%p 이내면 PASS."""
    run = SimpleNamespace(run_id="rid-1", status="completed")
    metrics = [
        SimpleNamespace(tier="gap_open", pass_rate_simulated=0.10, pass_rate_actual=0.05),
        SimpleNamespace(tier="prev_high", pass_rate_simulated=0.20, pass_rate_actual=0.15),
    ]
    run_result = MagicMock()
    run_result.scalars.return_value.first.return_value = run
    metric_result = MagicMock()
    metric_result.scalars.return_value.all.return_value = metrics

    session = _make_session()
    session.execute = AsyncMock(side_effect=[run_result, metric_result])

    gate = LiveGateEvaluator(session_factory=_make_session_factory(session))
    out = await gate._eval_gbt1(session)
    assert out["passed"] is True
    assert out["max_gap"] == pytest.approx(0.05)


@pytest.mark.asyncio
async def test_gbt1_fail_gap_exceeds_threshold():
    """격차 > 10%p → FAIL."""
    run = SimpleNamespace(run_id="rid-2", status="completed")
    metrics = [
        SimpleNamespace(tier="gap_open", pass_rate_simulated=0.30, pass_rate_actual=0.05),
    ]
    run_result = MagicMock()
    run_result.scalars.return_value.first.return_value = run
    metric_result = MagicMock()
    metric_result.scalars.return_value.all.return_value = metrics

    session = _make_session()
    session.execute = AsyncMock(side_effect=[run_result, metric_result])

    gate = LiveGateEvaluator(session_factory=_make_session_factory(session))
    out = await gate._eval_gbt1(session)
    assert out["passed"] is False
    assert out["max_gap"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_gbt1_underspecified_when_no_run():
    """BacktestRun 없음 → underspecified=True, passed=False (보수적 차단)."""
    run_result = MagicMock()
    run_result.scalars.return_value.first.return_value = None
    session = _make_session()
    session.execute = AsyncMock(return_value=run_result)

    gate = LiveGateEvaluator(session_factory=_make_session_factory(session))
    out = await gate._eval_gbt1(session)
    assert out["passed"] is False
    assert out["underspecified"] is True


@pytest.mark.asyncio
async def test_gbt1_underspecified_when_no_metrics():
    """BacktestRun 있으나 메트릭 없음 → underspecified=True, passed=False (보수적 차단)."""
    run = SimpleNamespace(run_id="rid-3", status="completed")
    run_result = MagicMock()
    run_result.scalars.return_value.first.return_value = run
    metric_result = MagicMock()
    metric_result.scalars.return_value.all.return_value = []

    session = _make_session()
    session.execute = AsyncMock(side_effect=[run_result, metric_result])

    gate = LiveGateEvaluator(session_factory=_make_session_factory(session))
    out = await gate._eval_gbt1(session)
    assert out["passed"] is False
    assert out["underspecified"] is True
    assert out["reason"] == "no_metrics"


# ---------- G-Bt2 ----------


@pytest.mark.asyncio
async def test_gbt2_pass_ci_lower_above_threshold():
    """일별 신호 수 충분 → bootstrap CI 하한 ≥ 1.0 → PASS."""
    gate = LiveGateEvaluator(session_factory=_make_session_factory(_make_session()))
    gate._daily_signal_counts = AsyncMock(return_value=[3, 4, 5, 4, 3, 4, 5] * 5)
    out = await gate._eval_gbt2(MagicMock())
    assert out["passed"] is True
    assert out["ci_lower"] >= 1.0


@pytest.mark.asyncio
async def test_gbt2_fail_ci_lower_below_threshold():
    """0건 위주 → CI 하한 < 1.0 → FAIL."""
    gate = LiveGateEvaluator(session_factory=_make_session_factory(_make_session()))
    gate._daily_signal_counts = AsyncMock(return_value=[0] * 30)
    out = await gate._eval_gbt2(MagicMock())
    assert out["passed"] is False
    assert out["ci_lower"] < 1.0


# ---------- G-Bt3 ----------


@pytest.mark.asyncio
async def test_gbt3_pass_high_mean_low_zero_ratio():
    """일평균 ≥ 1.5 AND 0건 일수 ≤ 30% → PASS."""
    gate = LiveGateEvaluator(session_factory=_make_session_factory(_make_session()))
    gate._daily_signal_counts = AsyncMock(return_value=[2, 3, 1, 2, 3])
    out = await gate._eval_gbt3(MagicMock())
    assert out["passed"] is True
    assert out["daily_mean"] >= 1.5
    assert out["zero_ratio"] <= 0.30


@pytest.mark.asyncio
async def test_gbt3_fail_low_daily_mean():
    """일평균 < 1.5 → FAIL."""
    gate = LiveGateEvaluator(session_factory=_make_session_factory(_make_session()))
    gate._daily_signal_counts = AsyncMock(return_value=[1, 0, 1, 0, 1])
    out = await gate._eval_gbt3(MagicMock())
    assert out["passed"] is False


@pytest.mark.asyncio
async def test_gbt3_fail_high_zero_ratio():
    """일평균은 충족이지만 0건 비율 > 30% → FAIL."""
    gate = LiveGateEvaluator(session_factory=_make_session_factory(_make_session()))
    gate._daily_signal_counts = AsyncMock(return_value=[5, 0, 5, 0, 0])
    out = await gate._eval_gbt3(MagicMock())
    assert out["passed"] is False
    assert out["zero_ratio"] > 0.30


# ---------- assess() 통합 ----------


@pytest.mark.asyncio
async def test_assess_all_passed_inserts_status_no_dry_run_flag():
    """3개 모두 PASS → LiveGateStatus INSERT, dry_run_forced 미설정, 알림 미발송."""
    session = _make_session()
    factory = _make_session_factory(session)
    notifier = MagicMock()
    notifier.send = AsyncMock()

    with patch("modules.backtest.live_gate.settings") as mock_settings, \
         patch("modules.backtest.live_gate.redis_client") as mock_redis:
        mock_settings.LIVE_GATE_AUTO_EVAL_ENABLED = True
        mock_redis.set = AsyncMock()

        gate = LiveGateEvaluator(session_factory=factory, notifier=notifier)
        _stub_gate_methods(
            gate,
            g1={"passed": True, "max_gap": 0.02},
            g2={"passed": True, "ci_lower": 2.0, "ci_upper": 3.0},
            g3={"passed": True, "daily_mean": 2.0, "zero_ratio": 0.0},
        )
        result = await gate.assess()

        assert result is not None
        assert result.all_passed is True
        session.add.assert_called_once()
        session.commit.assert_awaited_once()
        notifier.send.assert_not_awaited()
        for call in mock_redis.set.await_args_list:
            assert call.args[0] != "metrics:live_gate:dry_run_forced"


@pytest.mark.asyncio
async def test_assess_one_failed_sets_dry_run_and_alerts():
    """1개라도 FAIL → dry_run_forced=true, 텔레그램 알림 발송."""
    session = _make_session()
    factory = _make_session_factory(session)
    notifier = MagicMock()
    notifier.send = AsyncMock()

    with patch("modules.backtest.live_gate.settings") as mock_settings, \
         patch("modules.backtest.live_gate.redis_client") as mock_redis:
        mock_settings.LIVE_GATE_AUTO_EVAL_ENABLED = True
        mock_redis.set = AsyncMock()

        gate = LiveGateEvaluator(session_factory=factory, notifier=notifier)
        _stub_gate_methods(
            gate,
            g1={"passed": True, "max_gap": 0.02},
            g2={"passed": False, "ci_lower": 0.3, "ci_upper": 0.8},
            g3={"passed": True, "daily_mean": 2.0, "zero_ratio": 0.0},
        )
        result = await gate.assess()

        assert result is not None
        assert result.all_passed is False
        notifier.send.assert_awaited_once()
        keys = [c.args[0] for c in mock_redis.set.await_args_list]
        assert "metrics:live_gate:dry_run_forced" in keys


@pytest.mark.asyncio
async def test_assess_disabled_returns_none():
    """LIVE_GATE_AUTO_EVAL_ENABLED=False → 평가 스킵, None 반환."""
    factory = _make_session_factory(_make_session())
    with patch("modules.backtest.live_gate.settings") as mock_settings:
        mock_settings.LIVE_GATE_AUTO_EVAL_ENABLED = False
        gate = LiveGateEvaluator(session_factory=factory)
        result = await gate.assess()
        assert result is None


# ---------- 잡 래퍼 ----------


@pytest.mark.asyncio
async def test_run_weekly_job_runs_walkforward_and_assess():
    """잡 래퍼 — BACKTEST_ENABLED=True → walk-forward 호출 + 게이트 평가 + last_backtest_assess set."""
    factory = _make_session_factory(_make_session())

    with patch("modules.backtest.live_gate.settings") as mock_settings, \
         patch("modules.backtest.live_gate.redis_client") as mock_redis, \
         patch("modules.backtest.walkforward.WalkForwardRunner") as MockRunner, \
         patch("modules.backtest.live_gate.LiveGateEvaluator") as MockGate:
        mock_settings.BACKTEST_ENABLED = True
        mock_settings.BACKTEST_DEFAULT_N_DAYS = 60
        mock_settings.LIVE_GATE_AUTO_EVAL_ENABLED = True
        mock_redis.set = AsyncMock()

        runner_inst = MockRunner.return_value
        runner_inst.run = AsyncMock()

        gate_inst = MockGate.return_value
        gate_inst.assess = AsyncMock()

        await run_weekly_backtest_and_gate_assess(factory, notifier=None)

        runner_inst.run.assert_awaited_once()
        gate_inst.assess.assert_awaited_once()
        assert any(
            c.args[0] == "scheduler:last_backtest_assess"
            for c in mock_redis.set.await_args_list
        )


@pytest.mark.asyncio
async def test_run_weekly_job_skips_walkforward_when_disabled():
    """BACKTEST_ENABLED=False → walk-forward 스킵, 평가는 진행."""
    factory = _make_session_factory(_make_session())

    with patch("modules.backtest.live_gate.settings") as mock_settings, \
         patch("modules.backtest.live_gate.redis_client") as mock_redis, \
         patch("modules.backtest.walkforward.WalkForwardRunner") as MockRunner, \
         patch("modules.backtest.live_gate.LiveGateEvaluator") as MockGate:
        mock_settings.BACKTEST_ENABLED = False
        mock_settings.LIVE_GATE_AUTO_EVAL_ENABLED = True
        mock_redis.set = AsyncMock()

        gate_inst = MockGate.return_value
        gate_inst.assess = AsyncMock()

        await run_weekly_backtest_and_gate_assess(factory, notifier=None)

        MockRunner.assert_not_called()
        gate_inst.assess.assert_awaited_once()
