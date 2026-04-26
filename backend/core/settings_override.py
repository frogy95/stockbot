"""Redis settings override 통합 유틸 (Phase 8.5 Sprint 2.5).

Sprint 2 Task 5에서 정의한 `settings:override:*` 규약을 단일 진입점으로 통합.
각 호출부(momentum_breakout, realtime_screener)가 동일한 parsing 로직을 공유한다.
"""
from typing import TypeVar, Callable
import logging

from core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")
OVERRIDE_PREFIX = "settings:override:"


async def resolve_override(
    redis_client,
    key: str,
    default: T,
    *,
    cast: Callable[[str], T] = str,
) -> T:
    """Redis `settings:override:{key}` → default 순으로 값 해석.

    `SETTINGS_OVERRIDE_ENABLED=False`면 항상 default 반환.
    redis_client가 None이거나 조회/cast 실패 시 logger.warning 후 default.
    """
    if not settings.SETTINGS_OVERRIDE_ENABLED:
        return default
    if redis_client is None:
        return default
    try:
        raw = await redis_client.get(f"{OVERRIDE_PREFIX}{key}")
        if raw is None:
            return default
        val = raw if isinstance(raw, str) else raw.decode()
        try:
            return cast(val)
        except Exception as exc:  # noqa: BLE001
            logger.warning("resolve_override(%s) cast failed: %s", key, exc)
            return default
    except Exception as exc:  # noqa: BLE001
        logger.warning("resolve_override(%s) redis failed: %s", key, exc)
        return default
