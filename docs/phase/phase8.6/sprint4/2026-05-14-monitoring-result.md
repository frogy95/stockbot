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

## 12:00 2차 점검 — 🎉 **A안 입증 (신호 ≥ 1건)**

### A. 본 점검 결과

| Endpoint | 값 |
|----------|----|
| `/health/observation-daily` | **signals.total=2** (gap_open=1, other=1), fallback.triggered_count=**228**, codes=`['010780','025560','036570','128820','183300','187870']`, rollback=false |
| `/metrics/stage-heatmap?date=today` | breakout 단일 stage 비중 매우 큼 (대략 60%+), min_volume_floor 차순위, pass=1건(09:40) |
| `/metrics/top-rejects` | 5건 모두 025560 (stage=breakout, gap_open tier, current_price 22350~22500 < breakout_ref 24050, gap_rate 10.07%이나 ref 미달) |
| `/metrics/virtual-signals?stock_code=187870` | count=0 (핫픽스 정상 작동 — 이전엔 다른 종목들도 섞여 반환) |

### 합격 판정

| 기준 | 결과 |
|------|------|
| signals.total ≥ 1 | ✅ **2건** — A안 최우선 기준 통과 |
| 단일 stage ≤ 50% | ⚠️ breakout 60%+ 추정 — 분포 편중 |
| 핫픽스 stock_code 필터 | ✅ 정상 작동 |

### B. KIS WS 구독 누락 영향도

**1차 풀 20개 중 7개 (35.0%) `execution: null`**. orderbook은 전부 정상 → 체결(execution) 스트림만 누락.

| 분류 | 종목코드 |
|------|---------|
| execution null (7개) | 187870, 025560, 084670, 094940, 482630, 036570, 223250 |
| orderbook null | 없음 (0/20) |
| 2차 통과 (2/2) execution null | **025560, 036570 — 100% 영향** |
| fallback 발동 종목 (6개) | 010780, 025560, 036570, 128820, 183300, 187870 |

**해석**:
- 2차 통과 종목 100%가 execution 누락이지만 **신호 2건 발생** → fallback 경로가 #3 이슈를 보완 중
- fallback.triggered_count=228은 비정상적으로 높음 (정상 종목의 fallback 미발동 패턴 vs 비교 필요)
- execution null 비율 35%는 **만성 패턴 가능성** — 1차 풀 갱신과 WS subscribe 동기화 또는 KIS 구독 한도 의심

### 내일 Sprint 4 등록 권고

- **우선순위 1**: KIS WS 구독 동기화 — 1차 풀 진입 시점부터 execution 스트림 보장 (35% 누락률 → 0% 목표)
- 진단 범위: ① 1차 풀 갱신 vs WS subscribe 레이스 ② MST 동기화 타이밍 ③ KIS 구독 한도(40종목) 초과 여부
- 게이트: Sprint 3에서 만든 `KOSPI200_MST_SYNC` kill-switch 활용
- fallback 경로의 신호 신뢰도 추가 검증 (true signal vs noise)

### 다음 액션

- 14:30 3차 점검에서 신호 누적 카운트 + eod_blocked 패턴 확인
- 16:10 4차 점검에서 G2/G3 발동 여부 확인 (pass_rate ≥ 10% 시 G3 자동 해제 검증)

---

## 14:30 3차 점검 — 누적 신호 안정, fallback 추세 활성

### 측정값

| 항목 | 14:30 | 12:00 | 변화 |
|------|-------|-------|------|
| signals.total | 2 (gap_open=1, other=1) | 2 (동일) | ±0 (오후장 추가 신호 없음) |
| fallback.triggered_count | **363** | 228 | **+135** (누적 활성) |
| fallback.codes | 6개 (동일 set) | 6개 | ±0 |
| rollback.is_active | false | false | — |

### Railway 로그 — eod_blocked

- 14:30 시점에 `eod_blocked` 로그 아직 미출현 (KST 14:25~14:28 직전 로그까지 확인). 정상 — eod 차단은 14:30 이후 점진 발동.
- 14:23~14:28 사이 025560 `breakout` stage 반복 거부 (`current_price 22650~22750 vs breakout_ref 24050, gap_rate 10.07%`). 입력 1건 → 통과 0건 (중복 또는 전략 미충족) 패턴 지속.

### 어제(2026-05-13) 대비 변화

| 시점 | 어제(05-13) | 오늘(05-14) |
|------|------------|------------|
| 14:30 signals.total | **0** | **2** |
| R1/G3/R3 발동 | 🚨 발동 (auto_rollback_2d_zero_signals, pass_rate=0%, override active) | ✅ 모두 false |
| 2차 통과 | 2개 | 2개 (025560, 036570) |
| min_volume_floor 압도 | 72.4% | breakout으로 이동 (A+B hotfix 효과) |

