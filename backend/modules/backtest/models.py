"""백테스트 인메모리 데이터 구조 (DB 모델과 별개)."""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class BacktestConfig:
    """백테스트 실행 설정."""

    period_start: date
    period_end: date
    n_trading_days: int
    regime_box_days: int
    regime_trend_days: int
    run_id: str = ""


@dataclass
class BacktestResult:
    """백테스트 실행 결과 (인메모리)."""

    run_id: str
    config: BacktestConfig
    pass_rates: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    success: bool = True


@dataclass
class GateEvalResult:
    """LIVE 진입 게이트 평가 결과 (인메모리)."""

    g_bt1_passed: bool
    g_bt2_passed: bool
    g_bt3_passed: bool
    details: dict = field(default_factory=dict)

    @property
    def all_passed(self) -> bool:
        return self.g_bt1_passed and self.g_bt2_passed and self.g_bt3_passed
