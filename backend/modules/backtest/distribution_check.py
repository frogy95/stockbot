"""KS 2-sample + 카이제곱 검정. p<0.05 시 시뮬 재구축 알림 트리거."""
import logging
from typing import Any

from scipy import stats

from core.redis import redis_client

logger = logging.getLogger(__name__)


def ks_test(simulated: list[float], actual: list[float]) -> dict:
    """KS 2-sample 검정. rebuild_required = pvalue < 0.05."""
    if not simulated or not actual:
        return {"statistic": None, "pvalue": None, "rebuild_required": False}
    result = stats.ks_2samp(simulated, actual)
    return {
        "statistic": float(result.statistic),
        "pvalue": float(result.pvalue),
        "rebuild_required": bool(result.pvalue < 0.05),
    }


def chi_square_test(observed: list[int], expected: list[float]) -> dict:
    """카이제곱 적합도 검정. expected 합이 observed 합과 일치해야 함."""
    if not observed or not expected or len(observed) != len(expected):
        return {"statistic": None, "pvalue": None, "rebuild_required": False}
    result = stats.chisquare(observed, expected)
    return {
        "statistic": float(result.statistic),
        "pvalue": float(result.pvalue),
        "rebuild_required": bool(result.pvalue < 0.05),
    }


async def trigger_rebuild_alert(notifier: Any, ks_result: dict, chi_result: dict) -> None:
    """p<0.05 시 텔레그램 알림 + Redis 플래그 set.

    notifier는 dependency-injected (테스트에서 mock 가능).
    """
    if not (ks_result.get("rebuild_required") or chi_result.get("rebuild_required")):
        return
    msg = (
        f"⚠️ 시뮬-실측 분포 괴리 감지\n"
        f"KS p={ks_result.get('pvalue')}, 카이제곱 p={chi_result.get('pvalue')}"
    )
    if notifier is not None:
        try:
            await notifier.send(msg)
        except Exception:
            logger.warning("telegram send failed", exc_info=True)
    try:
        await redis_client.set(
            "metrics:backtest:rebuild_required", "true", ttl=7 * 24 * 3600
        )
    except Exception:
        logger.warning("redis set failed", exc_info=True)
