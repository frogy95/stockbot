"""5분봉 거래량 집계 모듈 테스트."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from modules.collector.volume_aggregator import (
    VolumeAggregator,
    calc_5min_slot,
    make_redis_key,
)


# ── FakeRedis (scan_keys 지원) ──────────────────────────────


class FakeRedisForVolume:
    """dict 기반 간이 Redis mock — VolumeAggregator 테스트용."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._store[key] = value

    async def scan_keys(self, pattern: str) -> list[str]:
        """패턴에 매칭되는 키 목록 반환. 단순 prefix 매칭."""
        prefix = pattern.replace("*", "")
        return [k for k in self._store if k.startswith(prefix)]


# ── calc_5min_slot 테스트 ────────────────────────────────────


def test_calc_5min_slot_0900():
    """09:00 → slot 0."""
    assert calc_5min_slot(9, 0) == 0


def test_calc_5min_slot_0935():
    """09:35 → slot 7 (elapsed=35, 35//5=7)."""
    assert calc_5min_slot(9, 35) == 7


def test_calc_5min_slot_1230():
    """12:30 → slot 42 (elapsed=210, 210//5=42)."""
    assert calc_5min_slot(12, 30) == 42


def test_calc_5min_slot_1530():
    """15:30 → slot 77 (clamped; 390//5=78 → max 77)."""
    assert calc_5min_slot(15, 30) == 77


def test_calc_5min_slot_before_market():
    """08:30 → slot 0 (clamped, 장전)."""
    assert calc_5min_slot(8, 30) == 0


def test_calc_5min_slot_after_market():
    """16:00 → slot 77 (clamped, 장후)."""
    assert calc_5min_slot(16, 0) == 77


# ── make_redis_key 테스트 ────────────────────────────────────


def test_make_redis_key():
    """키 형식: vol5m:{code}:{date}:{slot}."""
    assert make_redis_key("062040", "20260413", 7) == "vol5m:062040:20260413:7"


# ── aggregate_execution 테스트 ───────────────────────────────


@pytest.mark.asyncio
async def test_aggregate_execution_increments():
    """같은 슬롯 2회 호출 시 누적값 확인."""
    fake_redis = FakeRedisForVolume()
    agg = VolumeAggregator(fake_redis)

    with patch("modules.collector.volume_aggregator.datetime") as mock_dt:
        mock_now = mock_dt.now.return_value
        mock_now.strftime.return_value = "20260413"

        # 1차 매수 체결: 09:10, volume=500
        await agg.aggregate_execution("005930", "091000", 500, "2")
        # 2차 매도 체결: 09:12, volume=300 (같은 5분 슬롯)
        await agg.aggregate_execution("005930", "091200", 300, "1")

    key = "vol5m:005930:20260413:2"  # slot = calc_5min_slot(9, 10) = 2
    raw = await fake_redis.get(key)
    assert raw is not None
    data = json.loads(raw)

    assert data["buy_vol"] == 500
    assert data["sell_vol"] == 300
    assert data["total_vol"] == 800
    assert data["trade_count"] == 2


@pytest.mark.asyncio
async def test_aggregate_execution_buy_sell_split():
    """매수(sell_or_buy='2')와 매도(sell_or_buy='1') 분리 누적."""
    fake_redis = FakeRedisForVolume()
    agg = VolumeAggregator(fake_redis)

    with patch("modules.collector.volume_aggregator.datetime") as mock_dt:
        mock_now = mock_dt.now.return_value
        mock_now.strftime.return_value = "20260413"

        # 매수 체결
        await agg.aggregate_execution("005930", "093500", 1000, "2")
        # 매도 체결
        await agg.aggregate_execution("005930", "093700", 400, "1")

    key = "vol5m:005930:20260413:7"  # slot = calc_5min_slot(9, 35) = 7
    raw = await fake_redis.get(key)
    data = json.loads(raw)

    assert data["buy_vol"] == 1000  # 매수만
    assert data["sell_vol"] == 400  # 매도만
    assert data["total_vol"] == 1400  # 합계


# ── get_recent_slots 테스트 ──────────────────────────────────


@pytest.mark.asyncio
async def test_get_recent_slots_returns_data():
    """최근 12슬롯 조회 — 데이터 있는 슬롯과 빈 슬롯 혼재."""
    fake_redis = FakeRedisForVolume()
    agg = VolumeAggregator(fake_redis)

    # 슬롯 10, 11에 데이터 삽입
    slot10_data = {"buy_vol": 100, "sell_vol": 50, "total_vol": 150, "trade_count": 3}
    slot11_data = {"buy_vol": 200, "sell_vol": 80, "total_vol": 280, "trade_count": 5}
    await fake_redis.set("vol5m:005930:20260413:10", json.dumps(slot10_data))
    await fake_redis.set("vol5m:005930:20260413:11", json.dumps(slot11_data))

    with patch("modules.collector.volume_aggregator.datetime") as mock_dt:
        mock_now = mock_dt.now.return_value
        mock_now.strftime.return_value = "20260413"
        mock_now.hour = 9
        mock_now.minute = 58  # current_slot = calc_5min_slot(9, 58) = 11

        results = await agg.get_recent_slots("005930", count=12)

    assert len(results) == 12

    # 마지막 항목 = slot 11 (현재 슬롯)
    assert results[-1]["slot"] == 11
    assert results[-1]["buy_vol"] == 200
    assert results[-1]["total_vol"] == 280

    # slot 10 데이터 확인
    assert results[-2]["slot"] == 10
    assert results[-2]["buy_vol"] == 100

    # 빈 슬롯은 0으로 채워짐
    empty_slot = results[0]  # slot 0
    assert empty_slot["total_vol"] == 0
    assert empty_slot["trade_count"] == 0
