"""Phase 8.6 Sprint 2 Task 2 — KOSPI200 ATR 분위수 캘리브레이션.

08:35 KST 잡으로 KOSPI200 종목별 N영업일(기본 20) ATR/close 비율을 산출하고,
IQR ×1.5 트리밍 후 단면 P80 × ATR_CEIL_MULT(1.2)를 동적 ATR 상한으로 Redis에 캐싱한다.

폴백 3단:
  1단: market_data 결측 ≥30 OR KOSPI200 마스터 <10 → 직전일 캐시 재사용
  2단: 직전일 캐시 부재 → ATR_CEIL_HARD 정적 사용 + fallback_count INCR
  3단: fallback_count ≥3 누적 → 안전모드 (signals 발행 SAFE_MODE_TIMEOUT_MIN분 중단 + 텔레그램)

Redis 키:
  metrics:atr:ceil:{date}            (TTL 3거래일 ≈ 5일) — 동적 상한값 (HARD 캡)
  metrics:atr:dist:{date}            P10/P20/P50/P80/P95 + sample_n
  metrics:atr:ceil_grid:{date}       mult {1.0,1.1,1.2,1.3} × P80 4종 (shadow)
  metrics:atr:ceil:fallback_count    누적 폴백 카운터
  quant_dist_drift_warn:{date}       단면 P80 vs 시계열 P80(직전 5일) 차 ≥0.015
  safe_mode:active                   안전모드 신호 발행 차단 키 (TTL = SAFE_MODE_TIMEOUT_MIN분)
"""

from __future__ import annotations

import json
import logging
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.market_data import MarketData
from core.models.stock import Stock

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")

CEIL_KEY_PREFIX = "metrics:atr:ceil"
DIST_KEY_PREFIX = "metrics:atr:dist"
GRID_KEY_PREFIX = "metrics:atr:ceil_grid"
FALLBACK_COUNT_KEY = "metrics:atr:ceil:fallback_count"
DRIFT_WARN_PREFIX = "quant_dist_drift_warn"
SAFE_MODE_KEY = "safe_mode:active"

SHADOW_GRID = (1.0, 1.1, 1.2, 1.3)
DRIFT_THRESHOLD = 0.015
DAILY_TTL_3D = 60 * 60 * 24 * 5  # 약 3거래일 (주말 포함 5일)
KOSPI200_MIN_MASTER = 10
MARKET_DATA_MIN_COVERAGE_GAP = 30
FALLBACK_TO_SAFE_MODE_THRESHOLD = 3


# ---------- 순수 함수 ----------


def _apply_iqr_trim(values: list[float], k: float = 1.5) -> list[float]:
    """IQR ×k 트리밍. 길이 <4면 그대로 반환."""
    if len(values) < 4:
        return list(values)
    sorted_v = sorted(values)
    q1 = _percentile(sorted_v, 25)
    q3 = _percentile(sorted_v, 75)
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return [v for v in values if lo <= v <= hi]


def _apply_ewma(series: list[float], lambda_: float = 0.94) -> float:
    """EWMA 가중 평균 (최신값에 (1-λ), 직전값에 λ(1-λ), …).

    series 순서: 가장 오래된 → 가장 최근. 빈 리스트면 0.0.
    """
    if not series:
        return 0.0
    weight = 1 - lambda_
    ewma = series[0]
    for v in series[1:]:
        ewma = lambda_ * ewma + weight * v
    return ewma


