"""Phase 8.6 Sprint 3 Task 2 — VolumeSurgeStrategy 단위 테스트.

13+ 케이스로 거래량 급등 전략의 모든 분기를 검증한다.
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from modules.collector.volume_aggregator import calc_5min_slot, make_redis_key

_KST = ZoneInfo("Asia/Seoul")
_STOCK = "005930"


def _dt(h: int, m: int) -> datetime:
    """KST datetime 헬퍼 — 평일 (2026-05-07 목)."""
    return datetime(2026, 5, 7, h, m, 0, tzinfo=_KST)


def _candidate(**overrides) -> dict:
    base = {
        "stock_code": _STOCK,
        "current_price": 10600,  # +0.95% > 0.5% 임계
        "prev_close": 10500,
    }
    base.update(overrides)
    return base


class _FakeRedis:
    """단순 dict 기반 Redis fake — get만 사용한다."""

    def __init__(self, data: dict[str, str | None] | None = None):
        self._data: dict[str, str | None] = dict(data or {})

    async def get(self, key: str):
        return self._data.get(key)


def _build_redis(
    *,
    now_kst: datetime,
    bid: int = 200,
    ask: int = 80,
    bars: list[dict] | None = None,
    orderbook_present: bool = True,
    vol5m_present: bool = True,
) -> _FakeRedis:
    """주어진 슬롯 정보로 Redis fake를 구성한다."""
    data: dict[str, str | None] = {}
    if orderbook_present:
        data[f"realtime:{_STOCK}:orderbook"] = json.dumps(
            {
                "stock_code": _STOCK,
                "total_bid_volume": bid,
                "total_ask_volume": ask,
            }
        )
    if vol5m_present and bars is not None:
        date_str = now_kst.strftime("%Y%m%d")
        current_slot = calc_5min_slot(now_kst.hour, now_kst.minute)
        for i, b in enumerate(bars):
            slot = current_slot - 4 + i
            if slot < 0:
                continue
            data[make_redis_key(_STOCK, date_str, slot)] = json.dumps(b)
    return _FakeRedis(data)


def _surge_bars() -> list[dict]:
    """vol_ratio = 10000 / 1500 ≈ 6.67 → 임계 5.0 통과."""
    return [
        {"buy_vol": 800, "sell_vol": 700, "total_vol": 1500},
        {"buy_vol": 800, "sell_vol": 700, "total_vol": 1500},
        {"buy_vol": 800, "sell_vol": 700, "total_vol": 1500},
        {"buy_vol": 800, "sell_vol": 700, "total_vol": 1500},
        {"buy_vol": 6000, "sell_vol": 4000, "total_vol": 10000},
    ]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_emits_signal():
    """3대 조건 충족 + 09:35 → 신호 발행."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 35)
    redis = _build_redis(now_kst=now, bid=200, ask=80, bars=_surge_bars())
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result is not None
    assert result.get("rejected") is not True
    assert result["tier"] == "volume_surge"
    assert result["matched_tiers"] == ["volume_surge"]
    assert result["dry_run"] is True  # 기본 VOLUME_SURGE_DRY_RUN=True
    assert result["vol_ratio"] >= 5.0
    assert result["bid_ask_ratio"] >= 2.0
    assert result["price_change"] > 0
    assert 0 <= result["confidence"] <= 1


# ---------------------------------------------------------------------------
# Reject branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_when_vol_ratio_below_threshold():
    """vol_ratio < 5.0 → reject vol_surge_ratio."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 35)
    bars = [
        {"total_vol": 1500}, {"total_vol": 1500},
        {"total_vol": 1500}, {"total_vol": 1500},
        {"total_vol": 4000},  # 4000/1500 ≈ 2.67 < 5.0
    ]
    redis = _build_redis(now_kst=now, bars=bars)
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    assert result["reason"] == "vol_surge_ratio"


@pytest.mark.asyncio
async def test_reject_when_bid_ask_ratio_below_threshold():
    """bid/ask < 2.0 → reject vol_surge_orderbook."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 35)
    redis = _build_redis(now_kst=now, bid=100, ask=80, bars=_surge_bars())
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    assert result["reason"] == "vol_surge_orderbook"


@pytest.mark.asyncio
async def test_reject_when_price_below_threshold():
    """price/prev_close < 1.005 → reject vol_surge_price."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 35)
    redis = _build_redis(now_kst=now, bars=_surge_bars())
    s = VolumeSurgeStrategy(redis_client=redis)

    # 10520 / 10500 ≈ 1.0019 < 1.005
    result = await s.evaluate(
        _candidate(current_price=10520, prev_close=10500), now_kst=now
    )
    assert result["rejected"] is True
    assert result["reason"] == "vol_surge_price"


@pytest.mark.asyncio
async def test_reject_before_active_window_0925():
    """09:25 (활성 전) → reject vol_surge_time."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 25)
    redis = _build_redis(now_kst=now, bars=_surge_bars())
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    # 09:25는 morning_lockout 시간 외 (09:10 이후) → vol_surge_time 으로 reject
    assert result["reason"] == "vol_surge_time"


