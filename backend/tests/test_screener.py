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

        # _get_recent_market_data를 모킹 — momentum(4개 이상), volatility(2개 이상) 계산 가능하도록
        recent_data = {}
        for i, code in enumerate(["005930", "000660", "035420"]):
            base = 50_000 + i * 10_000
            recent_data[code] = [
                {"close_price": base, "high_price": base + 2000, "low_price": base - 2000, "data_date": today},
                {"close_price": base - 500, "high_price": base + 1500, "low_price": base - 2500, "data_date": today},
                {"close_price": base - 1000, "high_price": base + 1000, "low_price": base - 3000, "data_date": today},
                {"close_price": base - 1500, "high_price": base + 500, "low_price": base - 3500, "data_date": today},
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
            # 1차 스크리닝은 3팩터만 사용 — 실시간 팩터 미포함
            for item in result:
                assert "trade_strength_factor" not in item["factors"]
                assert "orderbook_ratio_factor" not in item["factors"]
            # 3팩터 + pass_threshold=60 → 상위 종목은 통과
            assert any(item["is_passed"] for item in result)


# ---------------------------------------------------------------------------
# _build_candidates 실시간 팩터 미포함 테스트
# ---------------------------------------------------------------------------

class TestBuildCandidates:
    """_build_candidates가 3팩터만 반환하는지 검증."""

    def test_build_candidates_no_realtime_factors(self):
        """_build_candidates 결과 dict에 실시간 전용 팩터 키가 없음."""
        screener = PrimaryScreener()
        filtered = [
            _make_row("005930", "삼성전자", volume=200_000, prev_volume=50_000),
            _make_row("000660", "SK하이닉스", volume=150_000, prev_volume=40_000),
        ]
        today = date.today()
        recent_data = {
            "005930": [
                {"close_price": 50000, "high_price": 52000, "low_price": 48000, "data_date": today},
                {"close_price": 49000, "high_price": 51000, "low_price": 47000, "data_date": today},
                {"close_price": 48000, "high_price": 50000, "low_price": 46000, "data_date": today},
                {"close_price": 47000, "high_price": 49000, "low_price": 45000, "data_date": today},
            ],
            "000660": [
                {"close_price": 80000, "high_price": 83000, "low_price": 77000, "data_date": today},
                {"close_price": 79000, "high_price": 82000, "low_price": 76000, "data_date": today},
                {"close_price": 78000, "high_price": 81000, "low_price": 75000, "data_date": today},
                {"close_price": 77000, "high_price": 80000, "low_price": 74000, "data_date": today},
            ],
        }
        candidates = screener._build_candidates(filtered, recent_data)
        assert len(candidates) == 2
        for c in candidates:
            assert "trade_strength_factor" not in c
            assert "orderbook_ratio_factor" not in c
            assert "tracking_error_factor" not in c
            assert "volume_factor" in c
            assert "volatility_factor" in c
            assert "momentum_factor" in c


# ---------------------------------------------------------------------------
# save_results 테스트
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# kis_daily 소스 필터 + market_cap 추정 테스트
# ---------------------------------------------------------------------------

class TestFetchTodayAndPrev:
    """_fetch_today_and_prev 소스 필터 확장 + market_cap 추정 검증."""

    @pytest.mark.asyncio
    async def test_fetch_includes_kis_daily_source(self):
        """date_subq가 source IN ('data_go_kr', 'kis_daily')를 포함하는지 확인."""
        screener = PrimaryScreener()
        session = AsyncMock()

        captured_stmts = []

        async def capture_execute(stmt, *args, **kwargs):
            captured_stmts.append(stmt)
            mock_result = MagicMock()
            mock_result.mappings.return_value.all.return_value = []
            return mock_result

        session.execute = capture_execute

        await screener._fetch_today_and_prev(session)

        assert len(captured_stmts) >= 1
        compiled = str(captured_stmts[0].compile(compile_kwargs={"literal_binds": True}))
        assert "kis_daily" in compiled

    @pytest.mark.asyncio
    async def test_market_cap_estimation_from_listed_shares(self):
        """market_cap=None이고 listed_shares와 close_price가 있으면 추정값 반환."""
        screener = PrimaryScreener()
        session = AsyncMock()

        today = date.today()
        row = {
            "stock_code": "005930",
            "data_date": today,
            "stock_name": "삼성전자",
            "stock_type": "STOCK",
            "market_type": "KOSPI",
            "volume": 100_000,
            "market_cap": None,
            "listed_shares": 5_000_000_000,
            "change_rate": Decimal("1.5"),
            "close_price": 70_000,
            "high_price": 72_000,
            "low_price": 69_000,
            "open_price": 70_000,
        }

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [row]
        session.execute = AsyncMock(return_value=mock_result)

        result = await screener._fetch_today_and_prev(session)

        assert "005930" in result
        expected_cap = 5_000_000_000 * 70_000
        assert result["005930"]["market_cap"] == expected_cap

    @pytest.mark.asyncio
    async def test_market_cap_zero_when_no_listed_shares(self):
        """listed_shares가 None이면 market_cap=0 유지."""
        screener = PrimaryScreener()
        session = AsyncMock()

        today = date.today()
        row = {
            "stock_code": "005930",
            "data_date": today,
            "stock_name": "삼성전자",
            "stock_type": "STOCK",
            "market_type": "KOSPI",
            "volume": 100_000,
            "market_cap": None,
            "listed_shares": None,
            "change_rate": Decimal("1.5"),
            "close_price": 70_000,
            "high_price": 72_000,
            "low_price": 69_000,
            "open_price": 70_000,
        }

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [row]
        session.execute = AsyncMock(return_value=mock_result)

        result = await screener._fetch_today_and_prev(session)

        assert "005930" in result
        assert result["005930"]["market_cap"] == 0

    @pytest.mark.asyncio
    async def test_mixed_source_latest_date_priority(self):
        """동일 종목에 data_go_kr(최신)과 kis_daily(이전 날짜)가 있으면 최신 날짜 우선."""
        screener = PrimaryScreener()
        session = AsyncMock()

        today = date.today()
        from datetime import timedelta
        yesterday = today - timedelta(days=1)

        rows = [
            # data_go_kr (최신: today)
            {
                "stock_code": "005930",
                "data_date": today,
                "stock_name": "삼성전자",
                "stock_type": "STOCK",
                "market_type": "KOSPI",
                "volume": 200_000,
                "market_cap": 400_000_000_000_000,
                "listed_shares": None,
                "change_rate": Decimal("2.0"),
                "close_price": 80_000,
                "high_price": 82_000,
                "low_price": 78_000,
                "open_price": 79_000,
            },
            # kis_daily (이전: yesterday — prev_volume으로 사용)
            {
                "stock_code": "005930",
                "data_date": yesterday,
                "stock_name": "삼성전자",
                "stock_type": "STOCK",
                "market_type": "KOSPI",
                "volume": 100_000,
                "market_cap": None,
                "listed_shares": None,
                "change_rate": Decimal("1.0"),
                "close_price": 78_000,
                "high_price": 80_000,
                "low_price": 76_000,
                "open_price": 77_000,
            },
        ]

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = rows
        session.execute = AsyncMock(return_value=mock_result)

        result = await screener._fetch_today_and_prev(session)

        assert "005930" in result
        # 최신 날짜 데이터가 당일로 선택됨
        assert result["005930"]["close_price"] == 80_000
        # 이전 날짜가 prev_volume으로 사용됨
        assert result["005930"]["prev_volume"] == 100_000


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


# ---------------------------------------------------------------------------
# 적응형 필터 테스트
# ---------------------------------------------------------------------------

class TestAdaptiveFilter:
    """_apply_filters_with_adaptive 단계적 완화 로직 검증."""

    def _make_rows_with_ratio(self, count: int, volume_ratio: float, base_code: int = 0) -> list[dict]:
        """volume_ratio를 정확히 가지는 행 생성."""
        rows = []
        for i in range(count):
            prev = 100_000
            vol = int(prev * volume_ratio)
            rows.append(_make_row(
                f"{base_code + i:06d}", f"종목{base_code + i}",
                volume=vol, prev_volume=prev,
                market_cap=100_000_000_000, change_rate=3.0,
            ))
        return rows

    def test_no_relaxation_when_enough(self):
        """1.5 기본 필터로 10개 이상 → is_relaxed=False."""
        screener = PrimaryScreener()
        # volume_ratio=2.0 → 1.5 통과 12개
        rows = self._make_rows_with_ratio(12, volume_ratio=2.0)
        passed, is_relaxed = screener._apply_filters_with_adaptive(rows)
        assert len(passed) >= 10
        assert is_relaxed is False

    def test_adaptive_relaxes_when_below_min(self):
        """1.5 통과 <10개, 1.2 통과 >=10개 → is_relaxed=True."""
        screener = PrimaryScreener()
        # volume_ratio=1.6 → 1.5 통과 5개
        rows_pass_15 = self._make_rows_with_ratio(5, volume_ratio=1.6, base_code=0)
        # volume_ratio=1.3 → 1.2 통과 but 1.5 미통과 10개
        rows_pass_12 = self._make_rows_with_ratio(10, volume_ratio=1.3, base_code=100)
        passed, is_relaxed = screener._apply_filters_with_adaptive(rows_pass_15 + rows_pass_12)
        assert len(passed) >= 10
        assert is_relaxed is True

    def test_adaptive_stops_at_1_2(self):
        """모든 adaptive_step 소진해도 0건이면 is_relaxed=True로 마지막 결과 반환."""
        screener = PrimaryScreener()
        # volume_ratio=1.0 → 1.2도 미통과 (1.0 < 1.2)
        rows = self._make_rows_with_ratio(5, volume_ratio=1.05, base_code=0)
        passed, is_relaxed = screener._apply_filters_with_adaptive(rows)
        # 1.2 기준 통과 불가 → 빈 결과 or 소수
        assert is_relaxed is True  # 완화 시도는 했음

    @pytest.mark.asyncio
    async def test_is_relaxed_flag_on_screen_result(self):
        """적응형 완화 발생 시 screen() 결과 모든 항목에 is_relaxed=True."""
        screener = PrimaryScreener()
        # 1.5 통과 5개, 1.2 통과 10개
        rows_15 = self._make_rows_with_ratio(5, volume_ratio=1.6, base_code=0)
        rows_12 = self._make_rows_with_ratio(10, volume_ratio=1.3, base_code=100)
        today_prev = {r["stock_code"]: r for r in rows_15 + rows_12}
        recent_data = {}

        with patch.object(screener, "_fetch_today_and_prev", new_callable=AsyncMock) as mf, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mr:
            mf.return_value = today_prev
            mr.return_value = recent_data
            session = AsyncMock()
            result = await screener.screen(session)

        assert len(result) > 0
        for item in result:
            assert item.get("is_relaxed") is True


# ---------------------------------------------------------------------------
# prev_volume 폴백 테스트
# ---------------------------------------------------------------------------

class TestPrevVolumeFallback:
    """prev_volume=0 시 5일 평균 폴백 동작 검증."""

    @pytest.mark.asyncio
    async def test_fallback_5day_avg(self):
        """prev_volume=0 종목에 5일 평균 거래량 폴백 적용 (일괄 조회)."""
        screener = PrimaryScreener()
        session = AsyncMock()

        volumes = [100_000, 120_000, 110_000]  # 3일 유효 데이터

        # session.execute → result.all() → [(code, vol), ...]
        fallback_result = MagicMock()
        fallback_result.all.return_value = [("005930", v) for v in volumes]
        session.execute = AsyncMock(return_value=fallback_result)

        result = await screener._get_fallback_prev_volumes(session, ["005930"])

        expected = sum(volumes) // len(volumes)
        assert result.get("005930") == expected

    @pytest.mark.asyncio
    async def test_fallback_insufficient_data(self):
        """유효 데이터 2일 이하면 해당 종목 미포함."""
        screener = PrimaryScreener()
        session = AsyncMock()

        # 2일치만 반환
        fallback_result = MagicMock()
        fallback_result.all.return_value = [("005930", 80_000), ("005930", 90_000)]
        session.execute = AsyncMock(return_value=fallback_result)

        result = await screener._get_fallback_prev_volumes(session, ["005930"])

        assert "005930" not in result


# ---------------------------------------------------------------------------
# 기본 후보 선정 테스트 (0건 시 거래량 상위 15개)
# ---------------------------------------------------------------------------

class TestFallbackCandidates:
    """적응형 필터 0건 시 기본 후보(거래량 상위 15개, 시총 500억+) 선정 검증."""

    def _make_rows_bulk(self, count: int, volume: int, market_cap: int, base_code: int = 0) -> list[dict]:
        return [
            _make_row(
                f"{base_code + i:06d}", f"종목{base_code + i}",
                volume=volume - i * 100,  # 거래량 내림차순 보장
                prev_volume=0,
                market_cap=market_cap,
                change_rate=0.5,  # 필터 미통과 (1.0 미만)
            )
            for i in range(count)
        ]

    @pytest.mark.asyncio
    async def test_fallback_returns_top_15(self):
        """적응형 필터 0건 시 거래량 상위 15개 반환."""
        screener = PrimaryScreener()
        # 20개 종목 모두 필터 미통과 (change_rate=0.5 < 1.0)
        rows = self._make_rows_bulk(20, volume=200_000, market_cap=100_000_000_000)
        today_prev = {r["stock_code"]: r for r in rows}

        with patch.object(screener, "_fetch_today_and_prev", new_callable=AsyncMock) as mf, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mr:
            mf.return_value = today_prev
            mr.return_value = {}
            session = AsyncMock()
            result = await screener.screen(session)

        assert len(result) == 15

    @pytest.mark.asyncio
    async def test_fallback_market_cap_filter(self):
        """시총 500억 미만 종목은 기본 후보에서 제외."""
        screener = PrimaryScreener()
        # 10개: 시총 500억+ / 5개: 시총 500억 미만
        rows_ok = self._make_rows_bulk(10, volume=200_000, market_cap=100_000_000_000, base_code=0)
        rows_small = self._make_rows_bulk(5, volume=300_000, market_cap=10_000_000_000, base_code=100)
        today_prev = {r["stock_code"]: r for r in rows_ok + rows_small}

        with patch.object(screener, "_fetch_today_and_prev", new_callable=AsyncMock) as mf, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mr:
            mf.return_value = today_prev
            mr.return_value = {}
            session = AsyncMock()
            result = await screener.screen(session)

        codes = {r["stock_code"] for r in result}
        # 시총 500억 미만 종목(base_code=100+)은 결과에 없어야 함
        assert not any(c.startswith("1") for c in codes)

    @pytest.mark.asyncio
    async def test_fallback_flags(self):
        """기본 후보에 is_fallback, auto_trade_blocked, position_size_ratio 플래그 설정."""
        screener = PrimaryScreener()
        rows = self._make_rows_bulk(20, volume=200_000, market_cap=100_000_000_000)
        today_prev = {r["stock_code"]: r for r in rows}

        with patch.object(screener, "_fetch_today_and_prev", new_callable=AsyncMock) as mf, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mr:
            mf.return_value = today_prev
            mr.return_value = {}
            session = AsyncMock()
            result = await screener.screen(session)

        for item in result:
            assert item.get("is_fallback") is True
            assert item.get("is_relaxed") is True
            assert item.get("auto_trade_blocked") is True
            assert item.get("position_size_ratio") == 0.5

    @pytest.mark.asyncio
    async def test_fallback_skips_scoring(self):
        """기본 후보는 스코어링 skip — score=0, factors={}."""
        screener = PrimaryScreener()
        rows = self._make_rows_bulk(20, volume=200_000, market_cap=100_000_000_000)
        today_prev = {r["stock_code"]: r for r in rows}

        with patch.object(screener, "_fetch_today_and_prev", new_callable=AsyncMock) as mf, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mr:
            mf.return_value = today_prev
            mr.return_value = {}
            session = AsyncMock()
            result = await screener.screen(session)

        for item in result:
            assert item.get("score") == 0
            assert item.get("factors") == {}

    @pytest.mark.asyncio
    async def test_no_fallback_when_candidates_exist(self):
        """필터 통과 후보가 있으면 기본 후보 미생성."""
        screener = PrimaryScreener()
        # 12개 종목 필터 통과 (volume_ratio=2.0, change_rate=3.0)
        rows = [
            _make_row(f"{i:06d}", f"종목{i}", volume=200_000, prev_volume=100_000,
                      market_cap=100_000_000_000, change_rate=3.0)
            for i in range(12)
        ]
        today_prev = {r["stock_code"]: r for r in rows}

        with patch.object(screener, "_fetch_today_and_prev", new_callable=AsyncMock) as mf, \
             patch.object(screener, "_get_recent_market_data", new_callable=AsyncMock) as mr:
            mf.return_value = today_prev
            mr.return_value = {}
            session = AsyncMock()
            result = await screener.screen(session)

        # 기본 후보가 아닌 일반 스코어링 결과여야 함
        for item in result:
            assert item.get("is_fallback") is not True
