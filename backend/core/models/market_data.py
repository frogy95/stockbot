from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class MarketData(Base):
    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint("stock_code", "data_date", "source"),
        Index("ix_market_data_date", "data_date"),
        Index("ix_market_data_stock_date", "stock_code", "data_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("stocks.stock_code"), nullable=False
    )
    data_date: Mapped[date] = mapped_column(Date, nullable=False)
    open_price: Mapped[int | None] = mapped_column(Numeric(12, 0), nullable=True)
    high_price: Mapped[int | None] = mapped_column(Numeric(12, 0), nullable=True)
    low_price: Mapped[int | None] = mapped_column(Numeric(12, 0), nullable=True)
    close_price: Mapped[int | None] = mapped_column(Numeric(12, 0), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    listed_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    change_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
