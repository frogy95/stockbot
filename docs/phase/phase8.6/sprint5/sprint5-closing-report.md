# Phase 8.6 Sprint 5 — 종합 보고 (Task 5)

> 작성: 2026-05-15 KST
> 브랜치: `phase8.6-sprint5`
> 산출물: T1 진단서, T2 백테스트/DB 스냅샷 3건, T3 trace 인프라, Hotfix A/B/C 3건 머지 완료

---

## 1. 7개 미해결 결함 결론

| # | 결함 | T 산출 | 결론 | 후속 |
|---|------|--------|------|------|
| **#6** | KIS WS execution 35% 누락 (2차 통과 100% 영향) | T3 trace 토글 + 집계 스크립트 (commit ca01f75). Railway `WS_TRACE_ENABLED=true` 설정 완료 (2026-05-15). | ⏳ **Paper 1거래일 자연 누적 대기** — 보고서는 데이터 수집 후 별도. 채택될 root cause 후보(A 한도 / B 레이스 / C MST sync)는 trace 결과로 확정. | Sprint 6 또는 hotfix (2026-05-15 장 마감 후) |
| **#8** | R1 자동 발동 (signals=2에서 active) | T1 진단서 §1. **결정적 결함**: scheduler가 `if should_*=True`일 때만 `execute_*`를 호출 → self-clear 분기 영원히 미도달. | ✅ **Hotfix C(PR #240) 머지로 해소**. 회귀 테스트 2건 추가. | 16:12 cron으로 자동 해제 효과 검증 예정 |
| **#9** | G3 임계 부등호 | T1 진단서 §2. `r < threshold` (strict less than)가 phase8.6.md §3 정의("< 10%")와 일치. | ✅ **의도 일치 — Hotfix 불필요**. | 문서 보강만 (선택) |
| **#10** | breakout 72.2% 단일 stage 편중 | T2 `t2-backtest-report.md` (commit 7c48e12). KIS 일봉 캐시 21거래일만 존재(60일 부족), trend=0일 → `DatasetInsufficientError`. Partial 21일 시뮬 결과: prev_high 0.90 (최고) → volume_surge 0.29 (최저). | ⚠️ **판정 보류** (백필 필요). | Sprint 6 또는 별도 hotfix — KIS 일봉 60일 백필 후 walk-forward 재실행 |
| **#11** | 임계 게임 (`momentum_breakout` 직렬 AND) | T1 진단서 §3. tier 수준은 Sprint 2 병렬 OR. 동일 tier 내부 stage는 **여전히 직렬 AND** (volume_threshold → trade_strength → orderbook_ratio → breakout 순차, 첫 fail에서 short-circuit). | ⚠️ **구조 결함 확인, 정량 미완** (T2 백필 후). | Sprint 6 본격 결정 — stage 병렬 OR 또는 가중 평균 구조 검토 |
| **#13** | fallback 폭증 (어제 456건) — 의미 분리 오해 | T2 `t2-fallback-db-snapshot.md` + 추가 트레이스. `triggered_count`(폴백 풀 진입 시도, Redis counter)와 `fallback_signal_count`(strategy 통과 신호, DB)는 **다른 단계 측정**. 저장 경로 결함 없음. | ✅ **결함 아님 — 메트릭 의미 분리**. 단, **새 본질 #16 발견** (아래) | 진단서 명시 |
| **#14** | secondary 4h 100% 교체율 | T2 `t2-secondary-churn-db-snapshot.md` (commit 7c48e12). 측정1 churn≈1.0, 측정2 평균 0.41. hysteresis 부재 가설 지지. | ⚠️ **부분 재현** — 구조 결함 가능성 잔존. | Sprint 6 — secondary 풀 hysteresis 도입 검토 |

### 신규 발견 — #16 (Sprint 5 진단 부산물)

**#16 fallback strategy 통과율 0%** — 어제 폴백 풀 후보 평가 456회 → strategy 통과해 실제 신호 0건.
- 폴백 종목이 secondary는 통과하나 `momentum_breakout.generate_signal()`에서 모두 `RejectedSignal` 반환.
- E2(fallback 비중 ≤ 20%)는 분자=0이라 자동 합격이지만 **본질은 폴백이 신호 차단 해소를 못함**.
- 원인 가설: (A) fallback candidate가 momentum_breakout 게이트(breakout/volume_threshold/trade_strength)에서 모두 reject, (B) 폴백 종목 정의상 본 score가 낮아 strategy 기준 미달.
- 후속: Sprint 6 또는 추가 진단 hotfix.

---

## 2. Phase 8.7 entry gate 평가 (§11.5)

