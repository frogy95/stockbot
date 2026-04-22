# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Hotfix: no-data-guard-log-level — 동시호가 가드 로그 DEBUG → INFO 승격 (2026-04-22)

PR: https://github.com/frogy95/stockbot/pull/159

- ✅ 자동 검증 완료 항목:
  - pytest `tests/test_scheduler.py`: **24 passed** (경고 5건은 AsyncMock Sprint 1 이월, 무관)
  - 타겟 API 검증: `/api/v1/health` 200 + `{"status":"healthy","database":"connected","redis":"connected"}`, `/api/v1/screening/status` 200
  - Playwright 타겟 검증: 로그 레벨 변경으로 UI 변경 없음 — 생략
  - 코드 리뷰: Critical/High 이슈 없음 (로그 레벨 1줄 변경)

- ⬜ 수동 검증 필요 항목:
  - `docker compose up --build` (코드 반영)
  - Railway 로그에서 15:10~15:30 구간 `동시호가 구간 — no_data 가드 스킵` INFO 로그 출력 확인 (2거래일 관찰)

---

### Phase 8 Sprint 2 — 다층 진입 + 리스크 안전장치 + 2026-04-21 버그 수정

포함: momentum_breakout 3단계 tier (gap_open/prev_close/prev_high) · 13:00 가드 · confidence 상한 · prev_close 반 포지션 · 일일 거래 한도 10건/일 (+env override) · engine 차단 6지점 구조화 로그 · 프론트 리스크 리셋 버튼 · WS 동시호가 가드 · 재연결/일일 리포트 dedup + OHLC 파싱 회귀 픽스처

PR: https://github.com/frogy95/stockbot/pull/157

#### 코드 리뷰 결과 (sprint-review, 2026-04-22)

- ✅ 코드 리뷰 완료 — Critical/High 이슈 없음, Medium 이슈 2건 수정 완료
  - 이슈 1 (Medium, 수정 완료): `incr_daily_trade_count` TTL 재설정 버그 — 기존 값 있을 때 `set(..., ttl=86400)` 재호출로 마지막 거래 후 24시간으로 한도가 연장되는 버그 → 첫 증가 시에만 TTL 설정으로 수정 (커밋 0256d26)
  - 이슈 2 (Medium, 수정 완료): `DAILY_MAX_TRADE_COUNT_OVERRIDE`를 `os.getenv()` 직접 호출에서 `core/config.py` Settings로 이동 — 12인자 검증 자동화, `int` 파싱 오류 제거 (커밋 0256d26)

#### 자동 검증 결과 (sprint-review, 2026-04-22)

- ✅ pytest 전체: **895 passed**, 2 pre-existing fail
  - `test_kis_api.py::test_kis_status` — Sprint 1 이월 (await 없이 사용)
  - `test_ws_stability.py::test_ws_manager_env_max_subscriptions` — Sprint 1 이월
- ✅ risk_manager 테스트: **19 passed** (이슈 1/2 수정 후 전체 통과)
- ✅ API 스모크: `/api/v1/health` 200, `/api/v1/health/readiness` 503(pipeline unhealthy — 장 외 시간 정상), `/api/v1/screening/status` 200
- ✅ Playwright UI 검증:
  - 대시보드: PAPER 배지 표시, 리스크 상태 카드 + "일일 리스크 카운터 리셋" 버튼 노출 정상
  - 리셋 다이얼로그: 클릭 시 2단계 확인 다이얼로그 표시, 체크박스 체크 전 "리셋 실행" 비활성화, 체크 후 활성화 정상
  - 스크리닝: 1차 스크리닝 목록 30건 정상 표시
  - 매매 신호: 페이지 정상 접속
- ✅ Phase 8 Sprint 2 완료 마킹 (phase8.md Sprint 2 ✅, 미해결 이슈 #5 해결 표시)

#### 배포 후 필수 수동 조치

- ⬜ Railway 환경변수 추가 확인: (Sprint 3 E2E Paper 통과 전까지) `DAILY_MAX_TRADE_COUNT_OVERRIDE=3`
- ⬜ `docker compose exec backend python -m scripts.seed_settings` 또는 배포 자동 시드로 `daily_max_trade_count=10` row 적재 확인
- ⬜ 프론트 대시보드 리스크 상태 카드의 "일일 리스크 카운터 리셋" 버튼 노출 + LIVE/PAPER 배지 정상
- ⬜ 2거래일 관찰: `SELECT reason->>'breakout_tier', COUNT(*) FROM trade_signals GROUP BY 1` 3 tier 모두 출현
- ⬜ 2거래일 관찰: 15:10~15:30 구간 WS 재연결 0회 (백엔드 로그 `동시호가 구간 — no_data 가드 스킵`)
- ⬜ 2거래일 관찰: 재연결 시 텔레그램 `WS 재연결 완료 (구독 N종목, reason=...)` 60초 내 1통
- ⬜ 2거래일 관찰: 15:30 이후 일일 마감 리포트 1건만 수신
- ⬜ 13:00 이후 prev_close tier 거부 로그 존재 (`stage=prev_close_time_guard`)
- ⬜ 상세: `docs/phase/phase8/sprint2/validation-notes.md`

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
