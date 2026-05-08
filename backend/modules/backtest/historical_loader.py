"""백테스트 60일 일봉 데이터 로더 + 박스권/추세장 분류기.

설계 메모:
- KOSPI200 종목 일봉을 거래일별로 횡단면 평균 종가(avg_close), 등락률(pct_change),
  횡단면 표준편차(stddev)로 집계해 시계열을 만든다.
- regime 분류: 직전 20일 등락률 표준편차(rolling σ)가 전체 시계열 σ_long_term × 1.5 이하면
  "box"(박스권), 초과면 "trend"(추세장). 첫 19일은 rolling 윈도우 부족으로 "box" 기본값.
- 데이터셋 충분성: 박스권 ≥20 AND 추세장 ≥20 AND 총 ≥60.
- backfill helper: 거래일 단위로 KISDailyCollector.collect_all 순차 호출 (1초 sleep).
"""

from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from core.models.market_data import MarketData
from core.models.stock import Stock
from core.trading_calendar import is_trading_day

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from core.clients.kis_rest import KISRestClient

logger = logging.getLogger(__name__)

_KOSPI_DAILY_SOURCES = ("data_go_kr", "kis_daily")
_LOAD_MARGIN_DAYS = 90  # 휴장 보정 — 60거래일 확보 마진
_REGIME_ROLLING_WINDOW = 20
_REGIME_SIGMA_MULTIPLIER = 1.5
_REQUIRED_BOX_DAYS = 20
_REQUIRED_TREND_DAYS = 20
_REQUIRED_TOTAL_DAYS = 60


class DatasetInsufficientError(Exception):
    """60일 백테스트 데이터셋 충분성 미충족."""


async def load_kospi_daily(
    session: "AsyncSession",
    period_end: date,
    n_days: int = 60,
) -> list[dict]:
    """KOSPI200 종목 일봉을 거래일별 횡단면 집계해 시계열로 반환.

    Args:
        session: SQLAlchemy async session
        period_end: 시계열 마지막 날짜 (포함)
        n_days: 필요한 거래일 수 (충족 미달 시 DatasetInsufficientError)

    Returns:
        list of {"date": date, "avg_close": float, "pct_change": float, "stddev": float}
        날짜 오름차순. pct_change는 첫 day 0.0, 이후 (today-prev)/prev*100.

    Raises:
        DatasetInsufficientError: 거래일 수 < n_days
    """
    period_start = period_end - timedelta(days=_LOAD_MARGIN_DAYS)

    stmt = (
        select(
            MarketData.data_date,
            func.avg(MarketData.close_price).label("avg_close"),
            func.stddev_pop(MarketData.close_price).label("stddev"),
        )
        .join(Stock, Stock.stock_code == MarketData.stock_code)
        .where(
            Stock.is_kospi200.is_(True),
            MarketData.source.in_(_KOSPI_DAILY_SOURCES),
            MarketData.data_date >= period_start,
            MarketData.data_date <= period_end,
            MarketData.close_price.is_not(None),
        )
        .group_by(MarketData.data_date)
        .order_by(MarketData.data_date.asc())
    )

    result = await session.execute(stmt)
    rows = list(result.all())

    if len(rows) < n_days:
        raise DatasetInsufficientError(
            f"KOSPI200 일봉 거래일 부족: {len(rows)}일 < 요구 {n_days}일 "
            f"(period_end={period_end}, lookback={_LOAD_MARGIN_DAYS}일)"
        )

    # 마지막 n_days만 사용 (오름차순)
    rows = rows[-n_days:]

    series: list[dict] = []
    prev_close: float | None = None
    for data_date, avg_close, stddev in rows:
        avg_close_f = float(avg_close) if avg_close is not None else 0.0
        stddev_f = float(stddev) if stddev is not None else 0.0
        if prev_close is None or prev_close == 0:
            pct = 0.0
        else:
            pct = (avg_close_f - prev_close) / prev_close * 100.0
        series.append({
            "date": data_date,
            "avg_close": avg_close_f,
            "pct_change": pct,
            "stddev": stddev_f,
        })
        prev_close = avg_close_f

    return series


