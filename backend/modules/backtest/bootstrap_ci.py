"""Bootstrap 95% CI 하한 산출 — G-Bt2 LIVE 토글 게이트 입력."""
import numpy as np


def bootstrap_ci_lower(
    daily_signal_counts: list[int],
    n_resamples: int = 1000,
    ci: float = 0.95,
    seed: int | None = None,
) -> tuple[float, float]:
    """일별 신호 수 시계열에서 평균의 95% CI 하한/상한 반환."""
    if not daily_signal_counts:
        return (0.0, 0.0)
    arr = np.asarray(daily_signal_counts, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.array([
        rng.choice(arr, size=len(arr), replace=True).mean()
        for _ in range(n_resamples)
    ])
    alpha = (1 - ci) / 2
    return (
        float(np.percentile(means, alpha * 100)),
        float(np.percentile(means, (1 - alpha) * 100)),
    )


def evaluate_g_bt2(daily_signal_counts: list[int], threshold: float = 1.0) -> bool:
    """G-Bt2: Bootstrap CI 하한 ≥ threshold(=1.0) → PASS."""
    lower, _ = bootstrap_ci_lower(daily_signal_counts)
    return lower >= threshold
