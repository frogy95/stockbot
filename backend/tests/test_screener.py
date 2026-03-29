"""1차 스크리닝 엔진 테스트 (DB 모킹 — 순수 로직 검증)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from modules.screening.filters import PrimaryFilters
from modules.screening.screener import PrimaryScreener


# ---------------------------------------------------------------------------
# 헬퍼: 테스트용 종목 데이터 생성
# ---------------------------------------------------------------------------

def _make_row(
    stock_code: str,
    stock_name: str,
    stock_type: str = "STOCK",
    market_type: str = "KOSPI",
    volume: int = 200_000,
    prev_volume: int = 50_000,
    market_cap: int = 100_000_000_000,
    change_rate: float = 3.0,
    close_price: int = 10_000,
    high_price: int = 10_500,
    low_price: int = 9_500,
) -> dict:
    """필터/스코어링 테스트에 사용할 행 데이터."""
    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "stock_type": stock_type,
        "market_type": market_type,
        "volume": volume,
        "prev_volume": prev_volume,
        "market_cap": market_cap,
        "change_rate": change_rate,
        "close_price": close_price,
        "high_price": high_price,
        "low_price": low_price,
    }


# ---------------------------------------------------------------------------
# _apply_filters 테스트
# ---------------------------------------------------------------------------

class TestApplyFilters:
    """PrimaryScreener._apply_filters 순수 로직 검증."""

    def setup_method(self):
        self.screener = PrimaryScreener()

    def test_filters_pass_and_reject(self):
        """5종목 중 3종목만 필터 통과."""
        rows = [
            # 통과: 거래량비율 4x, 시총 OK, 등락률 OK
            _make_row("005930", "삼성전자", volume=200_000, prev_volume=50_000,
                      market_cap=100_000_000_000, change_rate=3.0),
            # 통과
            _make_row("000660", "SK하이닉스", volume=100_000, prev_volume=30_000,
                      market_cap=80_000_000_000, change_rate=5.0),
            # 제외: 시총 미달
            _make_row("999999", "소형주A", volume=200_000, prev_volume=50_000,
                      market_cap=10_000_000_000, change_rate=3.0),
            # 제외: 등락률 초과
            _make_row("888888", "급등주B", volume=200_000, prev_volume=50_000,
                      market_cap=100_000_000_000, change_rate=10.0),
            # 통과
            _make_row("035420", "NAVER", volume=150_000, prev_volume=60_000,
                      market_cap=200_000_000_000, change_rate=2.5),
        ]
        result = self.screener._apply_filters(rows)
        codes = [r["stock_code"] for r in result]
        assert len(result) == 3
        assert "005930" in codes
        assert "000660" in codes
        assert "035420" in codes

    def test_all_rejected(self):
        """모든 종목 필터 미통과 시 빈 리스트."""
        rows = [
            _make_row("111111", "소형주", market_cap=1_000_000_000, change_rate=0.5),
        ]
        result = self.screener._apply_filters(rows)
        assert result == []

    def test_prev_volume_zero(self):
        """전일 거래량 0인 종목은 제외."""
        rows = [
            _make_row("222222", "무거래주", prev_volume=0),
        ]
        result = self.screener._apply_filters(rows)
        assert result == []

    def test_etf_volume_threshold(self):
        """ETF는 volume_min_etf(10000) 적용."""
        rows = [
            _make_row("069500", "KODEX200", stock_type="ETF",
                      volume=15_000, prev_volume=5_000,
                      market_cap=100_000_000_000, change_rate=2.0),
        ]
        result = self.screener._apply_filters(rows)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 후보 상한 테스트
# ---------------------------------------------------------------------------

class TestMaxCandidates:
    """상위 30종목 제한 테스트."""

    def setup_method(self):
        self.screener = PrimaryScreener()

    def test_truncate_to_max_candidates(self):
        """40종목 통과 시 스코어 상위 30종목만 반환."""
        # _apply_filters 결과에 40종목이 있는 상황 시뮬레이션
        scored = []
        for i in range(40):
            scored.append({
                "stock_code": f"{i:06d}",
                "stock_name": f"종목{i}",
                "stock_type": "STOCK",
                "market_type": "KOSPI",
                "score": Decimal(str(60 + i)),
                "rank": 0,
                "factors": {},
                "is_passed": True,
                "is_hot": False,
                "volume": 100_000,
                "volume_ratio": 3.0,
                "market_cap": 100_000_000_000,
                "change_rate": 3.0,
            })
        result = self.screener._truncate_and_rank(scored)
        assert len(result) == 30
        # 스코어 내림차순, rank 1부터
        assert result[0]["rank"] == 1
        assert result[0]["score"] >= result[-1]["score"]
        assert result[-1]["rank"] == 30


# ---------------------------------------------------------------------------
# 핫 종목 플래그 테스트
# ---------------------------------------------------------------------------

class TestHotStockFlag:
    """거래량 500%+ 종목에 is_hot=True."""

    def setup_method(self):
        self.screener = PrimaryScreener()

    def test_hot_stock_flag(self):
        rows = [
            {
                "stock_code": "005930",
                "volume_ratio": 6.0,
                "is_hot": False,
            },
            {
                "stock_code": "000660",
                "volume_ratio": 3.0,
                "is_hot": False,
            },
        ]
        self.screener._mark_hot_stocks(rows)
        assert rows[0]["is_hot"] is True
        assert rows[1]["is_hot"] is False


# ---------------------------------------------------------------------------
# DB 데이터 없음 시 빈 리스트 반환
# ---------------------------------------------------------------------------

class TestScreenEmpty:
    """DB에 데이터가 없을 때 빈 리스트 반환."""

    @pytest.mark.asyncio
    async def test_empty_db_returns_empty(self):
        screener = PrimaryScreener()
        session = AsyncMock()
        # scalars().all() 이 빈 리스트 반환
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []

        # session.execute -> result -> mappings -> all
        execute_result = MagicMock()
        execute_result.mappings.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=execute_result)

        result = await screener.screen(session)
        assert result == []


# ---------------------------------------------------------------------------
# screen 통합 (DB 모킹)
# ---------------------------------------------------------------------------

class TestScreenIntegration:
    """screen() 메서드의 전체 흐름 테스트 (DB + scorer 모킹)."""

    @pytest.mark.asyncio
    async def test_screen_full_flow(self):
        screener = PrimaryScreener()

        today = date.today()

        # DB에서 반환될 row 데이터 (mappings 형태)
        db_rows = []
        for i, (code, name) in enumerate([
            ("005930", "삼성전자"),
            ("000660", "SK하이닉스"),
            ("035420", "NAVER"),
        ]):
            # 당일 데이터
            db_rows.append({
                "stock_code": code,
                "stock_name": name,
                "stock_type": "STOCK",
                "market_type": "KOSPI",
                "data_date": today,
                "volume": 200_000 + i * 50_000,
                "market_cap": 100_000_000_000,
                "change_rate": Decimal("3.0"),
                "close_price": 50_000 + i * 10_000,
                "high_price": 52_000 + i * 10_000,
                "low_price": 48_000 + i * 10_000,
                "open_price": 49_000 + i * 10_000,
            })

        # _get_recent_market_data를 모킹하여 종목별 최근 데이터 반환
        recent_data = {}
        for code in ["005930", "000660", "035420"]:
            recent_data[code] = [
                {"close_price": 50000, "high_price": 52000, "low_price": 48000, "data_date": today},
            ]

        # _fetch_today_and_prev를 모킹
        today_prev = {}
        for i, code in enumerate(["005930", "000660", "035420"]):
            today_prev[code] = {
                "stock_code": code,
                "stock_name": ["삼성전자", "SK하이닉스", "NAVER"][i],
                "stock_type": "STOCK",
                "market_type": "KOSPI",
                "volume": 200_000 + i * 50_000,
                "prev_volume": 50_000,
                "market_cap": 100_000_000_000,
                "change_rate": float(Decimal("3.0")),
                "close_price": 50_000 + i * 10_000,
                "high_price": 52_000 + i * 10_000,
                "low_price": 48_000 + i * 10_000,
            }

        with patch.object(screener, "_fetch_today_and_prev", new_callable=AsyncMock) as mock_fetch, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mock_recent:

            mock_fetch.return_value = today_prev
            mock_recent.return_value = recent_data

            session = AsyncMock()
            result = await screener.screen(session)

            # 3종목 모두 필터 통과 (volume_ratio=4+, 시총 OK, 등락률 OK)
            assert len(result) == 3
            # 결과에 필수 키 포함
            for item in result:
                assert "stock_code" in item
                assert "stock_name" in item
                assert "score" in item
                assert "rank" in item
                assert "factors" in item
                assert "is_hot" in item
                assert "is_passed" in item
                assert "volume" in item
                assert "volume_ratio" in item
                assert "market_cap" in item
                assert "change_rate" in item
            # rank 순서
            assert result[0]["rank"] == 1


# ---------------------------------------------------------------------------
# save_results 테스트
# ---------------------------------------------------------------------------

class TestSaveResults:
    """screening_results 테이블에 결과 저장."""

    @pytest.mark.asyncio
    async def test_save_results(self):
        screener = PrimaryScreener()
        session = AsyncMock()
        session.commit = AsyncMock()

        results = [
            {
                "stock_code": "005930",
                "score": Decimal("85.00"),
                "rank": 1,
                "factors": {"volume": 90.0},
                "is_hot": True,
                "is_passed": True,
            },
            {
                "stock_code": "000660",
                "score": Decimal("75.00"),
                "rank": 2,
                "factors": {"volume": 70.0},
                "is_hot": False,
                "is_passed": False,
            },
        ]

        count = await screener.save_results(session, results)
        assert count == 2
        assert session.add.call_count == 2
        session.commit.assert_awaited_once()
