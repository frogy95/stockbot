# 모멘텀 돌파 전략

현재 유일한 매매 전략. `trading/strategies/momentum_breakout.py` 구현.

## 전략 개요

**전일 고가 돌파 + 다팩터 신뢰도** 전략.

종목이 전일(또는 당일) 고가를 돌파할 때 거래량/체결강도/호가를 종합하여 신뢰도를 산출, 임계값 이상이면 매수 신호를 생성한다.

## 핵심 로직

### 1. 갭 판별

```python
gap_rate = (open_price - prev_close) / prev_close

if gap_rate >= 0.03:  # 갭 3% 이상
    breakout_ref = high     # 당일 고가 기준
else:
    breakout_ref = prev_high  # 전일 고가 기준
```

갭 상승 시 전일 고가는 이미 돌파했으므로 당일 고가 기준으로 전환.

**Phase 7.2 버그**: 갭 분기 조건 내 OHLC 파싱 오류 수정 예정.

### 2. 돌파 조건

```python
if current_price <= breakout_ref:
    return None  # 돌파 미달 — 신호 없음
```

### 3. 거래량 조건 (시간가중 보정)

```python
market_progress = calc_market_progress()  # 0.15 ~ 1.0
volume_threshold = prev_volume * market_progress
```

장 초반(09:00~09:30)은 거래량이 자연히 적으므로 `MIN_MARKET_PROGRESS=0.15`로 하한 보정.

```python
MIN_VOLUME_FLOOR = 0.5  # 전일 대비 절대 거래량 하한
```

### 4. ATR 필터

```python
ATR_FILTER_PCT = 0.05  # 현재가 대비 ATR 5% 초과 시 제외
```

과도한 변동성 종목 제외 ([[screening-factors|변동성 팩터]] 기반).

### 5. 신뢰도 계산

다팩터 가중합:
```
confidence = w_volume * volume_score
           + w_trade_strength * strength_score
           + w_orderbook * orderbook_score
           + w_breakout * breakout_strength_score
```

`MIN_CONFIDENCE=0.6` 이상이어야 신호 생성.

## 시장 시간 상수

```python
MARKET_OPEN = time(9, 0)    # KST
MARKET_CLOSE = time(15, 30) # KST
MARKET_MINUTES = 390         # 6h30m
MIN_MARKET_PROGRESS = 0.15   # 장 초반 하한 보정
MIN_VOLUME_FLOOR = 0.5       # 전일 대비 거래량 하한
ATR_FILTER_PCT = 0.05        # ATR 필터 임계값
```

## 전략 등록

[[signal-generation|SignalGenerator]]에 전략 주입:
```python
strategy = MomentumBreakoutStrategy()
generator = SignalGenerator(session_factory, redis, strategy)
```

## 향후 전략 확장

`Strategy` 추상 클래스를 구현하면 새 전략 추가 가능:
- Phase 7.1: 5분봉 가속도 기반 모멘텀 전략
- Phase 8: VWAP 기반 전략
