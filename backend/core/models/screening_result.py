from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class ScreeningResult(Base):
    __tablename__ = "screening_results"
    __table_args__ = (
        UniqueConstraint("stock_code", "screening_type", "screened_at"),
        Index("ix_screening_results_type_date", "screening_type", "screened_at"),
        Index("ix_screening_results_score", "score", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("stocks.stock_code"), nullable=False
    )
    screening_type: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    factors: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    screened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
