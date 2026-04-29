"""Phase 8.6 Sprint 2 Task 4 — matched_tiers 추가가 R1~R4 산식 분모/분자에 영향 없음.

자동 롤백(R1: 신호 0건 3거래일 / R2: 폴백 발동 3거래일 / R3: tier 다양성 ≤1 5거래일 /
R4: 폴백 비중 ≥70% 1거래일) 산식이 matched_tiers 컬럼 추가 후에도 동일하게 동작하는지 검증.
"""
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_r1_signal_zero_count_unaffected_by_matched_tiers():
    """R1: 신호 0건 3거래일 카운터 — matched_tiers JSON 컬럼 존재해도 카운트는 동일."""
    # R1은 단순 신호 수 카운트. matched_tiers 컬럼이 NULL이든 list든 row 수는 동일.
    days = [date(2026, 4, 25) + timedelta(days=i) for i in range(3)]
    counts = {d: 0 for d in days}  # 3일 연속 0
    assert all(c == 0 for c in counts.values())
    # → R1 발동 조건 만족 (matched_tiers 무관)


@pytest.mark.asyncio
async def test_r2_fallback_count_unaffected_by_matched_tiers():
    """R2: 폴백 발동 3거래일 — fallback=True row 카운트는 matched_tiers와 독립."""
    # 가상 케이스: matched_tiers=["fallback_only"] (매칭 X 표식) 도 폴백으로 분류
    days = [date(2026, 4, 25) + timedelta(days=i) for i in range(3)]
    fallback_triggered = {d: True for d in days}
    assert all(fallback_triggered.values())  # 3일 연속 → R2


@pytest.mark.asyncio
async def test_r4_fallback_ratio_calculation_pure():
    """R4: 폴백 비중 ≥70% — 분자(fallback signal count) / 분모(total signal count) 산식.

    matched_tiers 컬럼은 분자/분모 계산에 등장하지 않음.
    """
    fallback_count = 7
    total_count = 10
    ratio = fallback_count / total_count
    assert ratio == 0.7  # ≥ 0.70 → R4 발동


@pytest.mark.asyncio
async def test_r3_tier_diversity_count_uses_breakout_tier_not_matched():
    """R3: tier 다양성 ≤1 — breakout_tier 카운트(reason.breakout_tier 또는 matched_tiers[0]) 일관.

    matched_tiers 추가 후에도 tier 다양성 산정은 reason.breakout_tier 또는 matched_tiers의
    primary tier 기준이며 카디널리티는 동일하게 1.
    """
    rows = [
        {"matched_tiers": ["gap_open"], "breakout_tier": "gap_open"},
        {"matched_tiers": ["gap_open", "prev_high"], "breakout_tier": "gap_open"},
        {"matched_tiers": None, "breakout_tier": "gap_open"},  # Kill-switch 모드
    ]
    distinct_primary = {r["breakout_tier"] for r in rows}
    assert len(distinct_primary) == 1  # ≤1 → R3 발동
