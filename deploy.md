# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### 프로덕션 배포 - v2.6.0 (2026-04-23)

포함 스프린트: Phase 8.5 Sprint 2 — 풀 하한 폴백 + 동적 MIN_VOLUME_FLOOR
PR: https://github.com/frogy95/stockbot/pull/171 (develop → main)

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

---

### Phase 8.5 Sprint 2 — 풀 하한 폴백 + 동적 MIN_VOLUME_FLOOR (2026-04-23)

브랜치: `phase8.5-sprint2` → develop
PR: (생성 예정)

#### 로컬 자동 검증 결과

- ✅ pytest 전체: 956 passed, 1 failed (기존 플레이크 `test_ws_manager_env_max_subscriptions` — Sprint 2 무관, git stash 후 동일 실패 확인)
- ✅ `/api/v1/metrics/fallback-stats` — 200 + `{"date":"2026-04-23","triggered_count":0,"codes":[]}`
- ✅ `/api/v1/metrics/top-rejects?limit=10` — 422 (limit 상한 5 강제)
- ✅ `/api/v1/metrics/top-rejects?limit=5` — 200
- ✅ `/api/v1/metrics/shadow-heatmap` — 200
- ✅ `/api/v1/metrics/stage-heatmap` — 200
- ✅ `npx tsc --noEmit` — 에러 없음

#### sprint-review 결과 (2026-04-23)

**코드 리뷰**: 이슈 없음 — Critical/High 0건, Medium 1건 (M3: import bisect 인라인 배치, 동작 무관)

**자동 검증 (Docker 로컬)**:
- ✅ pytest 전체: 956 passed / 1 failed (기존 플레이크 `test_ws_manager_env_max_subscriptions`, Sprint 2 무관)
  - Sprint 2 관련 90개 테스트 전부 통과 (`test_engine_fallback`, `test_momentum_breakout`, `test_realtime_screener`, `test_scheduler`)
- ✅ `/api/v1/metrics/fallback-stats` — 200 OK (`{"date":"2026-04-23","triggered_count":0,"codes":[]}`)
- ✅ `/api/v1/metrics/top-rejects?limit=5` — 200 OK (5건 반환)
- ✅ `/api/v1/metrics/top-rejects?limit=10` — 422 (limit 상한 5 강제 확인)
- ✅ `/api/v1/metrics/shadow-heatmap` — 200 OK
- ✅ `/api/v1/metrics/stage-heatmap` — 200 OK
- ✅ Playwright — /diagnostics 폴백 통계 카드, shadow heatmap, 탈락 상위 종목 리스트 정상 렌더링
- ✅ Playwright — /screening 2차 스크리닝 탭 정상 렌더링 (is_fallback 배지 미발동 상태 확인)
- ✅ `npx tsc --noEmit` — 에러 없음 (sprint-close 단계에서 확인)

**Phase 문서 반영**: ✅ phase8.5.md — Sprint 2 완료 표시, M1/M2 해결 표시, M3 신규 추가

#### 수동 검증 필요 항목 (Railway 프로덕션 배포 후)

- ⬜ Railway 환경변수 8종 추가 확인:
  - `MIN_VOLUME_FLOOR_MODE=dynamic`
  - `MIN_VOLUME_FLOOR_HARD=0.3`
  - `SECONDARY_POOL_FALLBACK_ENABLED=True`
  - `SECONDARY_POOL_FALLBACK_THRESHOLD=3`
  - `SECONDARY_POOL_MAX=5`
  - `FALLBACK_DROP_EXCLUDE_PCT=-3.0`
  - `FALLBACK_POSITION_SIZE_RATIO=0.5`
  - `FALLBACK_STOP_LOSS_PCT=-1.5`
- ⬜ 배포 후 5거래일 관찰: 폴백 발동 여부 (`/diagnostics` 폴백 통계 카드), 폴백 종목 신호 승률/손실률
- ⬜ 16:10 자동 롤백 job 실제 동작 확인 (2거래일 연속 신호 0건 조건, 수 거래일 관찰 필요)
- ⬜ DB 마이그레이션 불필요 (Redis 전용, 스키마 변경 없음)

---

### Phase 8.5 Sprint 2.5 — Railway 환경변수 동기화
- ⬜ `SETTINGS_OVERRIDE_ENABLED=True` Railway 반영 확인
- ⬜ Sprint 2 env 8종(`MIN_VOLUME_FLOOR_MODE` 외) Railway에 존재 확인 (Sprint 2 배포 시 반영되었어야 함 — 재확인 목적)
- ⬜ `python scripts/check_env_sync.py` 로컬 실행 결과 exit 0

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
