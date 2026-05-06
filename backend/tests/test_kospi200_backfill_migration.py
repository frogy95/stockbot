"""Hotfix — kospi200_static_backup.json 기준 is_kospi200 백필 마이그레이션 검증.

마이그레이션 모듈을 직접 import하여 다음을 확인:
1. revision 체인이 d2a30b8201ef → e5a7c91d4f08으로 이어진다.
2. _load_static_backup_codes()가 200개 6자리 종목 코드를 반환한다.
3. UPDATE 통계: 정적 백업 코드가 모두 stocks 테이블에 존재할 때 200건 update가 발생.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select

from core.database import get_engine
from core.models.stock import Stock


MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "e5a7c91d4f08_kospi200_master_backfill.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("hotfix_backfill", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_revision_chain():
    mod = _load_migration_module()
    assert mod.revision == "e5a7c91d4f08"
    assert mod.down_revision == "d2a30b8201ef"


def test_static_backup_loader_returns_200_codes():
    mod = _load_migration_module()
    codes = mod._load_static_backup_codes()
    assert len(codes) == 200
    assert all(isinstance(c, str) and len(c) == 6 and c.isdigit() for c in codes)
    assert len(set(codes)) == 200


@pytest.mark.asyncio
async def test_is_kospi200_backfilled_in_db():
    """마이그레이션 적용 후 stocks 테이블에서 정적 백업 코드와 교집합 종목이
    모두 is_kospi200=True로 마킹되어야 한다.

    CI/로컬 DB는 alembic upgrade head로 본 마이그레이션까지 반영된 상태여야 한다.
    """
    mod = _load_migration_module()
    static_codes = set(mod._load_static_backup_codes())

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(Stock.stock_code, Stock.is_kospi200).where(
                Stock.stock_code.in_(static_codes)
            )
        )
        rows = result.all()

    if not rows:
        pytest.skip("stocks 테이블에 정적 백업 종목 없음 (테스트 DB 미시드)")

    not_marked = [code for code, flag in rows if not flag]
    assert not not_marked, (
        f"is_kospi200=False인 정적 백업 종목 발견: {not_marked[:5]}... "
        f"(총 {len(not_marked)}건). 마이그레이션 e5a7c91d4f08 미적용 추정."
    )
