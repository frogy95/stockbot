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
