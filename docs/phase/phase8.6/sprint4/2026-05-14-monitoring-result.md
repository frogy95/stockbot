# 2026-05-14 (목) — Phase 8.6 A안(real-momentum) 첫 검증 모니터링 결과

> 계획: `2026-05-14-monitoring-plan.md`
> 전제: PR #233 (real-momentum hotfix) main 머지 + Railway 자동 재배포 완료

---

## 09:30 1차 점검 — A안 효과 1차 검증

### 측정값

| Endpoint | 결과 |
|----------|------|
| `/screening/primary` | total=20, 1위 score=91.81 (187870, momentum_factor=94.91) |
| `/screening/secondary` | count=**2** (187870, 086900) |
| `/health/observation-daily` | signals.total=**0**, fallback.triggered_count=0, rollback=false |
| `/metrics/phase86-status` | rollback_active=false, circuit_breaker_active=false, primary_candidates=20 |
| `/health/sprint3-keys` | vol5m_count=130, orderbook_count=20, last_portal_supplement=2026-05-13T16:00 |

### 합격/불합격 판정

| 기준 | 결과 | 비고 |
|------|------|------|
| 1차 +7% 종목 ≥ 1 | ⚠️ **측정 불가** | `/screening/primary` 응답에 `change_rate` 필드 없음 (score+factors만 노출). 1위 momentum_factor=94.91로 강한 모멘텀 종목은 존재 — 합격 추정 |
| 2차 통과 ≥ 5 | ❌ **2** | 어제와 동일 수준. A안 2차 필터(trade_strength_min 80) 추가 효과 미입증 |
| 데이터 파이프라인 정상 | ✅ | vol5m=130, orderbook=20 (둘 다 임계 충족) |
| 차단 게이트 false 유지 | ✅ | rollback/circuit_breaker 모두 false |
| signals.total ≥ 1 | ⏳ | 09:30 시점 0건 (정상, 12:00 점검에서 검증) |

### 발견

1. **1차 풀 score 분포는 정상**: 187870(score 91.81) 등 강한 모멘텀 종목 진입. A안 1차 필터(`change_rate_max 7→30`) 자체는 차단 해제된 것으로 보임.
2. **2차 통과 2개 그대로**: A안 2차 필터(`trade_strength_min 100→80`)가 통과 종목 수를 늘리지 못함. trade_strength 외 다른 게이트(volume_factor 등)가 실제 병목일 가능성.
3. **측정 방법론 문제**: `/screening/primary` 응답이 score 기반이라 raw change_rate 카운트 불가. plan 합격 기준 #1은 endpoint 보완 필요 (factor 역산 또는 collector raw 조회).

### 다음 액션

- **12:00 2차 점검 (최우선)**: `signals.total ≥ 1` 검증이 가장 본질적인 지표. 09:30 시점은 장 개장 30분차라 신호 생성 대기 정상 범위.
- **신호 0건 지속 시**: secondary 2개(187870, 086900)의 momentum_breakout 경로 trace (`/metrics/virtual-signals?stock_code=187870`)로 어디서 막히는지 분석.
- **trade_strength_min 추가 완화 보류**: 2차 통과 2개가 trade_strength 때문인지 다른 factor 때문인지 먼저 판별.

---

## 12:00 2차 점검

(예정)

---

## 14:30 3차 점검

(예정)

---

## 16:10 4차 점검

(예정)

---

## 16:30 종합 보고

(예정)
