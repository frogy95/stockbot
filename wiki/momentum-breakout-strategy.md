# 모멘텀 돌파 전략

현재 유일한 매매 전략. `trading/strategies/momentum_breakout.py` 구현.

## 전략 개요

**병렬 OR 다중 진입 경로 + 다팩터 신뢰도** 전략. Phase 8 Sprint 2부터 3단계 진입 tier로 분기, Phase 8.6 Sprint 2(2026-04-29)부터 직렬 AND → 병렬 OR로 구조 재설계되었다.

상세: [[tier-architecture]] 참조.

## 핵심 로직

### 1. tier 평가 (병렬 OR)

`PARALLEL_OR_TIER_ENABLED=true` (기본) 시 3개 tier가 독립 sub-게이트로 동시 평가된다.

```python
async def generate_signal(snapshot):
    if settings.TEMP_TIME_GUARD_SPRINT2 and (now < 09:10 or now >= 14:30):
        return reject(reason="temp_time_guard")

    if settings.PARALLEL_OR_TIER_ENABLED:
        results = [
            ("gap_open",   await self._evaluate_gap_open(snapshot, ctx)),
            ("prev_high",  await self._evaluate_prev_high(snapshot, ctx)),
            ("prev_close", await self._evaluate_prev_close(snapshot, ctx)),
        ]
        matched = [name for name, (passed, _) in results if passed]
        if not matched:
            return reject(...)
        confidence = mean([detail["confidence"] for _, (passed, detail) in results if passed])
        return signal(matched_tiers=matched, confidence=confidence, ...)
    else:
        # Sprint 1 직렬 동작 (Kill-switch 시 복원)
```

### 2. tier별 sub-게이트

| tier | sub-게이트 | 비고 |
|------|-----------|------|
| `gap_open` | `gap_rate ≥ 3%` AND ATR ∈ `[0.025, ATR_CEIL_HARD=0.08]` AND `current_price > open_price` | 매물 흡수 컷 (시초가 ≥ 현재가 시 거름). ATR HARD 절대 한계 — 우회 X |
| `prev_high` | `current_price > prev_high × 1.001` AND ATR ∈ `[ATR_FLOOR, ATR_CEIL_DYNAMIC]` | 동적 상한 적용 |
| `prev_close` | 13:00 시간가드 AND `current_price > prev_close × 1.001` AND **5분봉 거래량 컨펌** | 양봉 2연속 OR `vol_5m ≥ 직전 4봉 평균 × 2` |

`signals.matched_tiers` JSON 컬럼에 통과 tier list가 영속화된다.

### 3. ATR 동적 캘리브레이션

기존 `ATR_FILTER_PCT=0.05` 정적 상한 → KOSPI200 분위수 기반 동적 상한 + 하한 (Phase 8.6 Sprint 2).

```python
# _resolve_atr_ceil(snapshot, tier, redis_client, is_fallback)
ATR_FLOOR        = 0.025                        # 모든 tier 공통 (gap_open 포함)
ATR_CEIL_HARD    = 0.08                         # 절대 한계 (gap_open도 적용)
ATR_CEIL_FALLBACK = 0.05                        # 폴백 종목 고정 (동적 미적용)
ATR_CEIL_DYNAMIC = min(0.08, P80 × ATR_CEIL_MULT=1.2)  # Redis: metrics:atr:ceil:{date}
```

