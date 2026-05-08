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
- dry_run → LIVE: `VOLUME_SURGE_DRY_RUN=false`는 **G-Bt1~3 통과 전 절대 금지**

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
