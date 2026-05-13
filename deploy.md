# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### 프로덕션 배포 v2.10.0 — Phase 8.6 Sprint 4 (2026-05-08)

**PR**: #209 (develop → main, 머지 커밋 `0a3b594`, 21:57 KST)
**태그**: `v2.10.0`
**S4-M1/M2 sprint-pr-fix 반영**: PR #208 (run_id API↔DB 일치 + G-Bt1 underspecified 보수적 차단)

**프로덕션 자동 검증 결과 (2026-05-08 22:00~ KST):**
- ✅ Backend 헬스체크: `{"status":"healthy","database":"connected","redis":"connected"}`
- ✅ Alembic 자동 마이그레이션: `f3b1c4d5e201 → d5d5cc2b391e` (3테이블 신규: `backtest_runs`, `backtest_signal_metrics`, `live_gate_statuses`)
- ✅ Backtest API 6종 라우팅 등록 (openapi.json 확인): `/run`, `/runs`, `/runs/{run_id}`, `/distribution-check`, `/live-gate-status`, `/backfill-daily`
- ✅ Admin 가드 정상 동작: 6종 모두 401 Unauthorized (no auth)
- ✅ APScheduler 잡 등록: `weekly_backtest_gate` — 매주 월요일 00:00 KST (`run_weekly_backtest_and_gate_assess`)
- ✅ Vercel 프론트엔드 접속: 307 (도메인 redirect 정상), `/admin/backtest` 307 (auth redirect 정상)
- ✅ Backend Swagger `/docs`: 200
- ✅ Railway 백엔드 로그: 신규 ERROR/Traceback 없음
- ✅ pytest 회귀 (sprint-review 단계): 1174 passed, 0 failed

**Railway 환경변수 추가 필요 (사용자 직접 설정 — 자동 거부됨):**

실제 backend/core/config.py:115-123 정의 기준 — `BACKTEST_ENABLED`, `LIVE_GATE_AUTO_EVAL_ENABLED`, `BACKTEST_DEFAULT_N_DAYS`는 디폴트(true/true/60)로 동작하므로 **실설정이 필요한 건 `BACKTEST_ADMIN_USERNAME` 1개**.

```bash
railway variables --service stockbot --set "BACKTEST_ADMIN_USERNAME=admin"
```

- 디폴트가 `None`이면 인증된 모든 사용자도 차단됨 (임시 lockdown).
- JWT subject가 `"admin"`으로 하드코딩되어 있으므로 (auth.py:34), 값은 `admin` 고정.
- 이전 배포 가이드의 `BACKTEST_ADMIN_USER_ID`/`BACKTEST_REBUILD_REQUIRED`는 코드에 존재하지 않음 (deploy-prod agent 환각).
- **2026-05-11 추가 확인**: `BACKTEST_ADMIN_USERNAME`만 필수, 나머지 4종은 코드 default(`BACKTEST_DEFAULT_N_DAYS=60`) 또는 이미 설정됨.

**남은 사용자 직접 검증 항목 (UI/실행):**
- ⬜ admin 로그인 후 `/admin/backtest` 4종 카드 시각 렌더 확인 (Walk-forward 실행 / 최근 실행 결과 / KS 시계열+LIVE 게이트 / 60일 백필)
- ⬜ 실제 백테스트 1회 실행 → 결과 카드 렌더 확인 (run_id 응답 ↔ GET /runs/{id} 일치 확인 — S4-M1 검증)
- ⬜ UI 디자인/시각적 품질 판단
- ✅ 진단 리포트 기반 임계 재조정 hotfix 계획 수립 — `threshold_recalibration_hotfix_plan.md` (2026-05-11, 3단계: 진단→백필→재조정)
- ⬜ Notion 업데이트 (§8.5 트리거 — 릴리즈 노트 v2.10.0, 데이터 모델 3테이블, API 명세 6종, 기능 명세 Walk-forward + 통계 검증 + LIVE 토글 게이트)

---

### Phase 8.6 Sprint 3 v2.9.0 — Paper 1거래일 관찰 (2026-05-09 장마감 후)

