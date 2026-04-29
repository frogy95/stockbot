"""Phase 8.6 Sprint 2 Task 2 — ATR 캘리브레이션 모듈 단위 테스트.

순수 함수 + Redis 메트릭 + 폴백 3단 + 안전모드 트리거 검증.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from modules.screening import atr_calibration as ac


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}
        self._ttl: dict[str, int] = {}

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ttl=None):
        self._store[key] = value
        if ttl:
            self._ttl[key] = ttl

    async def setex(self, key, ttl, value):
        self._store[key] = value
        self._ttl[key] = ttl

    async def incr(self, key):
        cur = int(self._store.get(key, "0"))
        self._store[key] = str(cur + 1)
        return cur + 1

    async def delete(self, key):
        self._store.pop(key, None)


# === 순수 함수 ===


def test_iqr_trim_removes_outliers():
    values = [0.02, 0.03, 0.03, 0.03, 0.04, 0.04, 0.05, 0.5]  # 0.5 outlier
    trimmed = ac._apply_iqr_trim(values, k=1.5)
    assert 0.5 not in trimmed
    assert all(v <= 0.1 for v in trimmed)


def test_iqr_trim_short_returns_as_is():
    assert ac._apply_iqr_trim([0.01, 0.02, 0.03]) == [0.01, 0.02, 0.03]


def test_ewma_weights_recent_values():
    # Constant series → EWMA = constant
    assert ac._apply_ewma([0.05] * 10, lambda_=0.94) == pytest.approx(0.05)
    # Recent shock → EWMA shifts toward recent
    series = [0.02] * 9 + [0.10]
    out = ac._apply_ewma(series, lambda_=0.94)
    assert 0.02 < out < 0.10


def test_percentile_basic():
    sorted_v = [0.01, 0.02, 0.03, 0.04, 0.05]
    assert ac._percentile(sorted_v, 50) == pytest.approx(0.03)
    assert ac._percentile(sorted_v, 0) == pytest.approx(0.01)
    assert ac._percentile(sorted_v, 100) == pytest.approx(0.05)


# === compute_kospi200_atr_p80 ===


@pytest.mark.asyncio
async def test_compute_p80_with_sma_method(monkeypatch):
    """50종목 모의 데이터 → IQR 트리밍 → P80 산출."""
    fake_codes = [f"{i:06d}" for i in range(100, 150)]

    async def _fake_load_codes(_session):
        return fake_codes

    async def _fake_load_ratios(_session, codes, lookback_days, method, *, today):
        # 50종목 — 0.020 ~ 0.060 균일 분포 + outlier 1
        ratios = {c: 0.020 + (i / len(codes)) * 0.040 for i, c in enumerate(codes)}
        ratios[codes[0]] = 0.20  # outlier
        return ratios, 0

    monkeypatch.setattr(ac, "_load_kospi200_codes", _fake_load_codes)
    monkeypatch.setattr(ac, "_load_recent_atr_ratios", _fake_load_ratios)

    p80, info = await ac.compute_kospi200_atr_p80(
        AsyncMock(), lookback_days=20, method="sma", today=date(2026, 4, 30)
    )
    assert p80 is not None
    assert 0.020 < p80 < 0.080
    # outlier 제거 확인
    assert info["sample_n"] < info["raw_sample_n"]
    assert "p80" in info["dist"]


@pytest.mark.asyncio
async def test_compute_p80_returns_none_when_master_short(monkeypatch):
    async def _fake_load(_s):
        return ["005930"]  # <10
    monkeypatch.setattr(ac, "_load_kospi200_codes", _fake_load)
    p80, info = await ac.compute_kospi200_atr_p80(AsyncMock())
    assert p80 is None
    assert info["reason"] == "kospi200_master_insufficient"


@pytest.mark.asyncio
async def test_compute_p80_returns_none_when_coverage_gap_high(monkeypatch):
    fake_codes = [f"{i:06d}" for i in range(100, 200)]
    async def _fake_load(_s):
        return fake_codes
    async def _fake_ratios(_s, codes, ld, m, *, today):
        return {codes[0]: 0.04}, 30  # 30 missing
    monkeypatch.setattr(ac, "_load_kospi200_codes", _fake_load)
    monkeypatch.setattr(ac, "_load_recent_atr_ratios", _fake_ratios)
    p80, info = await ac.compute_kospi200_atr_p80(AsyncMock())
    assert p80 is None
    assert info["reason"] == "market_data_coverage_gap"


# === run_atr_calibration ===


@pytest.mark.asyncio
async def test_run_calibration_success_writes_redis_keys(monkeypatch):
    redis = _FakeRedis()
    notifier = AsyncMock()
    today = date(2026, 4, 30)

    async def _fake_compute(*a, **kw):
        return 0.05, {"sample_n": 40, "dist": {"p10": 0.02, "p20": 0.025, "p50": 0.035, "p80": 0.05, "p95": 0.07}}

    monkeypatch.setattr(ac, "compute_kospi200_atr_p80", _fake_compute)

    class _FakeSession:
        async def __aenter__(self): return AsyncMock()
        async def __aexit__(self, *a): return None

    sf = lambda: _FakeSession()  # noqa: E731
    result = await ac.run_atr_calibration(sf, redis, notifier, today=today)
    assert result["status"] == "ok"
    assert result["ceil"] == pytest.approx(min(0.05 * 1.2, 0.08))
    assert f"metrics:atr:ceil:{today.isoformat()}" in redis._store
    assert f"metrics:atr:dist:{today.isoformat()}" in redis._store
    grid = json.loads(redis._store[f"metrics:atr:ceil_grid:{today.isoformat()}"])
    assert "mult_1.0" in grid and "mult_1.2" in grid
    # mult_1.3 × 0.05 = 0.065 < HARD 0.08 → 그대로
    assert grid["mult_1.3"] == pytest.approx(0.065)


@pytest.mark.asyncio
async def test_run_calibration_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr("modules.screening.atr_calibration.settings.ATR_CALIBRATION_ENABLED", False)
    redis = _FakeRedis()
    sf = lambda: AsyncMock()  # noqa: E731
    result = await ac.run_atr_calibration(sf, redis, None)
    assert result["status"] == "disabled"


@pytest.mark.asyncio
async def test_run_calibration_falls_back_to_prev_cache(monkeypatch):
    """1단 폴백 — 데이터 부족 시 직전일 캐시 재사용."""
    redis = _FakeRedis()
    today = date(2026, 4, 30)
    yesterday = today - timedelta(days=1)
    await redis.set(f"metrics:atr:ceil:{yesterday.isoformat()}", "0.072")

    async def _fake_compute(*a, **kw):
        return None, {"reason": "market_data_coverage_gap"}
    monkeypatch.setattr(ac, "compute_kospi200_atr_p80", _fake_compute)

    class _FakeSession:
        async def __aenter__(self): return AsyncMock()
        async def __aexit__(self, *a): return None

    sf = lambda: _FakeSession()  # noqa: E731
    result = await ac.run_atr_calibration(sf, redis, None, today=today)
    assert result["status"] == "fallback_prev_cache"
    assert redis._store[f"metrics:atr:ceil:{today.isoformat()}"] == "0.072"


@pytest.mark.asyncio
async def test_run_calibration_safe_mode_after_3_consecutive(monkeypatch):
    """3단 폴백 — fallback_count ≥ 3 시 안전모드 진입."""
    redis = _FakeRedis()
    await redis.set(ac.FALLBACK_COUNT_KEY, "2")  # 다음 INCR으로 3 도달
    today = date(2026, 4, 30)
    notifier = AsyncMock()

    async def _fake_compute(*a, **kw):
        return None, {"reason": "market_data_coverage_gap"}
    monkeypatch.setattr(ac, "compute_kospi200_atr_p80", _fake_compute)

    class _FakeSession:
        async def __aenter__(self): return AsyncMock()
        async def __aexit__(self, *a): return None

    sf = lambda: _FakeSession()  # noqa: E731
    result = await ac.run_atr_calibration(sf, redis, notifier, today=today)
    assert result["status"] == "safe_mode"
    assert ac.SAFE_MODE_KEY in redis._store
    assert notifier.send_safe_mode_alert.await_count == 1


@pytest.mark.asyncio
async def test_run_calibration_drift_warn(monkeypatch):
    """직전 5거래일 캐시 vs 오늘 P80 차 ≥0.015 시 drift warn 트리거."""
    redis = _FakeRedis()
    today = date(2026, 4, 30)
    # 직전 5일 캐시 0.04 ± 미세
    for i in range(1, 6):
        d = today - timedelta(days=i)
        await redis.set(f"metrics:atr:ceil:{d.isoformat()}", "0.040")

    async def _fake_compute(*a, **kw):
        return 0.060, {"sample_n": 40, "dist": {"p80": 0.060}}  # 차 ≥0.015
    monkeypatch.setattr(ac, "compute_kospi200_atr_p80", _fake_compute)

    notifier = AsyncMock()

    class _FakeSession:
        async def __aenter__(self): return AsyncMock()
        async def __aexit__(self, *a): return None

    sf = lambda: _FakeSession()  # noqa: E731
    result = await ac.run_atr_calibration(sf, redis, notifier, today=today)
    assert result["status"] == "ok"
    drift_key = f"{ac.DRIFT_WARN_PREFIX}:{today.isoformat()}"
    assert drift_key in redis._store
    notifier.send_drift_warn.assert_awaited_once()


@pytest.mark.asyncio
async def test_atr_ratio_for_rows_basic():
    rows = [
        {"high_price": 71000, "low_price": 69000, "close_price": 70000},
        {"high_price": 71500, "low_price": 69500, "close_price": 71000},
        {"high_price": 72000, "low_price": 70000, "close_price": 71500},
    ]
    ratio = ac._atr_ratio_for_rows(rows)
    assert ratio is not None and 0.0 < ratio < 0.05
