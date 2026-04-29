"""Phase 8.6 Sprint 1 — fallback 컬럼 추가 (TradeSignal·Order)

Revision ID: b8f1c2a30201
Revises: a430a1c931b2
Create Date: 2026-04-29 03:40:00.000000

G1 메타데이터 전파 (Phase 8.6 Sprint 1 Task 3):
- trade_signals.fallback (boolean, server_default=false): 폴백 후보로부터 생성된 신호 여부
- orders.fallback (boolean, server_default=false): 부모 신호의 fallback 값을 승계
- ix_trade_signals_fallback_created 인덱스: M-F2 일별 폴백 신호율 집계 성능

백필 정책 (Quant 권고):
- 기존 row의 NULL → False는 server_default="false"로 자동 보장.
- 별도 UPDATE 백필 쿼리 불필요. 마이그레이션 적용 시 기존 row는 즉시 false로 채워짐.

PR 머지 게이트 — Alembic 왕복 테스트 (Risk Critical 보강):
- upgrade head → downgrade -1 → upgrade head 3단계 모두 성공 필수.
- downgrade에서 인덱스 → 컬럼 순서로 드롭하여 의존성 충돌 방지.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8f1c2a30201"
down_revision: Union[str, None] = "a430a1c931b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trade_signals",
        sa.Column(
            "fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_trade_signals_fallback_created",
        "trade_signals",
        ["fallback", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_trade_signals_fallback_created", table_name="trade_signals")
    op.drop_column("orders", "fallback")
    op.drop_column("trade_signals", "fallback")
