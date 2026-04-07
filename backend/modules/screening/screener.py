"""1차 스크리닝 엔진 — 장전 DB 정적 필터 + 팩터 스코어링."""
from __future__ import annotations

import logging
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
from modules.screening.scorer import FactorScorer, PRIMARY_FACTORS, PRIMARY_WEIGHTS

logger = logging.getLogger(__name__)


class PrimaryScreener:
    """장전 1차 스크리닝: DB 정적 데이터 기반 필터 + 팩터 스코어링."""

    def __init__(
        self,
        filters: PrimaryFilters | None = None,
        scorer: FactorScorer | None = None,
    ):
        self.filters = filters or PrimaryFilters()
        self.scorer = scorer or FactorScorer(
            factors={"STOCK": PRIMARY_FACTORS, "ETF": PRIMARY_FACTORS},
            factor_weights=PRIMARY_WEIGHTS,
            pass_threshold=60.0,
        )

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
        if len(filtered) < 5:
            logger.warning("1차 스크리닝 필터 통과 종목 %d개 — 소수 후보 시 백분위 왜곡 가능", len(filtered))

        candidates = self._build_candidates(filtered, recent_data)
        scored = self.scorer.score_candidates(candidates)
        result = self._truncate_and_rank(scored)
        self._mark_hot_stocks(result)
        return result

    def _apply_filters(self, rows: list[dict]) -> list[dict]:
        """필터 통과 종목만 반환."""
        passed = []
        reject_counts = {"prev_volume_zero": 0, "volume_ratio": 0, "volume_min": 0, "market_cap": 0, "change_rate": 0}
        for row in rows:
            stock_data = {
                "volume": row["volume"],
                "prev_volume": row["prev_volume"],
                "market_cap": row["market_cap"],
                "change_rate": float(row["change_rate"]),
                "stock_type": row["stock_type"],
            }
            reject_reason = self._check_filter_reject(stock_data)
            if reject_reason:
                reject_counts[reject_reason] += 1
            else:
                passed.append(row)
        logger.info(
            "1차 필터 결과: 입력=%d, 통과=%d, 탈락={prev_volume_zero=%d, volume_ratio=%d, volume_min=%d, market_cap=%d, change_rate=%d}",
            len(rows), len(passed),
            reject_counts["prev_volume_zero"], reject_counts["volume_ratio"],
            reject_counts["volume_min"], reject_counts["market_cap"], reject_counts["change_rate"],
        )
        return passed

    def _check_filter_reject(self, stock_data: dict) -> str | None:
        """필터 탈락 사유 반환. 통과 시 None."""
        prev_volume = stock_data["prev_volume"]
        if prev_volume == 0:
            return "prev_volume_zero"
        volume = stock_data["volume"]
        if volume / prev_volume < self.filters.volume_ratio:
            return "volume_ratio"
        volume_min = self.filters.volume_min_etf if stock_data["stock_type"] == "ETF" else self.filters.volume_min_stock
        if volume < volume_min:
            return "volume_min"
        if stock_data["market_cap"] < self.filters.market_cap_min:
            return "market_cap"
        change_rate = stock_data["change_rate"]
        if change_rate < self.filters.change_rate_min or change_rate > self.filters.change_rate_max:
            return "change_rate"
        return None

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
            logger.warning("_fetch_today_and_prev: DB에서 조회된 행이 0건")
            return {}

        # 날짜 분포 디버그
        date_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        for row in rows:
            d = str(row["data_date"])
            date_counts[d] = date_counts.get(d, 0) + 1
            # source는 메인 쿼리에 없으므로 date로만 집계
        logger.info("_fetch_today_and_prev: 총 %d행, 날짜별=%s", len(rows), date_counts)

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
