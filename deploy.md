# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Phase 8.6 Sprint 4 — Walk-forward 백테스트 + 임계 재조정 진단

**브랜치**: `phase8.6-sprint4` → develop (PR 번호: sprint-close 완료 후 기록)
**완료 날짜**: 2026-05-08

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

**Railway 환경변수 5종 추가 필요 (수동 설정):**
- `BACKTEST_ENABLED=True`
- `LIVE_GATE_AUTO_EVAL_ENABLED=True`
- `BACKTEST_REBUILD_REQUIRED=False`
- `BACKTEST_ADMIN_USER_ID=1`
- `BACKTEST_DEFAULT_N_DAYS=60`

**수동 검증 항목:**
- ⬜ `docker compose up --build` (scipy 의존성 반영 확인)
- ⬜ `alembic upgrade head` 적용 (backtest_runs, backtest_signal_metrics, live_gate_status 3테이블)
- ⬜ admin 백테스트 페이지 렌더 확인 (`/admin/backtest` 4종 카드)
- ⬜ 진단 리포트 기반 임계 재조정 hotfix 계획 수립 (`threshold_recalibration_candidates.md` 참조)

---

### Phase 8.6 Sprint 3 v2.9.0 — Paper 1거래일 관찰 (2026-05-09 장마감 후)

**배포 완료**: 2026-05-08 KST 13:01 (PR #201 머지) — 검증 기록은 `docs/deploy-history/2026-05-08.md`로 아카이빙됨.

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
  ✅ Sprint 3 미포함이었던 `record_block` 적재 코드는 hotfix `time-filter-block-counter` (PR #204, 2026-05-08)로 추가 완료 — 정상 적재 기대
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
