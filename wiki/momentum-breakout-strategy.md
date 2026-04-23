# 모멘텀 돌파 전략

현재 유일한 매매 전략. `trading/strategies/momentum_breakout.py` 구현.

## 전략 개요

**3단계 진입 tier 기반 돌파 + 다팩터 신뢰도** 전략.

종목이 기준선을 돌파할 때 거래량/체결강도/호가를 종합하여 신뢰도를 산출, 임계값 이상이면 매수 신호를 생성한다. Phase 8 Sprint 2부터 진입 조건을 3단계 tier로 분기하여 상황별 리스크를 차등 관리한다.

## 핵심 로직

### 1. 3단계 진입 tier 결정

```python
def _resolve_tier(snapshot, gap_rate) -> (breakout_ref, breakout_tier):
    if gap_rate >= 0.03:
        return snapshot.open_price, "gap_open"   # 갭 상승 — 시가 돌파 기준
    if snapshot.current_price > snapshot.prev_high:
        return snapshot.prev_high, "prev_high"   # 전일 고가 돌파 기준
    return snapshot.prev_close, "prev_close"     # 전일 종가 돌파 기준
```

| tier | 조건 | 돌파 기준선 | 비고 |
|------|------|------------|------|
| `gap_open` | `gap_rate ≥ 3%` | 당일 시가 | 갭 상승 추종 |
| `prev_high` | 현재가 > 전일 고가 | 전일 고가 | 고점 갱신 돌파 |
| `prev_close` | 위 둘 다 아님 | 전일 종가 | 추격매수 리스크 큼 |

`breakout_tier`는 신호 `reason` dict에 기록되어 engine 하류(`PositionSizer`)에서 반 포지션 적용에 활용된다.

### 2. prev_close tier 시간 가드 (13:00 KST)

```python
PREV_CLOSE_TIER_BLOCK_TIME = time(13, 0)
```

오후 추격매수 리스크가 커 `prev_close` tier는 **13:00 이후 진입 불가**. 해당 경우 `RejectedSignal(stage="prev_close_time_guard")`를 반환하고, 13:00~14:00 창에 해당하면 Phase 8.5 가상 신호 기록(`record_virtual_signal`)을 수행해 후속 검증 데이터로 축적한다.

### 3. 거래량 조건 (시간가중 보정 + tier별 임계값)

```python
market_progress = calc_market_progress()  # 0.15 ~ 1.0
effective_progress = max(progress, MIN_MARKET_PROGRESS)
adjusted_ratio = volume / (prev_volume * effective_progress)
```

장 초반(09:00~09:30)은 거래량이 자연히 적으므로 `MIN_MARKET_PROGRESS=0.15`로 하한 보정한다.

**tier + 돌파 강도 연동 임계값**:

| 조건 | `volume_threshold` |
|------|-------------------|
| `prev_close` tier | 2.5 (고정) |
| `breakout_pct ≥ 5%` | 1.5 |
| `breakout_pct ≥ 3%` | 1.8 |
| 그 외 | 2.0 |

또한 절대 거래량 하한 `MIN_VOLUME_FLOOR = 0.5` (전일 거래량 × 0.5) 미달 시 제외.

### 4. 체결강도 / ATR 필터

```python
if snapshot.trade_strength < 100.0:   # 체결강도 최소 100
    reject("trade_strength")

if atr / current_price > 0.05:        # ATR 현재가 대비 5% 초과 제외
    reject("atr_filter")
```

ATR은 `calc_volatility_factor`로 계산 — [[screening-factors|변동성 팩터]] 기반.

### 5. 신뢰도 계산 (tier별 momentum 가중)

```python
if tier == "prev_close":
    momentum_score = min(breakout_pct / 7.0, 1.0) * 0.7   # 분모 ↑, 배율 ↓
elif tier == "gap_open":
    momentum_score = min(breakout_pct / 5.0, 1.0) * 0.85  # 갭 tier 약간 감쇠
else:  # prev_high
    momentum_score = min(breakout_pct / 5.0, 1.0)

confidence = momentum_score * 0.3
           + volume_score * 0.3
           + strength_score * 0.2
           + orderbook_score * 0.2

if tier == "prev_close":
    confidence = min(confidence, 0.75)   # prev_close 상한
```

`MIN_CONFIDENCE = 0.6` 이상이어야 신호 생성.

## 신호 반환 타입

- 성공: `TradeSignalData` — engine으로 전달되어 주문 제출.
- 실패: `RejectedSignal(stage, detail)` — 차단 사유가 구조화되어 로그/텔레그램 알림에 활용됨. (None 반환 안 함)

## 주요 상수

```python
# 시장 시간 (KST)
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(15, 30)
MARKET_MINUTES = 390

# 시간가중/거래량
MIN_MARKET_PROGRESS = 0.15
MIN_VOLUME_FLOOR = 0.5

# 필터
ATR_FILTER_PCT = 0.05
MIN_CONFIDENCE = 0.6

# Phase 8 Sprint 2: prev_close tier 파라미터
PREV_CLOSE_TIER_BLOCK_TIME = time(13, 0)
PREV_CLOSE_VOLUME_THRESHOLD = 2.5
PREV_CLOSE_MOMENTUM_DIVISOR = 7.0
PREV_CLOSE_MOMENTUM_MULTIPLIER = 0.7
PREV_CLOSE_CONFIDENCE_CAP = 0.75

# gap_open tier
GAP_OPEN_MOMENTUM_MULTIPLIER = 0.85
```

## tier별 사이징 연동

[[position-sizing]]에서 `prev_close` tier는 `size_ratio=0.5` 반 포지션을 적용 — engine이 `signal.reason["breakout_tier"]`로 분기한다.

## 전략 등록

[[signal-generation|SignalGenerator]]에 전략 주입:
```python
strategy = MomentumBreakoutStrategy(redis_client=..., session_factory=...)
generator = SignalGenerator(session_factory, redis, strategy)
```

## 향후 전략 확장

`Strategy` 추상 클래스를 구현하면 새 전략 추가 가능:
- Phase 9 Sprint 0: 5분봉 가속도 기반 모멘텀 전략
- Phase 9 Sprint 2: VWAP 기반 전략
- Phase 10.1: 당일 고가 갱신 기반 4단계 tier 확장
