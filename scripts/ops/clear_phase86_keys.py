"""Phase 8.6 G2/G3 차단 키 manual DEL — 2026-05-12 ops.

실행 (로컬에서):
  cat scripts/ops/clear_phase86_keys.py | railway ssh --service stockbot "python3"

또는 컨테이너 내부:
  railway ssh --service stockbot
  # 컨테이너 진입 후
  python3 << 'EOF'
  <이 파일 내용 붙여넣기>
  EOF
"""
import asyncio
import os

from redis import asyncio as aioredis


TARGETS = [
    "phase86:rollback:active",
    "phase86:circuit_breaker:active",
    # G3 동시 차단되는 Phase 8.5 폴백 키도 함께 정리 (G3 발동 시 동시 SET됨)
    "settings:override:SECONDARY_POOL_FALLBACK_ENABLED",
    "settings:override:MIN_VOLUME_FLOOR_MODE",
    "settings:override:triggered_at",
    "settings:override:reason",
]


async def main() -> None:
    url = os.environ.get("REDIS_URL")
    if not url:
        print("ERROR: REDIS_URL not set")
        return

    r = aioredis.from_url(url, decode_responses=True)
    print(f"connected: {url.split('@')[-1] if '@' in url else url}")
    print()

    print("=== BEFORE ===")
    for k in TARGETS:
        v = await r.get(k)
        ttl = await r.ttl(k)
        print(f"  {k!r}\n    value={v!r}  ttl={ttl}s")

    print()
    print("=== DELETE ===")
    deleted_total = 0
    for k in TARGETS:
        result = await r.delete(k)
        deleted_total += int(result or 0)
        print(f"  DEL {k} -> {result}")

    print()
    print("=== AFTER ===")
    for k in TARGETS:
        v = await r.get(k)
        print(f"  {k!r}\n    value={v!r}")

    print()
    print(f"deleted_total={deleted_total}")
    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
