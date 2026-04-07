# Sprint 2: 완전 자동 모드 + 텔레그램 고도화 (Phase 5)

**Goal:** 신호 발생 시 승인 없이 즉시 주문하는 완전 자동 모드를 구현하고, 일일 마감 리포트 자동 발송 + 시스템 경고 알림을 강화한다.

**Architecture:** 기존 TradingEngine.process_screening_results()의 반자동 분기(notifier 존재 시 승인 요청)에 trading_mode 설정 기반 분기를 추가한다. trading_mode=auto일 때 리스크 체크 통과 후 즉시 주문하되, 적응형/기본 후보(is_fallback, is_relaxed)는 자동 매매 금지(반자동 강제). 일일 마감 리포트는 기존 NotifierManager.send_daily_report()를 스케줄러 market_close 잡에 연결한다. 시스템 경고 알림은 기존 텔레그램 send_notification()을 활용하여 파이프라인 실패, 비상 정지 등에 알림을 추가한다.

**Tech Stack:** FastAPI, SQLAlchemy, Redis, APScheduler, python-telegram-bot, Next.js, shadcn/ui

**Sprint 기간:** 2026-04-07 ~ 2026-04-07
**상태:** ✅ 완료 (2026-04-07)
**PR:** https://github.com/frogy95/stockbot/pull/102
**이전 스프린트:** Sprint 1 (709 passed, PR #101)
**브랜치명:** `phase5-sprint2`

---

## 제외 범위

- 성과 분석 대시보드 (Sprint 3)
- 수익률 차트/전략별 비교 (Sprint 3)
- 장세 판별 모듈 (Phase 6 이관 확정)
- 완전 자동 + 적응형/기본 후보 조합 (금지 확정 -- 최리스크 원칙)
- 텔레그램 명령어 추가 (/auto, /semi 등) -- 웹 설정에서만 모드 전환

## 실행 플랜

의존성 그래프:
- Task 1(trading_mode 설정 + seed)은 Task 2~3의 전제
- Task 2(엔진 자동 모드)와 Task 3(텔레그램 고도화)는 파일 겹침 없어 병렬 가능
- Task 4(프론트엔드 모드 전환 UI)는 Task 1의 API만 의존 -- Task 2와 병렬 가능
- Task 5(통합 검증)는 전체 완료 후

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | trading_mode 설정 추가 + 모드 전환 API 확장 | 백엔드 | -- |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | 매매 엔진 자동 모드 분기 + 안전장치 | 백엔드 | `feature-dev:feature-dev` |
| Task 3 | 일일 마감 리포트 스케줄 + 시스템 경고 알림 | 백엔드 | -- |
| Task 4 | 매매 모드 전환 UI (3단계: manual/semi-auto/auto) | 프론트엔드 | `frontend-design` |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | 통합 검증 | 전체 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 백엔드/프론트엔드 팀원이 각 Task를 병렬 구현합니다.

---

### Task 1: trading_mode 설정 추가 + 모드 전환 API 확장

**Files:**
- Modify: `backend/scripts/seed_settings.py` (SEED_DATA에 trading_mode 항목 추가)
- Modify: `backend/api/routes/settings.py` (switch_trading_mode -> switch_mode로 확장, trading_mode 전환 엔드포인트 추가)
- Create: `backend/tests/test_trading_mode.py`

**Step 1: 테스트 작성**
- `backend/tests/test_trading_mode.py` 생성
- 테스트 케이스:
  - trading_mode 기본값이 "semi-auto"인지 확인 (seed_settings 기준)
  - PUT /api/v1/settings/trading-mode로 "auto" 전환 시 비밀번호 재확인 + 장중 차단 동작
  - 활성 포지션 있을 때 auto -> semi-auto 전환은 허용 (반대만 차단하지 않음, auto에서 안전 방향 전환은 허용)
  - trading_mode 값이 "manual", "semi-auto", "auto" 외 값이면 422 반환
  - audit_log에 모드 전환 기록이 남는지 확인
- 검증: `docker compose exec backend pytest tests/test_trading_mode.py -v`
- 예상: FAIL (엔드포인트/시드 미존재)

**Step 2: seed_settings.py에 trading_mode 추가**
- `backend/scripts/seed_settings.py` SEED_DATA 리스트에 항목 추가:
  - key: `trading_mode`, value: `semi-auto`, value_type: `string`, category: `trading`, description: `매매 모드 (manual/semi-auto/auto)`
- 검증: `docker compose exec backend python -c "from scripts.seed_settings import SEED_DATA; assert any(s[0]=='trading_mode' for s in SEED_DATA)"`
- 예상: PASS

**Step 3: 모드 전환 API 엔드포인트 추가**
- `backend/api/routes/settings.py` 수정
- 새 Pydantic 모델 `TradingModeRequest(target_mode: str)` 추가 (허용값: "manual", "semi-auto", "auto")
- `PUT /api/v1/settings/trading-mode` 엔드포인트 추가:
  - 비밀번호 재확인 (password 필드)
  - target_mode 값 검증 ("manual", "semi-auto", "auto" 외 422)
  - 장중(09:00~15:30) 차단 (423)
  - auto로 전환 시 활성 포지션 체크 (409) -- semi-auto/manual로의 전환은 포지션 무관하게 허용
  - AuditLog 기록 (action="trading_mode_switch", target_key="trading_mode")
  - settings 테이블의 trading_mode 값 업데이트
- 검증: `docker compose exec backend pytest tests/test_trading_mode.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/scripts/seed_settings.py backend/api/routes/settings.py backend/tests/test_trading_mode.py
git commit -m "feat(phase5-sprint2): task1 -- trading_mode 설정 추가 + 모드 전환 API"
```

**완료 기준:**
- ✅ pytest 테스트 통과
- ✅ seed_settings에 trading_mode 항목 존재
- ✅ PUT /api/v1/settings/trading-mode 정상 동작

---

### Task 2: 매매 엔진 자동 모드 분기 + 안전장치

**skill:** `feature-dev:feature-dev`

기존 코드 3개+ 파일과 통합 필요: engine.py, risk_manager.py, position_sizer.py, signal_generator.py 간 상호작용 이해 필수.

**Files:**
- Modify: `backend/modules/trading/engine.py` (process_screening_results에 자동 모드 분기 추가)
- Modify: `backend/modules/trading/position_sizer.py` (position_size_ratio 플래그 반영)
- Create: `backend/tests/test_engine_auto_mode.py`

**Step 1: 테스트 작성**
- `backend/tests/test_engine_auto_mode.py` 생성
- 테스트 케이스:
  - trading_mode="auto"일 때 승인 없이 order_manager.submit_order 직접 호출 확인
  - trading_mode="semi-auto"일 때 기존 동작 유지 (notifier.notify_signal 호출)
  - trading_mode="manual"일 때 신호 생성만 하고 주문/승인 요청 모두 안 함
  - 자동 모드에서 is_fallback=True 종목은 반자동 강제 전환 (notifier.notify_signal 호출)
  - 자동 모드에서 is_relaxed=True (적응형 완화) 종목도 반자동 강제 전환
  - 자동 모드에서도 리스크 체크(can_trade) 통과 필수
  - position_size_ratio=0.5 플래그가 있으면 주문 수량 50% 적용
  - 자동 모드 주문 시 텔레그램에 "자동 주문 알림" 발송 확인 (승인 버튼 없이)
- 검증: `docker compose exec backend pytest tests/test_engine_auto_mode.py -v`
- 예상: FAIL

**Step 2: TradingEngine에 자동 모드 분기 구현**
- `backend/modules/trading/engine.py` 수정
- `__init__`에 `session_factory` 파라미터 추가 (settings 테이블에서 trading_mode 조회용)
- 새 메서드 `_get_trading_mode() -> str`:
  - settings 테이블에서 trading_mode 조회 (기본값: "semi-auto")
  - Redis 캐시 활용 (키: "trading:mode", TTL 60초) -- DB 매번 조회 방지
- `process_screening_results` 내 분기 변경:
  - 각 signal에 대해 후보의 플래그(is_fallback, is_relaxed, auto_trade_blocked) 확인
  - `mode == "auto"` AND `auto_trade_blocked != True`:
    - 리스크 체크 통과 후 즉시 submit_order
    - notifier가 있으면 "자동 주문 알림" 발송 (승인 버튼 없음)
  - `mode == "semi-auto"` OR (`mode == "auto"` AND `auto_trade_blocked == True`):
    - 기존 승인 요청 흐름 유지 (notify_signal)
  - `mode == "manual"`:
    - 신호 DB 저장만 (generate_signals까지만 실행, submit/notify 모두 스킵)
- screened_candidates에서 각 후보의 플래그를 signal에 전달하기 위해:
  - process_screening_results에서 candidates dict를 signal과 매핑 (stock_code 기준)

**Step 3: PositionSizer에 ratio 반영**
- `backend/modules/trading/position_sizer.py` 수정
- `calculate()` 메서드에 `size_ratio: float = 1.0` 파라미터 추가
  - 반환 전 `quantity = int(quantity * size_ratio)`, `invest_amount = int(invest_amount * size_ratio)` 적용
  - 기존 호출부는 기본값 1.0으로 영향 없음
- engine.py에서 후보의 position_size_ratio 플래그를 calculate()에 전달

**Step 4: 검증**
- 검증: `docker compose exec backend pytest tests/test_engine_auto_mode.py tests/test_engine_approval.py -v`
- 예상: PASS (신규 + 기존 승인 테스트 모두 통과)

**Step 5: 커밋**
```
git add backend/modules/trading/engine.py backend/modules/trading/position_sizer.py backend/tests/test_engine_auto_mode.py
git commit -m "feat(phase5-sprint2): task2 -- 매매 엔진 자동 모드 분기 + 안전장치"
```

**완료 기준:**
- ✅ auto 모드에서 승인 없이 즉시 주문 동작
- ✅ is_fallback/is_relaxed 종목은 auto에서도 반자동 강제
- ✅ position_size_ratio 50% 사이징 동작
- ✅ manual 모드에서 신호 저장만 확인
- ✅ 기존 engine_approval 테스트 회귀 없음

---

### Task 3: 일일 마감 리포트 스케줄 + 시스템 경고 알림

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (_market_close에 일일 리포트 호출 추가)
- Modify: `backend/modules/notifier/manager.py` (send_system_alert 메서드 추가)
- Modify: `backend/modules/notifier/telegram_bot.py` (format_system_alert 메서드 추가)
- Modify: `backend/modules/trading/risk_manager.py` (비상 정지 발동 시 알림 콜백)
- Create: `backend/tests/test_daily_report_schedule.py`
- Create: `backend/tests/test_system_alert.py`

**Step 1: 테스트 작성**
- `backend/tests/test_daily_report_schedule.py` 생성
  - _market_close 호출 시 notifier_manager.send_daily_report 호출 확인
  - notifier_manager가 None이면 에러 없이 스킵 확인
- `backend/tests/test_system_alert.py` 생성
  - send_system_alert("emergency_stop", details) 호출 시 텔레그램 메시지 발송 확인
  - send_system_alert("pipeline_failure", details) 호출 시 메시지 포맷 확인
  - 텔레그램 봇 미설정(None) 시 에러 없이 스킵
- 검증: `docker compose exec backend pytest tests/test_daily_report_schedule.py tests/test_system_alert.py -v`
- 예상: FAIL

**Step 2: NotifierManager에 send_system_alert 추가**
- `backend/modules/notifier/manager.py` 수정
- 새 메서드 `async def send_system_alert(self, alert_type: str, details: str) -> None`:
  - alert_type: "emergency_stop", "pipeline_failure", "consecutive_loss", "risk_warning"
  - self._bot.format_system_alert(alert_type, details) 호출로 메시지 생성
  - self._bot.send_notification(text) 호출로 발송

**Step 3: TelegramBot에 format_system_alert 추가**
- `backend/modules/notifier/telegram_bot.py` 수정
- 새 메서드 `def format_system_alert(self, alert_type: str, details: str) -> str`:
  - alert_type별 이모지/제목 매핑:
    - "emergency_stop": "[비상 정지]"
    - "pipeline_failure": "[파이프라인 실패]"
    - "consecutive_loss": "[연속 손절 경고]"
    - "risk_warning": "[리스크 경고]"
  - HTML 형식 메시지 반환

**Step 4: scheduler._market_close에 일일 리포트 호출 추가**
- `backend/modules/collector/scheduler.py` _market_close 메서드 수정
- 기존 WS 종료 코드 이후에 추가:
  - self._notifier_manager가 존재하면 send_daily_report(self._session_factory) 호출
  - try/except로 감싸서 리포트 실패가 WS 종료에 영향 안 주게
- CollectorScheduler.__init__에 notifier_manager 파라미터는 이미 없으므로:
  - set_notifier_manager(manager) 메서드 추가 (set_telegram_bot 패턴과 동일)
  - main.py lifespan에서 collector_scheduler.set_notifier_manager(notifier_manager) 호출 추가

**Step 5: RiskManager에 알림 콜백 연결**
- `backend/modules/trading/risk_manager.py` 수정
- __init__에 `notifier=None` 파라미터 추가
- check_emergency_stop()에서 비상 정지 발동 시:
  - self._notifier가 있으면 await self._notifier.send_system_alert("emergency_stop", ...) 호출
- main.py lifespan에서 risk_manager 생성 후 notifier 주입:
  - `risk_manager.set_notifier(notifier_manager)` (set_notifier 메서드 추가)

**Step 6: main.py lifespan 수정**
- notifier_manager 생성 후 collector_scheduler.set_notifier_manager(notifier_manager) 호출 추가
- risk_manager 생성 후 risk_manager.set_notifier(notifier_manager) 호출 추가
- 검증: `docker compose exec backend pytest tests/test_daily_report_schedule.py tests/test_system_alert.py -v`
- 예상: PASS

**Step 7: 커밋**
```
git add backend/modules/collector/scheduler.py backend/modules/notifier/manager.py backend/modules/notifier/telegram_bot.py backend/modules/trading/risk_manager.py backend/main.py backend/tests/test_daily_report_schedule.py backend/tests/test_system_alert.py
git commit -m "feat(phase5-sprint2): task3 -- 일일 마감 리포트 자동 발송 + 시스템 경고 알림"
```

**완료 기준:**
- ✅ 15:30 market_close 시 일일 리포트 텔레그램 자동 발송
- ✅ 비상 정지 발동 시 텔레그램 경고 알림
- ✅ 텔레그램 미설정 환경에서 에러 없이 스킵

---

### Task 4: 매매 모드 전환 UI (3단계: manual/semi-auto/auto)

**skill:** `frontend-design`

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx` (매매 모드 섹션 추가)
- Modify: `frontend/components/settings/mode-switch.tsx` (trading_mode 전환 지원 확장)
- Create: `frontend/components/mode-indicator.tsx` (현재 모드 표시 배지)
- Modify: `frontend/app/(dashboard)/layout.tsx` (모드 인디케이터 삽입)

**Step 1: mode-indicator 컴포넌트 생성**
- `frontend/components/mode-indicator.tsx` 생성
- SWR 또는 polling으로 `/api/v1/settings/trading_mode` 조회
- 현재 모드를 배지로 표시:
  - "manual": 회색 배지 "수동"
  - "semi-auto": 노란색 배지 "반자동"
  - "auto": 빨간색 배지 "자동" (경고 색상 -- 주의 환기)
- 대시보드 레이아웃 상단 네비게이션에 삽입

**Step 2: settings/page.tsx에 매매 모드 섹션 추가**
- `frontend/app/(dashboard)/settings/page.tsx` 수정
- 기존 ModeSwitch(모의/실전 전환) 아래에 "매매 모드" 섹션 추가:
  - 현재 모드 표시 (manual/semi-auto/auto)
  - 모드 전환 드롭다운 또는 라디오 버튼
  - "자동 모드로 전환" 선택 시 2단계 확인 모달:
    - Step 1: 경고 메시지 ("자동 모드에서는 신호 발생 시 즉시 주문됩니다. 적응형/기본 후보는 반자동으로 처리됩니다.")
    - Step 2: 비밀번호 재확인
  - 반자동/수동으로의 전환은 비밀번호만 확인 (1단계)
  - 장중(09:00~15:30) 전환 차단 시 에러 메시지 표시

**Step 3: mode-switch.tsx 확장**
- `frontend/components/settings/mode-switch.tsx` 수정
- 기존 ModeSwitch는 모의/실전 전환 전용 -- 그대로 유지
- 새 컴포넌트 `TradingModeSwitch` 추가 (같은 파일 또는 별도 파일):
  - props: currentMode, onSuccess
  - PUT /api/v1/settings/trading-mode 호출
  - 에러 처리: 423(장중), 409(포지션), 403(비밀번호), 422(잘못된 모드)

**Step 4: layout.tsx에 모드 인디케이터 삽입**
- `frontend/app/(dashboard)/layout.tsx` 수정
- 상단 네비게이션 영역에 ModeIndicator 컴포넌트 추가

**Step 5: 타입체크**
- 검증: `docker compose exec frontend npx tsc --noEmit`
- 예상: 에러 없음

**Step 6: 커밋**
```
git add frontend/app/(dashboard)/settings/page.tsx frontend/components/settings/mode-switch.tsx frontend/components/mode-indicator.tsx frontend/app/(dashboard)/layout.tsx
git commit -m "feat(phase5-sprint2): task4 -- 매매 모드 전환 UI + 모드 인디케이터"
```

**완료 기준:**
- ✅ 설정 페이지에서 manual/semi-auto/auto 모드 전환 가능
- ✅ 자동 모드 전환 시 2단계 확인 모달 동작
- ✅ 레이아웃 상단에 현재 모드 배지 표시
- ✅ tsc --noEmit 에러 없음

---

### Task 5: 통합 검증

**Files:**
- 기존 테스트 파일 전체

**Step 1: pytest 전체 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 기존 테스트 + 신규 테스트 모두 PASS

**Step 2: API 수동 검증**
- trading_mode 조회: `curl -s http://localhost:8000/api/v1/settings/trading_mode | jq .`
  - 예상: `{ "key": "trading_mode", "value": "semi-auto", ... }`
- trading_mode 전환: `curl -s -X PUT http://localhost:8000/api/v1/settings/trading-mode -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"target_mode": "auto", "password": "..."}' | jq .`
  - 예상: `{ "trading_mode": "auto", "switched_at": "..." }`

**Step 3: 프론트엔드 타입체크**
- 검증: `docker compose exec frontend npx tsc --noEmit`
- 예상: 에러 없음

**Step 4: 커밋 (필요 시)**
```
git add -A && git commit -m "fix(phase5-sprint2): task5 -- 통합 검증 수정"
```

**완료 기준:**
- ✅ pytest 전체 통과 (733 passed)
- ✅ API 응답 정상 확인
- ✅ 프론트 타입체크 통과 (tsc --noEmit 에러 없음)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 기존 709+ passed + 신규 테스트 |
| 프론트 타입체크 | `docker compose exec frontend npx tsc --noEmit` | 에러 없음 |
| trading_mode 조회 | `curl -s http://localhost:8000/api/v1/settings/trading_mode \| jq .` | value: "semi-auto" |
| 모드 전환 API | `curl -X PUT .../settings/trading-mode -d '{"target_mode":"auto","password":"..."}' \| jq .` | trading_mode: "auto" |
| 일일 리포트 (수동 트리거) | `curl -X POST .../collector/trigger/market-close \| jq .` | 텔레그램에 리포트 수신 |
| 시스템 알림 포맷 | 테스트 코드에서 format_system_alert 직접 호출 | HTML 포맷 문자열 |
