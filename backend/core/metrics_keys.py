"""Phase 8.5 Sprint 1 — 관측성 Redis 키 규약 단일 진입점.

모든 metrics 관련 Redis 키는 이 모듈의 함수를 통해 생성한다.
"""
from datetime import date, datetime

SECONDARY_SCORE_PREFIX = "metrics:secondary:score"
STRATEGY_STAGE_PREFIX = "metrics:strategy:stage"
TOP_REJECT_KEY = "metrics:strategy:top_reject"

# momentum_breakout._reject() 에서 호출되는 stage 이름 전수 + "pass"
TRACKED_STAGES: tuple[str, ...] = (
    "pass",
    "breakout",
    "min_volume_floor",
    "prev_close_time_guard",
    "volume_threshold",
    "trade_strength",
    "atr_filter",
    "confidence",
    "prev_volume_zero",
    "no_data",
)


def _date_str(d: date | str) -> str:
    if isinstance(d, date):
        return d.isoformat()
    return d


def score_bucket_for(score: float) -> list[str]:
    """점수를 bucket 라벨 리스트로 변환.

    75 이상이면 '>=75' + 10점 bucket 동시 반환.
    75 미만은 10점 bucket 단일 반환.
    """
    buckets: list[str] = []
    if score is None:
        return buckets
    try:
        value = float(score)
    except (TypeError, ValueError):
        return buckets
    if value < 0:
        value = 0.0
    if value >= 100:
        ten = "90-100"
    else:
        lower = int(value // 10) * 10
        ten = f"{lower}-{lower + 10}"
    if value >= 75:
        buckets.append(">=75")
    buckets.append(ten)
    return buckets


def hour_min_bucket_for(dt: datetime) -> str:
    """10분 단위 내림 (KST 가정). 09:37 → '09:30'."""
    minute = (dt.minute // 10) * 10
    return f"{dt.hour:02d}:{minute:02d}"


def score_histogram_key(d: date | str, bucket: str) -> str:
    return f"{SECONDARY_SCORE_PREFIX}:{_date_str(d)}:{bucket}"


def stage_counter_key(d: date | str, stage: str, hour_min: str) -> str:
    return f"{STRATEGY_STAGE_PREFIX}:{_date_str(d)}:{stage}:{hour_min}"


def stages() -> tuple[str, ...]:
    return TRACKED_STAGES
