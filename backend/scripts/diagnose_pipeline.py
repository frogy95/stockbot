"""스케줄러 파이프라인 상태 진단 (read-only).

scheduler:* 네임스페이스의 키, TTL, 값을 출력해
pipeline_unhealthy 차단 원인을 추정한다.

실행:
    railway run --service stockbot python scripts/diagnose_pipeline.py
또는 컨테이너 내부:
    railway ssh --service stockbot
    python scripts/diagnose_pipeline.py
"""
from __future__ import annotations

import os
import sys

import redis


SCAN_PATTERN = "scheduler:*"
KEY_FOCUS = [
    "scheduler:pipeline_healthy",
    "scheduler:premarket_pipeline:last_success",
    "scheduler:premarket_pipeline:last_failure",
    "scheduler:primary_screen:last_success",
    "scheduler:etf:last_success",
    "scheduler:dart:last_success",
    "scheduler:sentiment:last_success",
    "scheduler:atr_calibration:last_success",
]


def _decode(v):
    if v is None:
        return None
    return v.decode() if isinstance(v, (bytes, bytearray)) else v


def main() -> int:
    url = os.environ.get("REDIS_URL")
    if not url:
        print("ERROR: REDIS_URL not set", file=sys.stderr)
        return 2

    r = redis.from_url(url)

    print("=== 핵심 단계 키 (focused) ===")
    for k in KEY_FOCUS:
        ttl = r.ttl(k)
        val = _decode(r.get(k))
        print(f"{k:55s} ttl={ttl:>7}  val={val}")

    print()
    print(f"=== {SCAN_PATTERN} 전체 스캔 ===")
    keys = sorted(_decode(k) for k in r.scan_iter(SCAN_PATTERN, count=500))
    if not keys:
        print("(no keys)")
        return 0
    for k in keys:
        ttl = r.ttl(k)
        val = _decode(r.get(k))
        print(f"{k:55s} ttl={ttl:>7}  val={val}")

    print()
    print(f"총 {len(keys)}개 키")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
