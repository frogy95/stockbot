"""Phase 8.6 Sprint 2 Task 4 — tier phi 상관 + 조건부 통과율 테스트."""
from datetime import date, timedelta

import pytest

from modules.screening.tier_correlation import (
    compute_conditional_pass_rate,
    compute_pairwise_phi,
    evaluate_correlation_window,
)


def _days(n: int) -> list[date]:
    base = date(2026, 4, 23)
    return [base + timedelta(days=i) for i in range(n)]


def test_phi_low_when_mixed_overlap():
    """tier가 독립적으로 자주 함께 발생/단독 발생 혼재 → phi 약함."""
    days = _days(8)
    signals = {
        days[0]: {"gap_open", "prev_high"},
        days[1]: {"gap_open"},
        days[2]: {"prev_high"},
        days[3]: set(),
        days[4]: {"gap_open", "prev_high"},
        days[5]: {"prev_close"},
        days[6]: {"gap_open"},
        days[7]: {"prev_high"},
    }
    phi = compute_pairwise_phi(signals)
    # 절대값이 1보다 작은 정상 범위 + 독립성에 가까움
    assert all(-1.0 <= v <= 1.0 for v in phi.values())
    assert abs(phi["gap_open-prev_high"]) <= 0.6


def test_phi_high_when_always_co_occurring():
    """gap_open + prev_high가 매일 같이 발생 → phi 가까이 1."""
    days = _days(7)
    signals = {d: {"gap_open", "prev_high"} for d in days}
    phi = compute_pairwise_phi(signals)
    # 동일 패턴 → 분산 0 → denom 0 → phi=0 fallback OR ≈ 1 if 일부 변동
    # 변동 추가
    signals[days[0]] = set()
    phi = compute_pairwise_phi(signals)
    assert phi["gap_open-prev_high"] > 0.5


def test_conditional_pass_rate_basic():
    """gap_open 발생일 5일 중 prev_high 동시 발생 3일 → P(prev_high|gap_open)=0.6."""
    days = _days(5)
    signals = {
        days[0]: {"gap_open", "prev_high"},
        days[1]: {"gap_open", "prev_high"},
        days[2]: {"gap_open", "prev_high"},
        days[3]: {"gap_open"},
        days[4]: {"gap_open"},
    }
    cond = compute_conditional_pass_rate(signals)
    assert cond["gap_open|prev_high"] == pytest.approx(0.6)


def test_conditional_pass_rate_handles_zero_denominator():
    """A 발생 0일 → P(B|A)=0 (분모 0 회피)."""
    signals = {date(2026, 4, 23): {"prev_high"}}
    cond = compute_conditional_pass_rate(signals)
    assert cond["gap_open|prev_high"] == 0.0


def test_evaluate_window_returns_metrics():
    """7일 윈도우 평가 — phi/cond/threshold 정상 반환."""
    days = _days(7)
    signals = {
        days[0]: {"gap_open", "prev_high"},
        days[1]: {"gap_open"},
        days[2]: {"prev_high"},
        days[3]: {"gap_open", "prev_high"},
        days[4]: {"prev_close"},
        days[5]: {"gap_open"},
        days[6]: {"prev_high"},
    }
    out = evaluate_correlation_window(signals)
    assert out["window_days"] == 7
    assert "phi" in out and "cond_prob" in out
    assert out["phi_threshold"] == 0.3
    assert out["cond_threshold"] == 0.5
    assert isinstance(out["ok"], bool)
