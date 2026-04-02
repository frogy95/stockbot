"""팩터 스코어링 엔진 — 후보 종목의 팩터별 순위 백분위를 계산하고 가중 합산 스코어를 부여한다."""

from __future__ import annotations

STOCK_FACTORS = [
    "volume_factor",
    "volatility_factor",
    "momentum_factor",
    "trade_strength_factor",
    "orderbook_ratio_factor",
]

ETF_FACTORS = [
    "volume_factor",
    "volatility_factor",
    "momentum_factor",
    "trade_strength_factor",
    "tracking_error_factor",
]

PRIMARY_FACTORS = ["volume_factor", "volatility_factor", "momentum_factor"]
PRIMARY_WEIGHTS: dict[str, float] = {
    "volume_factor": 1 / 3,
    "volatility_factor": 1 / 3,
    "momentum_factor": 1 / 3,
}

# 낮을수록 좋은 팩터 (역순위 적용)
REVERSE_FACTORS = {"tracking_error_factor"}

DEFAULT_WEIGHTS: dict[str, float] = {
    "volume_factor": 0.2,
    "volatility_factor": 0.2,
    "momentum_factor": 0.2,
    "trade_strength_factor": 0.2,
    "orderbook_ratio_factor": 0.2,
    "tracking_error_factor": 0.2,
}


def _calc_percentiles(
    candidates: list[dict],
    factors: list[str],
) -> list[dict]:
    """팩터별 순위 백분위를 계산하여 factors dict를 추가한다."""
    total = len(candidates)
    if total == 0:
        return []

    # 팩터별 순위 계산
    factor_percentiles: dict[int, dict[str, float]] = {
        i: {} for i in range(total)
    }

    for factor in factors:
        reverse = factor in REVERSE_FACTORS
        values = [c[factor] for c in candidates]

        # 정렬: 일반 팩터는 오름차순(낮은 값이 낮은 순위), 역순위 팩터는 내림차순(높은 값이 낮은 순위)
        sorted_vals = sorted(enumerate(values), key=lambda x: x[1], reverse=reverse)

        # 동률 처리: 같은 값이면 같은 순위
        rank_map: dict[int, int] = {}
        current_rank = 0
        prev_val = None
        for pos, (idx, val) in enumerate(sorted_vals):
            if val != prev_val:
                current_rank = pos + 1
                prev_val = val
            rank_map[idx] = current_rank

        for idx in range(total):
            percentile = rank_map[idx] / total * 100
            factor_percentiles[idx][factor] = percentile

    # 결과에 factors dict 추가
    results = []
    for i, c in enumerate(candidates):
        result = dict(c)
        result["factors"] = factor_percentiles[i]
        results.append(result)

    return results


class FactorScorer:
    """팩터 기반 스코어링 엔진."""

    def __init__(
        self,
        factor_weights: dict[str, float] | None = None,
        pass_threshold: float = 80.0,
        factors: dict[str, list[str]] | None = None,
    ):
        self.factor_weights = factor_weights or dict(DEFAULT_WEIGHTS)
        self.pass_threshold = pass_threshold
        defaults = {"STOCK": STOCK_FACTORS, "ETF": ETF_FACTORS}
        factor_config = factors or defaults
        self._stock_factors = factor_config["STOCK"]
        self._etf_factors = factor_config["ETF"]

    def score_candidates(self, candidates: list[dict]) -> list[dict]:
        """후보 종목 리스트를 받아 팩터별 순위 백분위 계산 후 가중 합산 스코어를 추가한다."""
        if not candidates:
            return []

        # 주식/ETF 분리
        stocks = [c for c in candidates if c.get("stock_type") != "ETF"]
        etfs = [c for c in candidates if c.get("stock_type") == "ETF"]

        scored: list[dict] = []

        if stocks:
            scored.extend(_calc_percentiles(stocks, self._stock_factors))
        if etfs:
            scored.extend(_calc_percentiles(etfs, self._etf_factors))

        # 가중 합산 score 계산
        for item in scored:
            score = 0.0
            for factor, percentile in item["factors"].items():
                weight = self.factor_weights.get(factor, 0.2)
                score += percentile * weight
            item["score"] = round(score, 4)

        # score 내림차순 정렬
        scored.sort(key=lambda x: x["score"], reverse=True)

        # rank 부여 (1부터)
        for i, item in enumerate(scored):
            item["rank"] = i + 1
            item["is_passed"] = item["score"] >= self.pass_threshold

        return scored
