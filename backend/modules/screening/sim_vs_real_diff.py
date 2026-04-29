"""Phase 8.6 Sprint 2 Task 4 — 시뮬-실측 통과율 절대차 메트릭.

shadow tier 카운터(예상 통과율) vs 실제 신호 통과율 절대차를 산출, 0.15 이상이면 알림.
Sprint 4 walk-forward 이전에 분기 D 회귀 1주 내 감지.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

DIFF_KEY_PREFIX = "metrics:quant:sim_vs_real_diff"
DEFAULT_THRESHOLD = 0.15


async def _get_int(redis: Any, key: str) -> int:
    if redis is None:
        return 0
    try:
        v = await redis.get(key)
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0
    except Exception:  # noqa: BLE001
        return 0


async def compute_sim_vs_real_diff(
    redis: Any,
    *,
    target_date: date,
    real_signal_count: int,
    real_eligible_count: int,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """shadow vs real 통과율 절대차 산출.

    shadow:tier:{name}:passed:{date}, shadow:tier:{name}:failed:{date} 누적치에서
    pass_rate(shadow) = sum(passed) / (sum(passed)+sum(failed))
    pass_rate(real)   = real_signal_count / real_eligible_count
    diff = abs(pass_rate(shadow) - pass_rate(real))
    """
    today_iso = target_date.isoformat()
    shadow_passed = 0
    shadow_failed = 0
    for tier in ("gap_open", "prev_high", "prev_close"):
        shadow_passed += await _get_int(redis, f"shadow:tier:{tier}:passed:{today_iso}")
        shadow_failed += await _get_int(redis, f"shadow:tier:{tier}:failed:{today_iso}")
    shadow_total = shadow_passed + shadow_failed
    shadow_rate = (shadow_passed / shadow_total) if shadow_total > 0 else 0.0
    real_rate = (real_signal_count / real_eligible_count) if real_eligible_count > 0 else 0.0
    diff = abs(shadow_rate - real_rate)
    if redis is not None:
        try:
            await redis.set(f"{DIFF_KEY_PREFIX}:{today_iso}", f"{diff:.4f}")
        except Exception:  # noqa: BLE001
            logger.warning("sim_vs_real_diff Redis 저장 실패", exc_info=True)
    return {
        "date": today_iso,
        "shadow_pass_rate": round(shadow_rate, 4),
        "real_pass_rate": round(real_rate, 4),
        "diff": round(diff, 4),
        "threshold": threshold,
        "exceeded": diff >= threshold,
        "shadow_total": shadow_total,
        "real_eligible": real_eligible_count,
    }


async def run_daily_check(
    redis: Any,
    notifier: Any,
    *,
    target_date: date,
    real_signal_count: int,
    real_eligible_count: int,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """일별 시뮬-실측 절대차 체크 + 임계 초과 시 텔레그램 알림."""
    result = await compute_sim_vs_real_diff(
        redis,
        target_date=target_date,
        real_signal_count=real_signal_count,
        real_eligible_count=real_eligible_count,
        threshold=threshold,
    )
    if result["exceeded"] and notifier is not None and hasattr(notifier, "send_sim_real_diff_alert"):
        try:
            await notifier.send_sim_real_diff_alert(
                date_iso=result["date"], diff=result["diff"], threshold=threshold
            )
        except Exception:  # noqa: BLE001
            logger.warning("sim-real diff 알림 실패", exc_info=True)
    return result
