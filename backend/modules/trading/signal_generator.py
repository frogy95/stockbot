"""신호 생성기 — 스크리닝 결과에 전략을 적용하여 매매 신호를 생성한다."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.models.market_data import MarketData
from core.models.trading import TradeSignal
from core.redis import RedisClient
from modules.trading.strategy import (
    MarketSnapshot,
    RejectedSignal,
    Strategy,
    TradeSignalData,
)

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.6


class SignalGenerator:
    """2차 스크리닝 결과에 전략을 적용하여 trade_signals 테이블에 저장."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis_client: RedisClient,
        strategy: Strategy,
        circuit_breaker=None,
    ):
        self._session_factory = session_factory
        self._redis = redis_client
        self._strategy = strategy
        # Phase 8.6 Sprint 1 Task 5 — Daytrader Critical 보강 적용 위치.
        # 회로차단기 활성 시 신규 진입(buy)만 차단, 청산 계열은 통과.
        self._circuit_breaker = circuit_breaker

    async def generate_signals(
        self, screened_candidates: list[dict]
    ) -> list[TradeSignalData]:
        """후보 종목에 전략을 적용하여 신호를 생성하고 DB에 저장."""
        generated: list[TradeSignalData] = []
        skip_stats = {"dup": 0, "strategy_none": 0, "low_confidence": 0}

        async with self._session_factory() as session:
            for candidate in screened_candidates:
                stock_code = candidate["stock_code"]

                # 동일 종목 pending 신호 중복 체크
                dup_stmt = select(TradeSignal).where(
                    TradeSignal.stock_code == stock_code,
                    TradeSignal.status == "pending",
                )
                dup_result = await session.execute(dup_stmt)
                if dup_result.scalars().first() is not None:
                    skip_stats["dup"] += 1
                    logger.debug("중복 신호 스킵: %s", stock_code)
                    continue

                # MarketSnapshot 조립
                snapshot = await self._build_snapshot(candidate, session)

                # 전략 적용
                signal_data = await self._strategy.generate_signal(snapshot)
                # Phase 8.6 Sprint 1 — G1: candidate.is_fallback → signal/DB 전파
                is_fallback = bool(candidate.get("is_fallback", False))
                if isinstance(signal_data, RejectedSignal):
                    skip_stats["strategy_none"] += 1
                    logger.info(
                        "전략 거부 [%s]: %s detail=%s",
                        signal_data.stage, stock_code,
                        json.dumps(signal_data.detail, ensure_ascii=False),
                    )
                    continue

                # 최소 신뢰도 필터 (전략 내부에서 이미 걸렀지만 이중 방어)
                if signal_data.confidence < MIN_CONFIDENCE:
                    skip_stats["low_confidence"] += 1
                    logger.info(
                        "신뢰도 부족: %s confidence=%.3f < %.2f",
                        stock_code, signal_data.confidence, MIN_CONFIDENCE,
                    )
                    continue

                # G1: 폴백 메타데이터 전파 — TradeSignalData + reason JSON 둘 다 보존
                reason = {**signal_data.reason, "fallback": is_fallback}
                signal_data = signal_data.model_copy(
                    update={"fallback": is_fallback, "reason": reason}
                )

                # G3 회로차단기: 활성 시 신규 진입만 차단(청산 계열은 통과).
                if self._circuit_breaker is not None and not await self._circuit_breaker.allow_signal(signal_data):
                    logger.warning(
                        "G3 회로차단기 진입 신호 차단: %s (보유 포지션 청산 신호는 영향 없음)",
                        stock_code,
                    )
                    continue

                logger.info(
                    "전략 통과 [%s]: %s confidence=%.3f entry=%d reason=%s",
                    signal_data.strategy_name, stock_code,
                    signal_data.confidence, signal_data.entry_price,
                    json.dumps(signal_data.reason, ensure_ascii=False),
                )

                # DB 저장
                record = TradeSignal(
                    stock_code=signal_data.stock_code,
                    signal_type=signal_data.signal_type,
                    strategy_name=signal_data.strategy_name,
                    confidence=signal_data.confidence,
                    reason=signal_data.reason,
                    entry_price=signal_data.entry_price,
                    stop_loss=signal_data.stop_loss,
                    take_profit=signal_data.take_profit,
                    status="pending",
                    fallback=is_fallback,
                    matched_tiers=signal_data.matched_tiers,  # Phase 8.6 Sprint 2
                )
                session.add(record)
                generated.append(signal_data)

            if generated:
                await session.commit()

        if screened_candidates:
            logger.info(
                "신호 생성: 입력=%d, 통과=%d (중복=%d, 전략미충족=%d, 신뢰도부족=%d)",
                len(screened_candidates), len(generated),
                skip_stats["dup"], skip_stats["strategy_none"], skip_stats["low_confidence"],
            )

        return generated

    async def _build_snapshot(
        self, candidate: dict, session: AsyncSession
    ) -> MarketSnapshot:
        """candidate dict(realtime_screener가 조립) 기반 MarketSnapshot 조립.

        candidate에 prev_close/prev_high/prev_volume/recent_* 등이 모두 포함되어 있음.
        Redis 체결 데이터에 intraday open/high/low가 없어 current_price로 대체한다.
        """
        stock_code = candidate["stock_code"]
        current_price = candidate.get("current_price", 0)

        # 팩터 계산용 과거 5일 데이터 (candidate에 이미 포함)
        recent_highs = candidate.get("recent_highs", [])
        recent_lows = candidate.get("recent_lows", [])
        recent_closes = candidate.get("recent_closes", [])

        # ASC 정렬이므로 마지막 원소가 최근 일자(전일 기준)
        prev_close = candidate.get("prev_close") or (recent_closes[-1] if recent_closes else current_price)
        prev_high = candidate.get("prev_high") or (recent_highs[-1] if recent_highs else current_price)

        # H0STCNT0 파서가 OHLC를 전파. 미수신/0 시 prev_close 폴백 → gap_rate=0 처리로
        # 전략이 prev_high 돌파 경로 진입. current_price 폴백 시 gap_rate≥3% 오판정 발생.
        open_price = candidate.get("open_price") or prev_close or current_price
        high = candidate.get("high") or current_price
        low = candidate.get("low") or current_price

        # momentum/volatility 계산이 ASC 순서를 가정하는지는 기존 로직 유지
        return MarketSnapshot(
            stock_code=stock_code,
            stock_name=candidate.get("stock_name", ""),
            stock_type=candidate.get("stock_type", "STOCK"),
            current_price=current_price,
            open_price=open_price,
            high=high,
            low=low,
            prev_close=prev_close,
            prev_high=prev_high,
            volume=candidate.get("volume", 0),
            prev_volume=candidate.get("prev_volume", 0),
            change_rate=candidate.get("change_rate", 0.0),
            trade_strength=candidate.get("trade_strength", 0.0),
            total_bid_volume=candidate.get("total_bid_volume", 0),
            total_ask_volume=candidate.get("total_ask_volume", 0),
            recent_highs=recent_highs,
            recent_lows=recent_lows,
            recent_closes=recent_closes,
        )
