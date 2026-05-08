# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### 프로덕션 배포 - v2.10.0 (2026-05-08)

포함 스프린트: Phase 8.6 Sprint 4
PR: #209 (develop → main, 머지 커밋 0a3b5948)
머지 시각: 2026-05-08 21:57 KST

**주요 변경**:
- Walk-forward 백테스트 엔진 (60일 일봉, 박스권/추세장 분류)
- KS 검정 + 카이제곱 + Bootstrap CI 통계 검증
- LIVE 토글 게이트 G-Bt1/G-Bt2/G-Bt3 자동 평가 잡
- `/admin/backtest` 페이지 + backtest API 6종 (admin 가드)
- S4-M1 run_id 일치 수정 + S4-M2 G-Bt1 underspecified 보수적 차단 반영
- pytest: **1174 PASS**

**DB 마이그레이션 (Railway Start Command에 alembic upgrade head 포함 — 배포 시 자동 실행)**:
- `backtest_runs` 테이블 신규
- `backtest_signal_metrics` 테이블 신규
- `live_gate_statuses` 테이블 신규

**Railway 환경변수 5종 추가 필요 (수동 설정)**:
- `BACKTEST_ENABLED=True`
- `LIVE_GATE_AUTO_EVAL_ENABLED=True`
- `BACKTEST_REBUILD_REQUIRED=False`
- `BACKTEST_ADMIN_USER_ID=1`
- `BACKTEST_DEFAULT_N_DAYS=60`

자동 검증 결과 (2026-05-08 21:57 KST):
- ✅ Railway 백엔드 헬스체크: `{"status":"healthy","database":"connected","redis":"connected"}`
- ✅ Vercel 프론트엔드 접속: 307 (도메인 redirect, 정상)
- ✅ Vercel `/admin/backtest` 접속: 307 (auth redirect, 정상)
- ✅ Backend Swagger `/docs`: 200
- ✅ Alembic 마이그레이션 자동 실행 확인 (Railway 로그):
  - `Running upgrade f3b1c4d5e201 -> d5d5cc2b391e, add backtest tables for phase8.6 sprint4`
  - 3테이블 신규: `backtest_runs`, `backtest_signal_metrics`, `live_gate_statuses`
- ✅ Backtest API 6종 라우팅 등록 확인 (openapi.json):
  - `/api/v1/backtest/run`, `/runs`, `/runs/{run_id}`, `/distribution-check`, `/live-gate-status`, `/backfill-daily`
- ✅ Backtest API 인증 가드: `GET /api/v1/backtest/live-gate-status` 401 (admin 가드 정상)

수동 검증 필요 항목:
1. ⬜ Railway 환경변수 5종 추가 설정 (`BACKTEST_ENABLED`, `LIVE_GATE_AUTO_EVAL_ENABLED`, `BACKTEST_REBUILD_REQUIRED`, `BACKTEST_ADMIN_USER_ID`, `BACKTEST_DEFAULT_N_DAYS`)
2. ⬜ admin 로그인 후 `/admin/backtest` 페이지 4종 카드 렌더링 확인
3. ⬜ G-Bt1/G-Bt2/G-Bt3 게이트 평가 잡 스케줄 등록 확인 (Railway 스케줄러)
4. ⬜ 실제 백테스트 1회 실행 → 결과 카드 렌더 확인
5. ⬜ UI 디자인/시각적 품질 판단

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
