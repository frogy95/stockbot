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
    SECONDARY_POOL_FALLBACK_THRESHOLD: int = Field(default=3, ge=1, le=10, description="passed_count < N 시 폴백 발동")
    # 폴백 포함 풀 최대 종목 수
    SECONDARY_POOL_MAX: int = Field(default=5, ge=1, le=20, description="폴백 포함 풀 상한")
    # 전일 대비 이 이하 종목은 폴백 제외
    FALLBACK_DROP_EXCLUDE_PCT: float = Field(default=-3.0, ge=-100.0, le=0.0, description="전일 대비 이 이하는 폴백 제외 (%)")
    # 폴백 종목 포지션 사이즈 배수 (0.5 = 반 포지션)
    FALLBACK_POSITION_SIZE_RATIO: float = Field(default=0.5, gt=0.0, le=1.0, description="폴백 종목 포지션 사이즈 배수")
    # 폴백 종목 손절 % (-1.5 = -1.5%)
    FALLBACK_STOP_LOSS_PCT: float = Field(default=-1.5, ge=-100.0, le=0.0, description="폴백 종목 손절 % (절댓값 작을수록 타이트)")

    # --- Phase 8.5 Sprint 2.5: Redis settings override 경로 제어 ---
    SETTINGS_OVERRIDE_ENABLED: bool = Field(default=True, description="Redis settings override 경로 활성화 (긴급 차단용)")

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
