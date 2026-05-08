"""백테스트 관련 SQLAlchemy 모델 (Phase 8.6 Sprint 4)."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.models import Base


class BacktestRun(Base):
    """백테스트 실행 단위 기록."""

    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_period_end", "period_end", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    n_trading_days: Mapped[int] = mapped_column(Integer, nullable=False)
    regime_box_days: Mapped[int] = mapped_column(Integer, nullable=False)
    regime_trend_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BacktestSignalMetric(Base):
    """백테스트 신호 통계 지표 (KS 검정, Bootstrap CI 등)."""

    __tablename__ = "backtest_signal_metrics"
    __table_args__ = (
        Index("ix_backtest_signal_metrics_run_tier", "run_id", "tier"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("backtest_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    pass_rate_simulated: Mapped[float] = mapped_column(Float, nullable=False)
    pass_rate_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    ks_statistic: Mapped[float | None] = mapped_column(Float, nullable=True)
    ks_pvalue: Mapped[float | None] = mapped_column(Float, nullable=True)
    bootstrap_ci_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    bootstrap_ci_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LiveGateStatus(Base):
    """LIVE 진입 게이트 평가 결과 스냅샷."""

    __tablename__ = "live_gate_statuses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    g_bt1_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    g_bt2_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    g_bt3_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    all_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
