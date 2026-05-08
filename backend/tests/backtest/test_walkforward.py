"""walkforward 엔진 + 임계 재조정 진단 테스트."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.backtest.walkforward import (
    TIER_NAMES,
    WalkForwardRunner,
    _time_series_splits,
    compute_actual_pass_rate,
    diagnose_threshold_gap,
    simulate_tier_pass_rate,
)


def _make_series(n: int, *, base_pct: float = 0.5, jitter: float = 0.0) -> list[dict]:
    """일별 dummy series — pct_change/stddev 패턴 단순화."""
    base = date(2026, 3, 1)
    out = []
    for i in range(n):
        sign = 1 if i % 2 == 0 else -1
        pct = sign * (base_pct + (i % 5) * 0.1) + jitter
        out.append({
            "date": base + timedelta(days=i),
            "avg_close": 2500.0 + i,
            "pct_change": pct,
            "stddev": 50.0 + (i % 10),
        })
    return out


# ---------- Step 1: TimeSeriesSplit 슬라이드 수 ----------


def test_time_series_splits_60_days_one_slide():
    splits = _time_series_splits(60, train_size=40, test_size=20)
    assert len(splits) == 1
    train, test = splits[0]
    assert len(list(train)) == 40
    assert len(list(test)) == 20


def test_time_series_splits_80_days_two_slides():
    splits = _time_series_splits(80, train_size=40, test_size=20)
    assert len(splits) == 2


def test_time_series_splits_100_days_three_slides():
    splits = _time_series_splits(100, train_size=40, test_size=20)
    assert len(splits) == 3


# ---------- Step 2: simulate_tier_pass_rate ----------


def test_simulate_tier_pass_rate_changes_with_config():
    series = _make_series(60, base_pct=1.0)
    strict = {
        "prev_high": {"volume_threshold": 5.0, "atr_floor": 0.025, "atr_ceil": 0.0739},
        "gap_open": {"gap_min": 5.0, "atr_ceil_hard": 0.08},
        "prev_close": {"volume_threshold": 5.0},
        "volume_surge": {"vol_ratio": 50.0, "bid_ask_ratio": 2.0, "price_threshold": 5.0},
    }
    loose = {
        "prev_high": {"volume_threshold": 0.1, "atr_floor": 0.025, "atr_ceil": 0.0739},
        "gap_open": {"gap_min": 0.1, "atr_ceil_hard": 0.08},
        "prev_close": {"volume_threshold": 0.1},
        "volume_surge": {"vol_ratio": 0.1, "bid_ask_ratio": 0.1, "price_threshold": 0.1},
    }
    rates_strict = simulate_tier_pass_rate(series, strict)
    rates_loose = simulate_tier_pass_rate(series, loose)
    # tier 4종 모두 키 존재
    for tier in TIER_NAMES:
        assert tier in rates_strict
        assert tier in rates_loose
    # loose 가 strict 보다 pass율 ≥
    assert sum(rates_loose.values()) > sum(rates_strict.values())


# ---------- Step 3: compute_actual_pass_rate ----------


@pytest.mark.asyncio
async def test_compute_actual_pass_rate_returns_per_tier_dict():
    """tier별 발행 횟수 mock → tier별 비율 dict 반환."""
    # signals fixture: matched_tiers + strategy_name 별 카운트 결과
    # SQL 결과 mock — (tier_label, count)
    rows = [
        ("gap_open", 30),
        ("prev_high", 60),
        ("prev_close", 20),
        ("volume_surge", 10),
    ]
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_result)

    rates = await compute_actual_pass_rate(
        mock_session,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 5, 1),
    )
    for tier in TIER_NAMES:
        assert tier in rates
        assert 0.0 <= rates[tier] <= 1.0


# ---------- Step 4-5: diagnose_threshold_gap ----------


def test_diagnose_threshold_gap_too_strict_flagged():
    simulated = {"gap_open": 0.10, "prev_high": 0.10, "prev_close": 0.10, "volume_surge": 0.10}
    actual = {"gap_open": 0.02, "prev_high": 0.02, "prev_close": 0.02, "volume_surge": 0.02}
    diag = diagnose_threshold_gap(simulated, actual, threshold=0.05)
    assert diag["flag"] == "threshold_too_strict"
    assert "candidates" in diag
    assert "gaps" in diag


def test_diagnose_threshold_gap_no_flag_when_close():
    simulated = {"gap_open": 0.05, "prev_high": 0.05, "prev_close": 0.05, "volume_surge": 0.05}
    actual = {"gap_open": 0.04, "prev_high": 0.04, "prev_close": 0.04, "volume_surge": 0.04}
    diag = diagnose_threshold_gap(simulated, actual, threshold=0.05)
    assert diag["flag"] is None


# ---------- Step 6: grid search ----------


def test_diagnose_grid_search_returns_candidates():
    """grid search 결과로 volume_threshold/bid_ask_ratio 권고값 산출."""
    simulated = {"gap_open": 0.30, "prev_high": 0.30, "prev_close": 0.30, "volume_surge": 0.30}
    actual = {"gap_open": 0.05, "prev_high": 0.05, "prev_close": 0.05, "volume_surge": 0.05}
    diag = diagnose_threshold_gap(simulated, actual, threshold=0.05)
    assert "candidates" in diag
    cands = diag["candidates"]
    # grid search 후보 키 존재
    assert "volume_threshold" in cands
    assert "bid_ask_ratio" in cands
    assert cands["volume_threshold"] in [1.5, 1.6, 1.8, 2.0]
    assert cands["bid_ask_ratio"] in [1.0, 1.5, 2.0]


# ---------- Step 7: WalkForwardRunner.run 통합 ----------


@pytest.mark.asyncio
async def test_walkforward_runner_run_inserts_db_records():
    """historical_loader mock + 60일 데이터 → BacktestRun + BacktestSignalMetric tier 4종 INSERT."""
    series = _make_series(60, base_pct=0.5)
    # box/trend 충족 시뮬 summary
    summary = {
        "box_days": 30,
        "trend_days": 30,
        "labels": (["box"] * 30) + (["trend"] * 30),
        "sigma_long_term": 1.0,
        "threshold": 1.5,
    }

    mock_session = AsyncMock()
    # actual pass rate 호출 mock
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("gap_open", 30), ("prev_high", 60), ("prev_close", 20), ("volume_surge", 10)
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch("modules.backtest.walkforward.load_kospi_daily", AsyncMock(return_value=series)), \
         patch("modules.backtest.walkforward.classify_regime", return_value=summary), \
         patch("modules.backtest.walkforward.is_dataset_sufficient", return_value=True):
        runner = WalkForwardRunner(session=mock_session)
        result = await runner.run(period_end=date(2026, 5, 1), n_days=60)

    assert result.success is True
    assert result.run_id
    # tier 4종 pass_rates 있음
    for tier in TIER_NAMES:
        assert tier in result.pass_rates
    # session.add 호출 횟수: BacktestRun 1 + BacktestSignalMetric 4
    assert mock_session.add.call_count >= 5


@pytest.mark.asyncio
async def test_walkforward_runner_fails_on_insufficient_dataset():
    """classify_regime이 box/trend < 20 → status='failed', error 메시지 set."""
    series = _make_series(60)
    summary = {
        "box_days": 5,
        "trend_days": 5,
        "labels": ["box"] * 60,
        "sigma_long_term": 1.0,
        "threshold": 1.5,
    }
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch("modules.backtest.walkforward.load_kospi_daily", AsyncMock(return_value=series)), \
         patch("modules.backtest.walkforward.classify_regime", return_value=summary), \
         patch("modules.backtest.walkforward.is_dataset_sufficient", return_value=False):
        runner = WalkForwardRunner(session=mock_session)
        result = await runner.run(period_end=date(2026, 5, 1), n_days=60)

    assert result.success is False
    assert result.error is not None
    assert "데이터셋" in result.error or "insufficient" in result.error.lower()
