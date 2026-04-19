# 종목 스코어링

[[screening-factors|5팩터]]에 가중치를 적용하여 종목 순위를 결정. `screening/scorer.py` 구현.

## 스코어링 목적

- 1차 스크리닝 통과 종목 중 매매 우선순위 결정
- 수십 개 후보 → 소수 핵심 종목으로 압축
- [[signal-generation|신호 생성]] 대상 종목 결정

## 스코어 계산

```python
score = (
    w1 * volume_factor +
    w2 * volatility_factor +
    w3 * momentum_factor +
    w4 * trade_strength_factor +
    w5 * orderbook_ratio_factor
)
```

각 팩터 정의: [[screening-factors]] 참조.

**가중치 (w1~w5)**: settings 테이블에서 로드 (운영 중 조정 가능).

## 스코어 활용

- 스코어 기준 내림차순 정렬
- 상위 N개 종목만 2차 스크리닝 대상
- N은 [[risk-management|최대 포지션 수]] 및 API Rate Limit 고려

## 스코어 vs 신뢰도

- **스코어**: 스크리닝 단계 — 종목 선별에 사용
- **신뢰도 (confidence)**: 신호 생성 단계 — [[signal-generation]]에서 전략 적용 후 계산

둘은 다른 개념. 스코어가 높아도 전략 조건을 만족 못하면 신뢰도 0 (신호 없음).

## 파라미터 조정

- 가중치는 DB settings 테이블에 저장
- 장중 변경 가능 (실시간 적용)
- Phase 7.0: 전략 파라미터 최적화 작업 중
