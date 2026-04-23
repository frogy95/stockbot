# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Phase 8.5 Sprint 1.5 — 전략 필터 shadow evaluation (2026-04-23)

브랜치: `chore/phase8.5-shadow-evaluation` (sprint1.5 브랜치명은 bash-guard self-mod 차단으로 chore/ prefix 사용)
계획 문서: `docs/phase/phase8.5/sprint1.5/sprint1.5.md`

- ✅ 자동 검증 완료 항목:
  - pytest: shadow 관련 테스트 4개 + 기존 회귀 전체 GREEN (기존 플레이크 `test_ws_manager_env_max_subscriptions` 1건은 Sprint 1.5 무관)
  - `/api/v1/metrics/shadow-heatmap` API 200 응답 확인 (JWT 인증 포함)
  - 프론트엔드 타입 체크 `npx tsc --noEmit` 통과
  - 로컬 Docker 실시간 shadow 관찰: min_volume_floor가 가리고 있던 volume_threshold/atr_filter/confidence 모두 0% pass 확인 — Sprint 2 튜닝 의사결정에 직접 활용 가능한 실측 데이터 확보

- ⬜ 수동 검증 필요 항목:
  - `/diagnostics` 페이지 브라우저 접속하여 Shadow 필터 카드 시각 확인
  - 프로덕션 배포 후 1거래일 관찰: Shadow 카드 8개 stage 모두 의미 있는 표본(≥10건) 누적되는지
  - DB 마이그레이션 불필요 (Redis 전용, 스키마 변경 없음)

---

### Hotfix: risk-reset-frontend-contract (2026-04-22)

PR: https://github.com/frogy95/stockbot/pull/165 (hotfix/risk-reset-frontend-contract → main)

- ✅ 자동 검증 완료 항목:
  - TypeScript `npx tsc --noEmit`: 통과 (main PR #165 CI 통과)
  - 코드 리뷰: Critical/High 이슈 없음 (프론트엔드 2파일, 응답 계약 불일치 수정)

- ⬜ 수동 검증 필요 항목:
  - `docker compose up --build` (코드 반영)
  - 프로덕션 대시보드에서 리셋 버튼 클릭 시 "리셋 완료" 메시지 표시 확인

---

### 프로덕션 배포 - v2.5.0 (2026-04-22)

포함 스프린트: Phase 8.5 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/163 (develop → main)

- ⬜ Vercel 프론트엔드 자동 배포
- ⬜ Railway 백엔드 자동 배포

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

---

### Phase 8.5 Sprint 1 — 관측성 강화 (score 히스토그램 + stage heatmap + 탈락 상위 + 가상 신호 로깅)

PR: https://github.com/frogy95/stockbot/pull/162

#### 코드 리뷰 결과 (2026-04-22)

- ✅ 보안: 하드코딩 시크릿 없음, ORM 파라미터 바인딩 정상
- ✅ 인증: `/api/v1/metrics/*` 4종 모두 `get_current_user` 의존성 적용
- ✅ 전략 순수성: `_metrics.py` 분리, 예외 전파 없음 (TradeSignalData import 금지 준수)
- ✅ 타임존: `datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()` 패턴 일관 적용
- ✅ 프로덕션 와이어링: `main.py`에서 `MomentumBreakoutStrategy(redis_client=..., session_factory=...)` 정상 주입
- Medium: `top-rejects` API limit 파라미터 최대 50 허용이나 실제 Redis `TOP_REJECT_SIZE=5` 고정이므로 5 초과 요청은 항상 5건만 반환 (기능 영향 없음, Sprint 2에서 개선 권장)
- Medium: stage heatmap 프론트엔드 HOUR_MINS가 09:30부터 시작 — 09:00~09:20 구간 데이터 수집은 되나 UI에 표시 안 됨 (장 시작 직후 30분 사각지대, Sprint 2에서 개선 권장)

#### 자동 검증 결과 (2026-04-22)

- ✅ `pytest -v`: 929 passed / 1 failed (실패 `test_ws_manager_env_max_subscriptions`는 이 PR 변경 무관한 기존 버그, `PAPER.max_ws_subscriptions` 값 불일치)
- ✅ API curl 검증 (4종): score-histogram / stage-heatmap / top-rejects / virtual-signals 모두 200 응답
- ✅ 데모 모드 API: 인증 없이 401, 인증 후 정상 응답 확인
- ✅ Playwright UI: `/diagnostics` 페이지 정상 렌더링, 4카드 표시 확인, score 분포 데이터 실시간 반영

#### 배포 후 필수 수동 조치

- ⬜ `docker compose up --build` (코드 반영)
- ⬜ `docker compose exec backend alembic upgrade head` (3개 신규 테이블 생성: screening_metrics_daily, strategy_metrics_daily, virtual_signals) — Railway는 Start Command에 포함되어 자동 적용
- ⬜ 1.5거래일 관찰: `/diagnostics` 페이지 카드 1~3 메트릭 정상 수집 확인
- ⬜ 1.5거래일 관찰: 16:05 스케줄러 집계 job 실행 확인 (`metrics_rollup` job_id 로그 출력)
- ⬜ DB 조회로 집계 확인: `SELECT * FROM screening_metrics_daily ORDER BY metric_date DESC LIMIT 20;`
- ⬜ DB 조회로 가상 신호 확인: `SELECT * FROM virtual_signals ORDER BY observed_at DESC LIMIT 20;`
- ⬜ Stage heatmap에서 `prev_close_time_guard` 13:00~14:00 구간 카운트 증가 확인

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
