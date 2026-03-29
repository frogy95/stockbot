from core.models import Base
from core.models.settings import SystemSetting
from core.models.stock import Stock
from core.models.market_data import MarketData


def test_system_setting_fields():
    cols = {c.name for c in SystemSetting.__table__.columns}
    assert {"id", "key", "value", "value_type", "category"}.issubset(cols)


def test_stock_fields():
    cols = {c.name for c in Stock.__table__.columns}
    assert {"id", "stock_code", "stock_name", "market", "market_type", "stock_type"}.issubset(cols)


def test_market_data_fields():
    cols = {c.name for c in MarketData.__table__.columns}
    assert {"id", "stock_code", "data_date", "source"}.issubset(cols)


def test_market_data_unique_constraint():
    constraints = MarketData.__table__.constraints
    unique_cols = None
    for c in constraints:
        if hasattr(c, "columns") and len(c.columns) == 3:
            unique_cols = {col.name for col in c.columns}
    assert unique_cols == {"stock_code", "data_date", "source"}


def test_tables_registered():
    table_names = set(Base.metadata.tables.keys())
    assert {"settings", "stocks", "market_data"}.issubset(table_names)
