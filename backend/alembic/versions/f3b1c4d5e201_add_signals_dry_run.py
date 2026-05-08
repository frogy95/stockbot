"""Phase 8.6 Sprint 3 — trade_signals.dry_run 컬럼 추가

Revision ID: f3b1c4d5e201
Revises: e5a7c91d4f08
Create Date: 2026-05-07 09:00:00.000000

Sprint 3 Task 2 (VolumeSurgeStrategy):
- trade_signals.dry_run (Boolean nullable, server_default=false):
  거래량 급등 전략 신호의 dry_run 여부. True면 TradingEngine이 주문 실행 차단.
- NULL 안전: 기존 신호는 NULL 유지 → False 동등 처리 (Kill-switch 호환).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3b1c4d5e201"
down_revision: Union[str, None] = "e5a7c91d4f08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trade_signals",
        sa.Column(
            "dry_run",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("trade_signals", "dry_run")
