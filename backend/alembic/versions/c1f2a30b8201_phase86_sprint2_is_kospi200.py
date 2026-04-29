"""Phase 8.6 Sprint 2 — stocks.is_kospi200 컬럼 추가

Revision ID: c1f2a30b8201
Revises: b8f1c2a30201
Create Date: 2026-04-29 06:30:00.000000

Sprint 2 Task 1:
- stocks.is_kospi200 (boolean, server_default=false): KOSPI200 마스터 플래그
- ix_stocks_is_kospi200 인덱스: ATR 캘리브레이션 잡 KOSPI200 조회 성능

백필 정책:
- 기존 row의 is_kospi200 → False는 server_default="false"로 자동 보장.
- KOSPI200 마스터 갱신은 별도 잡(분기 리밸런싱 시) 또는 정적 백업 JSON 폴백.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1f2a30b8201"
down_revision: Union[str, None] = "b8f1c2a30201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stocks",
        sa.Column(
            "is_kospi200",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_stocks_is_kospi200",
        "stocks",
        ["is_kospi200"],
    )


def downgrade() -> None:
    op.drop_index("ix_stocks_is_kospi200", table_name="stocks")
    op.drop_column("stocks", "is_kospi200")
