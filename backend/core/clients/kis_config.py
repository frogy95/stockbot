from dataclasses import dataclass

from core.config import settings


@dataclass(frozen=True)
class KISEnvironment:
    name: str
    rest_domain: str
    ws_url: str
    order_tr_prefix: str
    app_key_env: str
    app_secret_env: str
    account_env: str
    rate_limit_interval: float

    @property
    def base_url(self) -> str:
        return f"https://{self.rest_domain}"

    @property
    def app_key(self) -> str:
        return getattr(settings, self.app_key_env)

    @property
    def app_secret(self) -> str:
        return getattr(settings, self.app_secret_env)

    @property
    def account_no(self) -> str:
        return getattr(settings, self.account_env)


PAPER = KISEnvironment(
    name="paper",
    rest_domain="openapivts.koreainvestment.com:29443",
    ws_url="ws://ops.koreainvestment.com:31000",
    order_tr_prefix="V",
    app_key_env="KIS_MOCK_APP_KEY",
    app_secret_env="KIS_MOCK_APP_SECRET",
    account_env="KIS_MOCK_ACCOUNT_NO",
    rate_limit_interval=1.5,
)

LIVE = KISEnvironment(
    name="live",
    rest_domain="openapi.koreainvestment.com:9443",
    ws_url="ws://ops.koreainvestment.com:21000",
    order_tr_prefix="T",
    app_key_env="KIS_APP_KEY",
    app_secret_env="KIS_APP_SECRET",
    account_env="KIS_ACCOUNT_NO",
    rate_limit_interval=0.07,
)

_ENVIRONMENTS = {"paper": PAPER, "live": LIVE}


def get_environment(name: str) -> KISEnvironment:
    if name not in _ENVIRONMENTS:
        raise ValueError(f"알 수 없는 거래 환경: {name!r} (paper 또는 live만 허용)")
    return _ENVIRONMENTS[name]


def get_current_environment() -> KISEnvironment:
    return get_environment(settings.TRADING_ENV)
