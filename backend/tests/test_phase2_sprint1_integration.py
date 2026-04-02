"""Phase 2 Sprint 1 통합 테스트."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from main import create_app
from modules.collector.scheduler import CollectorScheduler
from modules.collector.trade_strength import TradeStrengthCalculator
from modules.collector.sources.kis_realtime import (
    parse_raw_message,
    parse_execution,
    parse_orderbook,
)


# ── 장전 수집 파이프라인 ─────────────────────────────

@pytest.mark.asyncio
async def test_premarket_collect_pipeline():
    """공공데이터포털 mock -> 수집기 -> DB 저장 확인."""
    response_json = {
        "response": {
            "header": {"resultCode": "00"},
            "body": {
                "items": {
                    "item": [
                        {
                            "basDt": "20260329",
                            "srtnCd": "005930",
                            "itmsNm": "삼성전자",
                            "mrktCtg": "KOSPI",
                            "clpr": "70000",
                            "mkp": "69500",
                            "hipr": "70500",
                            "lopr": "69000",
                            "trqu": "15000000",
                            "mrktTotAmt": "417900000000000",
                            "lstgStCnt": "5969782550",
                            "fltRt": "1.45",
                        }
                    ]
                }
            },
        }
    }

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = response_json

    mock_db = AsyncMock()

    with patch("modules.collector.sources.data_go_kr.httpx.AsyncClient") as mock_client:
        mock_ctx = AsyncMock()
        mock_ctx.get.return_value = mock_resp
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        from modules.collector.sources.data_go_kr import DataGoKrCollector
        collector = DataGoKrCollector(mock_db)
        result = await collector.collect_all(retry_delay=0)

    assert result.collected == 1
    # stocks upsert + market_data insert = 2 execute calls
    assert mock_db.execute.call_count == 2
    mock_db.commit.assert_called_once()


# ── 실시간 데이터 파이프라인 ─────────────────────────

@pytest.mark.asyncio
async def test_realtime_data_pipeline():
    """WS 데이터 -> 파싱 -> 체결강도 계산."""
    # 체결 데이터 원시 메시지
    fields = [""] * 20
    fields[0] = "005930"
    fields[1] = "100530"
    fields[2] = "70000"
    fields[3] = "2"
    fields[4] = "1000"
    fields[5] = "1.45"
    fields[12] = "100"
    fields[13] = "5000000"
    fields[17] = "2"  # 매수
    body = "^".join(fields)

    raw = f"0|H0STCNT0|1|{body}"

    # 파싱
    parsed = parse_raw_message(raw)
    assert parsed is not None
    tr_id, _, msg_body = parsed
    assert tr_id == "H0STCNT0"

    execution = parse_execution(msg_body)
    assert execution is not None
    assert execution.stock_code == "005930"
    assert execution.sell_or_buy == "2"

    # 체결강도에 반영
    calc = TradeStrengthCalculator(window_seconds=300)
    calc.add_execution("005930", 1000.0, execution.volume, execution.sell_or_buy)
    # 5분 미달이므로 중립값
    assert calc.get_strength("005930", now=1100.0) == 50.0
    # 5분 경과 후
    assert calc.get_strength("005930", now=1300.0) == 100.0  # 매수만


# ── API 엔드포인트 통합 ─────────────────────────────

@pytest.mark.asyncio
async def test_collector_api_endpoints():
    """collector API 엔드포인트 동작 확인."""
    app = create_app()

    mock_scheduler = MagicMock(spec=CollectorScheduler)
    mock_scheduler.get_status.return_value = {
        "running": True,
        "job_count": 4,
        "next_jobs": [],
        "ws_subscriptions": 0,
        "last_premarket": None,
        "last_etf": None,
    }
    mock_scheduler.trigger_premarket = AsyncMock(return_value={"stocks_collected": 50})
    app.state.collector_scheduler = mock_scheduler
    app.state.trade_strength = TradeStrengthCalculator()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 상태 조회
        resp = await ac.get("/api/v1/collector/status")
        assert resp.status_code == 200
        assert resp.json()["running"] is True

        # 수동 트리거
        resp = await ac.post("/api/v1/collector/trigger/premarket")
        assert resp.status_code == 200
        assert resp.json()["triggered"] is True

        # 실시간 시세 (빈 데이터)
        resp = await ac.get("/api/v1/collector/realtime/005930")
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution"] is None
        assert data["trade_strength"] == 50.0


# ── ETF 수집 파이프라인 ─────────────────────────────

@pytest.mark.asyncio
async def test_etf_collect_pipeline():
    """ETF 수집 -> market_data 저장."""
    from core.clients.kis_rest import StockPrice
    from modules.collector.sources.kis_collector import KISCollector

    mock_rest = MagicMock()
    mock_rest.get_stock_price = AsyncMock(
        return_value=StockPrice(
            stock_code="069500",
            price=40000,
            change=500,
            change_rate=1.27,
            volume=3000000,
            trade_amount=120000000000,
            high=40500,
            low=39500,
            open_price=39800,
        )
    )
    mock_db = AsyncMock()

    collector = KISCollector(mock_rest, mock_db)
    result = await collector.collect_etf_prices(["069500", "252670"])

    assert result.collected == 2
    mock_db.commit.assert_called_once()
