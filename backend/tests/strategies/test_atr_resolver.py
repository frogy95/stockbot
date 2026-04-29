"""Phase 8.6 Sprint 2 Task 1 — `_resolve_atr_ceil` 단위 테스트.

핵심 규칙:
1. ATR < ATR_FLOOR(0.025) → 모든 tier(gap_open 포함) None 반환
2. is_fallback=True → ATR_CEIL_FALLBACK(0.05) 정적 사용
3. tier=="gap_open" → ATR_CEIL_HARD(0.08) 절대 한계 (Sprint v1 우회 X)
4. tier IN ("prev_high","prev_close") + Redis `metrics:atr:ceil:{date}` → 그 값 (HARD 캡)
5. ATR_CALIBRATION_ENABLED=false → HARD 정적
6. 동적 상한이 HARD 초과 시 HARD로 캡
"""
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from modules.trading.strategy import MarketSnapshot
from modules.trading.strategies.momentum_breakout import _resolve_atr_ceil

_KST = ZoneInfo("Asia/Seoul")
_NOW = datetime(2026, 4, 30, 10, 0, tzinfo=_KST)


class _FakeRedis:
    def __init__(self, store=None):
        self._store = store or {}

    async def get(self, key):
        return self._store.get(key)


def _snap(*, atr_target: float, current_price: int = 70000) -> MarketSnapshot:
    """recent_highs/lows/closes를 atr_target × current_price 비율 ATR이 나오도록 구성.

    `calc_volatility_factor`는 TR = max(high-low, |high-prev_close|, |low-prev_close|)을
    평균하므로, close가 동일하면 TR ≈ high-low. atr_ratio = TR/current_price 이므로
    high-low = atr_target × current_price 가 되도록 ±atr_target/2 로 잡는다.
    """
    half = current_price * atr_target / 2.0
    high = int(current_price + half)
    low = int(current_price - half)
    return MarketSnapshot(
        stock_code="005930",
        stock_name="삼성전자",
        stock_type="STOCK",
        current_price=current_price,
        open_price=current_price,
        high=high,
        low=low,
        prev_close=current_price - 1000,
        prev_high=high - 100,
        volume=10000000,
        prev_volume=10000000,
        change_rate=1.0,
        trade_strength=120.0,
        total_bid_volume=500000,
        total_ask_volume=500000,
        recent_highs=[high] * 14,
        recent_lows=[low] * 14,
        recent_closes=[current_price] * 14,
    )


@pytest.mark.asyncio
async def test_below_floor_returns_none_even_for_gap_open():
    """ATR=0.020 < ATR_FLOOR(0.025) — gap_open이라도 None 반환 (하한 우선 적용)."""
    snap = _snap(atr_target=0.020)
    redis = _FakeRedis()
    result = await _resolve_atr_ceil(snap, "gap_open", redis, is_fallback=False, now_kst=_NOW)
    assert result is None


@pytest.mark.asyncio
async def test_fallback_returns_static_ceil():
    """is_fallback=True — 0.05 정적 (동적 미적용)."""
    snap = _snap(atr_target=0.04)
    redis = _FakeRedis({"metrics:atr:ceil:2026-04-30": "0.072"})
    result = await _resolve_atr_ceil(snap, "prev_high", redis, is_fallback=True, now_kst=_NOW)
    assert result == pytest.approx(0.05)


@pytest.mark.asyncio
async def test_gap_open_uses_hard_ceil_not_dynamic():
    """tier=gap_open + 동적 상한 0.072 존재해도 HARD(0.08) 반환 (절대 한계)."""
    snap = _snap(atr_target=0.04)
    redis = _FakeRedis({"metrics:atr:ceil:2026-04-30": "0.072"})
    result = await _resolve_atr_ceil(snap, "gap_open", redis, is_fallback=False, now_kst=_NOW)
    assert result == pytest.approx(0.08)


@pytest.mark.asyncio
async def test_prev_high_uses_dynamic_ceil_when_present():
    """tier=prev_high + Redis 동적 상한 0.072 → 그 값 반환."""
    snap = _snap(atr_target=0.04)
    redis = _FakeRedis({"metrics:atr:ceil:2026-04-30": "0.072"})
    result = await _resolve_atr_ceil(snap, "prev_high", redis, is_fallback=False, now_kst=_NOW)
    assert result == pytest.approx(0.072)


@pytest.mark.asyncio
async def test_prev_high_falls_back_to_hard_when_redis_missing():
    """Redis 키 부재 → HARD(0.08) 폴백."""
    snap = _snap(atr_target=0.04)
    redis = _FakeRedis()
    result = await _resolve_atr_ceil(snap, "prev_high", redis, is_fallback=False, now_kst=_NOW)
    assert result == pytest.approx(0.08)


@pytest.mark.asyncio
async def test_calibration_disabled_uses_hard():
    """ATR_CALIBRATION_ENABLED=False → 동적 키 무시, HARD 사용."""
    snap = _snap(atr_target=0.04)
    redis = _FakeRedis({"metrics:atr:ceil:2026-04-30": "0.072"})
    with patch(
        "modules.trading.strategies.momentum_breakout.settings.ATR_CALIBRATION_ENABLED",
        False,
    ):
        result = await _resolve_atr_ceil(
            snap, "prev_high", redis, is_fallback=False, now_kst=_NOW
        )
    assert result == pytest.approx(0.08)


@pytest.mark.asyncio
async def test_dynamic_ceil_capped_by_hard():
    """동적 상한 0.085 (HARD 초과) → HARD(0.08)로 캡."""
    snap = _snap(atr_target=0.04)
    redis = _FakeRedis({"metrics:atr:ceil:2026-04-30": "0.085"})
    result = await _resolve_atr_ceil(snap, "prev_close", redis, is_fallback=False, now_kst=_NOW)
    assert result == pytest.approx(0.08)


@pytest.mark.asyncio
async def test_floor_applied_for_fallback_too():
    """폴백 종목도 ATR_FLOOR 미달 시 None — 모든 tier 공통 하한."""
    snap = _snap(atr_target=0.020)
    redis = _FakeRedis()
    result = await _resolve_atr_ceil(snap, "prev_high", redis, is_fallback=True, now_kst=_NOW)
    assert result is None