08:35 캘리브레이션 잡이 매일 Redis에 동적 상한을 저장 (TTL 3거래일). SMA/EWMA 옵션 + IQR ×1.5 트리밍 + 폴백 3단(직전일 캐시 → HARD 정적 → 안전모드). 상세: [[tier-architecture#atr-동적-캘리브레이션]].

### 4. prev_close tier 거래량 컨펌

13:00 이전이라도 prev_close tier는 5분봉 거래량 컨펌을 추가로 통과해야 한다.

```python
# 양봉 2연속 OR vol_5m ≥ mean(vol_5m, last 4) × 2
volume_confirmed = (consecutive_bullish_5m >= 2) or (vol_5m_ratio >= 2.0)
```

5분봉 데이터 부재 시 fail-safe(거름).

13:00 이후는 `RejectedSignal(stage="prev_close_time_guard")`로 차단되며, 13:00~14:00 창은 가상 신호(`record_virtual_signal`)로 후속 검증 데이터 축적.

### 5. 거래량 조건 (시간가중 + tier별 임계 + 시간대 슬라이딩)

```python
market_progress = calc_market_progress()
effective_progress = max(progress, MIN_MARKET_PROGRESS=0.15)
adjusted_ratio = volume / (prev_volume * effective_progress)
```

**tier + 돌파 강도 연동 임계값**:

| 조건 | `volume_threshold` |
|------|-------------------|
| `prev_close` tier | 2.5 (고정) |
| `breakout_pct ≥ 5%` | 1.5 |
| `breakout_pct ≥ 3%` | 1.8 |
| 그 외 | 2.0 |

**`min_volume_floor` 시간대 슬라이딩** (Phase 8.6 Sprint 1 — 분기 D 풀 협소 대응):

| 시간대 | floor |
|-------|-------|
| 09:00 ~ 11:00 | **0.3** |
| 그 외 | 0.5 (strong=False) / 0.4 (strong=True) / 0.6 (전일 거래량 부진) |

HARD floor 0.3 강제 적용 직전에 슬라이딩이 적용된다.

### 6. 체결강도 / 신뢰도

```python
if snapshot.trade_strength < 100.0:
    reject("trade_strength")

# tier별 momentum 가중
if tier == "prev_close":
    momentum_score = min(breakout_pct / 7.0, 1.0) * 0.7
elif tier == "gap_open":
    momentum_score = min(breakout_pct / 5.0, 1.0) * 0.85
else:
    momentum_score = min(breakout_pct / 5.0, 1.0)

confidence = momentum_score * 0.3 + volume_score * 0.3 + strength_score * 0.2 + orderbook_score * 0.2

if tier == "prev_close":
    confidence = min(confidence, 0.75)
```

병렬 OR 통과 시 통과 tier들의 confidence **평균**을 신호의 최종 confidence로 사용. `MIN_CONFIDENCE = 0.6` 이상이어야 신호 생성.

## 신호 반환 타입

- 성공: `TradeSignalData` (matched_tiers 포함) — engine으로 전달되어 주문 제출.
- 실패: `RejectedSignal(stage, detail)` — 차단 사유가 구조화되어 로그/텔레그램 알림에 활용. (None 반환 안 함)

## 안전모드

ATR 캘리브레이션 폴백 3단 도달 시 `safe_mode:active` Redis 키가 설정되며, engine은 신호 발행을 `SAFE_MODE_TIMEOUT_MIN=120`분간 중단한다. [[tier-architecture#폴백-3단]] 참조.

## 주요 상수 / env

```python
# 시장 시간 (KST)
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(15, 30)

# 시간가중 / 거래량
MIN_MARKET_PROGRESS = 0.15
MIN_VOLUME_FLOOR_HARD = 0.3

# 신뢰도
MIN_CONFIDENCE = 0.6

# Phase 8 Sprint 2 — prev_close tier
PREV_CLOSE_TIER_BLOCK_TIME = time(13, 0)
PREV_CLOSE_VOLUME_THRESHOLD = 2.5
PREV_CLOSE_CONFIDENCE_CAP = 0.75

# gap_open tier
GAP_OPEN_MOMENTUM_MULTIPLIER = 0.85
```

**Phase 8.6 Sprint 2 신규 env (총 10종, Railway 수동 설정)**:

| env | 기본값 | 용도 |
|-----|--------|------|
| `PARALLEL_OR_TIER_ENABLED` | `true` | 병렬 OR 활성화 (Kill-switch) |
| `ATR_CALIBRATION_ENABLED` | `true` | 08:35 캘리브레이션 잡 활성화 |
| `ATR_CALIBRATION_METHOD` | `sma` | `sma` 또는 `ewma`(λ=0.94) |
| `ATR_FLOOR` | `0.025` | ATR 하한 (모든 tier 공통) |
| `ATR_CEIL_HARD` | `0.08` | ATR 상한 절대 한계 |
| `ATR_CEIL_FALLBACK` | `0.05` | 폴백 종목 ATR 상한 (고정) |
| `ATR_CEIL_MULT` | `1.2` | 동적 상한 곱계수 (P80 × mult) |
| `ATR_CALIBRATION_WINDOW_DAYS` | `20` | KOSPI200 ATR 평균 윈도우 |
| `TEMP_TIME_GUARD_SPRINT2` | `true` | 09:00~09:10 / 14:30+ 임시 차단 (Sprint 3 본 가드 도입 시 제거) |
| `SAFE_MODE_TIMEOUT_MIN` | `120` | 폴백 3단 안전모드 신호 중단 시간 (분) |

**Phase 8.6 Sprint 1 신규 env**:

| env | 기본값 | 용도 |
|-----|--------|------|
| `SECONDARY_POOL_FALLBACK_THRESHOLD` | `5` | 풀 하한 폴백 발동 종목 수 (v2.6.1 3 → 5) |
| `SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP` | `5` | 폴백 보강 종목 수 상한 |
| `AUTO_ROLLBACK_R{1..4}_ENABLED` | `true` | 자동 롤백 트리거 4종 OR — [[risk-management]] |
| `CIRCUIT_BREAKER_*` | — | 1차→2차 통과율 회로차단기 — [[risk-management]] |

## tier별 사이징 연동

[[position-sizing]]에서 `prev_close` tier는 `size_ratio=0.5` 반 포지션을 적용 — engine이 `signal.reason["breakout_tier"]`(병렬 OR 시 첫 번째 matched tier) 또는 `matched_tiers`로 분기한다.

## 전략 등록

[[signal-generation|SignalGenerator]]에 전략 주입:
```python
strategy = MomentumBreakoutStrategy(redis_client=..., session_factory=...)
generator = SignalGenerator(session_factory, redis, strategy)
```

## 향후 전략 확장

- Phase 8.6 Sprint 3: `volume_surge` tier (5분봉 거래량 ×5 + 호가창 매수/매도 ≥ 2배 + dry_run 우선)
- Phase 8.6 Sprint 4: 60일 Walk-forward 백테스트 + 시뮬↔실측 KS 검정
- Phase 9 Sprint 0: 5분봉 가속도 기반 모멘텀 전략
- Phase 10.1: 피라미딩(당일 고가 갱신), 2차 점수 하이브리드, VI 재개 tier
