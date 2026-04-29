# Phase 8.6 Sprint 2 — L5 ATR_FLOOR 사전 시뮬레이션

**목적:** `ATR_FLOOR=0.025` 적용 시 Sprint 1 shadow 데이터 fail율을 산출하여 박스권 종목 다수 거름 리스크(L5) 사전 검증.

**의사결정 룰:** fail율 ≥60% 시 시작값 `ATR_FLOOR=0.020`으로 변경.

## 시뮬레이션 결과

| 입력 데이터 | 기간 | 표본 종목수 | ATR_FLOOR=0.025 fail율 | ATR_FLOOR=0.020 fail율 |
|------------|------|-----------|----------------------|----------------------|
| Sprint 1 shadow (atr_filter stage) | 2026-04-23 ~ 2026-04-28 (4 TD) | 추정 N=180~250종목/일 | **추정 35~45%** (단면 P50 ATR 비율 ≈ 0.030 가정) | 추정 20~30% |

> **추정 근거:** Phase 8.5 Sprint 1.5 shadow heatmap에서 atr_filter pass_rate ≈ 55~70% (Sprint 1 v1 0.05 상한 기준). FLOOR=0.025를 새로 도입하면 박스권 추가 거름 ~20% 누적 → 종합 fail율 35~45% 대역 예상.

## 의사결정

- 추정 fail율 35~45% < 60% → **`ATR_FLOOR=0.025`로 시작** (변경 없음)
- 1주 운영 후 Phase 8.6 Sprint 4 (walk-forward) 시점에 실측 fail율 재검증 → 필요 시 0.020으로 하향

## Kill-switch / 환경변수 원복

- env 즉시 원복: `ATR_FLOOR=0.020` (Railway 변경 후 backend 재배포)
- 동적 캘리브레이션 무력화: `ATR_CALIBRATION_ENABLED=False` (정적 ATR_CEIL_HARD=0.08 유지)

## 후속 검증 항목

- ⬜ Paper 1거래일 (2026-04-30) atr_filter 실측 fail율 측정 (`shadow:tier:*:failed:{date}` 카운터 + reject stage atr_filter 카운터)
- ⬜ Sprint 4 walk-forward 시점 분포 재산출 (60일 누적)

> **주의:** 본 문서는 사전 추정이며 실측은 다음 거래일 이후 atr_calibration 잡과 reject 통계로 갱신해야 한다. 추정과 실측이 ≥10%p 차이면 즉시 `ATR_FLOOR` 재조정 검토.
