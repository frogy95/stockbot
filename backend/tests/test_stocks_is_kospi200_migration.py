"""Phase 8.6 Sprint 2 Task 1 — `stocks.is_kospi200` 컬럼/인덱스/기본값 검증."""
import json
from pathlib import Path

import pytest
from sqlalchemy import inspect

from core.database import get_engine
from core.models.stock import Stock


@pytest.mark.asyncio
async def test_is_kospi200_column_exists():
    engine = get_engine()
    async with engine.connect() as conn:
        def _inspect(sync_conn):
            insp = inspect(sync_conn)
            cols = {c["name"]: c for c in insp.get_columns("stocks")}
            indexes = insp.get_indexes("stocks")
            return cols, indexes

        cols, indexes = await conn.run_sync(_inspect)

    assert "is_kospi200" in cols
    assert cols["is_kospi200"]["nullable"] is False
    # server_default=False 확인
    default = cols["is_kospi200"].get("default")
    assert default is not None and "false" in str(default).lower()
    # 인덱스
    index_names = {ix["name"] for ix in indexes}
    assert "ix_stocks_is_kospi200" in index_names


def test_static_backup_json_contains_200_codes():
    """정적 백업 JSON 파일이 200 종목 포함 — KRX 분기 리밸런싱 폴백."""
    path = Path(__file__).resolve().parent.parent / "data" / "kospi200_static_backup.json"
    assert path.exists(), f"missing: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "codes" in data
    codes = data["codes"]
    assert len(codes) == 200
    # 6자리 stock_code 형식 확인
    assert all(isinstance(c, str) and len(c) == 6 and c.isdigit() for c in codes)
    # 중복 없음
    assert len(set(codes)) == 200
