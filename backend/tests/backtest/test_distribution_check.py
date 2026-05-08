"""KS 검정 + 카이제곱 검정 + trigger_rebuild_alert 테스트."""
import pytest
import numpy as np
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# ks_test
# ---------------------------------------------------------------------------

def test_ks_same_distribution_no_rebuild():
    """동일 분포 두 표본 → KS p ≥ 0.05 → rebuild_required=False."""
    from modules.backtest.distribution_check import ks_test

    rng = np.random.default_rng(42)
    a = rng.normal(0, 1, 100).tolist()
    b = rng.normal(0, 1, 100).tolist()
    result = ks_test(a, b)

    assert result["pvalue"] is not None
    assert result["pvalue"] >= 0.05
    assert result["rebuild_required"] is False


def test_ks_different_distribution_rebuild_required():
    """명백히 다른 분포 (mean=0 vs mean=5) → KS p < 0.05 → rebuild_required=True."""
    from modules.backtest.distribution_check import ks_test

    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 200).tolist()
    b = rng.normal(5, 1, 200).tolist()
    result = ks_test(a, b)

    assert result["pvalue"] is not None
    assert result["pvalue"] < 0.05
    assert result["rebuild_required"] is True


def test_ks_empty_inputs():
    """빈 리스트 입력 → statistic/pvalue None, rebuild_required=False."""
    from modules.backtest.distribution_check import ks_test

    result = ks_test([], [])
    assert result["statistic"] is None
    assert result["pvalue"] is None
    assert result["rebuild_required"] is False


# ---------------------------------------------------------------------------
# chi_square_test
# ---------------------------------------------------------------------------

def test_chi_square_matching_no_rebuild():
    """일치하는 observed/expected → p ≥ 0.05 → rebuild_required=False."""
    from modules.backtest.distribution_check import chi_square_test

    # observed와 expected가 거의 같으면 귀무가설 채택
    observed = [10, 20, 30, 40]
    expected = [10.0, 20.0, 30.0, 40.0]
    result = chi_square_test(observed, expected)

    assert result["pvalue"] is not None
    assert result["pvalue"] >= 0.05
    assert result["rebuild_required"] is False


def test_chi_square_different_rebuild_required():
    """명백히 다른 observed/expected → p < 0.05 → rebuild_required=True."""
    from modules.backtest.distribution_check import chi_square_test

    observed = [1, 1, 1, 97]
    expected = [25.0, 25.0, 25.0, 25.0]
    result = chi_square_test(observed, expected)

    assert result["pvalue"] is not None
    assert result["pvalue"] < 0.05
    assert result["rebuild_required"] is True


# ---------------------------------------------------------------------------
# trigger_rebuild_alert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_rebuild_alert_calls_notifier_and_sets_redis():
    """rebuild_required=True 시 notifier.send 호출 + Redis 플래그 set 검증."""
    from modules.backtest.distribution_check import trigger_rebuild_alert

    mock_notifier = AsyncMock()
    mock_notifier.send = AsyncMock()

    ks_result = {"pvalue": 0.01, "rebuild_required": True}
    chi_result = {"pvalue": 0.5, "rebuild_required": False}

    with patch("modules.backtest.distribution_check.redis_client") as mock_rc:
        mock_rc.set = AsyncMock()
        await trigger_rebuild_alert(mock_notifier, ks_result, chi_result)

    mock_notifier.send.assert_called_once()
    call_args = mock_notifier.send.call_args[0][0]
    assert "KS" in call_args or "분포" in call_args

    mock_rc.set.assert_called_once_with(
        "metrics:backtest:rebuild_required", "true", ttl=7 * 24 * 3600
    )


@pytest.mark.asyncio
async def test_trigger_rebuild_alert_no_action_when_not_required():
    """rebuild_required=False 시 notifier/Redis 호출 없음."""
    from modules.backtest.distribution_check import trigger_rebuild_alert

    mock_notifier = AsyncMock()

    ks_result = {"pvalue": 0.5, "rebuild_required": False}
    chi_result = {"pvalue": 0.8, "rebuild_required": False}

    with patch("modules.backtest.distribution_check.redis_client") as mock_rc:
        mock_rc.set = AsyncMock()
        await trigger_rebuild_alert(mock_notifier, ks_result, chi_result)

    mock_notifier.send.assert_not_called()
    mock_rc.set.assert_not_called()
