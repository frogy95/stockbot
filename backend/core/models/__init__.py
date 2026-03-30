from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from core.models.settings import SystemSetting  # noqa: E402, F401
from core.models.stock import Stock  # noqa: E402, F401
from core.models.market_data import MarketData  # noqa: E402, F401
from core.models.screening_result import ScreeningResult  # noqa: E402, F401
from core.models.corp_code import CorpCode  # noqa: E402, F401
from core.models.financial_data import FinancialData  # noqa: E402, F401
from core.models.news_sentiment import NewsSentiment  # noqa: E402, F401
from core.models.trading import TradeSignal, Order, PositionRecord, TradeHistory  # noqa: E402, F401