def _percentile(sorted_values: list[float], p: float) -> float:
    """리스트가 정렬되었다고 가정. p=80 → 80번째 백분위."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (p / 100.0) * (len(sorted_values) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return sorted_values[lo]
    frac = rank - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def _atr_ratio_for_rows(rows: list[dict]) -> float | None:
    """일봉 row 리스트에서 ATR/close 비율 (단순 평균 ATR ÷ 마지막 close).

    rows 항목: {high_price, low_price, close_price} (정렬: 오래된→최신).
    """
    if len(rows) < 2:
        return None
    trs = [float(rows[0]["high_price"]) - float(rows[0]["low_price"])]
    for i in range(1, len(rows)):
        prev_close = float(rows[i - 1]["close_price"])
        h = float(rows[i]["high_price"])
        lo = float(rows[i]["low_price"])
        tr = max(h - lo, abs(h - prev_close), abs(lo - prev_close))
        trs.append(tr)
    last_close = float(rows[-1]["close_price"])
    if last_close <= 0:
        return None
    atr = sum(trs) / len(trs)
    return atr / last_close


# ---------- DB / 마스터 로딩 ----------


def _load_static_backup_codes() -> list[str]:
    """정적 백업 JSON 로드. 실패 시 빈 리스트."""
    path = Path(__file__).resolve().parent.parent.parent / "data" / "kospi200_static_backup.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        codes = data.get("codes", [])
        return [c for c in codes if isinstance(c, str)]
    except (OSError, ValueError):
        logger.warning("KOSPI200 정적 백업 JSON 로드 실패: %s", path)
        return []


async def _load_kospi200_codes(session: AsyncSession) -> list[str]:
    """`stocks.is_kospi200=True` 조회. ≥10 미만이면 정적 백업 폴백."""
    result = await session.execute(
        select(Stock.stock_code).where(Stock.is_kospi200.is_(True))
    )
    codes = [r[0] for r in result.all()]
    if len(codes) < KOSPI200_MIN_MASTER:
        backup = _load_static_backup_codes()
        if backup:
            logger.warning(
                "KOSPI200 마스터 %d종(<%d) — 정적 백업(%d) 폴백",
                len(codes), KOSPI200_MIN_MASTER, len(backup),
            )
            return backup
    return codes


async def _load_recent_atr_ratios(
    session: AsyncSession,
    codes: list[str],
    lookback_days: int,
    method: str,
    *,
    today: date,
) -> tuple[dict[str, float], int]:
    """종목별 ATR/close 비율 계산. (results, missing_count) 반환.

    누수 방지: `data_date < today` (당일 row 미포함).
    """
    if not codes:
        return {}, 0
    stmt = (
        select(
            MarketData.stock_code,
            MarketData.data_date,
            MarketData.high_price,
            MarketData.low_price,
            MarketData.close_price,
        )
        .where(MarketData.stock_code.in_(codes))
        .where(MarketData.data_date < today)
        .order_by(MarketData.stock_code, MarketData.data_date)
    )
    result = await session.execute(stmt)
    by_code: dict[str, list[dict]] = {}
    for code, d, h, lo, cl in result.all():
        if h is None or lo is None or cl is None:
            continue
        by_code.setdefault(code, []).append(
            {"high_price": h, "low_price": lo, "close_price": cl}
        )

    out: dict[str, float] = {}
    for code, rows in by_code.items():
        rows = rows[-lookback_days:]
        ratio = _atr_ratio_for_rows(rows)
        if ratio is None or ratio <= 0:
            continue
        if method == "ewma":
            # EWMA over per-day TR/close ratio sequence
            tr_ratios = []
            for i in range(1, len(rows)):
                prev_close = float(rows[i - 1]["close_price"])
                h = float(rows[i]["high_price"])
                lp = float(rows[i]["low_price"])
                tr = max(h - lp, abs(h - prev_close), abs(lp - prev_close))
                if prev_close > 0:
                    tr_ratios.append(tr / prev_close)
            if tr_ratios:
                ratio = _apply_ewma(tr_ratios, lambda_=0.94)
        out[code] = ratio
    missing = max(0, len(codes) - len(out))
    return out, missing


# ---------- Redis 헬퍼 ----------


async def _safe_set(redis: Any, key: str, value: str, ttl: int | None = None) -> None:
    try:
        await redis.set(key, value, ttl=ttl) if ttl else await redis.set(key, value)
    except TypeError:
        # 일부 클라이언트는 ttl kwarg 없음 — setex 시도
        if ttl:
            try:
                await redis.setex(key, ttl, value)
                return
            except Exception:  # noqa: BLE001
                pass
        await redis.set(key, value)
    except Exception:  # noqa: BLE001
        logger.warning("Redis set failed: %s", key, exc_info=True)


async def _safe_get(redis: Any, key: str) -> str | None:
    try:
        return await redis.get(key)
    except Exception:  # noqa: BLE001
        return None


async def _safe_incr(redis: Any, key: str) -> int:
    try:
        return await redis.incr(key)
    except (AttributeError, NotImplementedError):
        cur = await _safe_get(redis, key)
        new = (int(cur) if cur else 0) + 1
        await _safe_set(redis, key, str(new))
        return new
    except Exception:  # noqa: BLE001
        return 0


async def _record_grid_and_dist(
    redis: Any,
    *,
    today_iso: str,
    p80: float,
    sample_n: int,
    dist_pcts: dict[str, float],
) -> None:
    grid = {f"mult_{m:.1f}": min(p80 * m, settings.ATR_CEIL_HARD) for m in SHADOW_GRID}
    dist = {**dist_pcts, "sample_n": sample_n}
    await _safe_set(redis, f"{GRID_KEY_PREFIX}:{today_iso}", json.dumps(grid), DAILY_TTL_3D)
    await _safe_set(redis, f"{DIST_KEY_PREFIX}:{today_iso}", json.dumps(dist), DAILY_TTL_3D)


async def _check_drift(
    redis: Any, *, today: date, today_p80: float
) -> bool:
    """직전 5거래일 캐시된 P80 평균과 오늘 P80 차 ≥ DRIFT_THRESHOLD 시 카운터 INCR."""
    history = []
    for i in range(1, 6):
        d = today - timedelta(days=i)
        cached = await _safe_get(redis, f"{CEIL_KEY_PREFIX}:{d.isoformat()}")
        if cached:
            try:
                history.append(float(cached))
            except (TypeError, ValueError):
                continue
    if not history:
        return False
    historical_mean = sum(history) / len(history)
    if abs(today_p80 - historical_mean) >= DRIFT_THRESHOLD:
        await _safe_incr(redis, f"{DRIFT_WARN_PREFIX}:{today.isoformat()}")
        return True
    return False


async def _trigger_safe_mode(
    redis: Any, notifier: Any, *, reason: str
) -> None:
    """안전모드 진입: signals 발행 차단 + 텔레그램 알림."""
    ttl = settings.SAFE_MODE_TIMEOUT_MIN * 60
    until = (datetime.now(_KST) + timedelta(minutes=settings.SAFE_MODE_TIMEOUT_MIN)).isoformat()
    await _safe_set(redis, SAFE_MODE_KEY, json.dumps({"reason": reason, "until": until}), ttl)
    if notifier and hasattr(notifier, "send_safe_mode_alert"):
        try:
            await notifier.send_safe_mode_alert(reason=reason, until=until)
        except Exception:  # noqa: BLE001
            logger.warning("safe_mode 텔레그램 알림 실패", exc_info=True)


# ---------- 메인 진입점 ----------


async def compute_kospi200_atr_p80(
    session: AsyncSession,
    *,
    lookback_days: int = 20,
    method: str = "sma",
    today: date | None = None,
) -> tuple[float | None, dict]:
    """KOSPI200 종목별 ATR/close 비율 단면 분포 → IQR 트리밍 → P80 반환.

    Returns:
        (p80, info) — p80=None이면 데이터 부족. info에 sample_n / coverage_gap / dist 포함.
    """
    today = today or datetime.now(_KST).date()
    codes = await _load_kospi200_codes(session)
    info: dict = {"codes_loaded": len(codes), "method": method}
    if len(codes) < KOSPI200_MIN_MASTER:
        info["reason"] = "kospi200_master_insufficient"
        return None, info

    ratios, missing = await _load_recent_atr_ratios(
        session, codes, lookback_days, method, today=today
    )
    info["coverage_gap"] = missing
    info["raw_sample_n"] = len(ratios)
    if missing >= MARKET_DATA_MIN_COVERAGE_GAP:
        info["reason"] = "market_data_coverage_gap"
        return None, info

    values = list(ratios.values())
    trimmed = _apply_iqr_trim(values, k=1.5)
    if not trimmed:
        info["reason"] = "no_data_after_trim"
        return None, info
    sorted_t = sorted(trimmed)
    dist = {
        "p10": _percentile(sorted_t, 10),
        "p20": _percentile(sorted_t, 20),
        "p50": _percentile(sorted_t, 50),
        "p80": _percentile(sorted_t, 80),
        "p95": _percentile(sorted_t, 95),
    }
    info["dist"] = dist
    info["sample_n"] = len(trimmed)
    return dist["p80"], info


async def run_atr_calibration(
    session_factory: Any,
    redis_client: Any,
    notifier: Any,
    *,
    today: date | None = None,
) -> dict:
    """08:35 잡 메인 진입점. 폴백 3단 + Redis 메트릭 4종 + drift warn + 안전모드."""
    if not settings.ATR_CALIBRATION_ENABLED:
        logger.info("ATR_CALIBRATION_ENABLED=false — no-op")
        return {"status": "disabled"}

    today = today or datetime.now(_KST).date()
    today_iso = today.isoformat()

    async with session_factory() as session:
        p80, info = await compute_kospi200_atr_p80(
            session,
            lookback_days=settings.ATR_CALIBRATION_WINDOW_DAYS,
            method=settings.ATR_CALIBRATION_METHOD,
            today=today,
        )

    # Rule: 데이터 충분 → 동적 상한 저장
    if p80 is not None:
        ceil_value = min(p80 * settings.ATR_CEIL_MULT, settings.ATR_CEIL_HARD)
        await _safe_set(
            redis_client, f"{CEIL_KEY_PREFIX}:{today_iso}", f"{ceil_value:.6f}", DAILY_TTL_3D
        )
        await _record_grid_and_dist(
            redis_client,
            today_iso=today_iso,
            p80=p80,
            sample_n=info.get("sample_n", 0),
            dist_pcts=info.get("dist", {}),
        )
        drifted = await _check_drift(redis_client, today=today, today_p80=p80)
        if drifted and notifier and hasattr(notifier, "send_drift_warn"):
            try:
                await notifier.send_drift_warn(date_iso=today_iso, today_p80=p80)
            except Exception:  # noqa: BLE001
                logger.warning("drift warn 텔레그램 실패", exc_info=True)
        # 정상 사이클 — fallback_count 리셋
        await _safe_set(redis_client, FALLBACK_COUNT_KEY, "0")
        return {"status": "ok", "ceil": ceil_value, "info": info}

    # Rule: 데이터 부족 — 폴백 3단
    # 1단: 직전일 캐시 재사용
    yesterday = (today - timedelta(days=1)).isoformat()
    cached_prev = await _safe_get(redis_client, f"{CEIL_KEY_PREFIX}:{yesterday}")
    if cached_prev:
        await _safe_set(
            redis_client, f"{CEIL_KEY_PREFIX}:{today_iso}", cached_prev, DAILY_TTL_3D
        )
        return {"status": "fallback_prev_cache", "ceil": float(cached_prev), "info": info}

    # 2단: HARD 정적 + fallback_count INCR
    await _safe_set(
        redis_client,
        f"{CEIL_KEY_PREFIX}:{today_iso}",
        f"{settings.ATR_CEIL_HARD:.6f}",
        DAILY_TTL_3D,
    )
    fb_count = await _safe_incr(redis_client, FALLBACK_COUNT_KEY)

    # 3단: 누적 카운터 ≥ N → 안전모드
    if fb_count >= FALLBACK_TO_SAFE_MODE_THRESHOLD:
        await _trigger_safe_mode(
            redis_client,
            notifier,
            reason=f"atr_calibration_fallback_{fb_count}_consecutive",
        )
        return {
            "status": "safe_mode",
            "ceil": settings.ATR_CEIL_HARD,
            "fallback_count": fb_count,
            "info": info,
        }
    return {
        "status": "fallback_hard",
        "ceil": settings.ATR_CEIL_HARD,
        "fallback_count": fb_count,
        "info": info,
    }
