"""Phase 8.6 Sprint 5 T2 Step 3 — secondary 4시간 윈도우 종목 교체율 측정.

#14 진단 대상: secondary 풀 4h 100% 교체율이 (a) 데이터 신호 부족(저거래량 시간대 정상)
인지 (b) hysteresis 부재로 인한 구조 결함인지 정량 판정.

산출 로직:
- 기준 시점 t (KST 09:30 / 11:30 / 13:30) 마다 직전 4시간 윈도우 [t-4h, t]의
  screening_type='secondary' 종목 집합 A
- 비교 윈도우 [t-8h, t-4h] 종목 집합 B
- jaccard = |A ∩ B| / |A ∪ B|, churn_rate = 1 - jaccard
- 분모=0(어느 한쪽 풀이 비어있음)일 때 churn은 None — fail-safe
- 일별 / 시간대별 결과 표 + 종합 결론용 평균 churn

DB 의존:
- screening_results.screening_type='secondary'
- screening_results.screened_at (timezone-aware)

사용법:
  docker compose exec backend python -c "import asyncio; from scripts.diagnostic.secondary_churn import compute_churn_4h; asyncio.run(compute_churn_4h(days=5))"
  docker compose exec backend python -m scripts.diagnostic.secondary_churn --days 5 \
    --output docs/phase/phase8.6/sprint5/task2/t2-secondary-churn-db-snapshot.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select

from core.config import settings
from core.database import get_session_factory
from core.models.screening_result import ScreeningResult

CHECK_HOURS = (9, 30), (11, 30), (13, 30)  # KST 기준 점검 시각
WINDOW_HOURS = 4


def _kst() -> ZoneInfo:
    return ZoneInfo(settings.MARKET_TIMEZONE)


async def _fetch_codes(session, start_utc: datetime, end_utc: datetime) -> set[str]:
    """screened_at ∈ [start_utc, end_utc) 의 secondary 종목 집합."""
    stmt = (
        select(ScreeningResult.stock_code)
        .where(
            ScreeningResult.screening_type == "secondary",
            ScreeningResult.screened_at >= start_utc,
            ScreeningResult.screened_at < end_utc,
        )
        .distinct()
    )
    rows = (await session.execute(stmt)).scalars().all()
    return set(rows)


async def compute_churn_4h(days: int = 5) -> dict[str, Any]:
    """최근 days 거래일에 대해 KST 점검 시각별 4h 윈도우 churn 산출.

    Returns:
        {
            "days": int,
            "rows": [{"date","check_at_kst","current_pool","prev_pool","intersect","union","jaccard","churn_rate"}],
            "summary": {"mean_churn","p50_churn","n_samples","null_samples"},
        }
    """
    tz = _kst()
    today_kst = datetime.now(tz).date()
    rows: list[dict[str, Any]] = []
    null_samples = 0

    factory = get_session_factory()
    async with factory() as session:
        for offset in range(days):
            d = today_kst - timedelta(days=offset)
            for h, m in CHECK_HOURS:
                check_kst = datetime.combine(d, time(h, m), tzinfo=tz)
                current_start = check_kst - timedelta(hours=WINDOW_HOURS)
                prev_start = current_start - timedelta(hours=WINDOW_HOURS)

                current_pool = await _fetch_codes(
                    session, current_start.astimezone(ZoneInfo("UTC")), check_kst.astimezone(ZoneInfo("UTC"))
                )
                prev_pool = await _fetch_codes(
                    session, prev_start.astimezone(ZoneInfo("UTC")), current_start.astimezone(ZoneInfo("UTC"))
                )

                inter = current_pool & prev_pool
                union = current_pool | prev_pool

                if not union:
                    jaccard = None
                    churn = None
                    null_samples += 1
                else:
                    jaccard = len(inter) / len(union)
                    churn = 1.0 - jaccard

                rows.append({
                    "date": d.isoformat(),
                    "check_at_kst": check_kst.strftime("%Y-%m-%d %H:%M"),
                    "current_pool": len(current_pool),
                    "prev_pool": len(prev_pool),
                    "intersect": len(inter),
                    "union": len(union),
                    "jaccard": round(jaccard, 4) if jaccard is not None else None,
                    "churn_rate": round(churn, 4) if churn is not None else None,
                })

    # 요약 통계 (None 제외)
    valid = [r["churn_rate"] for r in rows if r["churn_rate"] is not None]
    valid_sorted = sorted(valid)
    if valid:
        mean_churn = sum(valid) / len(valid)
        p50 = valid_sorted[len(valid_sorted) // 2]
    else:
        mean_churn = None
        p50 = None

    result = {
        "days": days,
        "rows": rows,
        "summary": {
            "mean_churn": round(mean_churn, 4) if mean_churn is not None else None,
            "p50_churn": round(p50, 4) if p50 is not None else None,
            "n_samples": len(valid),
            "null_samples": null_samples,
        },
    }

    # 사람이 보기 좋게 stdout 출력 (CLI 사용 시)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# T2 Step 3 — #14 secondary 4h 교체율 DB 측정 스냅샷",
        "",
        f"- 측정 일자(KST): 최근 {result['days']}거래일 × 점검 시각 3종(09:30/11:30/13:30)",
        f"- 윈도우: 직전 {WINDOW_HOURS}h vs 그 이전 {WINDOW_HOURS}h, jaccard 기반 churn",
        f"- 데이터 소스: `screening_results` (screening_type='secondary')",
        "",
        "## 일별 × 시간대별 churn 표",
        "",
        "| date | check (KST) | current pool | prev pool | inter | union | jaccard | churn |",
        "|------|-------------|--------------|-----------|-------|-------|---------|-------|",
    ]
    for r in result["rows"]:
        lines.append(
            f"| {r['date']} | {r['check_at_kst']} | {r['current_pool']} | {r['prev_pool']} | "
            f"{r['intersect']} | {r['union']} | {r['jaccard']} | {r['churn_rate']} |"
        )

    s = result["summary"]
    lines += [
        "",
        "## 요약",
        "",
        f"- 평균 churn: **{s['mean_churn']}**",
        f"- 중앙 churn (p50): {s['p50_churn']}",
        f"- 유효 샘플: {s['n_samples']} / null(풀 공집합): {s['null_samples']}",
        "",
        "## 판정",
        "",
        "> 임계값 변경 없는 진단 Sprint이므로 결론은 후속 Task 5(종합 보고)에서 통합 판정.",
        "> 본 스냅샷은 raw 측정치만 제공한다.",
        "",
        "- **데이터 부족 가설**: current_pool / prev_pool 한쪽이 0 또는 매우 작음 → 저거래량 시간대로 정상",
        "- **구조 결함 가설**: 양쪽 풀 모두 충분히 크나(>30) churn ≥ 0.9 → hysteresis 부재로 인한 교체",
        "",
        "## 한계",
        "",
        "- `screening_results.screened_at` 가 KST 09~16시 사이 균등하게 적재된다는 가정. 실제 적재 분포는 raw 표의 union 컬럼으로 검증 가능.",
        "- 시간대별 거래량 정규화 없음 — 13:30 점검은 점심시간 영향으로 prev 풀이 작을 수 있음.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=5)
    p.add_argument("--output", type=str, default=None, help="Markdown 출력 파일 경로")
    args = p.parse_args()

    result = asyncio.run(compute_churn_4h(days=args.days))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_render_markdown(result), encoding="utf-8")
        print(f"[OK] Markdown saved: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
