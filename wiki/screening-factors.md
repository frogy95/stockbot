# 스크리닝 팩터

[[screening-pipeline|스크리닝]]에서 사용하는 5가지 정량 팩터. `screening/factors.py` 구현.

## 5팩터 정의

### 1. 거래량 팩터 (Volume Factor)

```python
volume_factor = volume / prev_volume
```

전일 대비 거래량 비율. 높을수록 시장의 관심도 증가.
- `prev_volume == 0` 시 0.0 반환

### 2. 변동성 팩터 (Volatility Factor)

ATR(Average True Range) 5일 계산:

```python
True Range = max(high-low, |high-prev_close|, |low-prev_close|)
ATR = mean(TR for last N days)
```

- 데이터 2일 미만 시 0.0 반환
- [[momentum-breakout-strategy]]에서 ATR 5% 초과 종목 제외 (과도한 변동성 필터)

### 3. 모멘텀 팩터 (Momentum Factor)

3일 단기 수익률(%):

```python
momentum = (close[-1] - close[-4]) / close[-4] * 100
```

- 최소 4개 종가 필요
- 단기 상승 추세 포착

### 4. 체결강도 팩터 (Trade Strength Factor)

```python
trade_strength_factor = trade_strength  # 0~100 범위 그대로
```

[[websocket-management|WebSocket]]에서 실시간 계산된 체결강도를 팩터로 직접 활용.
- 50 초과: 매수 우세
- 50 미만: 매도 우세

### 5. 호가잔량 팩터 (Orderbook Ratio Factor)

```python
orderbook_ratio = total_bid_volume / total_ask_volume
```

- 매수/매도 호가 불균형 측정
- `total_ask_volume == 0` 시 0.0 반환
- 1 초과: 매수 우세 (수요 > 공급)

## 팩터 활용

[[scoring-system]]에서 5팩터에 가중치를 적용하여 최종 스코어 산출.

각 팩터는 독립적으로 계산되며, 팩터 값 자체가 스크리닝 필터의 임계값 판단에도 사용:
- 1차 스크리닝: 거래량, 변동성, 모멘텀 팩터 중심
- 2차 스크리닝: 체결강도, 호가잔량 팩터 추가

## ETF 팩터

`etf_factors.py`에 ETF 전용 팩터 구현 예정 (현재 미완성).
- ETF는 개별 종목 팩터와 다른 특성 보정 필요
- NAV 괴리율, 레버리지 배율 고려
