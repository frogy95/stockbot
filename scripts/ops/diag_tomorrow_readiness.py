"""내일 의미있는 모니터링 가능 여부 — 최종 진단 스크립트 (2026-05-12 ops).

실행:
  B64=$(base64 -i scripts/ops/diag_tomorrow_readiness.py | tr -d '\n')
  railway ssh --service stockbot "echo $B64 | base64 -d | python3"
"""
import asyncio
import os

from redis import asyncio as aioredis


async def main() -> None:
    url = os.environ.get("REDIS_URL")
    if not url:
        print("ERROR: REDIS_URL not set")
        return

    r = aioredis.from_url(url, decode_responses=True)
    print("=" * 60)
    print("내일 의미있는 모니터링 게이트 점검")
    print("=" * 60)

    # 모든 차단 키 점검 + ATR 진단
    keys = [
        # 1단 — engine.py:168 pipeline_healthy
        ("scheduler:pipeline_healthy", "engine.py:168 — !=true 시 모든 신호 차단"),
        # 2단 — engine.py:183 safe_mode
        ("safe_mode:active", "engine.py:183 — 비None 시 모든 신호 차단"),
        # 3단 — signal_generator.py:105 G3 circuit_breaker
        ("phase86:circuit_breaker:active", "signal_generator.py:105 — true 시 모든 진입 차단"),
        # 4단 — observability
        ("phase86:rollback:active", "G2 — observability only (consumer 없음)"),
        # 5단 — R3 Phase 8.5
        ("settings:override:MIN_VOLUME_FLOOR_MODE", "R3 — legacy 시 strict 0.5"),
        ("settings:override:SECONDARY_POOL_FALLBACK_ENABLED", "R3 — False 시 폴백 비활성"),
        ("settings:override:triggered_at", "R3 메타"),
        ("settings:override:reason", "R3 메타"),
        # ATR 캘리브레이션 — safe_mode 트리거 누적치
        ("screener:atr_calibration:fallback_count", "ATR 폴백 누적 → 임계 도달 시 safe_mode SET"),
    ]

    blocking_active = []
    for key, desc in keys:
        try:
            value = await r.get(key)
            ttl = await r.ttl(key)
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ {key}: ERROR {e}")
            continue
        ttl_str = f"ttl={ttl}s" if ttl > 0 else ("no-ttl" if ttl == -1 else "absent")
        print(f"  {key}")
        print(f"    {desc}")
        print(f"    value={value!r}  {ttl_str}")
        # 차단 활성 판별
        if key == "scheduler:pipeline_healthy":
            if value != "true":
                blocking_active.append((key, value, "pipeline_healthy != 'true'"))
        elif key == "safe_mode:active" and value is not None:
            blocking_active.append((key, value, "safe_mode active"))
        elif key == "phase86:circuit_breaker:active" and value is not None:
            blocking_active.append((key, value, "G3 active"))
        elif key == "settings:override:MIN_VOLUME_FLOOR_MODE" and value == "legacy":
            blocking_active.append((key, value, "R3 strict mode"))

    print()
    print("=" * 60)
    if not blocking_active:
        print("✅ 모든 신호 차단 layer 비활성")
        print("   → 내일 09:00~14:30 5.5h 매매 윈도우 신호 생성 가능")
    else:
        print("⚠️ 차단 활성 항목 발견:")
        for k, v, msg in blocking_active:
            print(f"   - {k} = {v!r} → {msg}")
    print("=" * 60)

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
