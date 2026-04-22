# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Phase 8 Sprint 2 — 다층 진입 + 리스크 안전장치 + 2026-04-21 버그 수정

포함: momentum_breakout 3단계 tier (gap_open/prev_close/prev_high) · 13:00 가드 · confidence 상한 · prev_close 반 포지션 · 일일 거래 한도 10건/일 (+env override) · engine 차단 6지점 구조화 로그 · 프론트 리스크 리셋 버튼 · WS 동시호가 가드 · 재연결/일일 리포트 dedup + OHLC 파싱 회귀 픽스처

PR: (sprint-close에서 생성)

#### sprint-review 대기 항목

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (curl/httpx/Playwright — sprint-review 에이전트로 실행 필요)

#### 자동 검증 결과 (sprint-dev 내부 실증)

- ✅ pytest 전체: **895 passed**, 1 pre-existing fail (`test_ws_manager_env_max_subscriptions`, Sprint 1 이월)
- ✅ momentum_breakout: 29 passed (기존 21 + 신규 tier 8)
- ✅ risk_manager: 19 passed (기존 10 + 신규 daily_trade_limit 9)
- ✅ scheduler: 24 passed (기존 16 + 신규 동시호가/재연결/일일 리포트 8)
- ✅ engine (auto_mode + trading_engine): 27 passed
- ✅ kis_realtime (OHLC 파싱): 44 passed
- ✅ 프론트 `tsc --noEmit` 에러 없음

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
