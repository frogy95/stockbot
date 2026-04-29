"""Phase 8.6 Sprint 2 Task 4 — tier 상관 분석 (phi coefficient + 조건부 P(B|A)).

병렬 OR 모드에서 tier 발생 패턴 독립성을 검증한다. 7일 누적:
  - phi ≤ 0.3 목표
  - P(B|A) ≤ 0.5 목표
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from itertools import combinations
from typing import Any


TIERS = ("gap_open", "prev_high", "prev_close")


def compute_pairwise_phi(daily_tier_signals: dict[date, set[str]]) -> dict[str, float]:
    """일별 tier 발생 0/1 시퀀스에서 phi coefficient 매트릭스.

    Args:
        daily_tier_signals: {날짜: 그날 통과한 tier 집합}.

    Returns:
        {"gap_open-prev_high": 0.12, ...} — 정렬된 pair key → phi.
    """
    days = sorted(daily_tier_signals.keys())
    n = len(days)
    if n == 0:
        return {}

    out: dict[str, float] = {}
    for a, b in combinations(TIERS, 2):
        n11 = sum(1 for d in days if a in daily_tier_signals[d] and b in daily_tier_signals[d])
        n10 = sum(1 for d in days if a in daily_tier_signals[d] and b not in daily_tier_signals[d])
        n01 = sum(1 for d in days if a not in daily_tier_signals[d] and b in daily_tier_signals[d])
        n00 = n - n11 - n10 - n01
        denom_sq = (n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00)
        if denom_sq <= 0:
            phi = 0.0
        else:
            phi = (n11 * n00 - n10 * n01) / math.sqrt(denom_sq)
        out[f"{a}-{b}"] = round(phi, 4)
    return out


def compute_conditional_pass_rate(
    daily_tier_signals: dict[date, set[str]]
) -> dict[str, float]:
    """조건부 통과율 P(B|A) — A 통과한 날 중 B도 통과한 비율.

    Returns:
        {"gap_open|prev_high": P(prev_high|gap_open), ...}
    """
    out: dict[str, float] = {}
    for a in TIERS:
        for b in TIERS:
            if a == b:
                continue
            a_days = [d for d, ts in daily_tier_signals.items() if a in ts]
            if not a_days:
                out[f"{a}|{b}"] = 0.0
                continue
            both = sum(1 for d in a_days if b in daily_tier_signals[d])
            out[f"{a}|{b}"] = round(both / len(a_days), 4)
    return out


def evaluate_correlation_window(
    daily_tier_signals: dict[date, set[str]],
    *,
    phi_threshold: float = 0.3,
    cond_threshold: float = 0.5,
) -> dict[str, Any]:
    """7일 윈도우에서 phi/조건부 임계 통과 여부 판정."""
    phi = compute_pairwise_phi(daily_tier_signals)
    cond = compute_conditional_pass_rate(daily_tier_signals)
    max_phi = max((abs(v) for v in phi.values()), default=0.0)
    max_cond = max(cond.values(), default=0.0)
    return {
        "phi": phi,
        "cond_prob": cond,
        "max_phi": round(max_phi, 4),
        "max_cond": round(max_cond, 4),
        "phi_threshold": phi_threshold,
        "cond_threshold": cond_threshold,
        "ok": max_phi <= phi_threshold and max_cond <= cond_threshold,
        "window_days": len(daily_tier_signals),
    }
