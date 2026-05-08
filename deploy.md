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

**남은 사용자 직접 검증 항목 (UI/실행):**
- ⬜ admin 로그인 후 `/admin/backtest` 4종 카드 시각 렌더 확인 (Walk-forward 실행 / 최근 실행 결과 / KS 시계열+LIVE 게이트 / 60일 백필)
- ⬜ 실제 백테스트 1회 실행 → 결과 카드 렌더 확인 (run_id 응답 ↔ GET /runs/{id} 일치 확인 — S4-M1 검증)
- ⬜ UI 디자인/시각적 품질 판단
- ⬜ 진단 리포트 기반 임계 재조정 hotfix 계획 수립 (`threshold_recalibration_candidates.md` 참조)
- ⬜ Notion 업데이트 (§8.5 트리거 — 릴리즈 노트 v2.10.0, 데이터 모델 3테이블, API 명세 6종, 기능 명세 Walk-forward + 통계 검증 + LIVE 토글 게이트)

---

### Phase 8.6 Sprint 3 v2.9.0 — Paper 1거래일 관찰 (2026-05-09 장마감 후)

**배포 완료**: 2026-05-08 KST 13:01 (PR #201 머지)

**Paper 1거래일 관찰 항목** (2026-05-09 장마감 후 16:30 KST):

- ⬜ `volume_surge` dry_run 신호 1건 이상:
  ```sql
  SELECT COUNT(*) FROM trade_signals WHERE strategy_name='volume_surge' AND dry_run=true AND created_at::date = current_date;
  ```
- ⬜ 호가창 Redis 키 적재 (≥10종):
  ```bash
  railway ssh --service stockbot "redis-cli SCAN 0 MATCH 'realtime:*:orderbook' COUNT 50"
  ```
- ⬜ 5분봉 vol5m 적재 (≥10종):
  ```bash
  railway ssh --service stockbot "redis-cli SCAN 0 MATCH 'vol5m:*:$(date +%Y%m%d):*' COUNT 100"
  ```
- ⬜ 시간 필터 차단 카운터 (≥1):
  ```bash
  railway ssh --service stockbot "redis-cli GET 'metrics:time_filter:morning_lockout:$(date +%Y-%m-%d)'"
  ```
- ⬜ R3 자동 롤백 미발동:
  ```bash
  railway ssh --service stockbot "redis-cli GET 'auto_rollback:active'"
  ```
- ⬜ portal_supplement / metrics_rollup 잡 키 16:10 시점 적재:
  ```bash
  railway ssh --service stockbot "redis-cli GET 'scheduler:last_portal_supplement' && redis-cli GET 'scheduler:last_metrics_rollup'"
  ```

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