**배포 완료**: 2026-05-08 KST 13:01 (PR #201 머지)

**Paper 1거래일 관찰 결과** (2026-05-11 12:00 KST 수집 — API 기반):

| # | 항목 | 게이트 기준 | 측정값 | 결과 |
|---|------|-----------|--------|------|
| 1 | volume_surge dry_run 신호 (05-08, 05-11) | ≥1 | 0 / 0 | ❌ NO-GO |
| 2 | 호가창 Redis 키 (realtime:*:orderbook) | ≥10종 | **18** | ✅ |
| 3 | 5분봉 vol5m 적재 | ≥10종 | **1000** | ✅ |
| 4 | 시간 필터 차단 카운터 (morning/afternoon/gap) | ≥1 | 0 / 0 / 0 | ❌ NO-GO |
| 5 | **R3 자동 롤백 미발동** | is_active=false | **is_active=true** (2026-05-08 16:10 KST 발동, 사유: `auto_rollback_2d_zero_signals`) | 🚨 **이미 발동** |
| 6 | scheduler.last_metrics_rollup | 16:10 적재 | 2026-05-10 16:05 KST | ✅ |
| 6 | scheduler.last_portal_supplement | 16:10 적재 | `null` | ⚠️ 미적재 (별도 조사) |

**측정 출처**: `GET /api/v1/health/observation-daily`, `GET /api/v1/metrics/volume-surge-stats`, `GET /api/v1/metrics/time-filter-stats`, **`GET /api/v1/health/sprint3-keys` (hotfix PR #219)**

**판정**: **NO-GO** — Paper 관찰 게이트 미통과 + R3 자동 롤백 이미 발동.
**핵심 발견**: 데이터 파이프라인(orderbook 18 / vol5m 1000)은 **정상**. 문제는 signal 생성 경로(volume_surge 0 / time_filter 차단 0)에 국한 — 임계값/스크리닝 이슈 가설 강화.
**부수 영향**: R3 롤백이 `MIN_VOLUME_FLOOR_MODE=legacy` + `SECONDARY_POOL_FALLBACK_ENABLED=False`를 강제하여 Sprint 1~3 신규 로직이 차폐된 상태.

**다음 액션** (`docs/phase/phase8.6/sprint4/threshold_recalibration_hotfix_plan.md` 3단계):
- ✅ 단계 A 진단 hotfix 배포 완료 (`hotfix/zero-signal-diagnosis-api`, PR #219, 2026-05-11)
- ⏳ 단계 B 백필 트리거됨 (2026-05-11, `POST /backtest/backfill-daily` start=2026-02-10 end=2026-05-11)
- ⬜ 단계 C grid search + 임계 재조정 hotfix (단계 B 완료 후)

**Kill-switch 런북** (긴급 시):
- volume_surge 폭증: `railway variables --service stockbot --set "VOLUME_SURGE_ENABLED=false"`
- 시간 필터 오작동: `railway variables --service stockbot --set "TIME_FILTER_ENABLED=false"`
- 우선순위 큐: `railway variables --service stockbot --set "SIGNAL_PRIORITY_QUEUE_ENABLED=false"`
- ⚠️ dry_run → LIVE: `VOLUME_SURGE_DRY_RUN=false`는 **Sprint 4 G-Bt1~3 통과 전 절대 금지**

---

### Notion 업데이트 권고 (사용자 수동)

Sprint 3에서 다음이 변경됨 — dev-process.md §8.5 트리거 해당:
- **DB 스키마**: `trade_signals.dry_run BOOLEAN` 컬럼 추가 (Alembic `f3b1c4d5e201`)
- **API 명세**: `/api/v1/metrics/volume-surge-stats`, `/api/v1/metrics/time-filter-stats` 신규
- **기능 명세**: volume_surge tier (4번째 진입 tier, dry_run 기본), 시간 필터 본 가드, 신호 우선순위 큐, R3 자동 롤백 활성화, 시간 필터 차단 카운터 적재 (hotfix `time-filter-block-counter`)
- **릴리즈 노트**: v2.9.0 — Phase 8.6 Sprint 3 (2026-05-08 배포)

---

---

### Hotfix: phase86-atr-volume-floor-relax (2026-05-13)

브랜치: `hotfix/phase86-atr-volume-floor-relax`
**배경**: 2026-05-13 장중 1차/2차 모니터링 결과 — PARALLEL OFF 정적 모드에서 `atr_filter` + `min_volume_floor`가 단일 압도 stage(min_volume_floor 72.4%)로 부상. 12:00 KST 시점 누적 reject 87건 중 min_volume_floor 63건, atr_filter 20건. 종목 009150(LG)이 거래량 825k/필요 869k(94.9%)에서 floor_ratio=0.4로 연속 reject, 322000(휴젤)이 atr_ratio=0.07로 atr_filter 정적 0.05 회귀 차단.

**수정 내용**:
- `momentum_breakout.py:33` `ATR_FILTER_PCT` 0.05 → 0.07 (정적 모드 ATR ceil 완화, ATR_CEIL_HARD=0.08 안쪽)
- Railway 환경변수 추가 필요: **`MIN_VOLUME_FLOOR_HARD=0.25`** (코드 default 0.3 → 0.25 완화, dynamic 슬라이딩 하한 동조 인하)

**변경 파일 (1개)**:
- `backend/modules/trading/strategies/momentum_breakout.py` (+3 -1)

**Railway 환경변수 추가 확인: MIN_VOLUME_FLOOR_HARD=0.25** (수동 설정 필요)

```bash
railway variables --service stockbot --set "MIN_VOLUME_FLOOR_HARD=0.25"
```

**검증 계획**: 14:30 KST 3차 모니터링에서 min_volume_floor 점유율 ≤ 50% + atr_filter 점유율 감소 + signals.total ≥ 1 확인.

---

### Hotfix: phase86-g2g3-self-clear (2026-05-12)

브랜치: `hotfix/phase86-g2g3-self-clear`
**배경**: R3 unset hotfix(#226) 배포 후 신호 0건 진단 심화 결과, signal_generator.py:105 `G3 circuit_breaker.allow_signal()`이 모든 신규 진입 신호를 차단하는 HARD GATE임을 발견. `phase86:circuit_breaker:active=true` 활성 상태에서는 momentum_breakout이 통과해도 DB 저장 전 차단. G2(`phase86:rollback:active`)는 observability flag(consumer 없음) 이나 G2/G3 evaluator 모두 unset 분기 부재로 TTL 24h 만료까지 자동 해제 불가. 매일 16:10 KST 재평가 시 동일 조건이면 재SET되어 영구 차단.

**수정 내용**:
- `auto_rollback.py:execute_rollback` — `should_rollback=False` && 기존 활성 시 `phase86:rollback:active` DEL + 해제 알림
- `circuit_breaker.py:execute` — `should_trigger=False` && 기존 활성 시 `phase86:circuit_breaker:active` + `SECONDARY_POOL_FALLBACK_ENABLED` 둘 다 DEL + 해제 알림
- 회귀 테스트 4종 추가 (G2 self-clear/no-clear, G3 self-clear/no-clear)

**변경 파일 (4개)**:
- `backend/modules/safety/auto_rollback.py` (+22)
- `backend/modules/safety/circuit_breaker.py` (+23)
- `backend/tests/safety/test_auto_rollback.py` (+52)
- `backend/tests/safety/test_circuit_breaker.py` (+22)

- ✅ 자동 검증 완료 항목:
  - pytest `tests/safety/ + tests/test_scheduler.py`: 60 passed, 0 failed (신규 4종 포함)

- ⬜ 수동 검증 필요 항목:
  - Railway 자동 배포 후 헬스체크 healthy 확인
  - `railway ssh` Redis manual DEL: `phase86:circuit_breaker:active` + `phase86:rollback:active` (배포만으로는 기존 active 키 자동 해제 안 됨 — 다음 16:10 KST 평가 시점에 자동 해제됨)
  - 내일(2026-05-13) 09:30 KST `stage-heatmap` 재측정 — `prev_close_volume_confirm`/`gap_open_absorb` 0건 + 신호 ≥1건 발생 확인

---

### Hotfix: auto-rollback-self-clear (2026-05-12)

브랜치: `hotfix/auto-rollback-self-clear`
**배경**: 2026-05-11 dedup hotfix(PR #223)로 신호 1건 회복 후에도 R3 strict mode가 풀리지 않아 2026-05-12 신호 0건 지속. 코드 분석 결과 `_check_auto_rollback`(scheduler.py:1133-1148)은 SET 분기만 있고 unset 분기가 없어 한번 발동되면 7일 TTL 만료 또는 수동 DEL로만 해제됨. 추가로 매일 16:10 KST 재실행 시 0건 유지되면 재SET되는 악순환 위험.

**즉시 조치 (2026-05-12 10:30 KST)**: `railway ssh`로 Redis override 4개 키 manual DEL — `is_active:false` 즉시 확인, fallback 풀 1건 즉시 작동.

**수정 내용**:
- `_check_auto_rollback`에 unset 분기 추가: `today_count>=1 OR prev_count>=1` && 기존 override 존재 시 4개 키 DEL + 해제 알림 발송
- 회귀 테스트 2종 추가:
  - `test_auto_rollback_self_clears_when_signal_recovers` — 활성 상태에서 신호 회복 시 자동 해제 검증
  - `test_auto_rollback_no_clear_when_no_existing_override` — 기존 override 없을 때 불필요 알림 미발생 검증

**변경 파일 (2개)**:
- `backend/modules/collector/scheduler.py` (+24)
- `backend/tests/test_scheduler.py` (+52)

- ✅ 자동 검증 완료 항목:
  - pytest `tests/test_scheduler.py`: 31 passed, 0 failed (신규 2종 포함)
  - manual DEL 즉시 검증: `is_active:false`, `fallback.codes:["095610"]` (폴백 풀 즉시 작동)

- ⬜ 수동 검증 필요 항목:
  - Railway 자동 배포 후 헬스체크 healthy 확인
  - 차후 R3 재발동 시 다음 날 신호 1건 발생하면 16:10 KST `_check_auto_rollback`이 자동 해제하는지 로그 확인

---

### Hotfix: backtest-backfill-rest-client (2026-05-08)

PR: https://github.com/frogy95/stockbot/pull/217 (MERGED — 머지 커밋 9d1e704)

**원인**: `backend/modules/backtest/historical_loader.py:185` `KISRestClient()` 무인자 호출 → required 의존성(env/token_manager/throttler) 누락 → TypeError → 백필 실패
**수정**: `backfill_missing_daily(rest_client=...)` 인자 추가 + `backfill_daily` 라우트에서 `app.state.kis_inquiry` 주입 + 부재 시 503 반환 + 회귀 테스트 2종 추가

**변경 파일 (3개)**:
- `backend/modules/backtest/historical_loader.py` (rest_client 인자 추가, None → ValueError)
- `backend/api/routes/backtest.py` (Request 인자 추가, kis_inquiry 주입, 503 가드)
- `backend/tests/api/test_backtest_routes.py` (회귀 테스트 2종 추가)

- ✅ 자동 검증 완료 항목:
  - pytest `tests/api/test_backtest_routes.py`: 12종 통과 (0 failed)
  - pytest backfill/historical_loader 관련 14종 전체 통과
  - 헬스체크: healthy (database + redis connected)
  - 프로덕션: POST /backfill-daily 202 응답 정상, 백그라운드 백필 작동 확인

- ⬜ 수동 검증 필요 항목:
  - `docker compose up --build` (코드 반영)

---

### Hotfix: backtest-walkforward-session (2026-05-08)

PR: https://github.com/frogy95/stockbot/pull/213 (MERGED — 머지 커밋 ebd1c1a)

**원인**: `backend/api/routes/backtest.py:150` `WalkForwardRunner()` 무인자 호출 → `@dataclass` `session` required positional 누락 → TypeError → BackgroundTask 실패 → DB 미적재 → run_id 404
**수정**: `WalkForwardRunner(session=session)` 1줄 수정 + 회귀 테스트 `test_run_walkforward_instantiates_runner_with_session` 추가

**변경 파일 (2개)**:
- `backend/api/routes/backtest.py` (1줄 수정)
- `backend/tests/api/test_backtest_routes.py` (42줄 추가)

**코드 리뷰 결과 (경량)**:
- Critical/High 이슈: 0건
- 수정 범위 최소 (파일 2개, 코드 43줄) — Hotfix 기준 충족
- 회귀 테스트 stub 패턴 적절 (WalkForwardRunner 시그니처 검증)

- ✅ 자동 검증 완료 항목:
  - pytest 전체: 11종 pytest 통과 (프로덕션 검증 포함)
  - 프로덕션 S4-M1 검증: run_id `3a9aeb51-...` → GET /runs/{id} HTTP 200 정상
  - DB INSERT 정상 동작 확인
  - 타겟 API 검증: POST /backtest/run → run_id 반환 정상

- ⬜ 수동 검증 필요 항목:
  - `docker compose up --build` (코드 반영)
  - 실제 백테스트 결과는 KOSPI200 일봉 데이터 부족(56일/60일)으로 별도 backfill 필요

---

### Hotfix: time-filter-block-counter (2026-05-07)

브랜치: `hotfix/time-filter-block-counter`
커밋: `6d5a502 fix(time-filter): 차단 카운터 Redis incr 적재 (Sprint 3 잔존 부채)`

Sprint 3 v2.9.0 배포 직후 잔존 부채 해소. `should_block_entry` 차단 시 Redis INCR 카운터 적재 코드 미구현 → `record_block` 신규 추가.

- ✅ 자동 검증 완료 항목:
  - pytest (타겟 3파일): 66 passed, 0 failed
  - 타겟 API 검증: N/A (API 인터페이스 변경 없음)
  - Playwright 타겟 검증: N/A (UI 변경 없음)
  - 코드 리뷰: Critical/High 이슈 0건

- ⬜ 수동 검증 필요 항목:
  - `docker compose up --build` (코드 반영) — Railway 자동 배포로 대체 가능
  - 장중 첫 차단 발생 후 `redis-cli GET "metrics:time_filter:morning_lockout:$(date +%Y-%m-%d)"` ≥1 확인

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
