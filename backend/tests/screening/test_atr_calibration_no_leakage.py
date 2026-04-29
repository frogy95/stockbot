"""Phase 8.6 Sprint 2 Task 2 — 데이터 누수 방지 (`trade_date < CURRENT_DATE`).

캘리브레이션 쿼리가 당일 row를 포함하지 않는지 단위 검증.
"""
from datetime import date
from unittest.mock import AsyncMock

import pytest

from modules.screening import atr_calibration as ac


@pytest.mark.asyncio
async def test_load_recent_atr_ratios_excludes_today():
    """SQL 쿼리에 `data_date < today` 조건이 포함되어야 한다."""
    captured = {}

    class _Result:
        def all(self):
            return []

    class _Session:
        async def execute(self, stmt):
            captured["stmt"] = stmt
            return _Result()

    today = date(2026, 4, 30)
    out, missing = await ac._load_recent_atr_ratios(
        _Session(), ["005930"], lookback_days=20, method="sma", today=today
    )
    assert out == {}
    # SQL을 문자열로 컴파일하여 누수 가드 절 검증
    sql = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert "data_date" in sql.lower()
    assert "<" in sql  # data_date < today
    # today가 SQL에 포함되어야 함
    assert "2026-04-30" in sql
