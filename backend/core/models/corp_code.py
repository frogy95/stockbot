from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class CorpCode(Base):
    __tablename__ = "corp_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    corp_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    corp_name: Mapped[str] = mapped_column(String(100), nullable=False)
    stock_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    modify_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_corp_codes_stock_code", "stock_code"),
    )
