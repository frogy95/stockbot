# Sprint 3: 텔레그램 봇 + 반자동 승인 (Phase 3)

**Goal:** 텔레그램 웹훅 기반 매매 승인/거부 시스템과 알림(신호/체결/일일 리포트)을 구현하여, 매매 엔진의 신호 -> 승인 -> 주문 -> 알림 전체 사이클을 완성한다.

**Architecture:** `approval.py`가 Redis 기반 일회용 승인 토큰(UUID4, TTL)을 관리하고, `telegram_bot.py`가 python-telegram-bot의 Application으로 웹훅/콜백을 처리한다. `manager.py`가 신호 알림, 체결 알림, 일일 리포트를 오케스트레이션한다. 매매 엔진(`engine.py`)의 `process_screening_results`에 승인 대기 흐름을 삽입하여 반자동 매매를 완성한다.

**Tech Stack:** Python 3.12, FastAPI, python-telegram-bot 21.x, Redis (승인 키 TTL), pytest-asyncio, httpx

**Sprint 기간:** 2026-03-30 ~ (사용자 검토 후 구현)
**이전 스프린트:** Sprint 2 (pytest 통과, PR #33)
**브랜치명:** `phase3-sprint3`

---

## 제외 범위

- 웹 대시보드 승인 (Phase 4)
- 완전 자동 모드 (Phase 5)
- 네이버 센티멘트/DART 공시 팩터 통합 (Phase 5)
- 정식 백테스팅 프레임워크 (Phase 5)
- 텔레그램 장애 시 웹 폴백 승인 (Phase 4)
- 다중 사용자/그룹 지원 (Phase 6)

## 실행 플랜

의존성 그래프:
- Task 1(테스트 수정) -> Task 2(Sprint 2 리뷰 이슈 수정) -> Task 3(승인 처리) -> Task 4(텔레그램 봇) / Task 5(알림 매니저) 병렬 -> Task 6(엔진 승인 통합) -> Task 7(웹훅 API + main.py) -> Task 8(텔레그램 명령어) -> Task 9(통합 테스트)

### Phase 1 (순차 -- 기존 이슈 해결)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 기존 실패 테스트 4건 수정 (seed count 21 -> 32) | 백엔드 | -- |
| Task 2 | Sprint 2 코드 리뷰 Medium 이슈 3건 수정 | 백엔드 | -- |

### Phase 2 (순차 -- 승인 인프라)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | Redis 승인 토큰 관리 (생성/검증/만료) | 백엔드 | -- |

### Phase 3 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 텔레그램 봇 (웹훅 수신 + 콜백 처리 + 메시지 포맷팅) | 백엔드 | -- |
| Task 5 | 알림 매니저 (신호/체결/일일 리포트 오케스트레이션) | 백엔드 | -- |

### Phase 4 (순차 -- 통합)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | 매매 엔진 승인 흐름 통합 (engine.py 수정) | 백엔드 | `feature-dev:feature-dev` |
| Task 7 | 텔레그램 웹훅 API + main.py 모듈 등록 | 백엔드 | -- |
| Task 8 | 텔레그램 조회 명령어 (/status, /today, /mode, /help) | 백엔드 | -- |

### Phase 5 (순차 -- 검증)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 9 | Phase 3 전체 흐름 통합 테스트 | 백엔드 | -- |

> **팀 실행**: "Phase 3를 팀으로 실행해줘"라고 요청하면 Task 4, Task 5를 병렬 구현합니다.

---

### Task 1: 기존 실패 테스트 4건 수정 (seed count)

**Files:**
- Modify: `backend/tests/test_integration.py` (assert 21 -> 32, IntegrityError 해결)
- Modify: `backend/tests/test_settings_api.py` (assert 21 -> 32)
- Modify: `backend/tests/test_sprint2_integration.py` (assert 21 -> 32)

**Step 1: 테스트 파일 수정**
- `backend/tests/test_integration.py`:
  - `test_seed_data_count`: `assert count == 21` -> `assert count == 32`
  - `test_stock_crud`: IntegrityError 원인은 seed 관련 fixture 충돌 -- 테스트 격리 확인 필요. seed_settings.py의 SEED_DATA가 32건이므로 count 기대값 수정으로 해결 가능
- `backend/tests/test_settings_api.py`:
  - `test_get_all_settings`: `assert len(data) == 21` -> `assert len(data) == 32`
- `backend/tests/test_sprint2_integration.py`:
  - `test_settings_list_21_items`: `assert len(resp.json()) == 21` -> `assert len(resp.json()) == 32` (함수명도 `test_settings_list_32_items`로 변경)
- 검증: `docker compose exec backend pytest tests/test_integration.py tests/test_settings_api.py tests/test_sprint2_integration.py -v`
- 예상: 4건 모두 PASS

**Step 2: 전체 회귀 테스트**
- 검증: `docker compose exec backend pytest -v --tb=short`
- 예상: 기존 실패 4건 해소, 전체 PASS

**Step 3: 커밋**
```
git add backend/tests/test_integration.py backend/tests/test_settings_api.py backend/tests/test_sprint2_integration.py
git commit -m "fix(phase3-sprint3): task1 -- 실패 테스트 4건 수정 (seed count 21->32)"
```

**완료 기준:**
- ⬜ pytest 4건 테스트 PASS
- ⬜ 전체 pytest 회귀 없음

---

### Task 2: Sprint 2 코드 리뷰 Medium 이슈 3건 수정

**Files:**
- Modify: `backend/modules/trading/engine.py` (on_order_filled quantity=0 -> 실제 수량)
- Modify: `backend/api/routes/trading.py` (get_session_factory() -> Depends(get_db) 패턴)
- Modify: `backend/modules/trading/engine.py` (get_status() 공개 메서드 추가)

**Step 1: engine.py -- on_order_filled quantity 수정**
- `on_order_filled` 메서드 시그니처에 `quantity: int` 파라미터 추가
- `self._position_manager.open_position(signal, 0, filled_price)` -> `self._position_manager.open_position(signal, quantity, filled_price)`
- 호출부가 현재 Sprint에서는 직접 호출되지 않으므로 (Sprint 3 Task 6 엔진 통합에서 연결), 시그니처만 정확히 수정

**Step 2: engine.py -- get_status() 공개 메서드 추가**
- `TradingEngine`에 `get_status() -> dict` 메서드 추가:
  - `is_running: bool` (self._running)
  - `queue_size: int` (self._order_manager._queue.qsize() -- 내부 접근은 engine 자체에서만)
  - `monitor_active: bool` (self._monitor_task is not None and not self._monitor_task.done())
- 이 메서드는 engine 내부에서 프라이빗 속성을 접근하므로 캡슐화 문제 없음

**Step 3: trading.py -- Depends(get_db) 패턴 적용**
- `from core.database import get_session_factory` import 제거
- `from api.deps import get_db` import 추가 (이미 deps.py에 정의됨)
- `get_positions`, `get_history`, `get_signals`, `get_orders` 4개 엔드포인트:
  - 파라미터에 `session: AsyncSession = Depends(get_db)` 추가
  - `factory = get_session_factory()` + `async with factory() as session:` 블록 제거, 직접 session 사용
- `get_engine_status` 엔드포인트:
  - engine 상태 부분: `engine._running` / `engine._order_manager._queue.qsize()` -> `engine.get_status()` 호출로 교체
  - DB 부분: Depends(get_db)로 session 주입
- 검증: `docker compose exec backend pytest tests/ -k "trading" -v`
- 예상: 기존 trading 관련 테스트 전부 PASS

**Step 4: 전체 회귀 테스트**
- 검증: `docker compose exec backend pytest -v --tb=short`
- 예상: 전체 PASS

**Step 5: 커밋**
```
git add backend/modules/trading/engine.py backend/api/routes/trading.py
git commit -m "fix(phase3-sprint3): task2 -- Sprint 2 리뷰 Medium 이슈 3건 수정 (quantity/DI/캡슐화)"
```

**완료 기준:**
- ⬜ on_order_filled에 실제 quantity 전달
- ⬜ trading.py 4개 엔드포인트 Depends(get_db) 패턴 적용
- ⬜ get_engine_status에서 engine.get_status() 사용
- ⬜ 전체 pytest 회귀 없음

---

### Task 3: Redis 승인 토큰 관리 (approval.py)

**Files:**
- Create: `backend/modules/notifier/approval.py`
- Test: `backend/tests/test_approval.py`

**Step 1: 테스트 작성**
- `backend/tests/test_approval.py` 생성
- 테스트 케이스:
  1. `create_approval` -- UUID4 토큰 생성, Redis에 `approval:{token}` 키 저장, TTL 설정 확인
  2. `validate_approval` -- 유효한 토큰 검증 시 signal_data 반환 + 토큰 삭제 (일회용)
  3. `validate_approval_invalid` -- 존재하지 않는 토큰 시 None 반환
  4. `validate_approval_expired` -- TTL 만료 후 검증 시 None 반환
  5. `get_pending_approvals` -- 현재 대기 중인 승인 목록 조회
- Redis mock: `RedisClient` 인스턴스를 직접 생성하되, 실제 Redis 연결 대신 fakeredis 사용 또는 실제 Docker Redis 사용
- 검증: `docker compose exec backend pytest tests/test_approval.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 승인 처리 모듈 구현**
- `backend/modules/notifier/approval.py` 생성
- **ApprovalManager** 클래스:
  - `__init__(self, redis_client: RedisClient)` -- Redis 클라이언트 주입
  - `async create_approval(self, signal: TradeSignalData, quantity: int, timeout_sec: int) -> str`:
    - UUID4 토큰 생성
    - Redis 키 `approval:{token}`에 JSON 직렬화된 signal + quantity 저장, TTL=timeout_sec
    - 토큰 문자열 반환
  - `async validate_approval(self, token: str) -> dict | None`:
    - Redis에서 `approval:{token}` 조회
    - 존재하면 JSON 파싱 후 반환 + 키 삭제 (일회용)
    - 미존재(만료 포함)면 None 반환
  - `async cancel_approval(self, token: str) -> bool`:
    - Redis에서 `approval:{token}` 삭제
  - `async get_pending_count(self) -> int`:
    - `approval:*` 패턴 키 개수 반환 (SCAN 사용)
- 검증: `docker compose exec backend pytest tests/test_approval.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/notifier/approval.py backend/tests/test_approval.py
git commit -m "feat(phase3-sprint3): task3 -- Redis 승인 토큰 관리 (생성/검증/만료/일회용)"
```

**완료 기준:**
- ⬜ 토큰 생성/검증/만료/일회용 동작 확인
- ⬜ pytest 테스트 통과

---

### Task 4: 텔레그램 봇 (웹훅 수신 + 콜백 처리 + 메시지 포맷팅)

**Files:**
- Create: `backend/modules/notifier/telegram_bot.py`
- Test: `backend/tests/test_telegram_bot.py`

**Step 1: requirements.txt 업데이트**
- `backend/requirements.txt`에 `python-telegram-bot>=21.0,<22.0` 추가
- 검증: `docker compose exec backend pip install python-telegram-bot` (이미지 빌드 불필요, 런타임 확인)

**Step 2: 테스트 작성**
- `backend/tests/test_telegram_bot.py` 생성
- 테스트 케이스 (외부 API 호출 없이 로직만 검증):
  1. `test_format_signal_message` -- 신호 데이터를 HTML 메시지로 포맷팅
  2. `test_format_fill_message` -- 체결 데이터를 HTML 메시지로 포맷팅
  3. `test_format_daily_report` -- 일일 리포트 HTML 포맷팅
  4. `test_build_approval_keyboard` -- 승인/거부 인라인 버튼 구성
  5. `test_parse_callback_data` -- 콜백 데이터에서 action + token 파싱
  6. `test_is_authorized_chat` -- Chat ID 화이트리스트 검증
- 검증: `docker compose exec backend pytest tests/test_telegram_bot.py -v`
- 예상: FAIL (모듈 미존재)

**Step 3: 텔레그램 봇 구현**
- `backend/modules/notifier/telegram_bot.py` 생성
- **TelegramBot** 클래스:
  - `__init__(self, bot_token: str, chat_id: str, approval_manager: ApprovalManager)`:
    - `telegram.Bot` 인스턴스 생성
    - chat_id 화이트리스트 (단일 사용자)
  - **메시지 포맷팅** (HTML parse_mode):
    - `format_signal_message(signal: TradeSignalData, quantity: int, token: str) -> tuple[str, InlineKeyboardMarkup]`:
      - 종목명, 방향, 수량, 가격, 신뢰도, 근거 요약
      - 인라인 버튼: "승인 approve:{token}" / "거부 reject:{token}"
    - `format_fill_message(stock_code: str, quantity: int, price: int, order_type: str) -> str`:
      - 체결 확인 메시지
    - `format_daily_report(stats: dict) -> str`:
      - 총 거래, 실현 손익, 승률, 포지션 요약
  - **발송**:
    - `async send_signal_alert(signal, quantity, token) -> int`:
      - 승인 요청 메시지 + 인라인 버튼 발송, message_id 반환
    - `async send_notification(text: str) -> int`:
      - 일반 텍스트 알림 발송
    - `async edit_message(message_id: int, text: str)`:
      - 승인/거부 후 메시지 수정 (버튼 제거 + 결과 표시)
  - **콜백 처리**:
    - `parse_callback_data(data: str) -> tuple[str, str]`:
      - "approve:{token}" -> ("approve", token)
      - "reject:{token}" -> ("reject", token)
    - `is_authorized(chat_id: int) -> bool`:
      - 화이트리스트 검증
  - **웹훅 관리**:
    - `async set_webhook(url: str)`:
      - `bot.set_webhook(url)` 호출 (앱 시작 시 자동)
    - `async delete_webhook()`:
      - 종료 시 웹훅 삭제
- 검증: `docker compose exec backend pytest tests/test_telegram_bot.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/notifier/telegram_bot.py backend/tests/test_telegram_bot.py backend/requirements.txt
git commit -m "feat(phase3-sprint3): task4 -- 텔레그램 봇 (메시지 포맷 + 콜백 파싱 + 웹훅 관리)"
```

**완료 기준:**
- ⬜ 메시지 포맷팅 (HTML) 정상 동작
- ⬜ 인라인 버튼 구성 정상
- ⬜ 콜백 데이터 파싱 정상
- ⬜ 화이트리스트 검증 정상
- ⬜ pytest 테스트 통과

---

### Task 5: 알림 매니저 (manager.py)

**Files:**
- Create: `backend/modules/notifier/manager.py`
- Test: `backend/tests/test_notifier_manager.py`

**Step 1: 테스트 작성**
- `backend/tests/test_notifier_manager.py` 생성
- 테스트 케이스 (TelegramBot을 mock):
  1. `test_notify_signal` -- 신호 발생 시 승인 토큰 생성 + 텔레그램 발송 호출 확인
  2. `test_notify_fill` -- 체결 시 텔레그램 알림 발송 확인
  3. `test_notify_rejection` -- 거부 시 메시지 수정 확인
  4. `test_notify_timeout` -- 승인 만료 시 메시지 수정 + 로그
  5. `test_send_daily_report` -- 일일 리포트 데이터 조합 + 발송 확인
- 검증: `docker compose exec backend pytest tests/test_notifier_manager.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 알림 매니저 구현**
- `backend/modules/notifier/manager.py` 생성
- **NotifierManager** 클래스:
  - `__init__(self, telegram_bot: TelegramBot, approval_manager: ApprovalManager, session_factory)`:
    - 의존성 주입
    - `_pending_messages: dict[str, int]` -- token -> message_id 매핑
  - `async notify_signal(signal: TradeSignalData, quantity: int, timeout_sec: int) -> str`:
    - approval_manager.create_approval(signal, quantity, timeout_sec) -> token
    - telegram_bot.send_signal_alert(signal, quantity, token) -> message_id
    - _pending_messages[token] = message_id
    - token 반환
  - `async handle_approval(token: str, action: str) -> dict | None`:
    - approval_manager.validate_approval(token)
    - 유효하면: 승인/거부 결과 반환 + 메시지 수정 (버튼 제거)
    - 무효하면: None 반환 (이미 처리됨 또는 만료)
  - `async notify_fill(stock_code: str, quantity: int, price: int, order_type: str)`:
    - telegram_bot.send_notification(format_fill_message(...))
  - `async notify_timeout(token: str)`:
    - _pending_messages에서 message_id 조회
    - telegram_bot.edit_message(message_id, "만료됨") 호출
    - _pending_messages에서 제거
  - `async send_daily_report(session_factory)`:
    - DB에서 당일 trade_history 조회: 총 거래, 실현 손익 합계, 승률 계산
    - telegram_bot.send_notification(format_daily_report(stats))
- 검증: `docker compose exec backend pytest tests/test_notifier_manager.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/notifier/manager.py backend/tests/test_notifier_manager.py
git commit -m "feat(phase3-sprint3): task5 -- 알림 매니저 (신호/체결/만료/일일 리포트)"
```

**완료 기준:**
- ⬜ 신호 알림 -> 승인 토큰 생성 + 텔레그램 발송
- ⬜ 체결/거부/만료 알림 동작
- ⬜ 일일 리포트 조합 + 발송
- ⬜ pytest 테스트 통과

---

### Task 6: 매매 엔진 승인 흐름 통합

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/trading/engine.py` (승인 대기 흐름 삽입)
- Modify: `backend/modules/trading/order_manager.py` (승인 상태 주문 처리)
- Test: `backend/tests/test_engine_approval.py`

**Step 1: 테스트 작성**
- `backend/tests/test_engine_approval.py` 생성
- 테스트 케이스:
  1. `test_semi_auto_signal_creates_approval` -- 반자동 모드에서 신호 발생 시 주문 즉시 실행 안 함, 승인 토큰 생성 확인
  2. `test_approval_triggers_order` -- 승인 시 주문 실행 확인 (submit_order 호출)
  3. `test_rejection_cancels_signal` -- 거부 시 신호 상태 "rejected"로 업데이트
  4. `test_timeout_expires_signal` -- 타임아웃 시 신호 상태 "expired"로 업데이트
  5. `test_auto_mode_bypasses_approval` -- 자동 모드에서는 승인 없이 즉시 주문
  6. `test_approval_timeout_by_time_zone` -- 골든타임(20초), 마감 전(15초), 일반(30초) 타임아웃 확인
- 검증: `docker compose exec backend pytest tests/test_engine_approval.py -v`
- 예상: FAIL (수정 전)

**Step 2: engine.py 승인 흐름 수정**
- `TradingEngine.__init__`에 의존성 추가:
  - `notifier_manager: NotifierManager | None = None` (선택적, 없으면 자동 모드)
- `process_screening_results` 수정:
  - 기존: 리스크 체크 통과 -> 즉시 `order_manager.submit_order(signal, position_size)`
  - 변경: 리스크 체크 통과 -> `notifier_manager`가 있으면 승인 요청 (`notify_signal`), 없으면 즉시 주문
  - 승인 요청 시: signal + position_size를 Redis에 저장하여 나중에 approve 콜백에서 주문 실행
- `async approve_signal(token: str) -> bool` 신규 메서드:
  - notifier_manager.handle_approval(token, "approve") 호출
  - 결과에서 signal + quantity 복원
  - order_manager.submit_order(signal, position_size) 실행
  - on_order_filled 콜백 체인에 quantity 전달
- `async reject_signal(token: str) -> bool` 신규 메서드:
  - notifier_manager.handle_approval(token, "reject") 호출
  - 알림 발송
- `_get_approval_timeout` 메서드: 이미 존재, 그대로 사용

**Step 3: order_manager.py 주문 상태 확장**
- 주문 생성 시 `status="pending_approval"` 지원 (기존: "submitted"만)
- 승인 후 `status="submitted"`로 전환 후 큐에 enqueue

**Step 4: 검증**
- 검증: `docker compose exec backend pytest tests/test_engine_approval.py tests/test_trading_engine.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/modules/trading/engine.py backend/modules/trading/order_manager.py backend/tests/test_engine_approval.py
git commit -m "feat(phase3-sprint3): task6 -- 매매 엔진 승인 흐름 통합 (반자동/자동 분기)"
```

**완료 기준:**
- ⬜ 반자동 모드: 신호 -> 승인 대기 -> 승인 시 주문 실행
- ⬜ 자동 모드: 신호 -> 즉시 주문 (기존 동작 유지)
- ⬜ 거부/만료 시 신호 상태 업데이트
- ⬜ 시간대별 승인 타임아웃 적용
- ⬜ 기존 test_trading_engine.py 회귀 없음

---

### Task 7: 텔레그램 웹훅 API + main.py 모듈 등록

**Files:**
- Create: `backend/api/routes/telegram.py`
- Modify: `backend/main.py` (notifier 모듈 초기화 + 웹훅 라우터 등록)
- Modify: `backend/core/config.py` (TELEGRAM_WEBHOOK_URL 환경변수 추가)
- Test: `backend/tests/test_telegram_webhook.py`

**Step 1: config.py 환경변수 추가**
- `Settings` 클래스에 `TELEGRAM_WEBHOOK_URL: str = ""` 추가
- 이 값은 Railway 배포 시 설정 (로컬에서는 빈 문자열)

**Step 2: 테스트 작성**
- `backend/tests/test_telegram_webhook.py` 생성
- 테스트 케이스 (httpx AsyncClient로 FastAPI 테스트):
  1. `test_webhook_approve_callback` -- POST /api/v1/telegram/webhook에 승인 콜백 전송 시 approve_signal 호출 확인
  2. `test_webhook_reject_callback` -- 거부 콜백 시 reject_signal 호출 확인
  3. `test_webhook_unauthorized_chat` -- 화이트리스트 외 chat_id 차단 확인
  4. `test_webhook_message_command` -- /status 명령어 메시지 수신 시 처리 확인
- 검증: `docker compose exec backend pytest tests/test_telegram_webhook.py -v`
- 예상: FAIL (모듈 미존재)

**Step 3: 웹훅 API 구현**
- `backend/api/routes/telegram.py` 생성
- `router = APIRouter(prefix="/telegram", tags=["telegram"])`
- **POST `/webhook`**:
  - 요청 바디: 텔레그램 Update JSON
  - 콜백 쿼리(`callback_query`) 처리:
    - `parse_callback_data` -> action + token
    - `is_authorized` 검증
    - action == "approve": `engine.approve_signal(token)` -> 알림
    - action == "reject": `engine.reject_signal(token)` -> 알림
  - 메시지(`message`) 처리:
    - text가 명령어(`/status`, `/today`, `/mode`, `/help`)이면 해당 핸들러 호출
  - 응답: 항상 200 OK (텔레그램 재전송 방지)

**Step 4: main.py 모듈 등록**
- import 추가:
  - `from modules.notifier.approval import ApprovalManager`
  - `from modules.notifier.telegram_bot import TelegramBot`
  - `from modules.notifier.manager import NotifierManager`
  - `from api.routes.telegram import router as telegram_router`
- lifespan 함수에 notifier 초기화 추가 (매매 엔진 초기화 직후):
  - `approval_manager = ApprovalManager(redis_client)`
  - `telegram_bot = TelegramBot(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID, approval_manager)`
  - `notifier_manager = NotifierManager(telegram_bot, approval_manager, session_factory)`
  - `app.state.notifier_manager = notifier_manager`
  - `app.state.telegram_bot = telegram_bot`
  - `app.state.approval_manager = approval_manager`
  - TradingEngine 생성 시 `notifier_manager=notifier_manager` 전달
  - TELEGRAM_WEBHOOK_URL이 있으면 `await telegram_bot.set_webhook(settings.TELEGRAM_WEBHOOK_URL + "/api/v1/telegram/webhook")`
- shutdown에 `await telegram_bot.delete_webhook()` 추가 (WEBHOOK_URL 설정된 경우만)
- 라우터 등록: `app.include_router(telegram_router, prefix="/api/v1")`
- 검증: `docker compose exec backend pytest tests/test_telegram_webhook.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/api/routes/telegram.py backend/main.py backend/core/config.py backend/tests/test_telegram_webhook.py
git commit -m "feat(phase3-sprint3): task7 -- 텔레그램 웹훅 API + main.py notifier 모듈 등록"
```

**완료 기준:**
- ⬜ POST /api/v1/telegram/webhook 정상 동작
- ⬜ 승인/거부 콜백 처리 -> 주문 실행/취소
- ⬜ 비인가 chat_id 차단
- ⬜ 앱 시작 시 setWebhook 자동 호출 (TELEGRAM_WEBHOOK_URL 설정 시)
- ⬜ pytest 테스트 통과

---

### Task 8: 텔레그램 조회 명령어

**Files:**
- Create: `backend/modules/notifier/commands.py`
- Modify: `backend/api/routes/telegram.py` (명령어 핸들러 연결)
- Test: `backend/tests/test_telegram_commands.py`

**Step 1: 테스트 작성**
- `backend/tests/test_telegram_commands.py` 생성
- 테스트 케이스:
  1. `test_status_command` -- /status 명령어: 활성 포지션 요약 텍스트 생성
  2. `test_today_command` -- /today 명령어: 오늘 손익 요약 텍스트 생성
  3. `test_mode_command` -- /mode 명령어: 현재 모드 (TRADING_ENV + 반자동/자동) 텍스트
  4. `test_help_command` -- /help 명령어: 명령어 목록 텍스트
- 검증: `docker compose exec backend pytest tests/test_telegram_commands.py -v`
- 예상: FAIL

**Step 2: 명령어 핸들러 구현**
- `backend/modules/notifier/commands.py` 생성
- **CommandHandler** 클래스:
  - `__init__(self, session_factory, redis_client, telegram_bot: TelegramBot)`:
    - 의존성 주입
  - `async handle_status(chat_id: int) -> str`:
    - DB에서 활성 포지션 조회 (PositionRecord)
    - 각 포지션: 종목코드, 수량, 평균가, 현재가, 수익률
    - 포지션 없으면 "활성 포지션 없음"
  - `async handle_today(chat_id: int) -> str`:
    - DB에서 당일 trade_history 조회
    - 총 거래 건수, 실현 손익 합계, 승률 (pnl > 0 비율)
    - 거래 없으면 "오늘 거래 기록 없음"
  - `async handle_mode(chat_id: int) -> str`:
    - settings에서 TRADING_ENV 조회
    - notifier_manager 존재 여부로 반자동/자동 판별
    - "모의거래 / 반자동 모드" 형태 반환
  - `async handle_help(chat_id: int) -> str`:
    - 명령어 목록 고정 텍스트 반환
  - `async dispatch(command: str, chat_id: int) -> str`:
    - command에 따라 위 핸들러 분기 ("/status", "/today", "/mode", "/help")
    - 알 수 없는 명령어: handle_help 반환

**Step 3: telegram.py 명령어 연결**
- 웹훅 엔드포인트의 메시지 처리 부분에서 `command_handler.dispatch(text, chat_id)` 호출
- 결과를 `telegram_bot.send_notification(result)` 로 발송

**Step 4: 검증**
- 검증: `docker compose exec backend pytest tests/test_telegram_commands.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/modules/notifier/commands.py backend/api/routes/telegram.py backend/tests/test_telegram_commands.py
git commit -m "feat(phase3-sprint3): task8 -- 텔레그램 조회 명령어 (/status, /today, /mode, /help)"
```

**완료 기준:**
- ⬜ /status: 활성 포지션 요약 정상
- ⬜ /today: 당일 손익 요약 정상
- ⬜ /mode: 모의/실전 + 반자동/자동 표시 정상
- ⬜ /help: 명령어 목록 정상
- ⬜ pytest 테스트 통과

---

### Task 9: Phase 3 전체 흐름 통합 테스트

**Files:**
- Create: `backend/tests/test_phase3_integration.py`

**Step 1: 통합 테스트 작성**
- `backend/tests/test_phase3_integration.py` 생성
- 테스트 시나리오:
  1. `test_signal_to_approval_to_order` -- 신호 발생 -> 승인 토큰 생성 -> 승인 콜백 -> 주문 실행 -> 포지션 생성 전체 흐름
  2. `test_signal_rejection_flow` -- 신호 발생 -> 승인 토큰 -> 거부 콜백 -> 주문 미실행 확인
  3. `test_signal_timeout_flow` -- 신호 발생 -> 승인 타임아웃 -> 자동 만료 + 알림
  4. `test_daily_report_generation` -- 일일 리포트: DB에 trade_history 삽입 -> 리포트 생성 확인
  5. `test_webhook_endpoint_integration` -- POST /api/v1/telegram/webhook으로 콜백 전송 -> 처리 확인
  6. `test_command_via_webhook` -- POST /api/v1/telegram/webhook으로 /status 명령어 전송 -> 응답 확인
  7. `test_risk_check_then_approval` -- 리스크 체크 통과 -> 승인 요청 (리스크 차단 시 승인 요청 안 함)
- 모든 테스트는 TelegramBot의 실제 API 호출을 mock 처리 (send_message, edit_message 등)

**Step 2: 전체 회귀 테스트**
- 검증: `docker compose exec backend pytest -v --tb=short`
- 예상: 전체 PASS (기존 + 신규)

**Step 3: 커밋**
```
git add backend/tests/test_phase3_integration.py
git commit -m "feat(phase3-sprint3): task9 -- Phase 3 전체 흐름 통합 테스트"
```

**완료 기준:**
- ⬜ 신호->승인->주문->포지션 전체 흐름 통과
- ⬜ 거부/만료 흐름 통과
- ⬜ 일일 리포트 생성 통과
- ⬜ 웹훅 엔드포인트 통합 통과
- ⬜ 전체 pytest 회귀 없음

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS (기존 + 신규 ~40건 추가) |
| 기존 실패 테스트 해소 | `docker compose exec backend pytest tests/test_integration.py tests/test_settings_api.py tests/test_sprint2_integration.py -v` | 4건 모두 PASS |
| 승인 API | `curl -s -X POST http://localhost:8000/api/v1/telegram/webhook -H "Content-Type: application/json" -d '{"update_id":1,"callback_query":{"id":"1","chat_instance":"1","data":"approve:test-token","from":{"id":CHAT_ID},"message":{"message_id":1,"chat":{"id":CHAT_ID},"text":"test"}}}'` | 200 OK |
| 명령어 API | `curl -s -X POST http://localhost:8000/api/v1/telegram/webhook -H "Content-Type: application/json" -d '{"update_id":1,"message":{"message_id":1,"chat":{"id":CHAT_ID},"text":"/status","from":{"id":CHAT_ID}}}'` | 200 OK |
| 리스크 상태 | `curl -s http://localhost:8000/api/v1/trading/risk-status \| jq .` | 정상 응답 |
| 엔진 상태 | `curl -s http://localhost:8000/api/v1/trading/engine-status \| jq .` | `get_status()` 기반 응답 |

---

## 프로덕션 장애 기록: 2026-03-31 market_open 미실행

### 현상

- **발견 시각**: 09:07 (모니터링 시작 후 즉시)
- **영향 시간**: 09:00 ~ 장 마감 (전일 장중)
- **증상**:
  - `GET /api/v1/collector/status` → `ws_subscriptions: 0`
  - `GET /api/v1/screening/secondary` → `results: [], screened_at: null`
  - 2차 스크리닝 스케줄러는 30초 간격으로 정상 실행되나 전 종목 skip
  - `market_open` 잡의 `next_run` = 2026-04-01 09:00 (오늘 실행 누락)

### 근본 원인 분석

#### 실행 흐름 (정상)

```
08:00 premarket_collect → 전 종목 시세 수집
08:10 primary_screen → 1차 스크리닝 + ws_manager.subscribe() ← WS 구독 등록
09:00 market_open → ws_client.connect() + 2차 스크리닝 활성화
09:30~ secondary_screen (30초 주기) → Redis 실시간 데이터 기반 필터링
```

#### 장애 경로

1. **08:10 `primary_screen()` 실행 → 1차 스크리닝 30개 후보 도출 → DB 저장 성공**
   - 08:10 KST `screened_at` 확인됨 → 1차 스크리닝 자체는 성공

2. **WS 구독 등록 경로** (`scheduler.py:310-332`):
   ```python
   # _primary_screen() 내부
   for item in results:
       await self._ws_manager.subscribe(item["stock_code"], priority=...)
   ```
   - **ws_manager.subscribe()는 WS 연결 전 구독 목록만 등록**
   - 실제 WS 구독은 `_market_open()` → `ws_client.connect()` 이후 발생

3. **09:00 `_market_open()` 미실행 추정 원인**:
   - APScheduler `CronTrigger(hour=9, minute=0)` + `misfire_grace_time=60`
   - 09:00:00~09:01:00 사이 실행 불가 시 자동 skip → `next_run` = 내일
   - **가능 원인 A**: 이전 작업(08:00~08:20 수집 잡들) 장시간 실행으로 스케줄러 blocking
   - **가능 원인 B**: Railway 컨테이너 재시작/sleep으로 09:00 시점 인스턴스 미응답
   - **가능 원인 C**: NTP 시간 보정으로 시계 점프 (60초 grace 초과)

4. **`_market_open()` 미실행 → WS 미연결 → Redis 실시간 데이터 없음**:
   ```python
   # realtime_screener.py:160-179
   execution_raw = await self.redis_client.get(f"realtime:{code}:execution")
   if execution_raw is None:  # ← WS 데이터 없으면 None
       return None  # ← 해당 종목 skip
   ```

5. **결과**: 2차 스크리닝 30개 후보 전량 skip → `results: []` 지속

### 영향

- 장중 2차 스크리닝 완전 무력화 (09:00~15:30)
- 매매 신호 0건 발생 → 자동 매매 미작동
- 수동 복구 API(`POST /collector/trigger/market-open`) 존재하나 프로덕션 쓰기 권한 미확보로 미조치

### 개선 필요사항

| 우선순위 | 항목 | 설명 |
|----------|------|------|
| P0 | `misfire_grace_time` 확대 | 현재 60초 → 300초 이상으로 확대하여 실행 누락 가능성 축소 |
| P0 | `market_open` 실행 검증 | 09:05 시점에 `ws_subscriptions == 0`이면 재시도하는 자체 복구 로직 |
| P1 | WebSocket 구독 상태 알림 | `ws_subscriptions: 0` 상태가 09:05 이후 지속 시 텔레그램 경고 발송 |
| P1 | `_market_open` 재시도 잡 | 09:00 실패 시 09:05, 09:10에 재시도하는 fallback cron 등록 |
| P2 | Railway 로그 확인 | 09:00 전후 컨테이너 상태/스케줄러 로그 분석 → 정확한 원인 특정 |
| P2 | lifespan 시작 시 장중 감지 | 서버 재시작이 09:00~15:30 사이면 `_market_open()` 자동 호출 |

### 모니터링 로그

- 09:07~10:52 총 22회 5분 간격 점검 (CronCreate `*/5 * * * *`)
- 전 구간 `ws_subscriptions: 0`, `secondary results: 0`
- `secondary_last_run`은 5분 간격으로 정상 갱신 확인 → 스케줄러 자체는 정상
