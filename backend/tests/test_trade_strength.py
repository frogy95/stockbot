"""체결강도 계산 모듈 테스트."""

from modules.collector.trade_strength import TradeStrengthCalculator


def test_add_execution_and_calculate():
    """매수/매도 체결 추가 후 체결강도 계산."""
    calc = TradeStrengthCalculator(window_seconds=300)
    base_ts = 1000.0

    # 매수 300, 매도 100 -> 체결강도 = 300/(300+100)*100 = 75
    calc.add_execution("005930", base_ts, 200, "2")  # 매수
    calc.add_execution("005930", base_ts + 1, 100, "2")  # 매수
    calc.add_execution("005930", base_ts + 2, 100, "1")  # 매도

    # 5분(300초) 경과 후 조회
    strength = calc.get_strength("005930", now=base_ts + 300)
    assert strength == 75.0


def test_window_expiry():
    """5분 윈도우 이후 데이터 만료 확인."""
    calc = TradeStrengthCalculator(window_seconds=300)
    base_ts = 1000.0

    calc.add_execution("005930", base_ts, 100, "2")  # 매수
    calc.add_execution("005930", base_ts + 301, 50, "1")  # 매도

    # 601초 시점: base_ts 데이터는 윈도우 밖(cutoff=301)으로 만료
    # 남은 건 base_ts+301의 매도 50뿐 → 체결강도 0
    # first_ts가 1301로 갱신되어 (1601-1301)=300 >= 300이므로 5분 충족
    strength = calc.get_strength("005930", now=base_ts + 601)
    assert strength == 0.0

    # 모든 데이터 만료 시 중립값 반환
    strength2 = calc.get_strength("005930", now=base_ts + 900)
    assert strength2 == 50.0


def test_minimum_accumulation():
    """누적 5분 미만 시 중립값(50) 반환."""
    calc = TradeStrengthCalculator(window_seconds=300)
    base_ts = 1000.0

    calc.add_execution("005930", base_ts, 100, "2")
    calc.add_execution("005930", base_ts + 10, 100, "1")

    # 200초 후 (아직 5분 미달)
    strength = calc.get_strength("005930", now=base_ts + 200)
    assert strength == 50.0


def test_all_buy_strength_100():
    """전부 매수 시 체결강도 100."""
    calc = TradeStrengthCalculator(window_seconds=300)
    base_ts = 1000.0

    calc.add_execution("005930", base_ts, 100, "2")
    calc.add_execution("005930", base_ts + 10, 200, "2")

    strength = calc.get_strength("005930", now=base_ts + 300)
    assert strength == 100.0


def test_all_sell_strength_0():
    """전부 매도 시 체결강도 0."""
    calc = TradeStrengthCalculator(window_seconds=300)
    base_ts = 1000.0

    calc.add_execution("005930", base_ts, 100, "1")
    calc.add_execution("005930", base_ts + 10, 200, "1")

    strength = calc.get_strength("005930", now=base_ts + 300)
    assert strength == 0.0


def test_reset_stock():
    """종목 데이터 초기화."""
    calc = TradeStrengthCalculator(window_seconds=300)
    base_ts = 1000.0

    calc.add_execution("005930", base_ts, 100, "2")
    calc.reset("005930")

    assert calc.get_strength("005930") == 50.0


def test_unknown_stock_returns_neutral():
    """등록되지 않은 종목은 중립값 50 반환."""
    calc = TradeStrengthCalculator()
    assert calc.get_strength("999999") == 50.0


def test_multiple_stocks_independent():
    """종목별 독립 계산."""
    calc = TradeStrengthCalculator(window_seconds=300)
    base_ts = 1000.0

    calc.add_execution("005930", base_ts, 100, "2")  # 삼성 매수
    calc.add_execution("035720", base_ts, 100, "1")  # 카카오 매도

    s1 = calc.get_strength("005930", now=base_ts + 300)
    s2 = calc.get_strength("035720", now=base_ts + 300)

    assert s1 == 100.0
    assert s2 == 0.0
