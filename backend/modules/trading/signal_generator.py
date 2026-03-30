"""신호 생성기 — 스크리닝 결과에 전략을 적용하여 매매 신호를 생성한다."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.models.market_data import MarketData
from core.models.trading import TradeSignal
from core.redis import RedisClient
from modules.trading.strategy import MarketSnapshot, Strategy, TradeSignalData

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.6


class SignalGenerator:
    """2차 스크리닝 결과에 전략을 적용하여 trade_signals 테이블에 저장."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis_client: RedisClient,
        strategy: Strategy,
    ):
        self._session_factory = session_factory
        self._redis = redis_client
        self._strategy = strategy

    async def generate_signals(
        self, screened_candidates: list[dict]
    ) -> list[TradeSignalData]:
        """후보 종목에 전략을 적용하여 신호를 생성하고 DB에 저장."""
        generated: list[TradeSignalData] = []

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
                    logger.debug("중복 신호 스킵: %s", stock_code)
                    continue

                # MarketSnapshot 조립
                snapshot = await self._build_snapshot(candidate, session)

                # 전략 적용
                signal_data = await self._strategy.generate_signal(snapshot)
                if signal_data is None:
                    continue

                # 최소 신뢰도 필터
                if signal_data.confidence < MIN_CONFIDENCE:
                    continue

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
                )
                session.add(record)
                generated.append(signal_data)

            if generated:
                await session.commit()

        return generated

    async def _build_snapshot(
        self, candidate: dict, session: AsyncSession
    ) -> MarketSnapshot:
        """Redis 실시간 데이터 + DB 과거 데이터로 MarketSnapshot 조립."""
        stock_code = candidate["stock_code"]

        # Redis에서 실시간 시세
        realtime_raw = await self._redis.get(f"realtime:{stock_code}")
        if realtime_raw:
            realtime = json.loads(realtime_raw)
        else:
            realtime = {}

        # DB에서 최근 5일 시세
        md_stmt = (
            select(MarketData)
            .where(MarketData.stock_code == stock_code)
            .order_by(desc(MarketData.data_date))
            .limit(5)
        )
        md_result = await session.execute(md_stmt)
        md_rows = md_result.scalars().all()

        recent_highs = [int(r.high_price) for r in md_rows if r.high_price]
        recent_lows = [int(r.low_price) for r in md_rows if r.low_price]
        recent_closes = [int(r.close_price) for r in md_rows if r.close_price]

        # 전일 데이터 (첫 번째 row)
        prev_high = recent_highs[0] if recent_highs else candidate.get("current_price", 0)
        prev_close = recent_closes[0] if recent_closes else candidate.get("current_price", 0)

        return MarketSnapshot(
            stock_code=stock_code,
            stock_name=candidate.get("stock_name", ""),
            stock_type=candidate.get("stock_type", "STOCK"),
            current_price=candidate.get("current_price", 0),
            open_price=realtime.get("open_price", candidate.get("open_price", 0)),
            high=realtime.get("high", candidate.get("high", 0)),
            low=realtime.get("low", candidate.get("low", 0)),
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
