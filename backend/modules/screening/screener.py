"""1차 스크리닝 엔진 — 장전 DB 정적 필터 + 팩터 스코어링."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.market_data import MarketData
from core.models.screening_result import ScreeningResult
from core.models.stock import Stock
from modules.screening.factors import (
    calc_momentum_factor,
    calc_volatility_factor,
    calc_volume_factor,
)
from modules.screening.filters import PrimaryFilters, is_hot_stock, passes_primary_filter
from modules.screening.scorer import FactorScorer


class PrimaryScreener:
    """장전 1차 스크리닝: DB 정적 데이터 기반 필터 + 팩터 스코어링."""

    def __init__(
        self,
        filters: PrimaryFilters | None = None,
        scorer: FactorScorer | None = None,
    ):
        self.filters = filters or PrimaryFilters()
        self.scorer = scorer or FactorScorer()

    async def screen(self, session: AsyncSession) -> list[dict]:
        """1차 스크리닝 실행: DB 조회 → 필터 → 스코어링 → 상위 N종목 반환."""
        today_prev = await self._fetch_today_and_prev(session)
        if not today_prev:
            return []

        recent_data = await self._get_recent_market_data(session, days=5)

        rows = list(today_prev.values())
        filtered = self._apply_filters(rows)
        if not filtered:
            return []

        candidates = self._build_candidates(filtered, recent_data)
        scored = self.scorer.score_candidates(candidates)
        result = self._truncate_and_rank(scored)
        self._mark_hot_stocks(result)
        return result

    def _apply_filters(self, rows: list[dict]) -> list[dict]:
        """필터 통과 종목만 반환."""
        passed = []
        for row in rows:
            stock_data = {
                "volume": row["volume"],
                "prev_volume": row["prev_volume"],
                "market_cap": row["market_cap"],
                "change_rate": float(row["change_rate"]),
                "stock_type": row["stock_type"],
            }
            if passes_primary_filter(stock_data, self.filters):
                passed.append(row)
        return passed

    def _build_candidates(
        self, filtered: list[dict], recent_data: dict[str, list[dict]]
    ) -> list[dict]:
        """필터 통과 종목에 팩터 값을 계산하여 후보 리스트 생성."""
        candidates = []
        for row in filtered:
            code = row["stock_code"]
            volume = row["volume"]
            prev_volume = row["prev_volume"]
            volume_ratio = volume / prev_volume if prev_volume else 0

            recent = recent_data.get(code, [])
            closes = [int(r["close_price"]) for r in recent if r.get("close_price")]
            highs = [int(r["high_price"]) for r in recent if r.get("high_price")]
            lows = [int(r["low_price"]) for r in recent if r.get("low_price")]

            volume_factor = calc_volume_factor(volume, prev_volume)
            momentum_factor = calc_momentum_factor(closes) if len(closes) >= 4 else 0.0
            volatility_factor = (
                calc_volatility_factor(highs, lows, closes)
                if len(highs) >= 2
                else 0.0
            )
            # 1차 스크리닝에서는 체결강도/호가잔량 미사용 → 중립값
            trade_strength_factor = 50.0
            orderbook_ratio_factor = 1.0

            candidates.append({
                "stock_code": code,
                "stock_name": row["stock_name"],
                "stock_type": row["stock_type"],
                "market_type": row["market_type"],
                "volume": volume,
                "volume_ratio": volume_ratio,
                "market_cap": row["market_cap"],
                "change_rate": float(row["change_rate"]),
                "volume_factor": volume_factor,
                "momentum_factor": momentum_factor,
                "volatility_factor": volatility_factor,
                "trade_strength_factor": trade_strength_factor,
                "orderbook_ratio_factor": orderbook_ratio_factor,
            })
        return candidates

    def _truncate_and_rank(self, scored: list[dict]) -> list[dict]:
        """스코어 상위 max_candidates개만 추출하고 rank 재부여."""
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        truncated = scored[: self.filters.max_candidates]
        for i, item in enumerate(truncated, 1):
            item["rank"] = i
        return truncated

    @staticmethod
    def _mark_hot_stocks(results: list[dict]) -> None:
        """거래량 비율 500%+ 종목에 is_hot 플래그 설정."""
        for item in results:
            item["is_hot"] = is_hot_stock(item.get("volume_ratio", 0))

    async def _fetch_today_and_prev(
        self, session: AsyncSession
    ) -> dict[str, dict]:
        """최신 2일 market_data + stocks 조인 → 종목별 당일/전일 매핑."""
        # 최근 2개 날짜 조회
        date_subq = (
            select(MarketData.data_date)
            .distinct()
            .order_by(desc(MarketData.data_date))
            .limit(2)
            .subquery()
        )

        stmt = (
            select(
                MarketData.stock_code,
                MarketData.data_date,
                MarketData.volume,
                MarketData.market_cap,
                MarketData.change_rate,
                MarketData.close_price,
                MarketData.high_price,
                MarketData.low_price,
                MarketData.open_price,
                Stock.stock_name,
                Stock.stock_type,
                Stock.market_type,
            )
            .join(Stock, MarketData.stock_code == Stock.stock_code)
            .where(
                and_(
                    MarketData.data_date.in_(select(date_subq.c.data_date)),
                    Stock.is_active.is_(True),
                )
            )
            .order_by(MarketData.stock_code, desc(MarketData.data_date))
        )

        result = await session.execute(stmt)
        rows = result.mappings().all()

        if not rows:
            return {}

        # 종목별로 당일/전일 매핑
        stock_dates: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            stock_dates[row["stock_code"]].append(dict(row))

        mapped: dict[str, dict] = {}
        for code, date_rows in stock_dates.items():
            if not date_rows:
                continue
            today_row = date_rows[0]
            prev_volume = date_rows[1]["volume"] if len(date_rows) > 1 else 0
            mapped[code] = {
                "stock_code": code,
                "stock_name": today_row["stock_name"],
                "stock_type": today_row["stock_type"],
                "market_type": today_row["market_type"],
                "volume": int(today_row["volume"] or 0),
                "prev_volume": int(prev_volume or 0),
                "market_cap": int(today_row["market_cap"] or 0),
                "change_rate": float(today_row["change_rate"] or 0),
                "close_price": int(today_row["close_price"] or 0),
                "high_price": int(today_row["high_price"] or 0),
                "low_price": int(today_row["low_price"] or 0),
            }
        return mapped

    async def _get_recent_market_data(
        self, session: AsyncSession, days: int = 5
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
                MarketData.data_date,
                MarketData.close_price,
                MarketData.high_price,
                MarketData.low_price,
            )
            .where(MarketData.data_date.in_(select(date_subq.c.data_date)))
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
                "data_date": row["data_date"],
            })
        return grouped

    async def save_results(
        self, session: AsyncSession, results: list[dict]
    ) -> int:
        """screening_results 테이블에 결과 저장 (screening_type='primary')."""
        count = 0
        for item in results:
            record = ScreeningResult(
                stock_code=item["stock_code"],
                screening_type="primary",
                score=item.get("score"),
                rank=item.get("rank"),
                factors=item.get("factors", {}),
                is_hot=item.get("is_hot", False),
                status="active",
            )
            session.add(record)
            count += 1
        await session.commit()
        return count
