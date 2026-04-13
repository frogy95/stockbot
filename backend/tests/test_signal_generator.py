"""신호 생성기 테스트 — DB/Redis mock 기반."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.trading.strategy import MarketSnapshot, Strategy, TradeSignalData


# === 픽스처 ===


def _make_candidate(**overrides) -> dict:
    """2차 스크리닝 후보 종목 dict 생성."""
    defaults = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "stock_type": "STOCK",
        "current_price": 73000,
        "volume": 40000000,
        "prev_volume": 10000000,
        "trade_strength": 95.0,
        "total_bid_volume": 800000,
        "total_ask_volume": 400000,
        "change_rate": 5.04,
    }
    defaults.update(overrides)
    return defaults


def _make_signal_data(stock_code: str = "005930") -> TradeSignalData:
    return TradeSignalData(
        stock_code=stock_code,
        signal_type="buy",
        strategy_name="momentum_breakout",
        confidence=0.75,
        reason={"test": True},
        entry_price=73000,
        stop_loss=71540,
        take_profit=75190,
    )


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    # realtime:{stock_code} -> JSON 실시간 데이터
    redis.get = AsyncMock(return_value=json.dumps({
        "open_price": 69500,
        "high": 73000,
        "low": 69000,
    }))
    return redis


@pytest.fixture
def mock_session_factory():
    session = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.fixture
def mock_strategy():
    strategy = AsyncMock(spec=Strategy)
    strategy.name = "momentum_breakout"
    strategy.generate_signal = AsyncMock(return_value=_make_signal_data())
    return strategy


# === 테스트 ===


@pytest.mark.asyncio
async def test_generate_signals_saves_to_db(
    mock_session_factory, mock_redis, mock_strategy
):
    """2차 스크리닝 통과 종목에 전략 적용 -> trade_signals 저장."""
    from modules.trading.signal_generator import SignalGenerator

    factory, session = mock_session_factory

    # 중복 신호 없음 (scalars().first() -> None)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    # market_data 조회 (최근 5일)
    mock_md_result = MagicMock()
    mock_md_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[mock_result, mock_md_result])

    gen = SignalGenerator(factory, mock_redis, mock_strategy)
    results = await gen.generate_signals([_make_candidate()])

    assert len(results) == 1
    assert results[0].stock_code == "005930"
    session.add.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_strategy_returns_none_no_save(
    mock_session_factory, mock_redis, mock_strategy
):
    """전략이 None 반환 -> trade_signals 미저장."""
    from modules.trading.signal_generator import SignalGenerator

    factory, session = mock_session_factory
    mock_strategy.generate_signal = AsyncMock(return_value=None)

    # 중복 없음 + market_data 빈 결과
    mock_no_dup = MagicMock()
    mock_no_dup.scalars.return_value.first.return_value = None
    mock_md = MagicMock()
    mock_md.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[mock_no_dup, mock_md])

    gen = SignalGenerator(factory, mock_redis, mock_strategy)
    results = await gen.generate_signals([_make_candidate()])

    assert len(results) == 0
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_low_confidence_filtered(
    mock_session_factory, mock_redis, mock_strategy
):
    """신뢰도 0.6 미만 필터."""
    from modules.trading.signal_generator import SignalGenerator

    factory, session = mock_session_factory
    low_signal = _make_signal_data()
    low_signal.confidence = 0.5
    mock_strategy.generate_signal = AsyncMock(return_value=low_signal)

    # 중복 없음 + market_data 빈 결과
    mock_no_dup = MagicMock()
    mock_no_dup.scalars.return_value.first.return_value = None
    mock_md = MagicMock()
    mock_md.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[mock_no_dup, mock_md])

    gen = SignalGenerator(factory, mock_redis, mock_strategy)
    results = await gen.generate_signals([_make_candidate()])

    assert len(results) == 0
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_signal_prevented(
    mock_session_factory, mock_redis, mock_strategy
):
    """동일 종목 중복 신호 방지."""
    from modules.trading.signal_generator import SignalGenerator

    factory, session = mock_session_factory

    # 이미 pending 신호 존재
    existing = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = existing
    session.execute = AsyncMock(return_value=mock_result)

    gen = SignalGenerator(factory, mock_redis, mock_strategy)
    results = await gen.generate_signals([_make_candidate()])

    assert len(results) == 0
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_build_snapshot_assembly(
    mock_session_factory, mock_redis, mock_strategy
):
    """MarketSnapshot 조립 검증: candidate dict 기반 필드 매핑."""
    from modules.trading.signal_generator import SignalGenerator

    factory, session = mock_session_factory

    # 중복 없음
    mock_no_dup = MagicMock()
    mock_no_dup.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=mock_no_dup)

    # candidate는 realtime_screener가 조립해 넘기는 것을 모사 — recent_*, prev_* 포함
    candidate = _make_candidate(
        recent_highs=[70500 - i * 500 for i in range(4, -1, -1)],  # ASC
        recent_lows=[68000 - i * 500 for i in range(4, -1, -1)],
        recent_closes=[69500 - i * 500 for i in range(4, -1, -1)],
        prev_close=69500,
        prev_high=70500,
    )

    gen = SignalGenerator(factory, mock_redis, mock_strategy)
    await gen.generate_signals([candidate])

    # generate_signal이 MarketSnapshot으로 호출되었는지 확인
    call_args = mock_strategy.generate_signal.call_args
    snapshot = call_args[0][0]
    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.stock_code == "005930"
    # candidate에 open_price 없음 → current_price로 폴백
    assert snapshot.open_price == 73000
    assert snapshot.prev_close == 69500
    assert snapshot.prev_high == 70500
    assert len(snapshot.recent_highs) == 5