def _stddev(values: list[float]) -> float:
    """모집단 표준편차 — len<2일 때도 0.0 반환."""
    return statistics.pstdev(values) if len(values) >= 2 else 0.0


def classify_regime(daily_series: list[dict]) -> dict:
    """20일 rolling σ로 박스권/추세장 일별 라벨링.

    σ_long_term: 전체 시계열 등락률 표준편차 (명세 §Task 2 정의)
    각 일별: 직전 20일 등락률 σ ≤ σ_long_term × 1.5 → "box", 초과 → "trend"
    초기 19일은 rolling 윈도우 부족 → "box" 기본값.

    NOTE(설계 결정): 본 분류기는 다수 모드(우세 regime) 베이스라인 위에서
    소수 모드 구간을 검출하는 구조다 — `trend_days > box_days` 시나리오는
    수학적으로 도달하기 어렵다. Task 3 walkforward에서 임계 진단 시,
    box/trend 일수 비율과 regime shift 시점만 사용한다.
    """
    pct_series = [r["pct_change"] for r in daily_series]
    n = len(pct_series)
    sigma_long = _stddev(pct_series)
    threshold = sigma_long * _REGIME_SIGMA_MULTIPLIER

    labels: list[str] = []
    for i in range(n):
        if i < _REGIME_ROLLING_WINDOW - 1:
            labels.append("box")
            continue
        window = pct_series[i - _REGIME_ROLLING_WINDOW + 1 : i + 1]
        rolling_sigma = _stddev(window)
        labels.append("box" if rolling_sigma <= threshold else "trend")

    box_days = sum(1 for label in labels if label == "box")
    trend_days = sum(1 for label in labels if label == "trend")

    return {
        "box_days": box_days,
        "trend_days": trend_days,
        "labels": labels,
        "sigma_long_term": sigma_long,
        "threshold": threshold,
    }


def is_dataset_sufficient(summary: dict) -> bool:
    """박스권 ≥20 AND 추세장 ≥20 AND 총 ≥60 충족 시 True."""
    box = summary.get("box_days", 0)
    trend = summary.get("trend_days", 0)
    total = len(summary.get("labels", []))
    return (
        box >= _REQUIRED_BOX_DAYS
        and trend >= _REQUIRED_TREND_DAYS
        and total >= _REQUIRED_TOTAL_DAYS
    )


async def backfill_missing_daily(
    session: "AsyncSession",
    start_date: date,
    end_date: date,
    rest_client: "KISRestClient | None" = None,
) -> int:
    """[start_date, end_date] 범위 거래일별 KISDailyCollector.collect_all 순차 호출.

    Returns: 호출된 거래일 수.

    KIS Rate Limit 보호를 위해 거래일 간 1초 sleep.

    rest_client 가 None 이면 호출자가 KIS 인프라에 접근할 수 없는 컨텍스트이므로
    ValueError 를 발생시켜 잘못된 사용을 조기에 차단한다 (운영 시 app.state.kis_inquiry 주입 필수).
    """
    # 지연 import — KIS 클라이언트는 helper 사용 시점에만 필요.
    from modules.collector.sources.kis_daily_collector import KISDailyCollector

    if rest_client is None:
        raise ValueError(
            "backfill_missing_daily 는 rest_client (KISRestClient) 주입을 요구합니다. "
            "FastAPI 라우트에서는 request.app.state.kis_inquiry 를 전달하세요."
        )

    collector = KISDailyCollector(rest_client, session)

    days_called = 0
    current = start_date
    while current <= end_date:
        if is_trading_day(current):
            target_date_str = current.strftime("%Y%m%d")
            try:
                await collector.collect_all(target_date=target_date_str)
                days_called += 1
            except Exception:  # pragma: no cover — 운영 시 부분 실패 허용
                logger.exception("백필 실패: %s", target_date_str)
            await asyncio.sleep(1)
        current += timedelta(days=1)

    logger.info("KIS 일봉 백필 완료: %d 거래일 (%s ~ %s)", days_called, start_date, end_date)
    return days_called
