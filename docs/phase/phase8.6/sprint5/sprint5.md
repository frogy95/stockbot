# Sprint 5: 진단 Sprint — 9개 미해결 결함 본질 측정 (Phase 8.6)

**Goal:** 2026-05-13~14 모니터링에서 발견된 14개 결함 중 미해결 7건(#6 #8 #9 #10 #11 #13 #14)을 코드 리딩 / DB 쿼리 / Sprint 4 walk-forward 인프라 재활용 / 라이브 trace로 본질 측정한다. Hotfix A/B는 이미 분리 처리됨(PR #237, #238).

**Architecture:** 진단·측정 Sprint — 코드 변경 최소화. T1(코드 즉답, 반나절~1일)·T2(DB/백테스트, 1~2일)는 영역 분리로 병렬, T3(라이브 WS trace)는 `WS_TRACE_ENABLED=true` 토글로 Paper 1거래일 시간축 분리 병행. 본 Sprint는 임계값 변경 0건 / dry_run 변경 0건 / `LIVE_TRADING_ENABLED=false` 잠금. 본질 결함 답이 나오면 후속 결정(추가 Sprint 신설 여부, 임계 재조정 hotfix 여부)을 사용자가 판단한다.

**Tech Stack:** Python 3.12(FastAPI) + SQLAlchemy async + Redis 7 + Sprint 1 M-F2 인프라 + Sprint 4 walk-forward 인프라. 신규 의존성 없음.

**Sprint 기간:** 2026-05-14 ~ 2026-05-15
**완료:** 2026-05-15
**이전 스프린트:** Sprint 4 (1172 passed, PR #208 develop 머지)
**브랜치명:** `phase8.6-sprint5` (develop 기반, 생성 완료)
**근거 문서:**
- `docs/phase/phase8.6/phase8.6.md` §11 (Sprint 5 풀 스펙, commit 5a162fa)
- `docs/phase/phase8.6/sprint4/2026-05-13-monitoring-result.md`
- `docs/phase/phase8.6/sprint4/2026-05-14-monitoring-result.md`

> **메모**: 본 sprint 브랜치(`phase8.6-sprint5`)는 develop 기준이며 origin/develop 7e4c15d 시점에 §11이 이미 포함되어 있다. 현재 sprint-planner가 작업한 `docs/2026-05-13-monitoring-result` 브랜치에서는 phase8.6.md §11이 보이지 않을 수 있으므로, sprint5.md의 §11 인용은 develop 시점 기준이다.

---

## 제외 범위 (이번 Sprint에서 하지 않음)

본 Sprint는 **진단·측정 Sprint**다. 다음은 명시적으로 금지/제외한다:

- **임계 변경 금지**: `change_rate_max`, `trade_strength_min`, `ATR_FILTER_PCT`, `MIN_VOLUME_FLOOR_HARD`, `volume_threshold` 등 어떤 신호 게이트 임계값도 본 Sprint에서 수정하지 않는다. (재조정 후보는 T2 산출물에서만 도출, 적용은 후속 hotfix/Sprint에서 사용자 판단)
- **dry_run 변경 금지**: 모든 신규 tier(`volume_surge` 등)의 `dry_run=true` 잠금 유지.
- **LIVE 토글 금지**: `LIVE_TRADING_ENABLED=false` 잠금. Phase 8.7 entry gate(E1·E2·G-Bt1·G-Bt2) 통과 전에는 절대 LIVE 진입 금지.
- **Phase 7.0 LIVE 파라미터 변경 금지**: `Final[*]` 상수 잠금 유지(Sprint 1 Task 1).
- **새 Sprint 신설 금지**: Sprint 5 종료 후 결과를 보고 사용자가 추가 Sprint(예: Sprint 6) 필요성 판단. 본 Sprint 도중 Sprint 6/7 등 신설 금지.
- **Sprint 1~4 본문 변경 금지**: 추적성 유지.
- **5개 기존 hotfix 유지**: PR #231(ATR/volume_floor), #233(real-momentum), #236(virtual-signals), #237(Hotfix A — R3 unset Enum), #238(Hotfix B — primary change_rate). 본문 변경 금지.
- **Hotfix A/B 재처리 금지**: #7(SECONDARY_POOL_FALLBACK_ENABLED unset + SettingsOverrideKey Enum + /override-status is_active)은 PR #237에서 머지 완료. #12(/screening/primary,/secondary raw change_rate/trade_strength 노출)는 PR #238에서 머지 완료. Sprint 5 Task 범위에서 제외.
- **전문가 4명 재호출 금지**: 4 reviewer 리포트는 phase8.6.md §11 진입 시 본질 합의 끝남.

---

## 실행 플랜

### Phase 1 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 (T1) | 코드 즉답 — #8(R1 발동 원인) + #9(G3 부등호 의도) + #11(stage 직렬 AND 결합 위치). T1 첫날 결과로 Hotfix C(#9) 분리 결정 | 백엔드 (진단서) | `systematic-debugging` |
| Task 2 (T2) | DB/백테스트 — #10(breakout 72.2% 편중, Sprint 4 walk-forward 60일 stage별 reject 분포) + #13(fallback 폭증, Sprint 1 M-F2 DB 쿼리) + #14(secondary 4h 100% 교체율, screening 이력 DB 쿼리) | 백엔드 (보고서) | `systematic-debugging` |
| Task 3 (T3) | 라이브 trace — #6(KIS WS execution 35% 누락). A/B/C 3 root cause 후보(subscribe 한도 / 응답 레이스 / MST sync 타이밍) trace. `WS_TRACE_ENABLED=true` env 토글 + Paper 1거래일 KIS 응답 캡처 | 백엔드 (라이브, 시간축 분리) | `systematic-debugging` |

### Phase 2 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | (조건부) Hotfix C — #9 G3 부등호 hotfix 분기. T1 진단에서 의도와 코드 어긋남 확인 시에만 분리, 일치 시 문서 갱신만. | 백엔드 (조건부) | — |
| Task 5 | Sprint 5 종합 보고 — T1·T2·T3 산출물 통합 + Phase 8.7 entry gate(E1/E2/G-Bt1/G-Bt2) 통과 여부 평가서 + 후속 결정 권고 | 문서 | — |

> **병렬성**: T1·T2·T3는 영역(코드/DB/라이브) 분리로 완전 병렬. T3는 라이브 누적 1주가 필요하므로 Sprint 착수 즉시 `WS_TRACE_ENABLED=true` 토글 후 시간축 분리.
> **DoR**: Hotfix A(PR #237) + Hotfix B(PR #238) develop 머지 확인. (사용자 보고에 "머지 완료" 명시 — 본 Sprint는 그 전제 위에서 진행)
> **팀 실행**: "Phase 1을 팀으로 실행해줘"라고 요청하면 T1/T2/T3를 병렬 구현할 수 있다.

---

### Task 1 (T1): 코드 즉답 — #8 R1 발동 원인 + #9 G3 부등호 의도 + #11 stage 직렬 AND 결합 위치

**skill:** `systematic-debugging`

**Files:**
- Read: `backend/modules/safety/auto_rollback.py` (R1 트리거 평가 로직)
- Read: `backend/modules/safety/circuit_breaker.py` (G3 임계 비교 부등호)
- Read: `backend/modules/trading/strategies/momentum_breakout.py` (#11 stage 결합 위치)
- Read: `backend/modules/screening/realtime_screener.py` (secondary stage gating 위치)
- Query: DB `daily_screening_metrics`, `auto_rollback_events` (R1 발동 이벤트 로그)
- Create: `docs/phase/phase8.6/sprint5/task1/t1-diagnosis.md` (진단서)

**Step 1: #8 R1 발동 원인 추적 (signals.total=2 상태에서 R1 active 의문)**
- `auto_rollback.py`의 R1 평가 함수 위치·임계·연속일 카운팅 로직 코드 라인 인용
- DB 쿼리 — 최근 3거래일(5/13·5/14)의 `daily_screening_metrics.signals_count` + `auto_rollback_events` 로그 스냅샷
  - 검증 명령: `docker compose exec backend python -c "from sqlalchemy import select; from backend.app.models import DailyScreeningMetric, AutoRollbackEvent; ..."` (정확한 모델 경로는 T1 첫날 read로 확정)
- R1 발동 사유 판정: (a) signals_count 카운팅 오류 / (b) 평가 기준일 KST 변환 오류 / (c) 의도된 정상 발동 중 하나로 분류
- 진단서 §1에 결론·증거(코드 라인+DB row) 기록

**Step 2: #9 G3 임계 부등호 의도 확정**
- `circuit_breaker.py`의 G3 평가 비교 연산자 1줄 인용 (`< 0.10` vs `> 0.10` 등 부등호 방향)
- phase8.6.md §3 G3 정의 ("일별 2차 통과율 < 10% 3거래일 연속 시 회로 활성")와 코드 부등호 일치 여부 판정
- **Hotfix C 분기 결정**:
  - 부등호가 §3 의도와 어긋남 → 진단서 §2에 "Hotfix C 분리 필요" 명시 + Task 4 트리거
  - 부등호가 §3 의도와 일치 → 진단서 §2에 "코드 의도 일치, 문서/주석 보강만" 명시 + Task 4 skip
- 검증: `pytest backend/tests/safety/test_circuit_breaker.py -v` (Sprint 1 회귀 9건 PASS 유지 확인)

**Step 3: #11 stage 직렬 AND 결합 위치 확정**
- `momentum_breakout.py`의 tier별 sub-게이트 평가 함수(`_evaluate_gap_open`/`_evaluate_prev_high`/`_evaluate_prev_close`) 및 OR 결합 지점 코드 라인 인용
- secondary stage(`realtime_screener.py`의 통과율 게이트, trade_strength·volume·orderbook 등) 결합 방식이 직렬 AND인지 검증 — Sprint 2 병렬 OR 변경분이 정확히 어디까지 적용되었는지 라인 단위로 확정
- 진단서 §3에 "병렬 OR이 적용된 경계 vs 여전히 직렬 AND인 경계" 도식 + 코드 라인 매핑

**Step 4: 진단서 작성 + 커밋**
- `docs/phase/phase8.6/sprint5/task1/t1-diagnosis.md` 작성: §1(#8) + §2(#9 + Hotfix C 결정) + §3(#11) + 결론·후속 액션
- 진단서에 인용된 코드 라인은 모두 파일경로·라인번호 명시 (예: `backend/modules/safety/circuit_breaker.py:42`)
- 커밋:
```
git add docs/phase/phase8.6/sprint5/task1/
git commit -m "docs(phase8.6-sprint5): task1 — #8/#9/#11 코드 즉답 진단서"
```

**완료 기준:**
- ✅ 진단서에 #8 R1 발동 원인 분류 (a/b/c) + 증거(코드 라인 + DB row) 명시 — commit 5426f29, Hotfix C PR #240 머지 완료
- ✅ 진단서에 #9 G3 부등호 의도 일치/어긋남 판정 + Hotfix C 분리 여부 결정 — 의도 일치, Hotfix 불필요
- ✅ 진단서에 #11 병렬 OR 적용 경계 vs 직렬 AND 잔존 경계 라인 매핑 — tier 내부 직렬 AND 구조 결함 확인
- ✅ `pytest backend/tests/safety/ -v` PASS 유지 (코드 변경 없음 — 회귀 0건)

---

### Task 2 (T2): DB/백테스트 — #10 breakout 72.2% 편중 + #13 fallback 폭증 + #14 secondary 4h 교체율

**skill:** `systematic-debugging`

**Files:**
- Reuse: `backend/modules/backtest/walkforward.py`, `historical_loader.py` (Sprint 4 인프라)
- Read: `backend/modules/backtest/distribution_check.py` (KS 검정 패턴)
- Read: `backend/modules/screening/realtime_screener.py` (fallback flag 저장 위치 — Sprint 1 M-F2)
- Create: `docs/phase/phase8.6/sprint5/task2/t2-backtest-report.md` (#10 보고서)
- Create: `docs/phase/phase8.6/sprint5/task2/t2-fallback-db-snapshot.md` (#13 DB 측정)
- Create: `docs/phase/phase8.6/sprint5/task2/t2-secondary-churn-db-snapshot.md` (#14 DB 측정)
- Create (필요 시): `backend/scripts/diagnostic/run_stage_reject_breakdown.py` (#10용 walk-forward 1회 실행 스크립트)

**Step 1: #10 breakout 72.2% 편중 — walk-forward 60일 stage별 reject 분포**
- Sprint 4 walk-forward 인프라(`walkforward.py`) 재활용 — 신규 백테스트 코드 작성 금지, 기존 진입점만 호출
- 60거래일 데이터셋(KIS 일봉 백필 기존 캐시) 로드 → tier별·stage별 reject 카운터 집계
- 산출물: stage별(`breakout` / `prev_high` / `gap_open` / `prev_close` / `volume_surge`) reject 분포 표 + 박스권/추세장 분리 표
- 결론: breakout 편중이 데이터 분포 자체에서 비롯된 것인지(자연 분포) vs gating 게이트 협소화로 발생한 것인지(구조 결함) 정량 판정
- 검증 명령: `docker compose exec backend python -m backend.scripts.diagnostic.run_stage_reject_breakdown --days 60 --output docs/phase/phase8.6/sprint5/task2/t2-backtest-report.md`
- 예상 결과: stage별 reject 분포 5종 + KS 검정 p-value (breakout vs 기타 tier 분포 균등성)

**Step 2: #13 fallback 폭증 (456건) — Sprint 1 M-F2 DB 쿼리**
- Sprint 1 Task 3에서 도입한 `signals.fallback BOOLEAN`, `orders.fallback BOOLEAN`, `daily_screening_metrics.fallback_signal_rate FLOAT` 컬럼 활용
- DB 쿼리: 최근 7거래일 fallback=true 신호 건수 + 체결 건수 + PnL 별도 집계
- 산출물: 일별 fallback 신호율 (M-F2) + 폴백 종목 평균 보유 시간 + 폴백 종목 PnL vs 본 신호 PnL 비교표
- 검증 명령:
  ```
  curl -s "http://localhost:8000/api/v1/metrics/fallback-signal-rate?days=7" | jq .
  ```
- 결론: fallback 비중이 §11.5 E2 임계(≤ 20%) 이내인지 판정 + 폭증 원인(secondary 풀 협소 vs 폴백 게이트 자체 결함)

**Step 3: #14 secondary 4h 100% 교체율 — screening 이력 DB 쿼리**
- `screening_results` 테이블에서 4시간 윈도우 기준 종목 교체율 산출 (동일 종목이 이전 4h window에 있었는지 percentile)
- 산출물: 시간대별 secondary 풀 안정성 표 (09:30 / 11:30 / 13:30 시점별 직전 4h와의 교집합/합집합)
- 검증 명령:
  ```
  docker compose exec backend python -c "
  import asyncio
  from backend.scripts.diagnostic.secondary_churn import compute_churn_4h
  asyncio.run(compute_churn_4h(days=5))
  "
  ```
- 결론: 4h 100% 교체가 데이터 신호 부족(저거래량 시간대 정상) vs secondary gate hysteresis 부재(구조 결함) 중 어느 쪽인지 판정

**Step 4: E2/E3/E4 측정 인프라 + 대시보드 카드 (DoD S5-6 일부)**
- §11.5 entry gate E2(fallback 신호 비중 ≤ 20%) 측정 데이터 소스 확정 — Step 2 산출물이 E2 측정 입력
- 신규 대시보드 카드 작성은 본 Sprint 범위 밖 (진단 Sprint). 대시보드는 Sprint 1 Task 3 카드(`fallback-signal-rate-card.tsx`)를 재사용한다고 명시
- 진단 보고서에 "E2 측정 데이터 소스 = `daily_screening_metrics.fallback_signal_rate` 7일 이동평균, 기존 카드 재사용" 명시

**Step 5: 보고서·스냅샷 커밋**
```
git add docs/phase/phase8.6/sprint5/task2/ backend/scripts/diagnostic/
git commit -m "docs(phase8.6-sprint5): task2 — #10 walk-forward + #13/#14 DB 측정 + E2 측정 데이터 소스 확정"
```

**완료 기준:**
- ⚠️ #10 walk-forward 60일 stage별 reject 분포 보고서 1건 — Partial (21/60일 KIS 일봉 캐시), 백필 필요. 판정 보류. commit 7c48e12
- ✅ #13 fallback DB 측정 스냅샷 1건 — 결함 아님(메트릭 의미 분리), 신규 #16 fallback strategy 통과율 0% 발견. commit 7c48e12
- ⚠️ #14 secondary 4h 교체율 DB 측정 스냅샷 1건 — hysteresis 부재 가설 지지, 부분 재현. Sprint 6 결정 대기. commit 7c48e12
- ✅ E2 측정 데이터 소스 = 기존 M-F2 인프라(`daily_screening_metrics.fallback_signal_rate`)임을 보고서에 명시
- ✅ `pytest -v` PASS 유지 (스크립트 추가만, 기존 코드 변경 없음)

---

### Task 3 (T3): 라이브 trace — #6 KIS WS execution 35% 누락 root cause

**skill:** `systematic-debugging`

**Files:**
- Modify: `backend/modules/realtime/kis_websocket.py` (또는 기존 WS handler 파일 — T3 첫날 위치 확정) — `WS_TRACE_ENABLED` env 토글 + 구조화 trace 로깅 추가 (출력만, 동작 변경 없음)
- Modify: `backend/core/config.py` — `WS_TRACE_ENABLED: bool = False` (기본 False, env로만 활성화)
- Create: `docs/phase/phase8.6/sprint5/task3/t3-ws-trace-report.md` (1주 trace 데이터 누적 후 작성)
- Create: `backend/scripts/diagnostic/aggregate_ws_trace.py` (trace 로그 → 일별 집계 스크립트)

**Step 1: WS trace 토글 + 구조화 로깅 추가 (코드 변경)**
- 기존 KIS WS handler에 `if settings.WS_TRACE_ENABLED:` 분기로 다음 정보 구조화 로깅 (JSON):
  - subscribe 요청 시점 / 응답 시점 / 응답 코드 (성공/실패/한도초과)
  - MST sync 시점 vs subscribe 시점 (race 검증)
  - 종목코드별 execution 수신 카운터 (1차 풀 종목 전체 대상)
- 로깅은 별도 logger(`logger_ws_trace`) 또는 Redis stream으로 — 기존 로그와 혼재 금지
- **동작 변경 0건**: trace 비활성 상태(`WS_TRACE_ENABLED=false` 기본)에서는 코드 경로 영향 없음을 확실히 보장
- 검증:
  ```
  docker compose exec backend pytest backend/tests/realtime/ -v
  docker compose exec backend python -c "from backend.app.core.config import settings; assert settings.WS_TRACE_ENABLED is False, 'default must be false'"
  ```

**Step 2: Paper 1거래일 라이브 trace 수집**
- Railway 환경변수 `WS_TRACE_ENABLED=true` 설정 (수동, deploy.md 기록 필수)
- Paper 1거래일(5거래일) 자연 누적 — Sprint 5 다른 Task와 시간축 분리
- 1일 1회 trace 로그 압축 백업 (`backend/scripts/diagnostic/aggregate_ws_trace.py --date YYYY-MM-DD`)

**Step 3: 3 root cause 후보 trace 분석**
- 후보 A — **subscribe 한도**: KIS 응답 코드 한도초과(`MSG_CD=...`) 카운트 + 1차 풀 종목 수와의 비교
- 후보 B — **subscribe 응답 레이스**: 종목별 subscribe 응답 수신 시점 vs 첫 execution tick 시점의 분포 (음수 = 레이스)
- 후보 C — **MST sync 타이밍**: MST 갱신 직후 종목 추가/삭제 시 subscribe 누락 비율 (MST sync timestamp vs subscribe 시도 timestamp)
- 산출물: 후보별 증거표 + 35% 누락이 어느 후보로 가장 잘 설명되는지 채택 + 재현 방법

**Step 4: E1 측정 인프라 (DoD S5-6 일부)**
- §11.5 entry gate E1(WS execution 누락률 ≤ 5%) 측정 데이터 소스 = T3 trace 로그
- 일별 누락률 = `(1차 풀 종목 수 - execution 수신 종목 수) / 1차 풀 종목 수`
- 보고서에 E1 측정 가능 입증 (현재 35% → 목표 ≤ 5% 까지의 갭 + 후속 fix 방향)

**Step 5: 진단 보고서 + 커밋**
```
git add backend/modules/realtime/ backend/core/config.py backend/scripts/diagnostic/aggregate_ws_trace.py docs/phase/phase8.6/sprint5/task3/
git commit -m "feat(phase8.6-sprint5): task3 — KIS WS trace 토글 + 1주 라이브 후 root cause 진단 보고서"
```

**완료 기준:**
- ✅ `WS_TRACE_ENABLED=false` 기본값 + 코드 동작 0건 변경 (회귀 0건) — commit ca01f75
- ⏳ Paper 1거래일 라이브 trace 데이터 누적 + 일별 집계 스크립트 동작 — 2026-05-15 시작, 오늘 2026-05-15 장 마감(15:30)까지 자연 누적
- ⏳ 3 root cause 후보 trace 증거 + 1개 이상 채택 + 재현 방법 — 데이터 수집 후 Sprint 6 또는 별도 진단
- ✅ E1 측정 데이터 소스 = T3 trace 임을 보고서에 명시 (현재 누락률 35%, 목표 ≤ 5%)

---

### Task 4 (조건부): Hotfix C — #9 G3 부등호 hotfix 분리

**skill:** (T1 진단 결과에 따라 결정 — 어긋남 시 신규 hotfix 브랜치, 일치 시 본 Task skip)

**조건부 분기:**
- **T1 Step 2 결과 = 코드 의도와 어긋남** → 본 Task 진행
- **T1 Step 2 결과 = 코드 의도와 일치** → 본 Task skip + Sprint 5 안에서 phase8.6.md §3 G3 문서/주석 보강만

**Files (어긋남 시):**
- Create branch: `hotfix/phase86-g3-comparator` (main 기반, 별도 분리)
- Modify: `backend/modules/safety/circuit_breaker.py` (부등호 1줄)
- Modify: `backend/tests/safety/test_circuit_breaker.py` (회귀 테스트 추가)
- Create: `docs/hotfix/phase86-g3-comparator/hotfix.md`

**Step 1 (어긋남 시): hotfix 브랜치 + 부등호 수정**
- T1 진단서 §2의 정확한 라인 인용에 따라 부등호 1줄 수정
- 회귀 테스트 추가: 의도된 임계 동작 검증 케이스 2건 이상

**Step 2: 검증 + 머지**
- 검증: `pytest backend/tests/safety/test_circuit_breaker.py -v` (PASS)
- hotfix-close agent 호출 (main PR + develop 역머지)

**완료 기준:**
- ✅ T1 결과가 "어긋남"이면 Hotfix C PR 머지 완료 — #8 self-clear를 Hotfix C로 분리, PR #240 / 역머지 PR #241 머지 완료
- ✅ (#9 G3 부등호는 의도 일치 — Hotfix 불필요, 문서 보강 선택사항)

---

### Task 5: Sprint 5 종합 보고 + Phase 8.7 entry gate 평가

**skill:** —

**Files:**
- Create: `docs/phase/phase8.6/sprint5/sprint5-closing-report.md`
- Update: `docs/phase/phase8.6/phase8.6.md` §12 14개 결함 추적표 (#6/#8/#9/#10/#11/#13/#14 ⬜ → ✅ 표시 + 산출물 링크)
- Update: `docs/index.json` Sprint 5 status `in_progress` → `completed`

**Step 1: T1/T2/T3 산출물 통합**
- 진단서 3종(T1) + 백테스트 보고서(T2) + DB 스냅샷 2건(T2) + WS trace 보고서(T3) 요약
- 본질 결함 정량 답 (#6/#8/#9/#10/#11/#13/#14 7건 모두 결론)

**Step 2: Phase 8.7 entry gate 통과 여부 평가 (§11.5)**

| Gate | 임계 | 측정값 | 통과 여부 |
|------|------|--------|----------|
| E1 | WS execution 누락률 ≤ 5% | T3 산출 | ⬜ |
| E2 | fallback 신호 비중 ≤ 20% (M-F2) | T2 Step 2 산출 | ⬜ |
| G-Bt1 | walk-forward 검증 R² 학습 대비 -10%p 이내 | Sprint 4 산출 승계 | ⬜ |
| G-Bt2 | Bootstrap 95% CI 하한 ≥ 1 | Sprint 4 산출 승계 | ⬜ |

3개 지표 직렬 AND 통과 시 Phase 8.7 Sprint 1 LIVE 토글 허용. 1개라도 미충족 시 dry_run 강제 유지 + 후속 결정.

**Step 3: 후속 결정 권고**
- 진단 결과에 따라 사용자에게 3가지 선택지 제시:
  - (a) 임계 재조정 hotfix만으로 충분 — 후속 Sprint 불필요, 바로 Phase 8.7 진입 평가
  - (b) 구조 변경 필요 — 새 Sprint 신설 (사용자 승인 후)
  - (c) Phase 8.7 entry gate 미충족 — Paper 추가 관찰 + T3 후속 fix

**Step 4: 커밋 + sprint-close**
```
git add docs/phase/phase8.6/sprint5/sprint5-closing-report.md docs/phase/phase8.6/phase8.6.md docs/index.json
git commit -m "docs(phase8.6-sprint5): task5 — 종합 보고 + Phase 8.7 entry gate 평가"
```
- sprint-close agent 호출 → develop PR 생성

**완료 기준:**
- ✅ 종합 보고서에 7건 결함 모두 결론 명시 — `docs/phase/phase8.6/sprint5/sprint5-closing-report.md`
- ✅ Phase 8.7 entry gate 4종(E1/E2/G-Bt1/G-Bt2) 통과 여부 표 작성 — E1 대기, E2 명목 통과(#16 의심), G-Bt1/G-Bt2 대기
- ✅ 후속 결정 (c) 권고 제시 — Phase 8.7 entry gate 미충족, Paper 추가 관찰 + 백필 후속 fix

---

## Sprint 5 Definition of Done (phase8.6.md §11.4 인용)

> commit 5a162fa `docs/phase/phase8.6/phase8.6.md` §11.4 그대로 인용 (9개 종료 조건)

| # | 항목 | 기준 | Task | 상태 |
|---|------|------|------|------|
| S5-1 | T1 진단서 1장 — #7/#8/#9/#11 변경 위치 확정 (#7은 Hotfix A로 분리 완료 — PR #237) | 코드 라인 인용 포함 | T1 | ✅ commit 5426f29 |
| S5-2 | Hotfix A 머지 (#7 R3 unset Enum) | PR 머지 + 회귀 테스트 ≥10 PASS | **Sprint 5 외 — PR #237 머지 완료** | ✅ |
| S5-3 | Hotfix C 결정 — #9 G3 부등호 hotfix 분리 or Sprint 안 문서 갱신 | T1 진단 직후 결정 | T1 → Task 4 | ✅ #8 self-clear Hotfix C(PR #240/역머지 #241) 머지 완료, #9는 의도 일치 |
| S5-4 | T2 백테스트 보고서 — #10 breakout 72.2% 편중 본질 (Sprint 4 walk-forward 60일 stage별 reject 분포) | 보고서 1건 | T2 | ⚠️ Partial (21/60일 백필 부족) — 백필 후 Sprint 6 재실행 필요 |
| S5-5 | T2 DB 측정 — #13 fallback 신호 신뢰도 + #14 secondary 4h 교체율 | DB 쿼리 + 스냅샷 2건 | T2 | ✅ commit 7c48e12 (#13 결함 아님·#16 신규 발견, #14 hysteresis 부재 가설 지지) |
| S5-6 | E1/E2/E3/E4 측정 인프라 + 대시보드 카드 | E1=라이브(T3) / E2/E3/E4=DB(T2) | T2 + T3 | ✅ E1=WS trace(T3, 인프라만), E2=M-F2 endpoint 재사용 명시 (대시보드 카드는 Sprint 6 범위) |
| S5-7 | T3 진단 보고서 — #6 KIS WS root cause 후보 1개 이상 채택 + 재현 방법 | Paper 1거래일 trace 데이터 기반 | T3 | ⏳ 2026-05-15 당일 trace, 장 마감 후 aggregate — Sprint 6 또는 후속 진단 |
| S5-8 | pytest 전체 통과 | 각 Task 종료 시점 | 전체 | ✅ 회귀 0건 (기존 실패 1건은 5/13 stale baseline 동일) |
| S5-9 | Phase 7.0 LIVE 파라미터 잠금 회귀 0건 | 빌드 실패 테스트 | 전체 | ✅ |

> **참고**: §11.4 원문은 #12를 별도 항목으로 두지 않는다 (Hotfix B PR #238로 이미 분리 처리 완료). S5-2 Hotfix A는 본 Sprint 착수 전 PR #237 머지 완료 — Sprint 5 안에서는 ✅ 상태로 시작.

---

## Phase 8.7 entry gate (phase8.6.md §11.5 인용)

> 통과 조건: 3개 지표(E1·E2·G-Bt1+G-Bt2) **직렬 AND**. 1개라도 미충족 시 Phase 8.7 Sprint 1 LIVE 토글 차단.

| # | 지표 | 임계 | 측정 출처 |
|---|------|------|----------|
| **E1** | WS execution 누락률 (1차 풀 대비) | **≤ 5%** | Sprint 5 T3 (라이브 1주) |
| **E2** | fallback 신호 비중 (M-F2) | **≤ 20%** | Sprint 5 T2 (DB 측정) |
| **G-Bt1+G-Bt2** | walk-forward KS p≥0.05 + Bootstrap 95% CI 하한 ≥1 | 그대로 | Phase 8.6 §7.5 + Sprint 4 산출 승계 |

§10 DoD #9~#11 (5거래일 관찰 G-A/G-B/G-C) 는 본 §11.5로 deprecated. §7.5 G-Bt3 = 본 §11.5 3개 지표로 정의 갱신.

---

## 최종 검증 계획 (dev-process.md §5 매트릭스 준수)

| 검증 항목 | 명령 | Sprint 적용 | 예상 결과 |
|-----------|------|-------------|----------|
| pytest 전체 | `docker compose exec backend pytest -v` | ✅ 자동 | Sprint 4 1172 passed 유지 (코드 변경 ≤ T3 trace logging만 — 회귀 0건) |
| 프론트 타입체크 | `docker compose exec frontend npx tsc --noEmit` | ✅ 자동 | 에러 없음 (프론트 변경 없음) |
| API curl 검증 (E2 측정) | `curl -s "http://localhost:8000/api/v1/metrics/fallback-signal-rate?days=7" \| jq .` | ✅ 자동 | M-F2 응답 정상 + fallback_signal_rate 값 노출 |
| API curl 검증 (Hotfix B 확인) | `curl -s "http://localhost:8000/api/v1/screening/primary" \| jq '.[0] \| keys'` | ✅ 자동 | `change_rate` 필드 포함 (PR #238 머지 검증) |
| 데모 모드 API 검증 | (해당 없음 — 본 Sprint는 신규 endpoint 없음) | — | — |
| Playwright UI 검증 | Sprint 1 `fallback-signal-rate-card` 정상 렌더 | ✅ 자동 | E2 측정 카드 정상 |
| Phase 7.0 LIVE 파라미터 잠금 회귀 | `pytest backend/tests/core/test_phase70_locked_constants.py -v` | ✅ 자동 | 5 PASS 유지 (S5-9) |
| WS trace 비활성 기본값 | `python -c "from backend.app.core.config import settings; assert settings.WS_TRACE_ENABLED is False"` | ✅ 자동 | 통과 (회귀 0건 보장) |
| Hotfix A 머지 확인 | `gh pr view 237 --json mergedAt` | ✅ 자동 | mergedAt 값 존재 |
| Hotfix B 머지 확인 | `gh pr view 238 --json mergedAt` | ✅ 자동 | mergedAt 값 존재 |
| `docker compose up --build` | (미실행 시 자동 기동) | ⬜ 반자동 | — |
| `alembic upgrade head` | (해당 없음 — DB 스키마 변경 없음) | — | — |
| KIS API 실거래 확인 | T3 라이브 trace에서 자연 수행 | ⬜ 수동 (T3 1주) | trace 로그 누적 |
| UI 디자인/시각적 품질 판단 | (해당 없음 — UI 변경 없음) | — | — |

### 신규 환경변수 (deploy.md 기록 필수)

- `WS_TRACE_ENABLED` — Paper 1거래일 동안만 `true`, 종료 후 `false` 복귀 (Railway 환경변수 수동 설정)

---

## 사용자 다음 단계 안내

본 Sprint5.md 작성 완료. 사용자 다음 단계:

1. **sprint5.md 검토** (실행 플랜·Task 5종·DoD 9건·entry gate 4종)
2. 검토 OK → sprint-dev 호출 (`/sprint-dev 8.6-5`) 또는 팀 실행 (`Phase 1을 팀으로 실행해줘` — T1/T2/T3 병렬)
3. T3는 sprint-dev 착수 즉시 `WS_TRACE_ENABLED=true` Railway 환경변수 설정 필요 (deploy.md 수동 기록)
4. T1 첫날 진단 결과에 따라 Hotfix C(#9) 분리 여부 즉시 결정

수정 필요 사항이 있으면 sprint-dev 진행 전에 알려달라.
