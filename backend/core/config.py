from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 애플리케이션
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-to-random-secret-key"
    JWT_SECRET: str = "change-me-to-random-jwt-secret"
    TRADING_ENV: str = "paper"

    # 시장 타임존 (APScheduler, datetime 계산에 사용)
    MARKET_TIMEZONE: str = "Asia/Seoul"

    # PostgreSQL
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "stockbot"
    POSTGRES_USER: str = "stockbot"
    POSTGRES_PASSWORD: str = "stockbot"

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: str = ""

    # 프론트엔드
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    ADMIN_PASSWORD: str = ""
    JWT_EXPIRY_HOURS: int = 24

    # 리스크 관리
    # Sprint 3 이전 LIVE 초기에 일일 거래 한도를 임시 제한할 때 사용 (예: 3)
    # 미설정 시 settings 테이블의 daily_max_trade_count 값을 따름
    DAILY_MAX_TRADE_COUNT_OVERRIDE: int | None = None

    # --- Phase 8.5 Sprint 2: 풀 하한 폴백 + 동적 MIN_VOLUME_FLOOR ---
    # 거래량 하한 결정 방식 (legacy=0.5 고정 / dynamic=조건부)
    MIN_VOLUME_FLOOR_MODE: Literal["legacy", "dynamic"] = Field(default="dynamic", description="거래량 하한 결정 방식")
    # 어떤 분기도 이 이하로 내리지 않는 절대 하한
    MIN_VOLUME_FLOOR_HARD: float = Field(default=0.3, ge=0.0, le=1.0, description="어떤 분기도 이 이하 금지")
    # 2차 스크리닝 통과 < 이 값이면 1차 통과 종목으로 보강
    SECONDARY_POOL_FALLBACK_ENABLED: bool = Field(default=True, description="2차 풀 하한 폴백 활성화")
    SECONDARY_POOL_FALLBACK_THRESHOLD: int = Field(default=5, ge=1, le=10, description="passed_count < N 시 폴백 발동 (Phase 8.6 Sprint 1: 3→5 분기 D 풀 협소 대응)")
    # 폴백 포함 풀 최대 종목 수
    SECONDARY_POOL_MAX: int = Field(default=5, ge=1, le=20, description="폴백 포함 풀 상한")
    # 폴백 보강 종목 수 상한 (Phase 8.6 Sprint 1)
    SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP: int = Field(default=5, ge=1, le=10, description="폴백 보강 종목 수 상한")
    # 전일 대비 이 이하 종목은 폴백 제외
    FALLBACK_DROP_EXCLUDE_PCT: float = Field(default=-3.0, ge=-100.0, le=0.0, description="전일 대비 이 이하는 폴백 제외 (%)")
    # 폴백 종목 포지션 사이즈 배수 (0.5 = 반 포지션)
    FALLBACK_POSITION_SIZE_RATIO: float = Field(default=0.5, gt=0.0, le=1.0, description="폴백 종목 포지션 사이즈 배수")
    # 폴백 종목 손절 % (-1.5 = -1.5%)
    FALLBACK_STOP_LOSS_PCT: float = Field(default=-1.5, ge=-100.0, le=0.0, description="폴백 종목 손절 % (절댓값 작을수록 타이트)")

    # --- Phase 8.5 Sprint 2.5: Redis settings override 경로 제어 ---
    SETTINGS_OVERRIDE_ENABLED: bool = Field(default=True, description="Redis settings override 경로 활성화 (긴급 차단용)")

    # --- Phase 8.6 Sprint 1: G2 자동 롤백 R1~R4 ---
    AUTO_ROLLBACK_ENABLED: bool = Field(default=True, description="G2 자동 롤백 마스터 토글")
    AUTO_ROLLBACK_R1_ENABLED: bool = Field(default=True, description="R1: 신호 0건 3거래일 연속")
    AUTO_ROLLBACK_R2_ENABLED: bool = Field(default=True, description="R2: 폴백 발동 3거래일 연속 (v0)")
    AUTO_ROLLBACK_R3_ENABLED: bool = Field(default=True, description="R3: tier 종류 ≤1 5거래일")
    AUTO_ROLLBACK_R4_ENABLED: bool = Field(default=True, description="R4: 폴백 비중 ≥70% 1거래일")

    # --- Phase 8.6 Sprint 1: G3 1차→2차 통과율 회로차단기 ---
    CIRCUIT_BREAKER_ENABLED: bool = Field(default=True, description="G3 회로차단기 마스터 토글")
    CIRCUIT_BREAKER_PASS_RATE_THRESHOLD: float = Field(
        default=0.10, ge=0.0, le=1.0,
        description="일별 1차→2차 통과율 임계 (이 미만이 N일 연속이면 발동)",
    )
    CIRCUIT_BREAKER_CONSECUTIVE_DAYS: int = Field(
        default=3, ge=1, le=10,
        description="회로차단기 발동 연속 일수 임계",
    )

    # --- Phase 8.6 Sprint 2: 병렬 OR tier + ATR 분위수 캘리브레이션 ---
    # 병렬 OR tier 분기 활성화 (false 시 Sprint 1 직렬 동작 복원 — Kill-switch)
    PARALLEL_OR_TIER_ENABLED: bool = Field(default=True, description="병렬 OR tier 분기 활성화 (false=Sprint 1 직렬 복원)")
    # 08:35 KOSPI200 ATR 분위수 캘리브레이션 잡 활성화
    ATR_CALIBRATION_ENABLED: bool = Field(default=True, description="ATR 캘리브레이션 잡 활성화 (false=ATR_CEIL_HARD 정적 사용)")
    # 캘리브레이션 방식 — sma(20일 평균) 또는 ewma(λ=0.94)
    ATR_CALIBRATION_METHOD: Literal["sma", "ewma"] = Field(default="sma", description="ATR 캘리브레이션 방식 (sma|ewma)")
    # ATR 하한 (모든 tier 공통, 폴백 종목 포함, gap_open도 적용)
    ATR_FLOOR: float = Field(default=0.025, ge=0.0, le=0.5, description="ATR 하한 (모든 tier 공통)")
    # ATR 상한 절대 한계 (gap_open 우회 시에도 적용, 동적 상한도 이 값 초과 금지)
    ATR_CEIL_HARD: float = Field(default=0.08, ge=0.0, le=0.5, description="ATR 상한 절대 한계 (HARD)")
    # 폴백 종목 ATR 상한 (동적 미적용)
    ATR_CEIL_FALLBACK: float = Field(default=0.05, ge=0.0, le=0.5, description="폴백 종목 ATR 상한 (정적)")
    # 동적 상한 곱계수 (P80 × mult). shadow 그리드 {1.0, 1.1, 1.2, 1.3} 중 실 진입값
    ATR_CEIL_MULT: float = Field(default=1.2, gt=0.0, le=3.0, description="동적 상한 곱계수 (P80×mult)")
    # KOSPI200 ATR 캘리브레이션 윈도우 (영업일 단위)
    ATR_CALIBRATION_WINDOW_DAYS: int = Field(default=20, ge=5, le=120, description="ATR 캘리브레이션 윈도우(일)")
    # --- Phase 8.6 Sprint 3: 시간 필터 본 가드 ---
    TIME_FILTER_ENABLED: bool = Field(default=True, description="시간대 진입 차단 마스터 토글 (false=전 시간대 허용)")
    # --- Phase 8.6 Sprint 3: 거래량 급등 전략 (VolumeSurge) ---
    VOLUME_SURGE_ENABLED: bool = Field(default=True, description="거래량 급등 전략 활성화 (false=비활성)")
    VOLUME_SURGE_DRY_RUN: bool = Field(default=True, description="거래량 급등 전략 Dry-run 모드 (true=신호 발행 전용, 주문 없음)")
    VOLUME_SURGE_VOL_RATIO: float = Field(default=5.0, gt=0, description="거래량 급등 판정 비율 (현재/평균 ≥ 이 값)")
    VOLUME_SURGE_BID_ASK_RATIO: float = Field(default=2.0, gt=0, description="호가 매수/매도 잔량 비율 하한 (≥ 이 값)")
    VOLUME_SURGE_PRICE_THRESHOLD: float = Field(default=0.005, ge=0, description="거래량 급등 진입 가격 상승률 하한 (예: 0.005=0.5%)")
    VOLUME_SURGE_POSITION_SIZE: float = Field(default=0.30, gt=0, le=1.0, description="거래량 급등 전략 포지션 사이즈 비율 (0~1)")
    # --- Phase 8.6 Sprint 3: 신호 우선순위 큐 ---
    SIGNAL_PRIORITY_QUEUE_ENABLED: bool = Field(default=True, description="신호 우선순위 큐 활성화 (false=선입선출 복원)")
    # 폴백 3단 안전모드 신호 발행 중단 시간 (분)
    SAFE_MODE_TIMEOUT_MIN: int = Field(default=120, ge=1, le=720, description="안전모드 신호 발행 중단 시간(분)")
    # ATR 캘리브레이션 단면 OHLC 결측 허용 상한 — missing >= 임계 시 폴백 진입.
    ATR_COVERAGE_GAP_MAX: int = Field(default=30, ge=1, le=500, description="ATR 캘리브레이션 OHLC 결측 허용 상한 (기본 30)")
    # KIS kospi_code.mst 기반 KOSPI200 마스터 자동 동기화. 핫픽스 kospi200-real-200-backfill 도입.
    # default=False로 머지·배포 가능 (관찰 신호 보존). production에서 5/7 관찰 후 true 토글.
    KOSPI200_MST_SYNC_ENABLED: bool = Field(default=False, description="KIS mst 기반 KOSPI200 멤버십 일일 동기화 활성화")

    # --- Phase 8.6 Sprint 4: walk-forward 백테스트 + LIVE 토글 게이트 ---
    BACKTEST_ENABLED: bool = Field(default=True, description="walk-forward 백테스트 잡 마스터 토글")
    LIVE_GATE_AUTO_EVAL_ENABLED: bool = Field(default=True, description="LIVE 토글 게이트 G-Bt1/G-Bt2/G-Bt3 자동 평가 활성화")
    BACKTEST_DEFAULT_N_DAYS: int = Field(default=60, ge=30, le=120, description="walk-forward 기본 기간(일)")

    # 한국투자증권 종목 마스터파일
    KIS_MST_BASE_URL: str = "https://new.real.download.dws.co.kr/common/master"

    # 한국투자증권 (모의)
    KIS_MOCK_APP_KEY: str = ""
    KIS_MOCK_APP_SECRET: str = ""
    KIS_MOCK_ACCOUNT_NO: str = ""

    # 한국투자증권 (실전)
    KIS_APP_KEY: str = ""
    KIS_APP_SECRET: str = ""
    KIS_ACCOUNT_NO: str = ""

    # 네이버 검색
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    # DART
    DART_API_KEY: str = ""

    # 공공데이터포털
    DATA_GO_KR_API_KEY: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
