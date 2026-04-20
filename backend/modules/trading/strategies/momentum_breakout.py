"""모멘텀 브레이크아웃 전략 — 전일 고가 돌파 + 다팩터 신뢰도."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from modules.screening.factors import calc_volatility_factor
from modules.trading.strategy import (
    MarketSnapshot,
    RejectedSignal,
    Strategy,
    TradeSignalData,
)

# ATR 필터: 현재가 대비 ATR 비율이 이 값을 초과하면 제외
ATR_FILTER_PCT = 0.05

# 시장 시간 상수 (KST)
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(15, 30)
MARKET_MINUTES = 390  # 09:00 ~ 15:30 = 6h30m

# 시간가중 거래량 보정 상수
MIN_MARKET_PROGRESS = 0.15  # 장 초반 거래량 하한 보정 계수
MIN_VOLUME_FLOOR = 0.5  # 전일 대비 절대 거래량 하한

# 최소 신뢰도 (signal_generator의 MIN_CONFIDENCE와 동일)
MIN_CONFIDENCE = 0.6

_KST = ZoneInfo("Asia/Seoul")


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

    @property
    def name(self) -> str:
        return "momentum_breakout"

    def _reject(
        self, snapshot: MarketSnapshot, stage: str, detail: dict
    ) -> RejectedSignal:
        return RejectedSignal(
            stock_code=snapshot.stock_code,
            strategy_name=self.name,
            stage=stage,
            detail=detail,
        )

    async def generate_signal(
        self, snapshot: MarketSnapshot
    ) -> TradeSignalData | RejectedSignal:
        # 갭 비율 결정
        gap_rate = (
            (snapshot.open_price - snapshot.prev_close) / snapshot.prev_close
            if snapshot.prev_close > 0
            else 0.0
        )

        # 돌파 기준: 갭 3%+ 시 당일 시가(open_price), 그 외 전일 고가
        # high 기준이면 current_price <= high가 항상 성립 → breakout 게이트가 전체 갭 종목을 거부
        if gap_rate >= 0.03:
            breakout_ref = snapshot.open_price
        else:
            breakout_ref = snapshot.prev_high

        # 돌파 조건
        if snapshot.current_price <= breakout_ref:
            return self._reject(
                snapshot,
                "breakout",
                {
                    "current_price": snapshot.current_price,
                    "breakout_ref": breakout_ref,
                    "gap_rate": round(gap_rate, 4),
                },
            )

        # 거래량 조건: 전일 대비 시간가중 보정 + 돌파 강도 연동
        if snapshot.prev_volume == 0:
            return self._reject(
                snapshot,
                "prev_volume_zero",
                {"prev_volume": 0},
            )

        # 절대 거래량 하한 (너무 거래 없으면 제외)
        if snapshot.volume < snapshot.prev_volume * MIN_VOLUME_FLOOR:
            return self._reject(
                snapshot,
                "min_volume_floor",
                {
                    "volume": snapshot.volume,
                    "prev_volume": snapshot.prev_volume,
                    "floor_ratio": MIN_VOLUME_FLOOR,
                    "required": int(snapshot.prev_volume * MIN_VOLUME_FLOOR),
                },
            )

        # 시간가중 보정
        progress = calc_market_progress()
        effective_progress = max(progress, MIN_MARKET_PROGRESS)
        adjusted_ratio = snapshot.volume / (snapshot.prev_volume * effective_progress)

        # 돌파 강도 연동 임계값 (강한 돌파일수록 낮은 거래량 임계값 허용)
        breakout_pct = (snapshot.current_price - breakout_ref) / breakout_ref * 100
        if breakout_pct >= 5.0:
            volume_threshold = 1.5
        elif breakout_pct >= 3.0:
            volume_threshold = 1.8
        else:
            volume_threshold = 2.0

        if adjusted_ratio < volume_threshold:
            return self._reject(
                snapshot,
                "volume_threshold",
                {
                    "adjusted_ratio": round(adjusted_ratio, 4),
                    "volume_threshold": volume_threshold,
                    "breakout_pct": round(breakout_pct, 4),
                    "market_progress": round(progress, 4),
                    "volume_ratio": round(snapshot.volume / snapshot.prev_volume, 4),
                },
            )

        # 체결강도 조건
        if snapshot.trade_strength < 100.0:
            return self._reject(
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
            return self._reject(
                snapshot,
                "atr_filter",
                {
                    "atr": round(atr, 2),
                    "current_price": snapshot.current_price,
                    "atr_ratio": round(atr / snapshot.current_price, 4),
                    "limit_ratio": ATR_FILTER_PCT,
                },
            )

        # 신뢰도 계산
        momentum_score = min(
            (snapshot.current_price - breakout_ref) / breakout_ref * 100 / 5.0, 1.0
        )
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

        # 최소 임계값
        if confidence < MIN_CONFIDENCE:
            return self._reject(
                snapshot,
                "confidence",
                {
                    "confidence": round(confidence, 4),
                    "required": MIN_CONFIDENCE,
                    "momentum_score": round(momentum_score, 4),
                    "volume_score": round(volume_score, 4),
                    "strength_score": round(strength_score, 4),
                    "orderbook_score": round(orderbook_score, 4),
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
