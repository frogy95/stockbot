import pytest

from core.clients.kis_config import (
    KISEnvironment,
    PAPER,
    LIVE,
    get_environment,
    get_current_environment,
)


class TestKISEnvironment:
    def test_paper_fields(self):
        assert PAPER.name == "paper"
        assert "openapivts" in PAPER.rest_domain
        assert PAPER.order_tr_prefix == "V"
        assert PAPER.rate_limit_interval == 1.5

    def test_live_fields(self):
        assert LIVE.name == "live"
        assert "openapi" in LIVE.rest_domain
        assert "vts" not in LIVE.rest_domain
        assert LIVE.order_tr_prefix == "T"
        assert LIVE.rate_limit_interval == pytest.approx(0.07, abs=0.01)

    def test_paper_base_url(self):
        assert PAPER.base_url == f"https://{PAPER.rest_domain}"

    def test_live_base_url(self):
        assert LIVE.base_url == f"https://{LIVE.rest_domain}"

    def test_paper_env_var_names(self):
        assert PAPER.app_key_env == "KIS_MOCK_APP_KEY"
        assert PAPER.app_secret_env == "KIS_MOCK_APP_SECRET"
        assert PAPER.account_env == "KIS_MOCK_ACCOUNT_NO"

    def test_live_env_var_names(self):
        assert LIVE.app_key_env == "KIS_APP_KEY"
        assert LIVE.app_secret_env == "KIS_APP_SECRET"
        assert LIVE.account_env == "KIS_ACCOUNT_NO"

    def test_frozen(self):
        with pytest.raises(AttributeError):
            PAPER.name = "other"


class TestGetEnvironment:
    def test_paper(self):
        assert get_environment("paper") is PAPER

    def test_live(self):
        assert get_environment("live") is LIVE

    def test_invalid(self):
        with pytest.raises(ValueError):
            get_environment("invalid")


class TestGetCurrentEnvironment:
    def test_returns_based_on_trading_env(self):
        env = get_current_environment()
        # 기본 TRADING_ENV가 "paper"이므로 PAPER 반환
        assert env.name == "paper"
