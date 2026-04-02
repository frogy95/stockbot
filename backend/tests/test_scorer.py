"""FactorScorer 단위 테스트."""

import pytest

from modules.screening.scorer import (
    FactorScorer,
    PRIMARY_FACTORS,
    PRIMARY_WEIGHTS,
    STOCK_FACTORS,
    ETF_FACTORS,
)


class TestFactorScorerBasic:
    """기본 동작 테스트."""

    def test_empty_list_returns_empty(self):
        scorer = FactorScorer()
        assert scorer.score_candidates([]) == []

    def test_single_candidate_percentile_100(self):
        """단일 종목은 모든 팩터 백분위 100.0."""
        scorer = FactorScorer()
        candidates = [
            {
                "stock_code": "005930",
                "stock_type": "STOCK",
                "volume_factor": 150.0,
                "volatility_factor": 3.5,
                "momentum_factor": 2.0,
                "trade_strength_factor": 110.0,
                "orderbook_ratio_factor": 1.2,
            }
        ]
        result = scorer.score_candidates(candidates)
        assert len(result) == 1
        assert result[0]["score"] == pytest.approx(100.0)
        assert result[0]["rank"] == 1
        assert result[0]["is_passed"] is True
        for v in result[0]["factors"].values():
            assert v == pytest.approx(100.0)