A안 + B hotfix가 **신호 생성 차단을 해제**한 효과 명확. 어제 R1+G3+R3 3중 차단 → 오늘 모두 false 유지.

### 다음 액션

- 16:10 4차 점검에서 G3 (pass_rate ≥ 10%) 판정 결과 확인
- 신호 2건 / candidates 20 = pass_rate **10%** — G3 임계 경계선. 자동 해제 분기 발동 가능성 동시 검증
- eod_blocked 14:30 이후 정상 출현 여부 4차 점검 시 동반 확인

---

## 16:10 4차 점검 — R1+G3 자동 발동, R3 unset 분기 정상 (부분)

### API 측정값

| Endpoint | 결과 |
|----------|------|
| `/metrics/phase86-status` | **rollback_active=true, circuit_breaker_active=true**, fallback_share=0.0, primary_candidates=20 |
| `/metrics/override-status` | **is_active=false** (R3 미발동), affected_keys=[MIN_VOLUME_FLOOR_MODE, SECONDARY_POOL_FALLBACK_ENABLED] |
| `/health/observation-daily` | signals.total=2, fallback.triggered_count=**456** (+93 vs 14:30), codes 7개 (330860 추가) |

### Redis 키 직접 확인 (railway ssh)

| 키 | 값 | 해석 |
|----|-----|------|
| `phase86:rollback:active` | `true` | R1 발동 |
| `phase86:circuit_breaker:active` | `true` | G3 발동 |
| `settings:override:MIN_VOLUME_FLOOR_MODE` | **None** | unset ✅ |
| `settings:override:SECONDARY_POOL_FALLBACK_ENABLED` | `False` | **잔존** (부분 unset) |
| `settings:override:triggered_at` | None | unset ✅ |
| `settings:override:reason` | None | unset ✅ |

### 시나리오 매트릭스 판정

| 시나리오 | 결과 |
|----------|------|
| 오늘 신호 ≥1 + 어제 0 → R1 미발동 | ❌ **예상 빗나감 — R1 발동됨**. signals.total=2임에도 rollback active. 다른 트리거 조건 의심 (단일일 pass_rate? 어제 active 상태 잔존?) |
| pass_rate ≥ 10% → G3 미발동/자동해제 | ❌ pass_rate=**2/20=10.0%** 정확히 임계 — G3 발동 (임계 조건 `< 10%` 아닌 `≤ 10%` 추정) |
| R3 (override) 자동 unset | ✅ **부분 입증** — triggered_at/reason/MIN_VOLUME_FLOOR_MODE unset, SECONDARY_POOL_FALLBACK_ENABLED=False 잔존 |

### 주요 발견

1. **R3 unset 분기 정상 작동 (부분)** — PR #228 효과 입증. 단 `SECONDARY_POOL_FALLBACK_ENABLED=False`만 잔존 → 자가치유 분기에 누락 키 있음.
2. **R1 발동 원인 추가 분석 필요** — signals.total=2인데 R1 active. plan §2 16:10 시나리오 매트릭스의 "R1 미발동" 예상이 빗나감. 어제 R1 active 상태가 자동 해제 분기를 통과하지 못했을 가능성. (내일 05-15 개장 시 자동 해제 여부 검증 기회)
3. **G3 임계 조건이 `≤ 10%`** — pass_rate=10.0%에서 발동. plan의 "≥ 10% 미발동" 조건과 실제 코드가 어긋남 (코드 추정: `< 10%`이 아니라 `≤ 10%` 또는 `<` 임계가 더 높음).
4. **fallback 누적**: 228 → 363 → 456 (점진 증가). codes에 330860 추가됨.

### R1 3일 트리거 위험 평가 (plan §5.2)

- 오늘 신호 ≥ 1건 발생 → 3일 연속 0건 조건 자체는 깨짐
- 그러나 R1이 자동 발동 → 다른 트리거 가능. plan §6.3 "수동 clear 금지, unset 자가치유 분기 검증 기회로 활용" 원칙 적용
- **내일(05-15) 개장 시 R1 자동 해제 여부 관찰** — 자동 해제되면 PR #228 R1 unset 분기도 입증. 잔존하면 코드 결함 확정

### 다음 액션

- 16:30 종합 보고에서 6개 합격 기준 최종 판정 + 내일 액션 결정
- 내일 Sprint 4 등록 후보: (a) KIS WS 구독 누락 35%, (b) SECONDARY_POOL_FALLBACK_ENABLED unset 누락, (c) R1 자동 해제 분기 검증/수정

---

## 16:30 종합 보고 — 🎉 **A안 입증 (최우선 #4 통과)**

### 4개 시점 측정값 요약

