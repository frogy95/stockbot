"""Redis settings override 키 단일 진실 소스 (Phase 8.6 Sprint 5 Hotfix A).

R1(auto_rollback) / G3(circuit_breaker) 양쪽에서 동일 키를 다루는데
문자열로 흩어져 있어 발동/해제 분기 누락 위험 + override-status API와의 일관성 결여가
2026-05-14 16:10 모니터링에서 확인됨. Enum으로 통합.
"""
from __future__ import annotations

from enum import Enum

OVERRIDE_PREFIX = "settings:override:"
PHASE86_ROLLBACK_KEY = "phase86:rollback:active"
PHASE86_CIRCUIT_BREAKER_KEY = "phase86:circuit_breaker:active"


class SettingsOverrideKey(str, Enum):
    """`settings:override:*` Redis 키 (값에 prefix 포함되지 않음)."""

    MIN_VOLUME_FLOOR_MODE = "MIN_VOLUME_FLOOR_MODE"
    SECONDARY_POOL_FALLBACK_ENABLED = "SECONDARY_POOL_FALLBACK_ENABLED"
    TRIGGERED_AT = "triggered_at"
    REASON = "reason"

    @property
    def redis_key(self) -> str:
        return f"{OVERRIDE_PREFIX}{self.value}"


R1_OVERRIDE_KEYS: tuple[SettingsOverrideKey, ...] = (
    SettingsOverrideKey.MIN_VOLUME_FLOOR_MODE,
    SettingsOverrideKey.SECONDARY_POOL_FALLBACK_ENABLED,
    SettingsOverrideKey.TRIGGERED_AT,
    SettingsOverrideKey.REASON,
)

G3_OVERRIDE_KEYS: tuple[SettingsOverrideKey, ...] = (
    SettingsOverrideKey.SECONDARY_POOL_FALLBACK_ENABLED,
)
