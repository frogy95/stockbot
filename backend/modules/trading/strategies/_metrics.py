"""Phase 8.5 Sprint 1 — 전략 관측성 측면 기록 헬퍼.

전략 순수성 유지를 위한 엄격한 규칙:
- TradeSignalData / SignalGenerator / OrderManager / engine import 금지
- 모든 예외를 내부에서 흡수 → 전략 반환 경로에 영향 없음
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from core.config import settings
from core.metrics_keys import (
    SHADOW_TRACKED_STAGES,
    TOP_REJECT_KEY,
    hour_min_bucket_for,
    shadow_stage_counter_key,
    stage_counter_key,
)

logger = logging.getLogger(__name__)

STAGE_COUNTER_TTL = 86400 * 7
TOP_REJECT_SIZE = 5


async def record_stage(
    redis_client: Any,
    stage: str,
    now_kst: datetime | None = None,
    snapshot_info: dict | None = None,
) -> None:
    """stage 카운터 +1, reject 이벤트는 top_reject 리스트에 최근 5건 유지.

    redis_client가 None이거나 예외 발생 시 조용히 무시.
    """
    if redis_client is None:
        return
    try:
        if now_kst is None:
            from zoneinfo import ZoneInfo

            now_kst = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
        today = now_kst.date().isoformat()
        hour_min = hour_min_bucket_for(now_kst)
        key = stage_counter_key(today, stage, hour_min)
        await redis_client.incr(key, ttl=STAGE_COUNTER_TTL)

        if stage != "pass" and snapshot_info is not None:
            payload = json.dumps(
                {"recorded_at": now_kst.isoformat(), "stage": stage, **snapshot_info},
                default=str,
            )
            await redis_client.lpush(TOP_REJECT_KEY, payload)
            await redis_client.ltrim(TOP_REJECT_KEY, 0, TOP_REJECT_SIZE - 1)
    except Exception:  # noqa: BLE001
        logger.warning("record_stage failed (stage=%s)", stage, exc_info=True)


async def record_shadow_stage(
    redis_client: Any,
    stage: str,
    passed: bool,
    now_kst: datetime | None = None,
) -> None:
    """shadow 네임스페이스에 필터 독립 평가 pass/fail 카운터 +1.

    주문 경로에 영향 없음 — redis_client None이거나 예외 발생 시 조용히 무시.
    """
    if redis_client is None:
        return
    if stage not in SHADOW_TRACKED_STAGES:
        logger.debug("record_shadow_stage: unknown stage=%s ignored", stage)
        return
    try:
        if now_kst is None:
            from zoneinfo import ZoneInfo

            now_kst = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
        today = now_kst.date().isoformat()
        hour_min = hour_min_bucket_for(now_kst)
        outcome = "pass" if passed else "fail"
        key = shadow_stage_counter_key(today, stage, outcome, hour_min)
        await redis_client.incr(key, ttl=STAGE_COUNTER_TTL)
    except Exception:  # noqa: BLE001
        logger.warning(
            "record_shadow_stage failed (stage=%s passed=%s)", stage, passed, exc_info=True
        )


async def record_virtual_signal(
    session_factory: Any,
    snapshot: Any,
    virtual_stage: str,
    detail: dict,
    breakout_ref: int | None = None,
    gap_rate: float | None = None,
) -> None:
    """가상 신호 INSERT. 주문 경로와 완전 분리. 예외 전파 금지.

    TradeSignalData를 절대 import/생성하지 않는다.
    """
    if session_factory is None:
        return
    try:
        from core.models.metrics import VirtualSignal  # local import to avoid cycles

        async with session_factory() as session:
            record = VirtualSignal(
                stock_code=snapshot.stock_code,
                stock_name=getattr(snapshot, "stock_name", None),
                virtual_stage=virtual_stage,
                breakout_ref=breakout_ref,
                current_price=getattr(snapshot, "current_price", None),
                gap_rate=gap_rate,
                prev_close=getattr(snapshot, "prev_close", None),
                detail=detail or {},
                would_execute=False,
            )
            session.add(record)
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.warning("record_virtual_signal failed", exc_info=True)