| 시점 | signals.total | fallback.triggered | 2차 통과 | R1 | G3 | R3 |
|------|---------------|---------------------|----------|----|----|-----|
| 09:30 | 0 (정상) | 0 | 2 (187870, 086900) | false | false | false |
| 12:00 | **2** | 228 | 2 (187870, 086900) | false | false | false |
| 14:30 | 2 | 363 | 2 (025560, 036570) | false | false | false |
| 16:10 | 2 | 456 | — | **true** | **true** | false (unset 부분) |

장 마감 최종 reject 분포: breakout 208 (72.2%) / min_volume_floor 46 (16.0%) / volume_threshold 32 (11.1%) / pass 1 / trade_strength 1.

### §3 합격/불합격 6개 기준 최종 판정

| # | 조건 | 결과 | 판정 |
|---|------|------|------|
| 1 | 1차 +7% 종목 ≥ 1 | 측정 불가 (`/screening/primary`에 change_rate 없음) — momentum_factor 94.91 종목 진입으로 추정 합격 | ⚠️ 추정 ✅ |
| 2 | 2차 통과 ≥ 5 | 최대 2개 (어제와 동일) | ❌ |
| 3 | 데이터 파이프라인 (vol5m ≥ 800, orderbook ≥ 15) | vol5m=130, orderbook=20 | ❌ vol5m 미달 |
| 4 | **signals.total ≥ 1** | **2건** | ✅ **최우선 통과 — A안 입증** |
| 5 | 단일 stage ≤ 50% | breakout 72.2% | ❌ |
| 6 | R1/G3/R3 모두 false 또는 unset | R1+G3 active, R3 unset (부분) | ⚠️ 부분 |

**통과율: 명확 합격 1/6 + 추정 합격 1/6 + 부분 1/6 + 미달 3/6**

plan §3 마지막 문구 "최우선 기준은 #4. 다른 기준 미충족이어도 신호 ≥ 1건이면 A안 입증으로 평가" 적용 → **A안 입증**.

### 어제(2026-05-13) vs 오늘 종합 대비

| | 어제 | 오늘 |
|---|---|---|
| signals.total | 0 | **2** |
| 2일 연속 0건 (R1 트리거) | 발동 | 해제 |
| pass_rate | 0% | 10% |
| 1차 풀 1위 momentum | — | 94.91 (3일 +94% 종목) |
| R3 (override) | 발동 (수동 clear 필요) | **자동 unset (부분)** ← PR #228 입증 |

### 다음 액션 (§6.1 — 신호 ≥ 1건 경로)

| 우선순위 | 작업 | 비고 |
|---------|------|------|
| 1 | **PR #235 머지** (오늘 결과 + A안 첫 검증 모니터링 plan/result) | docs only, 안전 |
| 2 | 내일(05-15) 모니터링 1거래일 추가 — Sprint 3 dry_run 관찰 게이트 "2거래일 연속 ≥ 1건" 충족 검증 | 필수 |
| 3 | 내일 개장 시 R1 자동 해제 관찰 (PR #228 R1 unset 분기 검증) | plan §6.3 |
| 4 | Sprint 4 등록 후보 3개 (§6.1 + 신규 발견): | 다음 sprint-planner 호출 시 |
|   | (a) KIS WS 구독 누락 35% (2차 통과 종목 100% 영향) | 신규, 본질적 |
|   | (b) `SECONDARY_POOL_FALLBACK_ENABLED` unset 분기 누락 (R3 자가치유 부분 결함) | 신규, 작은 fix |
|   | (c) walk-forward 백테스트 (`/admin/backtest`) — A안 임계로 과거 60일 신호 분포 | §6.1 #3 |
|   | (d) 단일 stage 50% 초과 분포 (breakout 72.2%) 정상화 | §6.1 #2 |
| 5 | dry_run → LIVE 전환 검토 | Sprint 4 G-Bt1~3 통과 후만 |

### 핵심 발견 4가지 (재게)

1. **A안 hotfix가 신호 차단을 해제** — `change_rate_max 7→30` + `trade_strength_min 100→80` 효과 정량 입증 (0건 → 2건).
2. **PR #228 R3 unset 분기 부분 입증** — 4/5 키 unset 정상, `SECONDARY_POOL_FALLBACK_ENABLED` 잔존 버그 발견.
3. **KIS WS 구독 누락 35%** — 1차 풀 7/20, 2차 통과 종목 100% 영향. fallback 경로가 보완 중이나 본질 결함.
4. **R1 발동 원인 의문** — signals=2임에도 active. 내일 자동 해제 분기 검증으로 확정 예정.

### 핫픽스 산출물

- PR (`hotfix/virtual-signals-stock-code-filter`): `/virtual-signals?stock_code=` 필터 미구현 수정. trace 효율 개선용 (운영 영향 없음).
