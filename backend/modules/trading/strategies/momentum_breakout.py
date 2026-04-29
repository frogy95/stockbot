"""모멘텀 브레이크아웃 전략 — 전일 고가 돌파 + 다팩터 신뢰도."""

import logging
from datetime import datetime, time
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from core.config import settings
from core.settings_override import resolve_override
from modules.screening.factors import calc_volatility_factor
from modules.trading.strategies._metrics import (
    record_shadow_stage,
    record_stage,
    record_virtual_signal,
)
from modules.trading.strategy import (
    MarketSnapshot,
    RejectedSignal,
    Strategy,
    TradeSignalData,
)

logger = logging.getLogger(__name__)

# ATR 필터: 현재가 대비 ATR 비율이 이 값을 초과하면 제외
ATR_FILTER_PCT = 0.05

# 시장 시간 상수 (KST)
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(15, 30)
MARKET_MINUTES = 390  # 09:00 ~ 15:30 = 6h30m

# 시간가중 거래량 보정 상수
MIN_MARKET_PROGRESS = 0.15  # 장 초반 거래량 하한 보정 계수

# 최소 신뢰도 (signal_generator의 MIN_CONFIDENCE와 동일)
MIN_CONFIDENCE = 0.6

_KST = ZoneInfo("Asia/Seoul")

# Phase 8 Sprint 2: 3단계 진입 tier
# prev_close tier는 오후 추격매수 리스크가 커 13:00 이후 비활성화한다.
PREV_CLOSE_TIER_BLOCK_TIME = time(13, 0)

# prev_close tier 전용 고정 파라미터 (Phase 8 확정 파라미터)
PREV_CLOSE_VOLUME_THRESHOLD = 2.5
PREV_CLOSE_MOMENTUM_DIVISOR = 7.0
PREV_CLOSE_MOMENTUM_MULTIPLIER = 0.7
PREV_CLOSE_CONFIDENCE_CAP = 0.75

# gap_open tier momentum 가중 (Phase 8 확정 파라미터 #11)
GAP_OPEN_MOMENTUM_MULTIPLIER = 0.85


async def _resolve_atr_ceil(
    snapshot: "MarketSnapshot",
    tier: str,
    redis_client: Any,
    is_fallback: bool,
    *,
    now_kst: datetime | None = None,
) -> float | None:
    """ATR 상한값을 결정 (Phase 8.6 Sprint 2 v2).

    반환값:
        float — 적용할 ATR 상한 비율 (current_price 기준)
        None  — ATR 하한(`ATR_FLOOR`) 미달 등으로 즉시 reject 신호

    규칙:
        1. ATR < `ATR_FLOOR`(0.025) — 모든 tier(gap_open 포함) 즉시 None 반환
        2. is_fallback=True — `ATR_CEIL_FALLBACK`(0.05) 정적 사용 (동적 미적용)
        3. tier == "gap_open" — `ATR_CEIL_HARD`(0.08) 절대 한계 적용 (Sprint v1 우회 X)
        4. tier IN ("prev_high", "prev_close"):
           - `ATR_CALIBRATION_ENABLED=true` + Redis `metrics:atr:ceil:{date}` 존재 → 그 값
             (단, `ATR_CEIL_HARD`로 캡)
           - 키 부재 또는 `ATR_CALIBRATION_ENABLED=false` → `ATR_CEIL_HARD` 폴백
    """
    # ATR 비율 계산 — current_price 기준
    if snapshot.current_price <= 0:
        return None
    atr = calc_volatility_factor(
        snapshot.recent_highs, snapshot.recent_lows, snapshot.recent_closes
    )
    atr_ratio = atr / snapshot.current_price

    floor = settings.ATR_FLOOR
    hard = settings.ATR_CEIL_HARD

    # Rule 1: 하한 미달 — 즉시 reject
    if atr_ratio < floor:
        return None

    # Rule 2: 폴백 종목 — 정적 상한
    if is_fallback:
        return settings.ATR_CEIL_FALLBACK

    # Rule 3: gap_open — HARD 절대 한계
    if tier == "gap_open":
        return hard

    # Rule 4: prev_high / prev_close — 동적 상한 또는 HARD
    if not settings.ATR_CALIBRATION_ENABLED or redis_client is None:
        return hard

    effective_now = now_kst if now_kst is not None else _now_kst()
    today = effective_now.date().isoformat()
    try:
        cached = await redis_client.get(f"metrics:atr:ceil:{today}")
    except Exception:  # noqa: BLE001
        cached = None
    if cached is None:
        return hard
    try:
        dynamic = float(cached)
    except (TypeError, ValueError):
        return hard
    return min(dynamic, hard)


