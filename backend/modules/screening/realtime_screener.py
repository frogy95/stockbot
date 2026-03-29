"""2차 스크리닝 엔진 — 장중 실시간 데이터(Redis) 기반 동적 필터 + 팩터 스코어링."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, time

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.market_data import MarketData
from core.models.screening_result import ScreeningResult
from core.models.stock import Stock
from core.redis import RedisClient
from modules.collector.trade_strength import TradeStrengthCalculator
from modules.screening.factors import (
    calc_momentum_factor,
    calc_orderbook_ratio_factor,
    calc_trade_strength_factor,
    calc_volatility_factor,
    calc_volume_factor,
)
from modules.screening.filters import SecondaryFilters
from modules.screening.scorer import FactorScorer

logger = logging.getLogger(__name__)


class RealtimeScreener:
    """장중 2차 스크리닝: Redis 실시간 데이터 기반 필터 + 팩터 스코어링."""

    def __init__(
        self,
        filters: SecondaryFilters | None = None,
        scorer: FactorScorer | None = None,
        redis_client: RedisClient | None = None,
        trade_strength_calc: TradeStrengthCalculator | None = None,
    ):
        self.filters = filters or SecondaryFilters()
        self.scorer = scorer or FactorScorer()
        self.redis_client = redis_client
        self.trade_strength_calc = trade_strength_calc or TradeStrengthCalculator()

    async def screen(
        self, candidate_codes: list[str], session: AsyncSession
    ) -> list[dict]:
        """1차 후보 종목에 대해 실시간 데이터 기반 2차 필터 적용 후 스코어링."""
        if self._is_no_signal_period():
            return []

        if not candidate_codes:
            return []

        stock_info = await self._get_stock_info(session, candidate_codes)

        passed_candidates: list[dict] = []

        for code in candidate_codes:
            realtime = await self._get_realtime_data(code)
            if realtime is None:
                continue

            info = stock_info.get(code)
            if info is None:
                continue

            trade_strength = self.trade_strength_calc.get_strength(code)
            if trade_strength < self.filters.trade_strength_min:
                continue

            orderbook = realtime.get("orderbook", {})
            total_bid_volume = orderbook.get("total_bid_volume", 0)
            total_ask_volume = orderbook.get("total_ask_volume", 0)

            if total_ask_volume == 0:
                continue

            orderbook_ratio = total_bid_volume / total_ask_volume
            if orderbook_ratio < self.filters.orderbook_ratio_min:
                continue

            execution = realtime.get("execution", {})
            passed_candidates.append({
                "stock_code": code,
                "stock_name": info["stock_name"],
                "stock_type": info["stock_type"],
                "trade_strength": trade_strength,
                "orderbook_ratio": orderbook_ratio,
                "volume": execution.get("volume", 0),
                "prev_volume": execution.get("prev_volume", 0),
                "current_price": execution.get("current_price", 0),
                "change_rate": execution.get("change_rate", 0.0),
                "total_bid_volume": total_bid_volume,
                "total_ask_volume": total_ask_volume,
            })

        if not passed_candidates:
            return []

        # 팩터 계산
        codes = [c["stock_code"] for c in passed_candidates]
        recent_data = await self._get_recent_market_data(session, codes)

        factor_candidates = []
        for candidate in passed_candidates:
            code = candidate["stock_code"]
            recent = recent_data.get(code, [])
            closes = [int(r["close_price"]) for r in recent if r.get("close_price")]
            highs = [int(r["high_price"]) for r in recent if r.get("high_price")]
            lows = [int(r["low_price"]) for r in recent if r.get("low_price")]

            volume = candidate["volume"]
            prev_volume = candidate["prev_volume"]

            volume_factor = calc_volume_factor(volume, prev_volume)
            momentum_factor = calc_momentum_factor(closes) if len(closes) >= 4 else 0.0
            volatility_factor = (
                calc_volatility_factor(highs, lows, closes) if len(highs) >= 2 else 0.0
            )
            trade_strength_factor = calc_trade_strength_factor(candidate["trade_strength"])
            orderbook_ratio_factor = calc_orderbook_ratio_factor(
                candidate["total_bid_volume"], candidate["total_ask_volume"]
            )

            factor_candidates.append({
                "stock_code": code,
                "stock_name": candidate["stock_name"],
                "stock_type": candidate["stock_type"],
                "trade_strength": candidate["trade_strength"],
                "orderbook_ratio": candidate["orderbook_ratio"],
                "volume_factor": volume_factor,
                "momentum_factor": momentum_factor,
                "volatility_factor": volatility_factor,
                "trade_strength_factor": trade_strength_factor,
                "orderbook_ratio_factor": orderbook_ratio_factor,
            })

        scored = self.scorer.score_candidates(factor_candidates)

        await self.save_results(session, scored)

        return scored

    def _is_no_signal_period(self) -> bool:
        """시초가 구간(09:00~09:30) 판단."""
        now = datetime.now()
        no_signal_time = self.filters.no_signal_before.split(":")
        no_signal_hour = int(no_signal_time[0])
        no_signal_minute = int(no_signal_time[1])

        market_open = time(9, 0)
        no_signal_limit = time(no_signal_hour, no_signal_minute)
        current_time = now.time()

        return market_open <= current_time < no_signal_limit

    async def _get_realtime_data(self, code: str) -> dict | None:
        """Redis에서 실시간 체결/호가 데이터 조회."""
        if self.redis_client is None:
            return None

        execution_raw = await self.redis_client.get(f"realtime:{code}:execution")
        if execution_raw is None:
            return None

        orderbook_raw = await self.redis_client.get(f"realtime:{code}:orderbook")
        if orderbook_raw is None:
            return None

        try:
            execution = json.loads(execution_raw)
            orderbook = json.loads(orderbook_raw)
        except (json.JSONDecodeError, TypeError):
            return None

        return {"execution": execution, "orderbook": orderbook}

    async def _get_stock_info(
        self, session: AsyncSession, codes: list[str]
    ) -> dict[str, dict]:
        """종목 코드 리스트에 대한 기본 정보 조회."""
        stmt = (
            select(Stock.stock_code, Stock.stock_name, Stock.stock_type)
            .where(Stock.stock_code.in_(codes), Stock.is_active.is_(True))
        )
        result = await session.execute(stmt)
        rows = result.mappings().all()

        return {
            row["stock_code"]: {
                "stock_name": row["stock_name"],
                "stock_type": row["stock_type"],
            }
            for row in rows
        }

    async def _get_recent_market_data(
        self, session: AsyncSession, codes: list[str], days: int = 5
    ) -> dict[str, list[dict]]:
        """종목별 최근 N일 market_data 조회."""
        date_subq = (
            select(MarketData.data_date)
            .distinct()
            .order_by(desc(MarketData.data_date))
            .limit(days)
            .subquery()
        )

        stmt = (
            select(
                MarketData.stock_code,
                MarketData.close_price,
                MarketData.high_price,
                MarketData.low_price,
            )
            .where(
                MarketData.stock_code.in_(codes),
                MarketData.data_date.in_(select(date_subq.c.data_date)),
            )
            .order_by(MarketData.stock_code, MarketData.data_date)
        )

        result = await session.execute(stmt)
        rows = result.mappings().all()

        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row["stock_code"]].append({
                "close_price": row["close_price"],
                "high_price": row["high_price"],
                "low_price": row["low_price"],
            })
        return grouped

    async def save_results(
        self, session: AsyncSession, results: list[dict]
    ) -> int:
        """screening_results 테이블에 2차 스크리닝 결과 저장."""
        count = 0
        for item in results:
            record = ScreeningResult(
                stock_code=item["stock_code"],
                screening_type="secondary",
                score=item.get("score"),
                rank=item.get("rank"),
                factors=item.get("factors", {}),
                is_hot=False,
                status="active",
            )
            session.add(record)
            count += 1
        await session.commit()
        return count
