# 2026-05-13 (수) — Phase 8.6 신호 발생 검증 모니터링 계획

> 작성: 2026-05-12 16:50 KST
> 배경: 2026-04-21~2026-05-12 한 달간 신호 4건만 발생 (사실상 0건). 2026-05-12 종합 진단 + 5건 hotfix + 다층 차단 해제 완료. 내일 첫 실측 검증.

---

## 1. 진행 요약 (2026-05-12 적용된 변경)

| # | 변경 | 적용 시각 | 상태 |
|---|------|----------|------|
| 1 | PR #223 dedup 6h 시간 윈도우 | 2026-05-11 13:35 KST | ✅ 배포 |
| 2 | R3 4개 override 키 manual DEL | 10:30 KST | ✅ 완료 |
| 3 | PR #226 R3 unset 분기 hotfix | 10:26 KST 머지 | ✅ 배포 |
| 4 | PARALLEL_OR_TIER_ENABLED=false (Railway 환경변수) | 16:13 KST | ✅ 재배포 |
| 5 | PR #228 G2/G3 unset 분기 hotfix | 16:34 KST 머지 | ✅ 배포 |
| 6 | phase86 + R3 잔존 6키 manual DEL | 16:42 KST | ✅ 완료 |

**진짜 차단 원인 (D 검증 결과)**:
- `prev_close_volume_confirm` 게이트가 일중 reject의 74% (326/441) 차지
- G3 circuit_breaker (`phase86:circuit_breaker:active`)가 momentum_breakout 통과 신호조차 DB 저장 전 hard block
- R3 strict mode가 dynamic 임계를 legacy 0.5로 강제 — 09:00~11:00 KST 0.3 슬라이딩 무효화

---

## 2. 내일 모니터링 일정

### 09:00 KST — 장 개장
- 자동 동작: 2차 스크리닝 30초 주기, 폴백 풀 활성, momentum_breakout 직렬 모드 (PARALLEL OFF)
- **수동 액션 없음** — 시스템이 정상 동작하는지 관찰만

### 09:30 KST — 1차 점검 (T+30분)
- 목적: 신호 생성 메커니즘 작동 확인
- 점검 endpoints:
  - `GET /api/v1/health/observation-daily` — `signals.total` 추이
  - `GET /api/v1/metrics/stage-heatmap?date=today` — 09:00~09:30 stage 분포
  - `GET /api/v1/health/sprint3-keys` — orderbook/vol5m 키 카운트
- **합격 기준 (Go)**:
  - vol5m_count > 0 (실시간 5분봉 적재)
  - orderbook_count ≥ 10 (호가창 적재)
  - stage-heatmap에 `prev_close_volume_confirm` / `gap_open_absorb` **0건** (PARALLEL OFF 검증)
- **불합격 기준 (Hold)**:
  - PARALLEL OFF 게이트가 여전히 reject 누적 → Railway 환경변수 적용 실패
  - vol5m_count = 0 → 실시간 데이터 파이프라인 장애

### 12:00 KST — 2차 점검 (T+3h)
- 목적: 오전장 누적 신호 ≥ 1건 검증
- 점검:
  - `signals.total ≥ 1` (어떤 tier든)
  - stage-heatmap에서 reject 분포 다양화 — 단일 stage 압도(74%) 패턴 부재
- **신호 0건 시**: 임계 자체 추가 완화 필요. top-rejects API로 가장 가까웠던 후보 분석.

### 14:30 KST — eod_blocked 진입 직전 점검
- 목적: 오후장까지 누적 + 14:30 후 eod_blocked 전환 확인
- 점검:
  - `signals.total` 최종 카운트
  - 14:30 이후 `engine_block reason=eod_blocked` 로그 확인 (정상)

### 16:10 KST — `_check_auto_rollback` 자동 실행 결과 확인
- 목적: PR #226/228 unset 분기 작동 검증
- 점검:
  - `GET /api/v1/metrics/phase86-status` — G2/G3 발동 여부
  - `GET /api/v1/health/observation-daily` — rollback.is_active
  - Railway 로그 grep: `자동 롤백 해제` 또는 `자동 롤백 발동` 메시지
- **시나리오**:
  - 오늘 신호 ≥1건 + 어제 1건 → R1 미발동, R2 fallback_triggered 추이 확인
  - 신호 발생으로 pass_rate ≥ 10% → G3 미발동
  - 어느 쪽도 발동 안 하면 unset 분기 활성 (기존 키 없으니 no-op)
- **위험**:
  - 신호 0건이면 R2 재SET 가능 (오늘 fallback=215, 어제·그제 ≥1이면 충족)
  - G3 pass_rate < 10% 3일 연속이면 재SET

