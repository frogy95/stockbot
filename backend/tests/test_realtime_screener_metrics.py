"""Phase 8.5 Sprint 1 — Task 3: 2차 스크리닝 score 히스토그램 기록 검증."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core.config import settings
from core.metrics_keys import score_histogram_key
from modules.screening.realtime_screener import RealtimeScreener


class FakeRedis:
    def __init__(self):
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int:
        self.counters[key] = self.counters.get(key, 0) + amount
        if ttl is not None and key not in self.ttls:
            self.ttls[key] = ttl
        return self.counters[key]


@pytest.mark.asyncio
async def test_record_score_histogram_buckets_correctly():
    fake = FakeRedis()
    screener = RealtimeScreener(redis_client=fake)

    scored = [
        {"stock_code": "A", "score": 82.5},
        {"stock_code": "B", "score": 40.0},
        {"stock_code": "C", "score": 75.0},
    ]
    await screener._record_score_histogram(scored)

    today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date().isoformat()
    assert fake.counters[score_histogram_key(today, ">=75")] == 2
    assert fake.counters[score_histogram_key(today, "80-90")] == 1
    assert fake.counters[score_histogram_key(today, "70-80")] == 1
    assert fake.counters[score_histogram_key(today, "40-50")] == 1
    # TTL 1회 설정 (최초 생성 시)
    assert all(ttl == 86400 * 7 for ttl in fake.ttls.values())


@pytest.mark.asyncio
async def test_record_score_histogram_empty_list_no_redis_call():
    fake = FakeRedis()
    screener = RealtimeScreener(redis_client=fake)
    await screener._record_score_histogram([])
    assert fake.counters == {}


@pytest.mark.asyncio
async def test_record_score_histogram_no_redis_silent_skip():
    screener = RealtimeScreener(redis_client=None)
    # 예외 없이 반환해야 함
    await screener._record_score_histogram([{"score": 80.0}])
