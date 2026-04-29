from datetime import datetime

from sqlalchemy import (
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


class TradeSignal(Base):
    __tablename__ = "trade_signals"
    __table_args__ = (
        Index("ix_trade_signals_stock_status", "stock_code", "status"),
        Index("ix_trade_signals_fallback_created", "fallback", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("stocks.stock_code"), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=False)
    reason: Mapped[dict] = mapped_column(JSONB, default=dict)
    entry_price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    stop_loss: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    take_profit: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    fallback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Phase 8.6 Sprint 2 — 병렬 OR tier 통과 목록 (e.g. ["gap_open","prev_high"])
    matched_tiers: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_status", "status"),
        Index("ix_orders_stock", "stock_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("trade_signals.id"), nullable=True
    )
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)
    order_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    order_division: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending_approval")
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    signal_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fallback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class PositionRecord(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("stock_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("stocks.stock_code"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    current_price: Mapped[int] = mapped_column(Numeric(12, 0), default=0)
    unrealized_pnl: Mapped[int] = mapped_column(Integer, default=0)
    stop_loss: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    take_profit: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    trailing_activated: Mapped[bool] = mapped_column(Boolean, default=False)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class TradeHistory(Base):
    __tablename__ = "trade_history"
    __table_args__ = (
        Index("ix_trade_history_stock_exit", "stock_code", "exit_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    signal_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    entry_price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    exit_price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    realized_pnl: Mapped[int] = mapped_column(Integer, nullable=False)
    pnl_rate: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    holding_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    exit_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    exit_reason: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