class TestPercentileRanking:
    """순위 백분위 계산 테스트."""

    def test_three_candidates_volume_percentile(self):
        """3개 종목 volume_factor=[100, 200, 300] → 백분위 [33.3, 66.7, 100.0]."""
        scorer = FactorScorer()
        candidates = [
            {
                "stock_code": "A",
                "stock_type": "STOCK",
                "volume_factor": 100.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
            {
                "stock_code": "B",
                "stock_type": "STOCK",
                "volume_factor": 200.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
            {
                "stock_code": "C",
                "stock_type": "STOCK",
                "volume_factor": 300.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
        ]
        result = scorer.score_candidates(candidates)
        by_code = {r["stock_code"]: r for r in result}
        assert by_code["A"]["factors"]["volume_factor"] == pytest.approx(100 / 3 * 1, rel=1e-2)
        assert by_code["B"]["factors"]["volume_factor"] == pytest.approx(100 / 3 * 2, rel=1e-2)
        assert by_code["C"]["factors"]["volume_factor"] == pytest.approx(100.0, rel=1e-2)

    def test_tie_same_rank(self):
        """동률이면 같은 순위(= 같은 백분위)."""
        scorer = FactorScorer()
        candidates = [
            {
                "stock_code": "A",
                "stock_type": "STOCK",
                "volume_factor": 100.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
            {
                "stock_code": "B",
                "stock_type": "STOCK",
                "volume_factor": 100.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
        ]
        result = scorer.score_candidates(candidates)
        by_code = {r["stock_code"]: r for r in result}
        assert by_code["A"]["factors"]["volume_factor"] == by_code["B"]["factors"]["volume_factor"]


class TestWeightedScore:
    """가중 합산 테스트."""

    def test_equal_weight_five_factors(self):
        """5팩터 동일 가중(20%) 적용 검증."""
        scorer = FactorScorer()
        # 2개 종목: A가 모든 팩터에서 낮고, B가 높음
        candidates = [
            {
                "stock_code": "A",
                "stock_type": "STOCK",
                "volume_factor": 10.0,
                "volatility_factor": 10.0,
                "momentum_factor": 10.0,
                "trade_strength_factor": 10.0,
                "orderbook_ratio_factor": 10.0,
            },
            {
                "stock_code": "B",
                "stock_type": "STOCK",
                "volume_factor": 20.0,
                "volatility_factor": 20.0,
                "momentum_factor": 20.0,
                "trade_strength_factor": 20.0,
                "orderbook_ratio_factor": 20.0,
            },
        ]
        result = scorer.score_candidates(candidates)
        by_code = {r["stock_code"]: r for r in result}
        # B: 모든 팩터 백분위 100 → score = 100*0.2*5 = 100.0
        assert by_code["B"]["score"] == pytest.approx(100.0)
        # A: 모든 팩터 백분위 50 → score = 50*0.2*5 = 50.0
        assert by_code["A"]["score"] == pytest.approx(50.0)

    def test_custom_weights(self):
        """커스텀 가중치 적용 확인."""
        weights = {
            "volume_factor": 0.4,
            "volatility_factor": 0.1,
            "momentum_factor": 0.1,
            "trade_strength_factor": 0.1,
            "orderbook_ratio_factor": 0.3,
        }
        scorer = FactorScorer(factor_weights=weights)
        candidates = [
            {
                "stock_code": "A",
                "stock_type": "STOCK",
                "volume_factor": 100.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
        ]
        result = scorer.score_candidates(candidates)
        # 단일 종목이므로 모든 백분위 100 → score = 100
        assert result[0]["score"] == pytest.approx(100.0)


class TestPassThreshold:
    """통과 임계 테스트."""

    def test_score_above_threshold_passed(self):
        scorer = FactorScorer()
        candidates = [
            {
                "stock_code": "HIGH",
                "stock_type": "STOCK",
                "volume_factor": 999.0,
                "volatility_factor": 999.0,
                "momentum_factor": 999.0,
                "trade_strength_factor": 999.0,
                "orderbook_ratio_factor": 999.0,
            },
            {
                "stock_code": "LOW",
                "stock_type": "STOCK",
                "volume_factor": 1.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
        ]
        result = scorer.score_candidates(candidates)
        by_code = {r["stock_code"]: r for r in result}
        assert by_code["HIGH"]["is_passed"] is True
        assert by_code["LOW"]["is_passed"] is False

    def test_exact_threshold_passed(self):
        """score == 80.0 이면 is_passed=True."""
        scorer = FactorScorer(pass_threshold=80.0)
        # 5종목 중 4등 → 백분위 = 2/5*100 = 40 (기본 5팩터 모두 같다면)
        # 간단히 단일 종목(백분위 100) + threshold 100 테스트
        scorer2 = FactorScorer(pass_threshold=100.0)
        candidates = [
            {
                "stock_code": "ONLY",
                "stock_type": "STOCK",
                "volume_factor": 1.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
        ]
        result = scorer2.score_candidates(candidates)
        assert result[0]["score"] == pytest.approx(100.0)
        assert result[0]["is_passed"] is True


class TestETFFactor:
    """ETF 팩터 분기 테스트."""

    def test_etf_uses_tracking_error_instead_of_orderbook(self):
        """ETF는 orderbook_ratio_factor 대신 tracking_error_factor 사용."""
        scorer = FactorScorer()
        candidates = [
            {
                "stock_code": "ETF_A",
                "stock_type": "ETF",
                "volume_factor": 100.0,
                "volatility_factor": 3.0,
                "momentum_factor": 2.0,
                "trade_strength_factor": 110.0,
                "tracking_error_factor": 0.5,
            },
            {
                "stock_code": "ETF_B",
                "stock_type": "ETF",
                "volume_factor": 200.0,
                "volatility_factor": 4.0,
                "momentum_factor": 3.0,
                "trade_strength_factor": 120.0,
                "tracking_error_factor": 1.5,
            },
        ]
        result = scorer.score_candidates(candidates)
        by_code = {r["stock_code"]: r for r in result}
        assert "tracking_error_factor" in by_code["ETF_A"]["factors"]
        assert "orderbook_ratio_factor" not in by_code["ETF_A"]["factors"]

    def test_etf_tracking_error_reverse_rank(self):
        """tracking_error는 낮을수록 좋으므로 역순위."""
        scorer = FactorScorer()
        candidates = [
            {
                "stock_code": "ETF_LOW",
                "stock_type": "ETF",
                "volume_factor": 100.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "tracking_error_factor": 0.1,  # 낮음 → 좋음 → 높은 백분위
            },
            {
                "stock_code": "ETF_HIGH",
                "stock_type": "ETF",
                "volume_factor": 100.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "tracking_error_factor": 5.0,  # 높음 → 나쁨 → 낮은 백분위
            },
        ]
        result = scorer.score_candidates(candidates)
        by_code = {r["stock_code"]: r for r in result}
        assert (
            by_code["ETF_LOW"]["factors"]["tracking_error_factor"]
            > by_code["ETF_HIGH"]["factors"]["tracking_error_factor"]
        )

    def test_mixed_stock_and_etf(self):
        """주식/ETF 혼합 시 각각 독립적으로 순위 계산 후 합산."""
        scorer = FactorScorer()
        candidates = [
            {
                "stock_code": "STOCK_1",
                "stock_type": "STOCK",
                "volume_factor": 100.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
            {
                "stock_code": "ETF_1",
                "stock_type": "ETF",
                "volume_factor": 200.0,
                "volatility_factor": 2.0,
                "momentum_factor": 2.0,
                "trade_strength_factor": 2.0,
                "tracking_error_factor": 0.5,
            },
        ]
        result = scorer.score_candidates(candidates)
        assert len(result) == 2
        # 각각 단독 그룹이므로 모든 백분위 100 → score 100
        for r in result:
            assert r["score"] == pytest.approx(100.0)
            assert r["is_passed"] is True


class TestPrimaryFactorScorer:
    """1차 스크리닝 전용 3팩터 스코어러 테스트."""

    def _primary_scorer(self) -> FactorScorer:
        return FactorScorer(
            factors={"STOCK": PRIMARY_FACTORS, "ETF": PRIMARY_FACTORS},
            factor_weights=PRIMARY_WEIGHTS,
            pass_threshold=60.0,
        )

    def _make_primary_candidate(self, code: str, v: float) -> dict:
        return {
            "stock_code": code,
            "stock_type": "STOCK",
            "volume_factor": v,
            "volatility_factor": v,
            "momentum_factor": v,
        }

    def test_primary_3_factors_only(self):
        """PRIMARY_FACTORS + PRIMARY_WEIGHTS로 생성한 스코어러는 factors dict에 3개 키만 포함."""
        result = self._primary_scorer().score_candidates([self._make_primary_candidate("A", 1.0)])
        assert set(result[0]["factors"].keys()) == set(PRIMARY_FACTORS)

    def test_primary_threshold_60(self):
        """단일 종목 3팩터 all 백분위 100 → score=100 → is_passed=True (threshold=60)."""
        result = self._primary_scorer().score_candidates([self._make_primary_candidate("A", 1.0)])
        assert result[0]["score"] == pytest.approx(100.0)
        assert result[0]["is_passed"] is True

    def test_primary_threshold_rejects_low_score(self):
        """2종목 중 하위 종목 score < 60 → is_passed=False."""
        candidates = [
            self._make_primary_candidate("HIGH", 100.0),
            self._make_primary_candidate("LOW", 1.0),
        ]
        result = self._primary_scorer().score_candidates(candidates)
        by_code = {r["stock_code"]: r for r in result}
        assert by_code["HIGH"]["is_passed"] is True
        assert by_code["LOW"]["is_passed"] is False

    def test_factors_parameter_backward_compatible(self):
        """FactorScorer(factors 미지정)는 기존 STOCK_FACTORS/ETF_FACTORS 사용."""
        scorer = FactorScorer()
        assert scorer._stock_factors == STOCK_FACTORS
        assert scorer._etf_factors == ETF_FACTORS

    def test_bug_regression_all_tie_factors(self):
        """44개 후보에 trade_strength/orderbook 동률 시 5팩터 pass=0건, 3팩터 pass 존재."""
        candidates = [
            {
                "stock_code": f"{i:06d}",
                "stock_type": "STOCK",
                "volume_factor": float(i + 1),
                "volatility_factor": float(i + 1),
                "momentum_factor": float(i + 1),
                "trade_strength_factor": 50.0,   # 전체 동률
                "orderbook_ratio_factor": 1.0,   # 전체 동률
            }
            for i in range(44)
        ]

        # 버그 재현: 동률 팩터가 백분위 ~2.27로 낮아져 모두 pass_threshold=80 미달
        scorer_5 = FactorScorer(pass_threshold=80.0)
        passed_5 = [r for r in scorer_5.score_candidates(candidates) if r["is_passed"]]
        assert len(passed_5) == 0

        # 수정 검증: 3팩터만 사용하면 동률 팩터 영향 없이 통과 종목 존재
        passed_3 = [r for r in self._primary_scorer().score_candidates(candidates) if r["is_passed"]]
        assert len(passed_3) > 0


class TestRankOrder:
    """전체 순위 정렬 테스트."""

    def test_rank_descending_by_score(self):
        scorer = FactorScorer()
        candidates = [
            {
                "stock_code": "LOW",
                "stock_type": "STOCK",
                "volume_factor": 1.0,
                "volatility_factor": 1.0,
                "momentum_factor": 1.0,
                "trade_strength_factor": 1.0,
                "orderbook_ratio_factor": 1.0,
            },
            {
                "stock_code": "HIGH",
                "stock_type": "STOCK",
                "volume_factor": 100.0,
                "volatility_factor": 100.0,
                "momentum_factor": 100.0,
                "trade_strength_factor": 100.0,
                "orderbook_ratio_factor": 100.0,
            },
        ]
        result = scorer.score_candidates(candidates)
        assert result[0]["stock_code"] == "HIGH"
        assert result[0]["rank"] == 1
        assert result[1]["stock_code"] == "LOW"
        assert result[1]["rank"] == 2
