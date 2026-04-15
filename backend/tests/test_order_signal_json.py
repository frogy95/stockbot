"""Order 모델 signal_json 컬럼 직렬화/역직렬화 테스트."""

from unittest.mock import MagicMock


def _make_order_with_signal_json(signal_data: dict | None = None) -> MagicMock:
    """signal_json이 포함된 Order mock 생성."""
    order = MagicMock()
    order.id = 1
    order.stock_code = "005930"
    order.order_type = "buy"
    order.quantity = 10
    order.price = 50_000
    order.signal_json = signal_data
    return order


class TestOrderSignalJson:
    """Order.signal_json JSONB 필드 테스트."""

    def test_signal_json_none_by_default(self):
        """signal_json 미설정 시 None."""
        order = _make_order_with_signal_json(None)
        assert order.signal_json is None

    def test_signal_json_stores_dict(self):
        """signal_json에 dict 저장/읽기."""
        signal_data = {
            "stock_code": "005930",
            "signal_type": "buy",
            "strategy_name": "momentum_breakout",
            "confidence": 0.85,
            "entry_price": 50000,
            "stop_loss": 48000,
            "take_profit": 53000,
            "reason": {"volume_surge": True},
        }
        order = _make_order_with_signal_json(signal_data)

        assert order.signal_json == signal_data
        assert order.signal_json["stock_code"] == "005930"
        assert order.signal_json["confidence"] == 0.85

    def test_signal_json_roundtrip(self):
        """signal_json dict → 읽기 → 동일 확인."""
        original = {
            "stock_code": "000660",
            "signal_type": "buy",
            "strategy_name": "test",
            "confidence": 0.9,
            "entry_price": 100000,
            "stop_loss": 95000,
            "take_profit": 110000,
            "reason": {},
        }
        order = _make_order_with_signal_json(original)
        restored = order.signal_json

        assert restored == original
        assert restored is not None

    def test_column_exists_in_order_model(self):
        """Order.__table__에 signal_json 컬럼 존재."""
        from core.models.trading import Order

        columns = Order.__table__.columns.keys()
        assert "signal_json" in columns