@pytest.mark.asyncio
async def test_reject_after_active_window_1401():
    """14:01 (활성 종료, 14:30 이전) → reject vol_surge_time."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(14, 1)
    redis = _build_redis(now_kst=now, bars=_surge_bars())
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    assert result["reason"] == "vol_surge_time"


@pytest.mark.asyncio
async def test_reject_when_orderbook_missing():
    """호가창 Redis 키 부재 → reject vol_surge_orderbook_missing."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 35)
    redis = _build_redis(now_kst=now, bars=_surge_bars(), orderbook_present=False)
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    assert result["reason"] == "vol_surge_orderbook_missing"


@pytest.mark.asyncio
async def test_reject_when_vol5m_missing():
    """vol5m 키 부재 → reject vol_surge_vol5m_missing."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 35)
    # bars=None → vol5m 미적재
    redis = _build_redis(now_kst=now, bars=None, vol5m_present=False)
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    assert result["reason"] == "vol_surge_vol5m_missing"


@pytest.mark.asyncio
async def test_reject_when_avg4_zero_avoids_zerodivision():
    """직전 4봉 평균 0 → reject vol_surge_vol5m_zero (ZeroDivision 방지)."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 35)
    bars = [
        {"total_vol": 0}, {"total_vol": 0},
        {"total_vol": 0}, {"total_vol": 0},
        {"total_vol": 5000},  # 최신 슬롯에만 데이터
    ]
    redis = _build_redis(now_kst=now, bars=bars)
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    assert result["reason"] == "vol_surge_vol5m_zero"


@pytest.mark.asyncio
async def test_reject_when_volume_surge_disabled():
    """VOLUME_SURGE_ENABLED=False → reject vol_surge_disabled."""
    import modules.trading.strategies.volume_surge as vs_module

    now = _dt(9, 35)
    redis = _build_redis(now_kst=now, bars=_surge_bars())
    s = vs_module.VolumeSurgeStrategy(redis_client=redis)

    with patch.object(vs_module, "settings") as mock_s:
        mock_s.VOLUME_SURGE_ENABLED = False
        result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    assert result["reason"] == "vol_surge_disabled"


@pytest.mark.asyncio
async def test_dry_run_meta_reflects_setting_true():
    """VOLUME_SURGE_DRY_RUN=True 상태(기본) → dry_run=True 메타 + tier=volume_surge."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 35)
    redis = _build_redis(now_kst=now, bars=_surge_bars())
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["dry_run"] is True
    assert result["tier"] == "volume_surge"


@pytest.mark.asyncio
async def test_dry_run_meta_reflects_setting_false():
    """VOLUME_SURGE_DRY_RUN=False 시 dry_run=False로 발행 (실거래 모드)."""
    import modules.trading.strategies.volume_surge as vs_module

    now = _dt(9, 35)
    redis = _build_redis(now_kst=now, bars=_surge_bars())
    s = vs_module.VolumeSurgeStrategy(redis_client=redis)

    with patch.object(vs_module, "settings") as mock_s:
        mock_s.VOLUME_SURGE_ENABLED = True
        mock_s.VOLUME_SURGE_DRY_RUN = False
        mock_s.VOLUME_SURGE_VOL_RATIO = 5.0
        mock_s.VOLUME_SURGE_BID_ASK_RATIO = 2.0
        mock_s.VOLUME_SURGE_PRICE_THRESHOLD = 0.005
        # should_block_entry 내부에서 settings.TIME_FILTER_ENABLED 참조
        # (vs_module.settings를 patch하면 _time_filter는 영향 없음)
        result = await s.evaluate(_candidate(), now_kst=now)
    assert result.get("rejected") is not True, f"unexpected reject: {result}"
    assert result["dry_run"] is False


@pytest.mark.asyncio
async def test_time_filter_integration_at_1430_blocks():
    """14:30 — _time_filter 본 가드(afternoon_lockout) 위임 → reject time_filter."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(14, 30)
    redis = _build_redis(now_kst=now, bars=_surge_bars())
    s = VolumeSurgeStrategy(redis_client=redis)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    assert result["reason"] == "time_filter"


@pytest.mark.asyncio
async def test_no_redis_returns_orderbook_missing():
    """redis_client=None → orderbook_missing reject (graceful)."""
    from modules.trading.strategies.volume_surge import VolumeSurgeStrategy

    now = _dt(9, 35)
    s = VolumeSurgeStrategy(redis_client=None)

    result = await s.evaluate(_candidate(), now_kst=now)
    assert result["rejected"] is True
    assert result["reason"] == "vol_surge_orderbook_missing"
