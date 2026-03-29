from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class FinancialData(Base):
    __tablename__ = "financial_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("stocks.stock_code"), nullable=False
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operating_profit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_income: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    source: Mapped[str] = mapped_column(String(20), server_default="dart")
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("stock_code", "fiscal_year", "fiscal_quarter", name="uq_financial_data_stock_year_quarter"),
        Index("ix_financial_data_stock_code", "stock_code"),
        Index("ix_financial_data_year_quarter", "fiscal_year", "fiscal_quarter"),
    )
