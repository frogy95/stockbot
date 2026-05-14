"""Phase 8.6 Sprint 5 T3 — WS trace 로그를 일별 집계로 변환.

사용법:
  docker compose exec backend python -m scripts.diagnostic.aggregate_ws_trace \
    --date 2026-05-15 --output docs/phase/phase8.6/sprint5/task3/raw/2026-05-15.json

Railway에서는 stdout 로그를 다운로드한 후 로컬에서 실행:
  railway logs --service stockbot --start "YYYY-MM-DD 00:00" > /tmp/ws-trace.log
  python aggregate_ws_trace.py --input /tmp/ws-trace.log --output ...

집계 항목 (3 root cause 후보):
  A. subscribe 한도 — `over_limit_low_priority` reject 비율, 종목별 1차 풀 진입 vs 실제 구독 차이
  B. 응답 레이스 — subscribe_request → subscribe_result 지연 분포
  C. MST sync 타이밍 — MST sync 시각 vs subscribe 요청 시각 (별도 trace 이벤트로 추후 보강)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


TRACE_PREFIX = "ws_trace "


def _iter_events(lines: Iterable[str]):
    pat = re.compile(re.escape(TRACE_PREFIX) + r"(\{.*\})$")
    for line in lines:
        m = pat.search(line)
        if not m:
            continue
        try:
            yield json.loads(m.group(1))
        except json.JSONDecodeError:
            continue


def aggregate(events: list[dict]) -> dict:
    event_counter: Counter[str] = Counter()
    reject_reasons: Counter[str] = Counter()
    per_stock_requests: Counter[str] = Counter()
    per_stock_success: Counter[str] = Counter()
    paths: Counter[str] = Counter()
    request_ts: dict[tuple[str, float], float] = {}
    latencies_ms: list[float] = []

    for e in events:
        ev = e.get("event", "unknown")
        event_counter[ev] += 1
        stock = e.get("stock_code")
        ts = e.get("ts", 0.0)
        if ev == "subscribe_request":
            request_ts[(stock, ts)] = ts
            per_stock_requests[stock] += 1
        elif ev == "subscribe_result":
            paths[e.get("path", "?")] += 1
            if e.get("ok"):
                per_stock_success[stock] += 1
            # 가장 최근 request와 매칭
            candidates = [k for k in request_ts if k[0] == stock]
            if candidates:
                latest = max(candidates, key=lambda k: k[1])
                latencies_ms.append((ts - request_ts[latest]) * 1000)
                request_ts.pop(latest, None)
        elif ev == "subscribe_reject":
            reject_reasons[e.get("reason", "?")] += 1

    total_req = sum(per_stock_requests.values())
    total_ok = sum(per_stock_success.values())

    return {
        "total_events": len(events),
        "by_event": dict(event_counter),
        "subscribe_request_total": total_req,
        "subscribe_success_total": total_ok,
        "success_rate": (total_ok / total_req) if total_req else None,
        "reject_reasons": dict(reject_reasons),
        "paths": dict(paths),
        "latency_ms": {
            "count": len(latencies_ms),
            "min": min(latencies_ms) if latencies_ms else None,
            "p50": sorted(latencies_ms)[len(latencies_ms) // 2] if latencies_ms else None,
            "max": max(latencies_ms) if latencies_ms else None,
        },
        "per_stock_top10_requests": dict(per_stock_requests.most_common(10)),
        "per_stock_top10_success": dict(per_stock_success.most_common(10)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="-", help="trace 로그 파일 (- 면 stdin)")
    parser.add_argument("--output", required=True, help="집계 결과 JSON 출력 경로")
    args = parser.parse_args()

    if args.input == "-":
        lines = sys.stdin
    else:
        lines = Path(args.input).read_text(encoding="utf-8").splitlines()

    events = list(_iter_events(lines))
    result = aggregate(events)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"집계 완료: {out_path} (events={len(events)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
