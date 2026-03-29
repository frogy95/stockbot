from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from core.models.settings import SystemSetting  # noqa: E402, F401
from core.models.stock import Stock  # noqa: E402, F401
from core.models.market_data import MarketData  # noqa: E402, F401
