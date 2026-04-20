# Phase 7.2 퀀트 전문가 검토 — 박퀀트

> 검토일: 2026-04-17
> 검토 대상: 매매 전략 진입 조건 개선 아키텍처 초안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| OHLC 파싱 수정 (Sprint 1) | ✅ 통과 — 데이터 품질 결함, 전략 이전에 수정 |
| 다층 confidence 프레임워크 | ✅ 통과 — 기존 가중 평균 구조 자연 확장 |
| 돌파 강도(breakout_pct) 재설계 | ⚠️ 주의 — 기준점 변경 시 breakout_pct 분모도 변경 |
| 절대 기준 기반 스코어링 혼합 | ⚠️ 주의 — Phase 7.0 미해결 #10과 연관, 범위 외 유지 |

## 2. 항목별 검증 결과

### 데이터 품질 관점
- **모든 전략 판단의 전제는 정확한 데이터**. OHLC 미파싱은 전략 설계 이전의 인프라 결함.
- open_price가 prev_close로 폴백되면 gap_rate가 항상 0 → 갭 상승 종목을 식별 불가. 이는 전략의 가장 중요한 시장 상태 분류(갭 vs 비갭)를 무력화.

### confidence 프레임워크 확장 설계

현재 confidence 구조:
```
confidence = momentum_score * 0.3 + volume_score * 0.3 + strength_score * 0.2 + orderbook_score * 0.2
```

다층 진입 시 momentum_score 계산 변경 제안:
```
# 기준점에 따른 momentum_score 스케일링
if breakout_ref == prev_high:
    momentum_score = min(breakout_pct / 5.0, 1.0)  # 기존과 동일
elif breakout_ref == prev_close:
    momentum_score = min(breakout_pct / 7.0, 1.0) * 0.7  # 스케일 완화 + 상한 70%
elif breakout_ref == open_price (갭 분기):
    momentum_score = min(breakout_pct / 5.0, 1.0) * 0.85  # 갭 지지 확인이므로 중간
```

- **핵심 원칙**: 기준점이 낮을수록 momentum_score 상한을 낮춰서 confidence에 자연스러운 계층 구조 형성
- prev_high 돌파 → confidence 최대 1.0 (기존 그대로)
- prev_close 돌파 → confidence 최대 약 0.81 (momentum 기여 최대 0.7 * 0.3 = 0.21)
- 이 설계로 "보수적 진입 = 낮은 confidence = 작은 포지션" 자동 연계

### breakout_pct 재설계 주의사항
- 현재 `breakout_pct = (current_price - breakout_ref) / breakout_ref * 100`
- 기준점이 prev_close로 변경되면 breakout_pct가 커지면서 volume_threshold가 1.5로 떨어짐 (5%+ 돌파 시)
- **해결**: breakout_pct 계산은 항상 prev_high 대비로 고정하거나, 기준점별 별도 임계값 테이블 사용

### 과적합 경고
- 진입 조건 파라미터를 늘리면 과적합 위험 증가. 현재 시스템에 백테스트가 없으므로:
  1. 파라미터는 최소한으로 유지 (기준점 2단계 + 시간대 구분 정도)
  2. 최소 20거래일 Paper 관찰 후 파라미터 미세조정
  3. "단순한 전략이 살아남는다" 원칙 준수

## 3. 파라미터 조정 권고

| 항목 | 원래값 | 권고값 | 근거 |
|------|--------|--------|------|
| prev_close 돌파 momentum_score 상한 | 1.0 | 0.7 | 낮은 기준점 = 낮은 모멘텀 신뢰도 |
| prev_close 돌파 momentum_score 분모 | 5.0 | 7.0 | 더 큰 돌파폭 요구로 과민 반응 방지 |
| 갭 돌파 momentum_score 상한 | 1.0 | 0.85 | 갭 지지 확인이므로 prev_close보다 높게 |
| volume_threshold 기준 | breakout_pct 기반 단일 | 기준점별 별도 테이블 | 기준점 변경에 따른 breakout_pct 왜곡 방지 |
| confidence 최소 임계값 | 0.6 | 0.6 유지 | 기존 안전장치 유지, momentum 상한 조정으로 충분 |

## 4. 리스크 및 대안

- **과적합 리스크**: 백테스트 없이 파라미터 추가 → 시장 국면 변화 시 무력화
  - 대응: 파라미터 최소화 + 20거래일 관찰 기간 확보
- **지표 상관 리스크**: breakout_pct가 volume_threshold에 영향 → 기준점 변경 시 간접 효과 발생
  - 대응: prev_close 돌파 시 volume_threshold 별도 고정값 사용 (breakout_pct 연동 해제)
- **Phase 7.0 미해결 #10**: 2차 스크리닝 N=1 상대 백분위 문제는 신호 증가 시 자연 완화 가능. 하지만 근본 해결은 별도 Phase 유지.
