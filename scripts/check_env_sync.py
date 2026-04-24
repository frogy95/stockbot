"""`.env.example`과 `backend/core/config.py::Settings` 환경변수 이름 집합 동기화 검증.

사용: 프로젝트 루트에서 `python scripts/check_env_sync.py`
- env.example에만 존재 / Settings에만 존재하는 변수를 검출.
- 성공 시 exit 0, 불일치 시 exit 1.

Settings의 property(`database_url`, `redis_url` 등)와 내부 `REDIS_URL` 등
`.env.example`에 공개되지 않는 내부 전용 필드는 화이트리스트로 제외.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT / ".env.example"
BACKEND_DIR = ROOT / "backend"

# Settings에는 존재하지만 .env.example에는 의도적으로 노출하지 않는 내부 필드
SETTINGS_INTERNAL_ONLY = {"REDIS_URL", "MARKET_TIMEZONE"}

# .env.example에만 존재하고 백엔드 Settings는 참조하지 않는 변수
# (Docker Compose / 프론트엔드 전용 등)
ENV_ONLY_KEYS = {"INTERNAL_API_URL"}


def parse_env_example(path: Path) -> set[str]:
    keys: set[str] = set()
    pattern = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)\s*=")
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = pattern.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def parse_settings_fields() -> set[str]:
    sys.path.insert(0, str(BACKEND_DIR))
    from core.config import Settings  # type: ignore

    return set(Settings.model_fields.keys())


def main() -> int:
    env_keys = parse_env_example(ENV_EXAMPLE) - ENV_ONLY_KEYS
    settings_keys = parse_settings_fields() - SETTINGS_INTERNAL_ONLY

    missing_in_settings = env_keys - settings_keys
    missing_in_env = settings_keys - env_keys

    if missing_in_settings or missing_in_env:
        if missing_in_settings:
            print("❌ .env.example에만 있고 Settings에 없음:")
            for k in sorted(missing_in_settings):
                print(f"  - {k}")
        if missing_in_env:
            print("❌ Settings에만 있고 .env.example에 없음:")
            for k in sorted(missing_in_env):
                print(f"  - {k}")
        return 1

    print(f"OK: {len(env_keys)} variables synced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
