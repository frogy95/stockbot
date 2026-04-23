# 포지션 사이징

건당 투자금과 주문 수량을 결정. `trading/position_sizer.py` 구현.

## 투자금 결정 방식

**비율 기반 투자**: 총 투자 가능 금액 대비 비율로 건당 투자금 결정.

```python
건당_투자금 = 총_투자_가능금액 × 건당_비율
주문_수량 = floor(건당_투자금 / 현재가)
```

기본 건당 비율: 10% (전문가 확정 후 조정).

## 파라미터

DB `settings` 테이블에서 로드:

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `position_size_pct` | 10% | 건당 투자 비율 |
| `max_position_count` | 5 | 최대 동시 포지션 수 |

동시에 5개 포지션 보유 시: 최대 50% 투입 (10% × 5).

## 투자 가능 금액 산출

```python
총_투자_가능금액 = 계좌_현금 + 실현_가능_주식_평가액
# 단, 이미 오픈된 포지션 투입금은 제외
```

실제 잔고는 KIS API로 조회 — [[kis-api]].

## 수량 결정

```python
quantity = floor(position_amount / current_price)
if quantity == 0:
    return None  # 투자금 부족
```

최소 1주 미만이면 신호 포기.

## tier별 사이징 (Phase 8 Sprint 2)

`PositionSizer.calculate()`는 `size_ratio` 파라미터를 받아 수량/투자금을 비례 축소한다.

engine이 신호 `reason.breakout_tier`로 분기:

```python
breakout_tier = signal.reason.get("breakout_tier", "prev_high")
tier_ratio = 0.5 if breakout_tier == "prev_close" else 1.0
size_ratio = min(candidate_ratio, tier_ratio)  # 후보 플래그와 tier 중 작은 값
```

- `prev_close` tier: **반 포지션** (추격매수 리스크 억제)
- `gap_open` / `prev_high` tier: 전체 포지션
- 후보 자체 `position_size_ratio`가 지정된 경우 더 작은 값을 최종 적용

[[momentum-breakout-strategy|tier 결정 로직]] 참조.

## 레버리지/인버스 ETF 별도 관리

[[risk-management]]의 `max_leverage_position_count`로 별도 한도 관리.
동일한 비율을 적용하되 포지션 수 카운팅을 분리.

## 향후 개선 (Phase 7.0~)

전략별 파라미터 최적화 시 포지션 사이징도 함께 조정:
- 신뢰도에 따른 가변 비율
- ATR 기반 변동성 조정 사이징
- 켈리 공식 적용 검토
