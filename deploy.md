# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 핫픽스 배포 - risk-counter-reset (2026-04-21)

포함: `reset_daily_counters()` 자동 호출 누락 버그 수정 + 관리자 수동 리셋 API 추가
PR: https://github.com/frogy95/stockbot/pull/153 (hotfix/risk-counter-reset → main)

#### 자동 검증 결과

- ✅ Railway 헬스체크: `{"status":"healthy","database":"connected","redis":"connected"}` 확인
- ✅ 신규 엔드포인트 등록 확인: `POST /api/v1/trading/risk/reset` → HTTP 401 (인증 필요, 정상)
- ✅ pytest 회귀: `test_risk_daily_capital + test_scheduler_vol5m` 10 passed

#### 배포 후 필수 수동 조치

- ⬜ **즉시 필요**: `POST /api/v1/trading/risk/reset` JWT 인증으로 1회 호출 — 현재 연속 손절 카운터 3/쿨다운/비상정지 플래그 초기화
- ✅ 2026-04-22 09:00 장 시작 시 `일일 리스크 카운터 초기화 완료` 로그 자동 출력 확인 — Railway 로그 `2026-04-22 00:00:00 UTC [modules.trading.risk_manager] 당일 시작 잔고 캐시` 정시 발화
- ⬜ 리셋 후 장중 `momentum_breakout` 신호 생성 시 텔레그램 승인 요청 수신 확인

#### Phase 8 Sprint 1 잔여 관찰 항목 (A안 기준)

**Sprint 2 착수 필수 조건 (①②③)**

- ✅ ① Redis `realtime:{code}:execution` JSON OHLC 3필드 존재 — 2026-04-22 09:09 KST Railway SSH 직접 조회, 19개 키 중 샘플 10개 모두 open_price/high/low 정상 값 (missing 0건)
- ✅ ② 파싱 경고 비율 < 1% — 2026-04-22 09:05 KST 판정. Railway 로그 5000라인 스캔에서 `kis_realtime` 파싱 실패 WARN 0건
- ✅ ③ snapshot open_price 실값 사용 — ④⑤ 신호(036830, gap 3.93%)가 갭 3%+ 분기를 통과했으므로 동일 경로로 실값 사용 확인됨

**Sprint 2 내부 통합 검증으로 이관 (④⑤)**

- ✅ ④ `momentum_breakout` 신호 — 2026-04-21 10:00 036830 1건 관측 (gap_rate=0.0393, breakout_pct=8.83%)
- ✅ ⑤ 갭 3%+ 분기 `breakout_ref=open_price` — 동일 신호 reason에서 확인
- ⬜ 샘플 5종목 실시간 OHLC를 KIS 공식 시세와 대조 (김단타 권고, 참고 검증)
- ⬜ `docker compose up --build` 로컬 스테이징 검증

---

### Phase 8 Sprint 2 — 다층 진입 + 리스크 안전장치 + 2026-04-21 버그 수정

포함: momentum_breakout 3단계 tier (gap_open/prev_close/prev_high) · 13:00 가드 · confidence 상한 · prev_close 반 포지션 · 일일 거래 한도 10건/일 (+env override) · engine 차단 6지점 구조화 로그 · 프론트 리스크 리셋 버튼 · WS 동시호가 가드 · 재연결/일일 리포트 dedup + OHLC 파싱 회귀 픽스처

PR: (sprint-close에서 생성)

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