def _resolve_min_volume_floor(
    snapshot: "MarketSnapshot",
    tier: str,
    gap_rate: float | None,
    breakout_ref: float,
    *,
    mode: str | None = None,
    hard_floor: float | None = None,
    redis_override_mode: str | None = None,
    now_kst: datetime | None = None,
) -> float:
    """동적 거래량 하한 결정 함수 (순수 함수 — side effect 없음, logger.warning 제외).

    Args:
        snapshot: 현재 시장 스냅샷.
        tier: 진입 tier ("gap_open", "prev_high", "prev_close").
        gap_rate: 갭 비율 (None 허용).
        breakout_ref: 돌파 기준가.
        mode: 결정 방식 오버라이드. None이면 settings.MIN_VOLUME_FLOOR_MODE 사용.
        hard_floor: 하한값 오버라이드. None이면 settings.MIN_VOLUME_FLOOR_HARD 사용.
        redis_override_mode: Redis override key에서 읽은 모드 문자열.
            있으면 최우선 적용 (mode, settings 보다 우선).
        now_kst: KST 현재 시각. None이면 `_now_kst()` 호출. dynamic 모드에서
            09:00~11:00 KST이면 결과를 0.3으로 추가 완화한다 (Phase 8.6 Sprint 1).

    Returns:
        적용할 거래량 하한 비율 (0.0 ~ 1.0).
    """
    # 우선순위: redis_override_mode > mode > settings.MIN_VOLUME_FLOOR_MODE
    resolved_mode = redis_override_mode or mode or settings.MIN_VOLUME_FLOOR_MODE
    hard = hard_floor if hard_floor is not None else settings.MIN_VOLUME_FLOOR_HARD

    if resolved_mode == "legacy":
        result = 0.5
    else:
        strong_gap = gap_rate is not None and gap_rate >= 0.05
        strong_breakout = breakout_ref > 0 and snapshot.current_price >= breakout_ref * 1.03
        strong = strong_gap or strong_breakout

        if tier == "prev_close":
            result = 0.6
        elif strong:
            result = 0.4
        else:
            result = 0.5

        # Phase 8.6 Sprint 1 — 09:00~11:00 KST 시간대 슬라이딩 (분기 D 손실 차단)
        effective_now = now_kst if now_kst is not None else _now_kst()
        if 9 <= effective_now.hour < 11:
            result = min(result, 0.3)

    if result < hard:
        logger.warning("resolved floor %.3f < HARD %.3f, forcing HARD", result, hard)
        return hard
    return result


def _now_kst() -> datetime:
    """테스트 주입 지점: 현재 KST 시각을 반환."""
    return datetime.now(_KST)


def calc_market_progress(now_kst: datetime | None = None) -> float:
    """장중 시간가중 진행도 반환 (0.15 ~ 1.0).

    - 장 전(09:00 이전): MIN_MARKET_PROGRESS (0.15)
    - 장 후(15:30 이후): 1.0
    - 장중: max(elapsed_minutes / 390, MIN_MARKET_PROGRESS)

    Args:
        now_kst: 테스트 주입용 KST datetime. None이면 현재 KST 시각 사용.

    Returns:
        0.15 ~ 1.0 범위의 진행도.
    """
    if now_kst is None:
        now_kst = datetime.now(_KST)

    current = now_kst.time()
    if current < MARKET_OPEN:
        return MIN_MARKET_PROGRESS
    if current >= MARKET_CLOSE:
        return 1.0

    elapsed = (now_kst.hour * 60 + now_kst.minute) - (MARKET_OPEN.hour * 60)
    raw = elapsed / MARKET_MINUTES
    return max(raw, MIN_MARKET_PROGRESS)


