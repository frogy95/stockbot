"""Phase 8.6 Sprint 5 T2 Step 1 — #10 breakout 72.2% 편중 진단용 walkforward 진입점.

목적:
  Sprint 4 walkforward 인프라(`backend/modules/backtest/walkforward.py`)를 재활용하여
  60거래일 KOSPI200 일봉 데이터로 tier별 reject(=1 - pass_rate) 분포를 산출한다.
  신규 백테스트 코드 작성 금지 — 기존 `WalkForwardRunner.run()` + `simulate_tier_pass_rate`만 호출.

한계 (사전 인지):
  - walkforward.py docstring에 명시: 분봉 부재로 momentum_breakout/volume_surge 정확 시뮬 불가.
  - 본 진단은 일별 |pct_change|/stddev 기반 단순 모델 결과 + DB 실측(trade_signals) 비교.
  - 60일 KOSPI200 일봉 캐시 미충족 시 `DatasetInsufficientError` 발생 — 부분 결과
    (simulate_tier_pass_rate 직호출)을 별도로 캡처해 보고서에 부분 산출.

사용법:
  docker compose exec backend python -m scripts.diagnostic.run_stage_reject_breakdown \
    --days 60 --output docs/phase/phase8.6/sprint5/task2/t2-backtest-report.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, func

from core.config import settings
from core.database import get_session_factory
from core.models.market_data import MarketData
from core.models.stock import Stock
from modules.backtest.historical_loader import (
    DatasetInsufficientError,
    classify_regime,
    load_kospi_daily,
)
from modules.backtest.walkforward import (
    TIER_NAMES,
    WalkForwardRunner,
    compute_actual_pass_rate,
    simulate_tier_pass_rate,
)


DEFAULT_TIER_CFG = {
    "prev_high": {"volume_threshold": 2.0, "atr_floor": 0.025, "atr_ceil": 0.0739},
    "gap_open": {"gap_min": 3.0, "atr_ceil_hard": 0.08},
    "prev_close": {"volume_threshold": 2.5},
    "volume_surge": {"vol_ratio": 5.0, "bid_ask_ratio": 2.0, "price_threshold": 0.5},
}


async def _dataset_summary(session) -> dict[str, Any]:
    """KOSPI200 일봉 캐시 진단 요약."""
    stmt = (
        select(
            func.count(func.distinct(MarketData.data_date)).label("days"),
            func.min(MarketData.data_date).label("min_d"),
            func.max(MarketData.data_date).label("max_d"),
        )
        .join(Stock, Stock.stock_code == MarketData.stock_code)
        .where(
            Stock.is_kospi200.is_(True),
            MarketData.source.in_(("data_go_kr", "kis_daily")),
        )
    )
    row = (await session.execute(stmt)).one()
    return {
        "trading_days": int(row.days or 0),
        "min_date": row.min_d.isoformat() if row.min_d else None,
        "max_date": row.max_d.isoformat() if row.max_d else None,
    }


async def run_diagnostic(days: int, period_end: date) -> dict[str, Any]:
    """walkforward.run() 호출 + 데이터 부족 시 partial fallback."""
    out: dict[str, Any] = {
        "period_end": period_end.isoformat(),
        "requested_days": days,
        "full_run": None,
        "partial_run": None,
        "errors": [],
    }

    factory = get_session_factory()
    async with factory() as session:
        out["dataset_summary"] = await _dataset_summary(session)

        # 시도 1 — 정식 WalkForwardRunner
        try:
            runner = WalkForwardRunner(session=session)
            result = await runner.run(period_end=period_end, n_days=days)
            out["full_run"] = {
                "success": result.success,
                "run_id": result.run_id,
                "error": result.error,
                "pass_rates_simulated": result.pass_rates,
            }
        except DatasetInsufficientError as e:
            out["errors"].append({"phase": "full_run", "error": str(e)})
        except Exception as e:  # pragma: no cover
            out["errors"].append({
                "phase": "full_run",
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            })

        # 시도 2 — partial: load_kospi_daily 가능한 만큼 + 시뮬만 산출
        try:
            # n_days를 보유량으로 자동 조정
            available = out["dataset_summary"]["trading_days"]
            partial_n = max(2, min(days, available))
            series = await load_kospi_daily(session, period_end=period_end, n_days=partial_n)
            sim_rates = simulate_tier_pass_rate(series, DEFAULT_TIER_CFG)
            regime = classify_regime(series)

            # 박스/추세 일별 라벨로 시리즈 분할 후 tier별 시뮬 비교
            labels = regime["labels"]
            box_series = [r for r, lab in zip(series, labels) if lab == "box"]
            trend_series = [r for r, lab in zip(series, labels) if lab == "trend"]
            sim_box = simulate_tier_pass_rate(box_series, DEFAULT_TIER_CFG) if box_series else {}
            sim_trend = simulate_tier_pass_rate(trend_series, DEFAULT_TIER_CFG) if trend_series else {}

            # 실측 (trade_signals — 로컬 0건 가능)
            actual = await compute_actual_pass_rate(
                session,
                period_start=series[0]["date"],
                period_end=series[-1]["date"],
            )

            out["partial_run"] = {
                "n_days_used": len(series),
                "regime": {
                    "box_days": regime["box_days"],
                    "trend_days": regime["trend_days"],
                    "sigma_long_term": regime["sigma_long_term"],
                },
                "pass_rates_simulated_all": sim_rates,
                "pass_rates_simulated_box": sim_box,
                "pass_rates_simulated_trend": sim_trend,
                "pass_rates_actual_db": actual,
                "reject_rates_all": {t: round(1.0 - sim_rates.get(t, 0.0), 4) for t in TIER_NAMES},
                "reject_rates_box": {t: round(1.0 - sim_box.get(t, 0.0), 4) for t in TIER_NAMES} if sim_box else {},
                "reject_rates_trend": {t: round(1.0 - sim_trend.get(t, 0.0), 4) for t in TIER_NAMES} if sim_trend else {},
            }
        except DatasetInsufficientError as e:
            out["errors"].append({"phase": "partial_run", "error": str(e)})
        except Exception as e:  # pragma: no cover
            out["errors"].append({
                "phase": "partial_run",
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            })

    return out


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# T2 Step 1 — #10 breakout 72.2% 편중 walk-forward 진단 보고서",
        "",
        "> Sprint 4 walkforward 인프라(`backend/modules/backtest/walkforward.py`)를 재활용한 60거래일 진단.",
        "> 신규 백테스트 코드 작성 없음 — `WalkForwardRunner.run` + `simulate_tier_pass_rate` 호출만.",
        "",
        "## 데이터셋 진단",
        "",
        f"- 요청: `period_end={result['period_end']}, n_days={result['requested_days']}`",
        f"- 보유: KOSPI200 일봉(`data_go_kr`/`kis_daily`) {result['dataset_summary']['trading_days']}거래일 ({result['dataset_summary']['min_date']} ~ {result['dataset_summary']['max_date']})",
        f"- 충족 요구: 60거래일 (`is_dataset_sufficient`: box≥20 AND trend≥20 AND total≥60)",
        "",
    ]

    full = result.get("full_run")
    if full and full.get("success"):
        lines += [
            "## 정식 WalkForwardRunner.run 결과",
            "",
            f"- run_id: {full['run_id']}",
            f"- 시뮬 pass_rate: `{full['pass_rates_simulated']}`",
            "",
        ]
    else:
        lines += [
            "## 정식 WalkForwardRunner.run — 실패",
            "",
            "60거래일 + box≥20 + trend≥20 데이터 부족으로 `DatasetInsufficientError` 발생.",
            "에러 상세:",
            "",
            "```",
        ]
        for err in result.get("errors", []):
            if err.get("phase") == "full_run":
                lines.append(err["error"])
        lines += ["```", ""]

    partial = result.get("partial_run")
    if partial:
        lines += [
            "## Partial 진단 (보유 일수 기준)",
            "",
            f"- 사용 일수: {partial['n_days_used']}거래일 (요청 {result['requested_days']}일 중 보유분)",
            f"- regime 분류: box={partial['regime']['box_days']}일 / trend={partial['regime']['trend_days']}일 / sigma_long_term={partial['regime']['sigma_long_term']:.4f}",
            "",
            "### tier별 reject_rate 분포 (시뮬, 단순 모델)",
            "",
            "| tier | reject_all | reject_box | reject_trend | pass_simulated | pass_actual_db |",
            "|------|-----------:|-----------:|-------------:|---------------:|---------------:|",
        ]
        for t in TIER_NAMES:
            lines.append(
                f"| {t} | {partial['reject_rates_all'].get(t)} | "
                f"{partial['reject_rates_box'].get(t, 'n/a')} | "
                f"{partial['reject_rates_trend'].get(t, 'n/a')} | "
                f"{partial['pass_rates_simulated_all'].get(t, 0.0):.4f} | "
                f"{partial['pass_rates_actual_db'].get(t, 0.0):.4f} |"
            )
        lines.append("")

    lines += [
        "## #10 결론 (정량 판정)",
        "",
        "> 임계 변경 0건. raw 산출만 제공하고 후속 Task 5에서 통합 판정.",
        "",
    ]

    if not full or not full.get("success"):
        lines += [
            "- **정식 60일 walkforward 미수행** — 로컬 KIS 일봉 캐시 부족으로 #10의 '자연 분포 vs 구조 결함' 정량 판정 **불가**.",
            "- Partial 진단의 시뮬 reject 분포는 일별 평균 등락률 기반 단순 모델 결과로 prod momentum_breakout/volume_surge 진입과 직접 대응하지 않음 (walkforward.py docstring 명시 한계).",
            "- 'breakout 72.2% 편중' 주장은 prod `trade_signals.strategy_name` 분포 통계 — 본 인프라 산출물이 아님.",
            "",
            "## 후속 액션 (Task 5 입력)",
            "",
            "1. **KIS 일봉 백필** (Phase 9 Sprint 0 또는 별도 핫픽스): 90~120거래일 보강 → `WalkForwardRunner.run` 정상 동작.",
            "2. **prod `trade_signals` 직접 집계**: `SELECT strategy_name, count(*) FROM trade_signals GROUP BY 1 WHERE created_at > now() - interval '14 days'` 로 실제 strategy 분포 측정 — '72.2% breakout' 출처 재확인.",
            "3. **분봉 백필 후 정밀 시뮬 교체**: walkforward.py docstring(Phase 9 Sprint 0) 계획 그대로 진행.",
        ]
    else:
        lines += [
            "- 정식 60일 walkforward 실행 성공. 시뮬 vs 실측 격차는 위 표 참조.",
            "- 자연 분포 vs 구조 결함 판정은 Task 5 종합 보고에서 통합.",
        ]

    lines += [
        "",
        "## 검증 명령 재현",
        "",
        "```bash",
        "docker compose exec backend python -m scripts.diagnostic.run_stage_reject_breakdown \\",
        "  --days 60 --output docs/phase/phase8.6/sprint5/task2/t2-backtest-report.md",
        "```",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=60)
    p.add_argument(
        "--period-end",
        type=str,
        default=None,
        help="YYYY-MM-DD (KST). 미지정 시 KST 어제.",
    )
    p.add_argument("--output", type=str, default=None)
    args = p.parse_args()

    if args.period_end:
        period_end = date.fromisoformat(args.period_end)
    else:
        tz = ZoneInfo(settings.MARKET_TIMEZONE)
        period_end = (datetime.now(tz)).date()

    result = asyncio.run(run_diagnostic(args.days, period_end))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_render_markdown(result), encoding="utf-8")
        print(f"[OK] Markdown saved: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
