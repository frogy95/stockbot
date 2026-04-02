from dataclasses import dataclass, field


@dataclass
class CollectionResult:
    collected: int
    failed: int = 0
    skipped: int = 0
    total_target: int = 0
    data_date: str | None = None
    null_counts: dict[str, int] | None = None


@dataclass
class ValidationResult:
    passed: bool
    failure_type: str | None = None
    failure_reason: str | None = None
    details: dict = field(default_factory=dict)
    severity: str = "error"
