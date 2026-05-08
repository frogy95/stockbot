"""Bootstrap CI 하한 산출 + G-Bt2 게이트 테스트."""
import pytest


def test_bootstrap_ci_lower_low_signals():
    """`[0, 0, 1, 0, 2]` → 95% CI 하한 < 1 → evaluate_g_bt2=False."""
    from modules.backtest.bootstrap_ci import bootstrap_ci_lower, evaluate_g_bt2

    lower, upper = bootstrap_ci_lower([0, 0, 1, 0, 2], n_resamples=1000, seed=42)
    assert lower < 1.0
    assert evaluate_g_bt2([0, 0, 1, 0, 2]) is False


def test_bootstrap_ci_lower_high_signals():
    """`[2, 2, 3, 2, 3]` → 95% CI 하한 ≥ 1 → evaluate_g_bt2=True."""
    from modules.backtest.bootstrap_ci import bootstrap_ci_lower, evaluate_g_bt2

    lower, upper = bootstrap_ci_lower([2, 2, 3, 2, 3], n_resamples=1000, seed=42)
    assert lower >= 1.0
    assert evaluate_g_bt2([2, 2, 3, 2, 3]) is True


def test_bootstrap_ci_empty_list_returns_zero():
    """빈 리스트 → (0.0, 0.0) 반환."""
    from modules.backtest.bootstrap_ci import bootstrap_ci_lower

    result = bootstrap_ci_lower([])
    assert result == (0.0, 0.0)


def test_bootstrap_ci_default_n_resamples():
    """n_resamples 기본값 1000 사용 — kwargs override 가능 확인."""
    from modules.backtest.bootstrap_ci import bootstrap_ci_lower
    import inspect

    sig = inspect.signature(bootstrap_ci_lower)
    assert sig.parameters["n_resamples"].default == 1000

    # override도 동작해야 함
    lower, upper = bootstrap_ci_lower([1, 2, 3, 4, 5], n_resamples=500, seed=0)
    assert isinstance(lower, float)
    assert isinstance(upper, float)


def test_evaluate_g_bt2_threshold_customizable():
    """threshold 파라미터로 기준 조정 가능."""
    from modules.backtest.bootstrap_ci import evaluate_g_bt2

    # 평균 2짜리 데이터는 threshold=3에서 실패해야 함
    result_low = evaluate_g_bt2([2, 2, 2, 2, 2], threshold=3.0)
    assert result_low is False

    # threshold=1.0에서는 통과
    result_high = evaluate_g_bt2([2, 2, 2, 2, 2], threshold=1.0)
    assert result_high is True
