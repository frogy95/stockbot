"""Phase 8.6 Sprint 2 — trade_signals.matched_tiers 컬럼 추가

Revision ID: d2a30b8201ef
Revises: c1f2a30b8201
Create Date: 2026-04-29 06:50:00.000000

Sprint 2 Task 3 (병렬 OR tier):
- trade_signals.matched_tiers (JSONB nullable): 병렬 OR 평가에서 통과한 tier 목록
  예: ["gap_open"], ["prev_high","prev_close"]
- NULL 안전: PARALLEL_OR_TIER_ENABLED=false (Kill-switch) 시 NULL 그대로 저장 → 회귀 보장
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d2a30b8201ef"
down_revision: Union[str, None] = "c1f2a30b8201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trade_signals",
        sa.Column(
            "matched_tiers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("trade_signals", "matched_tiers")
