from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class ScreeningMetricsDaily(Base):
    __tablename__ = "screening_metrics_daily"
    __table_args__ = (
        UniqueConstraint("metric_date", "bucket", name="uq_screening_metrics_date_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bucket: Mapped[str] = mapped_column(String(16), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StrategyMetricsDaily(Base):
    __tablename__ = "strategy_metrics_daily"
    __table_args__ = (
        UniqueConstraint(
            "metric_date",
            "stage",
            "hour_min_bucket",
            name="uq_strategy_metrics_date_stage_bucket",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    hour_min_bucket: Mapped[str] = mapped_column(String(8), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VirtualSignal(Base):
    __tablename__ = "virtual_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    stock_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    stock_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    virtual_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    breakout_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gap_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    prev_close: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    would_execute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
