"""1차 스크리닝 엔진 — 장전 DB 정적 필터 + 팩터 스코어링."""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import replace
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
from modules.screening.scorer import FactorScorer, PRIMARY_FACTORS, PRIMARY_WEIGHTS

logger = logging.getLogger(__name__)

FALLBACK_CANDIDATE_LIMIT = 15  # 적응형 필터 0건 시 기본 후보 수

class PrimaryScreener:
    """장전 1차 스크리닝: DB 정적 데이터 기반 필터 + 팩터 스코어링."""

    def __init__(
        self,
        filters: PrimaryFilters | None = None,
        scorer: FactorScorer | None = None,
        adaptive_steps: list[float] | None = None,
        adaptive_min_candidates: int = 10,
    ):
        self.filters = filters or PrimaryFilters()
        self.scorer = scorer or FactorScorer(
            factors={"STOCK": PRIMARY_FACTORS, "ETF": PRIMARY_FACTORS},
            factor_weights=PRIMARY_WEIGHTS,
            pass_threshold=60.0,
        )
        self.adaptive_steps = adaptive_steps if adaptive_steps is not None else [1.5, 1.2]
        self.adaptive_min_candidates = adaptive_min_candidates

    async def screen(self, session: AsyncSession) -> list[dict]:
        """1차 스크리닝 실행: DB 조회 → 필터 → 스코어링 → 상위 N종목 반환."""
        today_prev = await self._fetch_today_and_prev(session)
        if not today_prev:
            return []

        recent_data = await self._get_recent_market_data(session, days=5)

        rows = list(today_prev.values())
        filtered, is_relaxed = self._apply_filters_with_adaptive(rows)

        if not filtered:
            fallback = self._get_fallback_candidates(rows)
            if fallback:
                logger.warning(
                    "1차 스크리닝 0건 — 기본 후보 %d개 투입 (거래량 상위, 시총 500억+)",
                    len(fallback),
                )
            return fallback

        if len(filtered) < 5:
            logger.warning("1차 스크리닝 필터 통과 종목 %d개 — 소수 후보 시 백분위 왜곡 가능", len(filtered))

        candidates = self._build_candidates(filtered, recent_data)
        scored = self.scorer.score_candidates(candidates)
        result = self._truncate_and_rank(scored)
        self._mark_hot_stocks(result)
        if is_relaxed:
            for item in result:
                item["is_relaxed"] = True
        return result

    def _apply_filters(
        self, rows: list[dict], filters: PrimaryFilters | None = None
    ) -> list[dict]:
        """필터 통과 종목만 반환."""
        f = filters or self.filters
        passed = []
        for row in rows:
            stock_data = {
                "volume": row["volume"],
                "prev_volume": row["prev_volume"],
                "market_cap": row["market_cap"],
                "change_rate": float(row["change_rate"]),
                "stock_type": row["stock_type"],
            }
            if passes_primary_filter(stock_data, f):
                passed.append(row)
        return passed

    def _apply_filters_with_adaptive(
        self, rows: list[dict]
    ) -> tuple[list[dict], bool]:
        """필터 통과 종목 수가 adaptive_min_candidates 미만이면 단계적 완화."""
        passed = self._apply_filters(rows)
        if len(passed) >= self.adaptive_min_candidates:
            return passed, False

        last_passed = passed
        for step in self.adaptive_steps:
            temp_filters = replace(self.filters, volume_ratio=step)
            last_passed = self._apply_filters(rows, temp_filters)
            if len(last_passed) >= self.adaptive_min_candidates:
                logger.warning(
                    "적응형 필터 적용: volume_ratio %.1f, 후보 %d개", step, len(last_passed)
                )
                return last_passed, True

        logger.warning(
            "적응형 필터 소진: 최종 후보 %d개 (volume_ratio %.1f 기준)",
            len(last_passed),
            self.adaptive_steps[-1] if self.adaptive_steps else self.filters.volume_ratio,
        )
        return last_passed, True

    def _get_fallback_candidates(self, rows: list[dict]) -> list[dict]:
        """적응형 필터 0건 시 거래량 상위 N개(시총 min 이상)를 기본 후보로 반환."""
        eligible = [r for r in rows if r.get("market_cap", 0) >= self.filters.market_cap_min]
        eligible.sort(key=lambda r: r.get("volume", 0), reverse=True)
        return [
            {
                **item,
                "is_fallback": True,
                "is_relaxed": True,
                "auto_trade_blocked": True,
                "position_size_ratio": 0.5,
                "score": 0,
                "rank": i,
                "is_passed": True,
                "factors": {},
                "volume_ratio": 0.0,
                "is_hot": False,
            }
            for i, item in enumerate(eligible[:FALLBACK_CANDIDATE_LIMIT], 1)
        ]

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

    async def _get_fallback_prev_volumes(
        self, session: AsyncSession, stock_codes: list[str]
    ) -> dict[str, int]:
        """prev_volume=0 종목들의 최근 5일 평균 거래량을 일괄 반환 (유효 3일+ 조건)."""
        if not stock_codes:
            return {}

        date_subq = (
            select(MarketData.data_date)
            .where(MarketData.source.in_(["data_go_kr", "kis_daily"]))
            .distinct()
            .order_by(desc(MarketData.data_date))
            .limit(5)
            .subquery()
        )
        stmt = (
            select(MarketData.stock_code, MarketData.volume)
            .where(
                MarketData.stock_code.in_(stock_codes),
                MarketData.data_date.in_(select(date_subq.c.data_date)),
                MarketData.source.in_(["data_go_kr", "kis_daily"]),
                MarketData.volume > 0,
            )
            .order_by(MarketData.stock_code, desc(MarketData.data_date))
        )
        result = await session.execute(stmt)

        volumes_by_code: dict[str, list[int]] = defaultdict(list)
        for code, volume in result.all():
            if volume:
                volumes_by_code[code].append(int(volume))

        return {
            code: sum(vols) // len(vols)
            for code, vols in volumes_by_code.items()
            if len(vols) >= 3
        }

    async def _fetch_today_and_prev(
        self, session: AsyncSession
    ) -> dict[str, dict]:
        """최신 2일 market_data + stocks 조인 → 종목별 당일/전일 매핑."""
        # 최근 2개 날짜 조회 — data_go_kr/kis_daily 소스만 사용 (KIS 실시간 ETF 날짜 오염 방지)
        date_subq = (
            select(MarketData.data_date)
            .where(MarketData.source.in_(["data_go_kr", "kis_daily"]))
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
                Stock.listed_shares,
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
            market_cap = int(today_row["market_cap"] or 0)
            if market_cap == 0 and today_row["listed_shares"] and today_row["close_price"]:
                market_cap = int(today_row["listed_shares"]) * int(today_row["close_price"])
            mapped[code] = {
                "stock_code": code,
                "stock_name": today_row["stock_name"],
                "stock_type": today_row["stock_type"],
                "market_type": today_row["market_type"],
                "volume": int(today_row["volume"] or 0),
                "prev_volume": int(prev_volume or 0),
                "market_cap": market_cap,
                "change_rate": float(today_row["change_rate"] or 0),
                "close_price": int(today_row["close_price"] or 0),
                "high_price": int(today_row["high_price"] or 0),
                "low_price": int(today_row["low_price"] or 0),
            }

        # prev_volume=0 종목 일괄 폴백 (N+1 방지)
        zero_codes = [code for code, data in mapped.items() if data["prev_volume"] == 0]
        if zero_codes:
            fallback_map = await self._get_fallback_prev_volumes(session, zero_codes)
            for code, fallback_vol in fallback_map.items():
                mapped[code]["prev_volume"] = fallback_vol

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
