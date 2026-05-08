"""Phase 8.6 Sprint 3 Task 2 — 거래량 급등(VolumeSurge) 전략.

09:30~14:00 KST 활성. 다음 3대 조건을 모두 만족하면 신호를 발행한다.

1. 거래량 급등 — 최근 5분봉 total_vol / 직전 4봉 평균 total_vol ≥ VOL_RATIO (기본 5.0)
2. 호가 매수우위 — total_bid_volume / total_ask_volume ≥ BID_ASK_RATIO (기본 2.0)
3. 가격 상승 — current_price / prev_close ≥ 1 + PRICE_THRESHOLD (기본 0.5%)

기본은 dry_run 모드(VOLUME_SURGE_DRY_RUN=True). 신호는 발행되지만 주문은
TradingEngine 측에서 차단한다. 본 모듈은 신호 dict만 반환한다.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from core.config import settings
from modules.collector.volume_aggregator import calc_5min_slot, make_redis_key
from modules.trading.strategies._time_filter import (
    record_block as record_time_filter_block,
)
from modules.trading.strategies._time_filter import should_block_entry

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")

# 활성 시간 (KST)
ACTIVE_START = time(9, 30)
ACTIVE_END = time(14, 0)

# tier 식별자
TIER_NAME = "volume_surge"


def _now_kst() -> datetime:
    """테스트 주입 지점."""
    return datetime.now(_KST)


class VolumeSurgeStrategy:
    """거래량 급등 + 호가 매수우위 + 가격 상승 동시 충족 시 신호 발행."""

    def __init__(
        self,
        redis_client: Any = None,
        session_factory: Any = None,
        telegram_bot: Any = None,
    ) -> None:
        self.redis_client = redis_client
        self.session_factory = session_factory
        self.telegram_bot = telegram_bot

    @property
    def name(self) -> str:
        return TIER_NAME

    @staticmethod
    def _reject(reason: str, **detail: Any) -> dict[str, Any]:
        """reject dict 헬퍼."""
        return {"signal": None, "rejected": True, "reason": reason, "detail": detail}

    async def _load_orderbook(self, stock_code: str) -> dict | None:
        """Redis `realtime:{code}:orderbook` 조회 + JSON 파싱."""
        if self.redis_client is None:
            return None
        try:
            raw = await self.redis_client.get(f"realtime:{stock_code}:orderbook")
        except Exception:  # noqa: BLE001
            logger.warning("orderbook get failed", exc_info=True)
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        except (TypeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    async def _load_vol5m_bars(
        self, stock_code: str, now_kst: datetime
    ) -> list[dict] | None:
        """현재 슬롯 + 직전 4슬롯 → 최신 5개 dict 반환. 모두 부재면 None."""
        if self.redis_client is None:
            return None
        date_str = now_kst.strftime("%Y%m%d")
        current_slot = calc_5min_slot(now_kst.hour, now_kst.minute)
        bars: list[dict] = []
        any_present = False
        for offset in range(5):
            slot = current_slot - 4 + offset
            if slot < 0:
                bars.append({"buy_vol": 0, "sell_vol": 0, "total_vol": 0})
                continue
            key = make_redis_key(stock_code, date_str, slot)
            try:
                raw = await self.redis_client.get(key)
            except Exception:  # noqa: BLE001
                return None
            if not raw:
                bars.append({"buy_vol": 0, "sell_vol": 0, "total_vol": 0})
                continue
            try:
                data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            except (TypeError, ValueError):
                return None
            if isinstance(data, dict):
                bars.append(data)
                any_present = True
            else:
                bars.append({"buy_vol": 0, "sell_vol": 0, "total_vol": 0})
        return bars if any_present else None

    async def evaluate(
        self, candidate: dict, now_kst: datetime | None = None
    ) -> dict | None:
        """후보 종목에 대해 거래량 급등 신호를 평가한다.

        Args:
            candidate: 최소한 `stock_code`, `current_price`, `prev_close` 포함.
            now_kst: 테스트 주입용 KST datetime. None이면 `_now_kst()`.

        Returns:
            신호 dict (통과) 또는 reject dict (`rejected=True`).
        """
        now = now_kst if now_kst is not None else _now_kst()
        stock_code = candidate.get("stock_code", "")

        # 1. 마스터 토글
        if not settings.VOLUME_SURGE_ENABLED:
            return self._reject("vol_surge_disabled")

        # 2. Sprint 3 시간 필터 본 가드 위임
        blocked, block_reason = should_block_entry(now, TIER_NAME)
        if blocked:
            await record_time_filter_block(self.redis_client, block_reason, now)
            return self._reject("time_filter", block_reason=block_reason)

        # 3. 활성 시간대 (09:30 ≤ t < 14:00)
        t = now.time()
        if not (ACTIVE_START <= t < ACTIVE_END):
            return self._reject(
                "vol_surge_time", now=t.isoformat(),
                active_start=ACTIVE_START.isoformat(),
                active_end=ACTIVE_END.isoformat(),
            )

        # 4. 가격 상승 — current/prev_close ≥ 1 + threshold
        current_price = float(candidate.get("current_price", 0) or 0)
        prev_close = float(candidate.get("prev_close", 0) or 0)
        if prev_close <= 0:
            return self._reject("vol_surge_price", reason="prev_close<=0")
        price_ratio = current_price / prev_close
        threshold = 1.0 + settings.VOLUME_SURGE_PRICE_THRESHOLD
        if price_ratio < threshold:
            return self._reject(
                "vol_surge_price",
                price_ratio=round(price_ratio, 6),
                threshold=round(threshold, 6),
            )

        # 5. 호가창 조회
        ob = await self._load_orderbook(stock_code)
        if ob is None:
            return self._reject("vol_surge_orderbook_missing")
        bid = float(ob.get("total_bid_volume", 0) or 0)
        ask = float(ob.get("total_ask_volume", 0) or 0)
        if ask <= 0:
            return self._reject("vol_surge_orderbook", reason="ask<=0", bid=bid, ask=ask)
        bid_ask_ratio = bid / ask
        if bid_ask_ratio < settings.VOLUME_SURGE_BID_ASK_RATIO:
            return self._reject(
                "vol_surge_orderbook",
                bid_ask_ratio=round(bid_ask_ratio, 4),
                required=settings.VOLUME_SURGE_BID_ASK_RATIO,
            )

        # 6. 거래량 급등 — vol5m 5슬롯 조회
        bars = await self._load_vol5m_bars(stock_code, now)
        if bars is None:
            return self._reject("vol_surge_vol5m_missing")
        prev4 = bars[:4]
        latest = float(bars[-1].get("total_vol", 0) or 0)
        avg4 = sum(float(b.get("total_vol", 0) or 0) for b in prev4) / 4.0
        if avg4 <= 0:
            return self._reject("vol_surge_vol5m_zero", latest=latest)
        vol_ratio = latest / avg4
        if vol_ratio < settings.VOLUME_SURGE_VOL_RATIO:
            return self._reject(
                "vol_surge_ratio",
                vol_ratio=round(vol_ratio, 4),
                required=settings.VOLUME_SURGE_VOL_RATIO,
            )

        # 통과 — 신호 dict 반환
        # confidence: 3대 비율을 0~1 정규화하여 평균
        vol_score = min(vol_ratio / (settings.VOLUME_SURGE_VOL_RATIO * 2.0), 1.0)
        ob_score = min(bid_ask_ratio / (settings.VOLUME_SURGE_BID_ASK_RATIO * 2.0), 1.0)
        price_score = min((price_ratio - 1.0) / (settings.VOLUME_SURGE_PRICE_THRESHOLD * 4.0), 1.0)
        confidence = round((vol_score + ob_score + price_score) / 3.0, 4)

        return {
            "stock_code": stock_code,
            "tier": TIER_NAME,
            "dry_run": bool(settings.VOLUME_SURGE_DRY_RUN),
            "vol_ratio": round(vol_ratio, 4),
            "bid_ask_ratio": round(bid_ask_ratio, 4),
            "price_change": round(price_ratio - 1.0, 6),
            "matched_tiers": [TIER_NAME],
            "confidence": confidence,
        }
