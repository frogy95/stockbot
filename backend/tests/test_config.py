from core.config import Settings


def test_settings_instance():
    s = Settings()
    assert s is not None


def test_trading_env_default():
    s = Settings()
    assert s.TRADING_ENV == "paper"


def test_database_url_format():
    s = Settings()
    assert s.database_url.startswith("postgresql+asyncpg://")


def test_redis_url_format():
    s = Settings()
    assert s.redis_url.startswith("redis://")
