from core.models import Base
from core.models.trading import TradeSignal, Order, PositionRecord, TradeHistory


# === TradeSignal ===

def test_trade_signal_tablename():
    assert TradeSignal.__tablename__ == "trade_signals"


def test_trade_signal_fields():
    cols = {c.name for c in TradeSignal.__table__.columns}
    expected = {
        "id", "stock_code", "signal_type", "strategy_name", "confidence",
        "reason", "entry_price", "stop_loss", "take_profit", "status",
        "created_at", "updated_at",
    }
    assert expected.issubset(cols)


def test_trade_signal_fk():
    fks = TradeSignal.__table__.foreign_keys
    fk_targets = {fk.target_fullname for fk in fks}
    assert "stocks.stock_code" in fk_targets


def test_trade_signal_indexes():
    index_names = {idx.name for idx in TradeSignal.__table__.indexes}
    assert "ix_trade_signals_stock_status" in index_names


def test_trade_signal_registered():
    assert "trade_signals" in Base.metadata.tables


# === Order ===

def test_order_tablename():
    assert Order.__tablename__ == "orders"


def test_order_fields():
    cols = {c.name for c in Order.__table__.columns}
    expected = {
        "id", "signal_id", "stock_code", "order_type", "order_no",
        "quantity", "price", "order_division", "status",
        "submitted_at", "filled_at", "created_at", "updated_at",
    }
    assert expected.issubset(cols)


def test_order_fk():
    fks = Order.__table__.foreign_keys
    fk_targets = {fk.target_fullname for fk in fks}
    assert "trade_signals.id" in fk_targets


def test_order_indexes():
    index_names = {idx.name for idx in Order.__table__.indexes}
    assert "ix_orders_status" in index_names
    assert "ix_orders_stock" in index_names


def test_order_registered():
    assert "orders" in Base.metadata.tables


# === PositionRecord ===

def test_position_record_tablename():
    assert PositionRecord.__tablename__ == "positions"


def test_position_record_fields():
    cols = {c.name for c in PositionRecord.__table__.columns}
    expected = {
        "id", "stock_code", "quantity", "avg_price", "current_price",
        "unrealized_pnl", "stop_loss", "take_profit",
        "trailing_activated", "entry_time", "strategy_name",
        "created_at", "updated_at",
    }
    assert expected.issubset(cols)


def test_position_record_fk():
    fks = PositionRecord.__table__.foreign_keys
    fk_targets = {fk.target_fullname for fk in fks}
    assert "stocks.stock_code" in fk_targets


def test_position_record_unique_stock_code():
    constraints = PositionRecord.__table__.constraints
    found = False
    for c in constraints:
        if hasattr(c, "columns") and len(c.columns) == 1:
            col_names = {col.name for col in c.columns}
            if col_names == {"stock_code"} and c.__class__.__name__ == "UniqueConstraint":
                found = True
    assert found, "positions 테이블에 stock_code UniqueConstraint 필요"


def test_position_record_registered():
    assert "positions" in Base.metadata.tables


# === TradeHistory ===

def test_trade_history_tablename():
    assert TradeHistory.__tablename__ == "trade_history"


def test_trade_history_fields():
    cols = {c.name for c in TradeHistory.__table__.columns}
    expected = {
        "id", "stock_code", "strategy_name", "signal_confidence",
        "entry_price", "exit_price", "quantity", "realized_pnl",
        "pnl_rate", "holding_duration_sec", "entry_time", "exit_time",
        "exit_reason", "created_at",
    }
    assert expected.issubset(cols)


def test_trade_history_indexes():
    index_names = {idx.name for idx in TradeHistory.__table__.indexes}
    assert "ix_trade_history_stock_exit" in index_names


def test_trade_history_registered():
    assert "trade_history" in Base.metadata.tables