### 16:30 KST — 최종 종합 보고
- 일별 신호 누적 + stage 분포 + G2/G3 상태 정리
- `docs/phase/phase8.6/sprint4/2026-05-13-monitoring-result.md` 작성 (이 문서 결과 채워서)

---

## 3. 합격/불합격 판정 기준 (전체)

| 조건 | 합격 기준 | 측정 |
|------|----------|------|
| 데이터 파이프라인 | vol5m ≥ 800, orderbook ≥ 15 | `sprint3-keys` |
| PARALLEL OFF 검증 | `prev_close_volume_confirm` + `gap_open_absorb` 합계 ≤ 5건 | `stage-heatmap` |
| 신호 생성 | total ≥ 1건 (어떤 tier든) | `observation-daily` |
| 자가치유 검증 | G2/G3 unset 분기 작동 (해제 알림 또는 미발동) | Railway 로그 + `phase86-status` |
| 임계 통과 분포 | 단일 stage가 50% 이상 차지하지 않음 | `stage-heatmap` |

---

## 4. 트러블슈팅 플레이북

### 신호 0건 지속
- 1순위: `stage-heatmap`에서 압도 stage 확인 → 그 stage 임계 완화 hotfix
  - `volume_threshold` 1.5~2.5 → 1.2~2.0
  - `trade_strength` ≥ 100 → ≥ 80
  - `confidence` ≥ 0.6 → ≥ 0.5
  - `atr_filter` 정적 0.05 → 0.07
- 2순위: KIS 실시간 데이터 정상 여부 (`vol5m_count`, `orderbook_count`)
- 3순위: 시장 환경 (변동성 낮은 날일 가능성) — 추가 거래일 관찰

### G2/G3 재발동
- 진단: 어떤 R? (R1=3일 0건 / R2=3일 fallback ≥1 / R4=share ≥0.7) 또는 G3 pass_rate
- 조치: `_check_auto_rollback` 다음 16:10에 자동 해제 분기 작동 (PR #228) — 신호 발생 시
- 강제 해제: `scripts/ops/clear_phase86_keys.py` 재실행

### Railway 자동 배포 실패 (BackgroundTasks 손실)
- 백필 + walk-forward 백테스트 BackgroundTasks가 워커 재시작 시 사망 — 별도 hotfix 필요 (APScheduler 영구 잡 전환)

---

## 5. PARALLEL_OR_TIER_ENABLED=false 영향 (검증 대상)

| 코드 경로 | dynamic (true) | static (false, 현재) |
|-----------|----------------|---------------------|
| `momentum_breakout.py:621-634` gap_open_absorb | 활성 (오늘 2건) | 비활성 ✅ |
| `momentum_breakout.py:637-646` prev_close_volume_confirm | 활성 (오늘 326건) | 비활성 ✅ |
| `momentum_breakout.py:752-766` atr_filter (dynamic ceil) | 활성 (오늘 81건) | 정적 0.05로 회귀 |
| `momentum_breakout.py:159-186` min_volume_floor | dynamic 0.3~0.5 | 동일 (R3 해제됨) |

**위험**: ATR 정적 0.05는 종목 가격 대비 ATR ≥ 5%면 차단 — 변동성 큰 종목은 막힘. 만약 atr_filter가 새 압도 stage로 부상하면 PARALLEL ON 복원 + `_evaluate_atr_gate` 임계 별도 완화 검토.

---

## 6. 의미있는 데이터 축적 후 다음 액션

내일 신호 ≥ 1건 발생 시:
1. dry_run signal 누적 (Sprint 3 관찰 게이트로 재개 — 2거래일 연속 ≥1건 충족 후)
2. stage-heatmap 분포 정상화 (50% 이하 단일 stage 점유)
3. **단계 C 임계 재조정** 본격 검토 — 일봉 백필 완료 후 grid search 결과로

내일 신호 0건이면:
1. stage-heatmap top 1 stage 분석
2. 해당 stage 임계 완화 hotfix
3. 추가 거래일 (2026-05-14) 반복 관찰

---

## 7. 참고 자료

- 진단 결과: `project_phase8.6_signal_zero_diagnosis.md` (memory)
- 운영 스크립트: `scripts/ops/clear_phase86_keys.py`, `scripts/ops/diag_tomorrow_readiness.py`
- 코드 위치: `backend/modules/trading/strategies/momentum_breakout.py`
- 게이트 코드: `backend/modules/safety/auto_rollback.py`, `backend/modules/safety/circuit_breaker.py`
- 진단 endpoints: `/health/sprint3-keys`, `/health/observation-daily`, `/metrics/stage-heatmap`, `/metrics/top-rejects`, `/metrics/phase86-status`, `/metrics/override-status`
