"""Hotfix — kospi200_static_backup.json 기준 stocks.is_kospi200 백필

Revision ID: e5a7c91d4f08
Revises: d2a30b8201ef
Create Date: 2026-05-06 10:00:00.000000

배경:
- Phase 8.6 Sprint 2 마이그레이션 c1f2a30b8201은 컬럼만 추가, 모든 row server_default=false.
- 200종을 is_kospi200=true로 마킹하는 production 코드/잡 부재 → ATR 캘리브레이션 잡이
  KOSPI200_MIN_MASTER(10) 미달로 정적 백업 폴백 → coverage_gap 누적 → 3거래일 연속
  fallback → safe_mode 발동 → 신호 발행 전면 차단.

본 마이그레이션:
- backend/data/kospi200_static_backup.json 의 200종에 한해 is_kospi200=true 백필.
- 향후 분기 리밸런싱은 별도 잡으로 갱신(존재 시) 또는 정적 백업 갱신 + 본 패턴 재실행.

리스크:
- 정적 백업 200종 중 stocks 테이블 부재 코드는 UPDATE 영향 0 row (silently skip).
- 일봉(market_data) 적재 부족은 별개 이슈 — coverage_gap=148 잔존 가능.
  → 후속 작업: 누락 종목 일봉 백필 잡 (별도 PR).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence, Union

from alembic import op


revision: str = "e5a7c91d4f08"
down_revision: Union[str, None] = "d2a30b8201ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _load_static_backup_codes() -> list[str]:
    # backend/alembic/versions/<this>.py → backend/data/kospi200_static_backup.json
    path = Path(__file__).resolve().parents[2] / "data" / "kospi200_static_backup.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    codes = data.get("codes", [])
    return [c for c in codes if isinstance(c, str)]


def upgrade() -> None:
    codes = _load_static_backup_codes()
    if not codes:
        return
    from sqlalchemy import bindparam, text

    stmt = text(
        "UPDATE stocks SET is_kospi200 = TRUE WHERE stock_code IN :codes"
    ).bindparams(bindparam("codes", expanding=True))
    op.get_bind().execute(stmt, {"codes": codes})


def downgrade() -> None:
    # 전체 false 복원 (컬럼 자체 server_default=false 의도와 일치)
    op.execute("UPDATE stocks SET is_kospi200 = FALSE")