class MomentumBreakoutStrategy(Strategy):
    """5분봉 전일 고가 돌파 + 거래량/체결강도/호가 다팩터 신뢰도 전략."""

    # Phase 8.5 Sprint 1: 가상 신호 기록 시간창 (prev_close_time_guard 한정).
    VIRTUAL_SIGNAL_WINDOW_START = time(13, 0)
    VIRTUAL_SIGNAL_WINDOW_END = time(14, 0)

    def __init__(
        self,
        redis_client: Any = None,
        session_factory: Any = None,
    ) -> None:
        # 의존성은 관측용이며 선택적. 기본 None 유지 (기존 테스트 회귀 방지).
        self.redis_client = redis_client
        self.session_factory = session_factory

    @property
    def name(self) -> str:
        return "momentum_breakout"

    async def _reject(
        self, snapshot: MarketSnapshot, stage: str, detail: dict
    ) -> RejectedSignal:
        now_kst = _now_kst()
        await record_stage(
            self.redis_client,
            stage,
            now_kst=now_kst,
            snapshot_info={
                "stock_code": snapshot.stock_code,
                "breakout_ref": detail.get("breakout_ref"),
                "current_price": detail.get("current_price", snapshot.current_price),
                "detail": detail,
            },
        )

        if (
            stage == "prev_close_time_guard"
            and self.VIRTUAL_SIGNAL_WINDOW_START
            <= now_kst.time()
            < self.VIRTUAL_SIGNAL_WINDOW_END
        ):
            gap_rate = None
            if snapshot.prev_close:
                gap_rate = (snapshot.open_price - snapshot.prev_close) / snapshot.prev_close
            await record_virtual_signal(
                self.session_factory,
                snapshot,
                virtual_stage="prev_close_time_guard_bypass",
                detail=detail,
                breakout_ref=detail.get("breakout_ref"),
                gap_rate=gap_rate,
            )

        return RejectedSignal(
            stock_code=snapshot.stock_code,
            strategy_name=self.name,
            stage=stage,
            detail=detail,
        )

    def _resolve_tier(
        self, snapshot: MarketSnapshot, gap_rate: float
    ) -> tuple[float, str]:
        """3단계 진입 tier 결정.

        - gap_open: gap_rate >= 3% (돌파 기준 = 당일 시가)
        - prev_high: gap_rate < 3% AND current_price > prev_high (돌파 기준 = 전일 고가)
        - prev_close: 나머지 (돌파 기준 = 전일 종가, 13:00 이후 비활성)
        """
        if gap_rate >= 0.03:
            return snapshot.open_price, "gap_open"
        if snapshot.current_price > snapshot.prev_high:
            return snapshot.prev_high, "prev_high"
        return snapshot.prev_close, "prev_close"

    async def _shadow_evaluate(
        self, snapshot: MarketSnapshot, now_kst: datetime
    ) -> None:
        """각 필터 조건을 독립 평가하여 shadow 네임스페이스에 pass/fail 카운터 기록.

        주문 경로와 완전 분리 — 어떤 예외도 상위로 전파하지 않는다.
        `generate_signal()`의 반환값/타이밍/임계값에 영향을 주지 않는다.

        skip 규칙: 계산이 불가능한 조건(prev_volume=0 이후의 volume 관련 필터,
        breakout_ref<=0일 때 volume_threshold, current_price<=0일 때 atr_filter)은
        pass도 fail도 기록하지 않는다 — 표본 오염 방지.
        """
        try:
            gap_rate = (
                (snapshot.open_price - snapshot.prev_close) / snapshot.prev_close
                if snapshot.prev_close > 0
                else 0.0
            )
            breakout_ref, tier = self._resolve_tier(snapshot, gap_rate)

            # 1. prev_close_time_guard — tier=="prev_close" + 13:00 이후면 fail
            guard_fail = (
                tier == "prev_close" and now_kst.time() >= PREV_CLOSE_TIER_BLOCK_TIME
            )
            await record_shadow_stage(
                self.redis_client,
                "prev_close_time_guard",
                passed=not guard_fail,
                now_kst=now_kst,
            )

            # 2. breakout — current_price > breakout_ref
            if breakout_ref > 0:
                await record_shadow_stage(
                    self.redis_client,
                    "breakout",
                    passed=snapshot.current_price > breakout_ref,
                    now_kst=now_kst,
                )

            # 3. prev_volume_zero
            prev_volume_ok = snapshot.prev_volume > 0
            await record_shadow_stage(
                self.redis_client,
                "prev_volume_zero",
                passed=prev_volume_ok,
                now_kst=now_kst,
            )

            # prev_volume=0이면 volume 관련 이후 필터는 skip
            if prev_volume_ok:
                # 4. min_volume_floor — Redis override 우선 적용
                shadow_floor = _resolve_min_volume_floor(
                    snapshot, tier, gap_rate, breakout_ref,
                    redis_override_mode=await resolve_override(
                        self.redis_client,
                        "MIN_VOLUME_FLOOR_MODE",
                        default=None,
                    ),
                    now_kst=now_kst,
                )
                await record_shadow_stage(
                    self.redis_client,
                    "min_volume_floor",
                    passed=snapshot.volume >= snapshot.prev_volume * shadow_floor,
                    now_kst=now_kst,
                )

                # 5. volume_threshold — breakout_ref>0 필요
                if breakout_ref > 0:
                    progress = calc_market_progress(now_kst)
                    effective_progress = max(progress, MIN_MARKET_PROGRESS)
                    adjusted_ratio = snapshot.volume / (
                        snapshot.prev_volume * effective_progress
                    )
                    breakout_pct = (
                        (snapshot.current_price - breakout_ref) / breakout_ref * 100
                    )
                    if tier == "prev_close":
                        volume_threshold = PREV_CLOSE_VOLUME_THRESHOLD
                    elif breakout_pct >= 5.0:
                        volume_threshold = 1.5
                    elif breakout_pct >= 3.0:
                        volume_threshold = 1.8
                    else:
                        volume_threshold = 2.0
                    await record_shadow_stage(
                        self.redis_client,
                        "volume_threshold",
                        passed=adjusted_ratio >= volume_threshold,
                        now_kst=now_kst,
                    )

            # 6. trade_strength — snapshot 단독 평가 가능
            await record_shadow_stage(
                self.redis_client,
                "trade_strength",
                passed=snapshot.trade_strength >= 100.0,
                now_kst=now_kst,
            )

            # 7. atr_filter — current_price>0 필요
            if snapshot.current_price > 0:
                atr = calc_volatility_factor(
                    snapshot.recent_highs,
                    snapshot.recent_lows,
                    snapshot.recent_closes,
                )
                await record_shadow_stage(
                    self.redis_client,
                    "atr_filter",
                    passed=atr / snapshot.current_price <= ATR_FILTER_PCT,
                    now_kst=now_kst,
                )

            # 8. confidence — breakout_ref>0 AND prev_volume>0 필요
            if breakout_ref > 0 and prev_volume_ok:
                progress = calc_market_progress(now_kst)
                effective_progress = max(progress, MIN_MARKET_PROGRESS)
                adjusted_ratio = snapshot.volume / (
                    snapshot.prev_volume * effective_progress
                )
                breakout_pct = (
                    (snapshot.current_price - breakout_ref) / breakout_ref * 100
                )
                if tier == "prev_close":
                    momentum_score = (
                        min(breakout_pct / PREV_CLOSE_MOMENTUM_DIVISOR, 1.0)
                        * PREV_CLOSE_MOMENTUM_MULTIPLIER
                    )
                elif tier == "gap_open":
                    momentum_score = (
                        min(breakout_pct / 5.0, 1.0) * GAP_OPEN_MOMENTUM_MULTIPLIER
                    )
                else:
                    momentum_score = min(breakout_pct / 5.0, 1.0)
                volume_score = min(adjusted_ratio / 5.0, 1.0)
                strength_score = min((snapshot.trade_strength - 50) / 50, 1.0)
                orderbook_score = min(
                    snapshot.total_bid_volume / max(snapshot.total_ask_volume, 1) / 2.0,
                    1.0,
                )
                confidence = (
                    momentum_score * 0.3
                    + volume_score * 0.3
                    + strength_score * 0.2
                    + orderbook_score * 0.2
                )
                if tier == "prev_close":
                    confidence = min(confidence, PREV_CLOSE_CONFIDENCE_CAP)
                await record_shadow_stage(
                    self.redis_client,
                    "confidence",
                    passed=confidence >= MIN_CONFIDENCE,
                    now_kst=now_kst,
                )
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning(
                "shadow evaluate failed", exc_info=True
            )

    async def generate_signal(
        self, snapshot: MarketSnapshot
    ) -> TradeSignalData | RejectedSignal:
        # Phase 8.5 Sprint 1.5 — shadow 평가(관측 전용, 주문 경로 불변)
        # 호출 자체를 try/except로 감싸 _shadow_evaluate 내부 try 실패 시에도
        # 주문 경로가 영향을 받지 않도록 이중 방어.
        try:
            await self._shadow_evaluate(snapshot, _now_kst())
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning(
                "shadow evaluate call failed", exc_info=True
            )

        # 갭 비율 결정
        gap_rate = (
            (snapshot.open_price - snapshot.prev_close) / snapshot.prev_close
            if snapshot.prev_close > 0
            else 0.0
        )

        # 3단계 tier 결정 (gap_open / prev_high / prev_close)
        breakout_ref, breakout_tier = self._resolve_tier(snapshot, gap_rate)

        # prev_close tier는 13:00 이후 비활성 — 오후 추격매수 리스크 억제
        if (
            breakout_tier == "prev_close"
            and _now_kst().time() >= PREV_CLOSE_TIER_BLOCK_TIME
        ):
            return await self._reject(
                snapshot,
                "prev_close_time_guard",
                {
                    "breakout_tier": breakout_tier,
                    "breakout_ref": breakout_ref,
                    "current_price": snapshot.current_price,
                    "block_after": "13:00 KST",
                },
            )

        # 돌파 조건
        if snapshot.current_price <= breakout_ref:
            return await self._reject(
                snapshot,
                "breakout",
                {
                    "current_price": snapshot.current_price,
                    "breakout_ref": breakout_ref,
                    "breakout_tier": breakout_tier,
                    "gap_rate": round(gap_rate, 4),
                },
            )

        # 거래량 조건: 전일 대비 시간가중 보정 + 돌파 강도 연동
        if snapshot.prev_volume == 0:
            return await self._reject(
                snapshot,
                "prev_volume_zero",
                {"prev_volume": 0},
            )

        # 절대 거래량 하한 (너무 거래 없으면 제외)
        floor = _resolve_min_volume_floor(
            snapshot, breakout_tier, gap_rate, breakout_ref,
            redis_override_mode=await resolve_override(
                self.redis_client,
                "MIN_VOLUME_FLOOR_MODE",
                default=None,
            ),
        )
        if snapshot.volume < snapshot.prev_volume * floor:
            return await self._reject(
                snapshot,
                "min_volume_floor",
                {
                    "volume": snapshot.volume,
                    "prev_volume": snapshot.prev_volume,
                    "floor_ratio": floor,
                    "required": int(snapshot.prev_volume * floor),
                },
            )

        # 시간가중 보정
        progress = calc_market_progress()
        effective_progress = max(progress, MIN_MARKET_PROGRESS)
        adjusted_ratio = snapshot.volume / (snapshot.prev_volume * effective_progress)

        # 돌파 강도 연동 임계값 (prev_close tier는 2.5 고정)
        breakout_pct = (snapshot.current_price - breakout_ref) / breakout_ref * 100
        if breakout_tier == "prev_close":
            volume_threshold = PREV_CLOSE_VOLUME_THRESHOLD
        elif breakout_pct >= 5.0:
            volume_threshold = 1.5
        elif breakout_pct >= 3.0:
            volume_threshold = 1.8
        else:
            volume_threshold = 2.0

        if adjusted_ratio < volume_threshold:
            return await self._reject(
                snapshot,
                "volume_threshold",
                {
                    "adjusted_ratio": round(adjusted_ratio, 4),
                    "volume_threshold": volume_threshold,
                    "breakout_pct": round(breakout_pct, 4),
                    "breakout_tier": breakout_tier,
                    "market_progress": round(progress, 4),
                    "volume_ratio": round(snapshot.volume / snapshot.prev_volume, 4),
                },
            )

        # 체결강도 조건
        if snapshot.trade_strength < 100.0:
            return await self._reject(
                snapshot,
                "trade_strength",
                {
                    "trade_strength": round(snapshot.trade_strength, 2),
                    "required": 100.0,
                },
            )

        # ATR 필터
        atr = calc_volatility_factor(
            snapshot.recent_highs, snapshot.recent_lows, snapshot.recent_closes
        )
        if snapshot.current_price > 0 and atr / snapshot.current_price > ATR_FILTER_PCT:
            return await self._reject(
                snapshot,
                "atr_filter",
                {
                    "atr": round(atr, 2),
                    "current_price": snapshot.current_price,
                    "atr_ratio": round(atr / snapshot.current_price, 4),
                    "limit_ratio": ATR_FILTER_PCT,
                },
            )

        # 신뢰도 계산 — tier별 momentum_score 가중
        if breakout_tier == "prev_close":
            momentum_score = (
                min(breakout_pct / PREV_CLOSE_MOMENTUM_DIVISOR, 1.0)
                * PREV_CLOSE_MOMENTUM_MULTIPLIER
            )
        elif breakout_tier == "gap_open":
            momentum_score = min(breakout_pct / 5.0, 1.0) * GAP_OPEN_MOMENTUM_MULTIPLIER
        else:
            momentum_score = min(breakout_pct / 5.0, 1.0)

        volume_score = min(adjusted_ratio / 5.0, 1.0)
        strength_score = min((snapshot.trade_strength - 50) / 50, 1.0)
        orderbook_score = min(
            snapshot.total_bid_volume / max(snapshot.total_ask_volume, 1) / 2.0, 1.0
        )

        confidence = (
            momentum_score * 0.3
            + volume_score * 0.3
            + strength_score * 0.2
            + orderbook_score * 0.2
        )

        # prev_close tier는 confidence 상한 적용 (추격매수 리스크 반영)
        if breakout_tier == "prev_close":
            confidence = min(confidence, PREV_CLOSE_CONFIDENCE_CAP)

        # 최소 임계값
        if confidence < MIN_CONFIDENCE:
            return await self._reject(
                snapshot,
                "confidence",
                {
                    "confidence": round(confidence, 4),
                    "required": MIN_CONFIDENCE,
                    "momentum_score": round(momentum_score, 4),
                    "volume_score": round(volume_score, 4),
                    "strength_score": round(strength_score, 4),
                    "orderbook_score": round(orderbook_score, 4),
                    "breakout_tier": breakout_tier,
                },
            )

        # 레버리지 여부 판별
        is_leverage = "레버리지" in snapshot.stock_name or "2X" in snapshot.stock_name

        # 손절/익절 계산
        entry_price = snapshot.current_price
        if is_leverage:
            stop_loss = int(entry_price * 0.985)
        else:
            stop_loss = int(entry_price * 0.98)
        take_profit = int(entry_price * 1.03)

        await record_stage(self.redis_client, "pass", now_kst=_now_kst())

        return TradeSignalData(
            stock_code=snapshot.stock_code,
            signal_type="buy",
            strategy_name=self.name,
            confidence=round(confidence, 4),
            reason={
                "momentum_score": round(momentum_score, 4),
                "volume_score": round(volume_score, 4),
                "strength_score": round(strength_score, 4),
                "orderbook_score": round(orderbook_score, 4),
                "breakout_ref": breakout_ref,
                "breakout_tier": breakout_tier,
                "gap_rate": round(gap_rate, 4),
                "volume_ratio": round(snapshot.volume / snapshot.prev_volume, 2),
                "adjusted_ratio": round(adjusted_ratio, 2),
                "volume_threshold": volume_threshold,
                "breakout_pct": round(breakout_pct, 2),
                "market_progress": round(progress, 4),
                "atr": round(atr, 2),
                "is_leverage": is_leverage,
            },
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