| Gate | 임계 | 측정값 (현재) | 통과 여부 |
|------|------|---------------|----------|
| **E1** | WS execution 누락률 ≤ 5% | **측정 진행 중** (T3 trace 1거래일 누적, 2026-05-15 당일 (장 마감 후 aggregate)) | ⏳ 대기 |
| **E2** | fallback 신호 비중 ≤ 20% (M-F2) | **0%** (어제 7일간 fallback_signals=0) | ✅ (단, #16 무효화 효과 의심) |
| **G-Bt1** | walk-forward KS p ≥ 0.05 | **판정 불가** (KIS 일봉 60일 백필 부족) | ⏳ 대기 |
| **G-Bt2** | Bootstrap 95% CI 하한 ≥ 1 | **판정 불가** (동일 사유) | ⏳ 대기 |

**판정**: 4개 지표 중 1개만 명목상 통과(E2), 나머지 3개 대기. **Phase 8.7 LIVE 토글 차단 유지**.

---

## 3. Sprint 5 DoD (§11.4) 달성도

| # | 항목 | 결과 |
|---|------|------|
| S5-1 | T1 진단서 — #7/#8/#9/#11 변경 위치 확정 | ✅ commit 5426f29 |
| S5-2 | Hotfix A (#7) 머지 | ✅ PR #237 / #239 머지 완료 |
| S5-3 | Hotfix C 결정 — #9 → 의도 일치, **#8을 Hotfix C로 분리** | ✅ PR #240 / #241 머지 완료 |
| S5-4 | T2 백테스트 보고서 (#10) | ⚠️ Partial (21/60일) — 백필 필요 |
| S5-5 | T2 DB 측정 (#13/#14) | ✅ commit 7c48e12 (단, #13은 의미 분리로 #16 신규 발견) |
| S5-6 | E1/E2 측정 인프라 | ✅ E1=WS trace(T3), E2=M-F2 endpoint 재사용 명시 |
| S5-7 | T3 진단 보고서 (#6 root cause) | ⏳ Paper 1거래일 누적 대기 (2026-05-15 당일) |
| S5-8 | pytest 전체 통과 | ✅ 회귀 0건 (실패 1건은 baseline 동일, 5/13 stale) |
| S5-9 | Phase 7.0 LIVE 파라미터 잠금 회귀 0건 | ✅ |

**달성**: 6/9 완료, 3/9 대기 (T3 데이터 누적 + 백필).

---

## 4. 후속 결정 권고

### 즉시 처리할 것

- (없음 — Hotfix A/B/C 모두 머지 완료, 임계 변경 금지 원칙 유지)

### Sprint 6 후보 — 우선순위 합의 필요

| 우선순위 | 항목 | 근거 |
|---------|------|------|
| 1 | KIS 일봉 60일 백필 인프라 + walk-forward 재실행 | #10/#11 정량 판정 + G-Bt1/G-Bt2 측정 — Phase 8.7 진입 차단 해제의 직접 입력 |
| 2 | #16 fallback strategy 통과율 0% trace + 구조 결정 | 폴백 메커니즘 무력화 — Phase 8.7 entry gate E2 의미 회복 |
| 3 | #11 stage 직렬 AND → 병렬 OR 또는 가중 평균 구조 변경 | 임계 게임 패턴 본질 해소. T2 백필 결과 입력 후 결정 |
| 4 | #14 secondary 풀 hysteresis 도입 | 4h 교체율 정량 → 진입 일관성 |

### Paper 자연 누적 (2026-05-15 당일)

- T3 WS trace 1거래일 (#6)
- 그동안 Hotfix C 효과(#8 R1/G3 자동 해제) 자연 검증 — 16:12 cron 등록됨

### Phase 8.7 진입

- 4개 entry gate 모두 측정 가능해진 시점에 평가
- 현재는 LIVE 토글 차단 유지, dry_run 강제

---

## 5. 권고 — 사용자 선택지

**(c) Phase 8.7 entry gate 미충족 — Paper 추가 관찰 + T3/백필 후속 fix**가 현재 상태에 부합.

- (a) "임계 재조정 hotfix만"은 적용 불가 — 본질 결함 #11/#16이 임계와 무관
- (b) "구조 변경 새 Sprint 신설"은 백필 후 데이터 확보 시 결정 — 지금은 백필 자체가 선행

**다음 액션**:
1. Sprint 6 sprint-planner 호출 (KIS 일봉 백필 인프라 + #11/#16 구조 결정)
2. 또는 #6/#8 라이브 자연 누적(2026-05-15 장 마감 후) 대기 후 종합 재평가

---

## 6. 참고 — 본 Sprint 산출 커밋·PR 목록

| 항목 | 커밋/PR |
|------|---------|
| T1 진단서 | commit 5426f29 |
| T3 WS trace 토글 + 집계 스크립트 | commit ca01f75 |
| T2 백테스트/DB 스냅샷 3종 | commit 7c48e12 |
| Hotfix A (#7 R3 unset + Enum) | PR #237 / #239 |
| Hotfix B (#12 raw change_rate) | PR #238 / #239 |
| Hotfix C (#8 self-clear) | PR #240 / #241 |
| Sprint 5 종합 보고 (본 문서) | (Task 5 커밋) |
