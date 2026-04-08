# Sprint 1: WS 재연결 안정화 + 구독 제한 (Phase 5.2)

**Goal:** KIS WebSocket 재연결 시 구독 버스트 전송을 방지하고, 환경별 구독 상한/캐시 TTL/2차 스크리닝 WS 연동을 개선하여 장중 실시간 파이프라인 안정화

**Architecture:** kis_ws.py의 _reconnect() 구독 복원에 종목당 0.5초 딜레이를 추가하고, KISEnvironment에 max_ws_subscriptions 필드를 도입하여 paper=25/live=35를 적용한다. 2차 스크리닝에 WS 연결 상태 가드를 추가하고, 재연결 실패 시 텔레그램 알림 콜백을 연결한다.

**Tech Stack:** Python 3.12, FastAPI, websockets, pytest, asyncio

**Sprint 기간:** 2026-04-08 ~ 2026-04-08
**완료일:** 2026-04-08
**상태:** ✅ 완료
**이전 스프린트:** Phase 5.1 Sprint 1 (완료, PR #105)
**브랜치명:** `phase5.2-sprint1`

---

## 제외 범위

- WS 완전 실패 시 REST 폴백 가격 감시 (Phase 6 이관)
- 장중 동적 우선순위 조정 (2차 스코어 기반, Phase 6 이관)
- approval_key 모의 환경 만료 재시도 (미해결 사항 #5 -- 기존 로직으로 대응)
- 프론트엔드 변경 없음 (백엔드 전용 수정)
- DB 스키마 변경 없음 (Alembic 마이그레이션 불필요)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | KISEnvironment max_ws_subscriptions + 재연결 파라미터 변경 | 백엔드 | -- |

### Phase 2 (순차, Task 1에 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | _reconnect() 구독 복원 딜레이 + close code 로깅 + 실패 콜백 | 백엔드 | -- |

### Phase 3 (순차, Task 2에 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | WSSubscriptionManager 환경 기반 max + 캐시 TTL + 2차 스크리닝 WS 가드 + 체결강도 웜업 | 백엔드 | `feature-dev:feature-dev` |

### Phase 4 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 테스트 업데이트 + 통합 검증 | 백엔드 | -- |

---

### Task 1: KISEnvironment max_ws_subscriptions + 재연결 파라미터 변경

**Files:**
- Modify: `backend/core/clients/kis_config.py` (KISEnvironment에 max_ws_subscriptions 필드 추가)
- Modify: `backend/core/clients/kis_ws.py` (모듈 상수 변경만)

**Step 1: kis_config.py -- KISEnvironment에 max_ws_subscriptions 필드 추가**
- `KISEnvironment` dataclass에 `max_ws_subscriptions: int` 필드 추가
- `ws_reconnect_delay: float` 필드 추가 (종목당 구독 복원 딜레이, 초)
- PAPER: `max_ws_subscriptions=25`, `ws_reconnect_delay=0.5`
- LIVE: `max_ws_subscriptions=35`, `ws_reconnect_delay=0.2`
- 검증: `docker compose exec backend python -c "from core.clients.kis_config import PAPER, LIVE; assert PAPER.max_ws_subscriptions == 25; assert LIVE.max_ws_subscriptions == 35; assert PAPER.ws_reconnect_delay == 0.5; assert LIVE.ws_reconnect_delay == 0.2; print('OK')"`
- 예상: OK

**Step 2: kis_ws.py -- 모듈 상수 변경**
- `MAX_RECONNECT_ATTEMPTS`: 5 -> 7
- `BACKOFF_BASE`: 1 -> 2
- 검증: `docker compose exec backend python -c "from core.clients.kis_ws import MAX_RECONNECT_ATTEMPTS, BACKOFF_BASE; assert MAX_RECONNECT_ATTEMPTS == 7; assert BACKOFF_BASE == 2; print('OK')"`
- 예상: OK

**Step 3: 커밋**
```
git add backend/core/clients/kis_config.py backend/core/clients/kis_ws.py
git commit -m "feat(phase5.2-sprint1): task1 -- KISEnvironment max_ws_subscriptions + 재연결 파라미터 조정"
```

**완료 기준:**
- ✅ PAPER.max_ws_subscriptions == 25, LIVE == 35
- ✅ PAPER.ws_reconnect_delay == 0.5, LIVE == 0.2
- ✅ MAX_RECONNECT_ATTEMPTS == 7, BACKOFF_BASE == 2

---

### Task 2: _reconnect() 구독 복원 딜레이 + close code 로깅 + 실패 콜백

**Files:**
- Modify: `backend/core/clients/kis_ws.py` (_reconnect 메서드 수정, connect에 ping_timeout 추가, on_ws_failure 콜백, ConnectionClosed 로깅)

**Step 1: on_ws_failure 콜백 인터페이스 추가**
- `__init__`에 `self._on_ws_failure: Callable | None = None` 추가
- `set_on_ws_failure(self, callback: Callable) -> None` 메서드 추가 (scheduler에서 등록할 콜백)
- 검증: `docker compose exec backend python -c "from core.clients.kis_ws import KISWebSocketClient; print('import OK')"`
- 예상: import OK

**Step 2: connect()에 ping_timeout=10 추가**
- `websockets.connect()` 호출에 `ping_timeout=10` 키워드 인자 추가 (기존 ping_interval=30 유지)
- 검증: 코드 리뷰 확인 (websockets.connect 호출부에 ping_timeout=10 존재)

**Step 3: _receive_loop() ConnectionClosed close code/reason 로깅**
- 기존: `logger.warning("WebSocket 연결 끊김, 재연결 시도")`
- 변경: `except ConnectionClosed as e:` 로 잡고, `logger.warning("WebSocket 연결 끊김: code=%s reason=%s", e.code, e.reason)` 로그
- 검증: 코드 리뷰 확인

**Step 4: _reconnect() 구독 복원 딜레이 추가**
- 핵심 수정: 기존 174~175줄의 구독 복원 루프에 딜레이 추가
- 기존:
  ```python
  for stock_code, tr_id in subscriptions_snapshot:
      await self.subscribe(stock_code, tr_id)
  ```
- 변경: 종목 단위로 그룹핑 후 종목 간 딜레이 삽입
  ```
  종목별로 그룹핑 (stock_code -> [tr_id, ...])
  각 종목의 tr_id 구독은 즉시 실행 (동일 종목 내 tr_id 간 딜레이 없음)
  종목 간 self._env.ws_reconnect_delay 초 대기
  ```
- 복원 진행 로그: `"구독 복원 중: %d/%d 종목"` (10종목마다 또는 완료 시)
- 검증: 코드 리뷰 확인 (asyncio.sleep(self._env.ws_reconnect_delay) 존재)

**Step 5: _reconnect() 연결 시 ping_timeout=10 추가**
- _reconnect() 내부 websockets.connect() 호출에도 `ping_timeout=10` 추가 (connect()와 동일하게)
- 검증: 코드 리뷰 확인

**Step 6: _reconnect() 실패 시 on_ws_failure 콜백 호출**
- 최대 시도 횟수 초과 후 `self._connected = False` 설정 직후:
  ```
  if self._on_ws_failure is not None:
      try:
          await/call self._on_ws_failure()
      except Exception:
          logger.exception("WS 실패 콜백 실행 오류")
  ```
- _on_ws_failure가 코루틴인지 일반 함수인지에 따라 await 분기 (asyncio.iscoroutinefunction 사용)
- 검증: 코드 리뷰 확인

**Step 7: 커밋**
```
git add backend/core/clients/kis_ws.py
git commit -m "feat(phase5.2-sprint1): task2 -- _reconnect 구독 복원 딜레이 + close code 로깅 + 실패 콜백"
```

**완료 기준:**
- ✅ 구독 복원 시 종목 간 ws_reconnect_delay 대기
- ✅ ConnectionClosed에서 code/reason 로깅
- ✅ ping_timeout=10 적용 (connect + reconnect)
- ✅ 재연결 최대 실패 시 on_ws_failure 콜백 호출

---

### Task 3: WSSubscriptionManager 환경 기반 max + 캐시 TTL + 2차 스크리닝 WS 가드 + 체결강도 웜업

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/collector/ws_manager.py` (환경 기반 max_subscriptions 주입 -- 이미 파라미터로 받고 있어 변경 최소)
- Modify: `backend/modules/collector/scheduler.py` (REALTIME_CACHE_TTL 변경, _secondary_screen WS 가드, WS 실패 콜백 등록, 연속 스킵 카운터)
- Modify: `backend/modules/collector/trade_strength.py` (reset_warmup 메서드 -- 재연결 후 특정 종목 웜업 초기화)
- Modify: `backend/main.py` (WSSubscriptionManager 생성 시 환경 기반 max_subscriptions 전달)

**Step 1: scheduler.py -- REALTIME_CACHE_TTL 변경**
- `REALTIME_CACHE_TTL = 5` -> `REALTIME_CACHE_TTL = 10` (42줄)
- 검증: `docker compose exec backend python -c "from modules.collector.scheduler import REALTIME_CACHE_TTL; assert REALTIME_CACHE_TTL == 10; print('OK')"`
- 예상: OK

**Step 2: trade_strength.py -- reset_all + warmup_until 지원**
- `TradeStrengthCalculator`에 `self._warmup_until: dict[str, float] = {}` 추가 (종목별 웜업 종료 시점)
- `set_warmup(self, stock_code: str, duration: float = 5.0) -> None`: `self._warmup_until[stock_code] = time.time() + duration` 설정
- `set_warmup_all(self, duration: float = 5.0) -> None`: 현재 _data에 있는 모든 종목에 웜업 설정
- `get_strength()` 수정: `stock_code in self._warmup_until`이고 `now < self._warmup_until[stock_code]`이면 중립값 50.0 반환. 만료되면 해당 키 삭제
- 검증: `docker compose exec backend python -c "from modules.collector.trade_strength import TradeStrengthCalculator; tc = TradeStrengthCalculator(); tc.set_warmup('005930', 5.0); assert tc.get_strength('005930') == 50.0; print('OK')"`
- 예상: OK

**Step 3: scheduler.py -- _secondary_screen WS 연결 상태 가드 추가**
- `__init__`에 `self._secondary_skip_count: int = 0` 추가
- `_secondary_screen()` 시작부에 WS 연결 상태 확인:
  ```
  if not self._ws_client.connected:
      self._secondary_skip_count += 1
      logger.warning("2차 스크리닝 스킵: WS 미연결 (연속 %d회)", self._secondary_skip_count)
      if self._secondary_skip_count >= 3 and self._telegram_bot:
          await self._telegram_bot.send_notification(
              "<b>[경고]</b> 2차 스크리닝 연속 %d회 스킵\nWS 미연결 상태 지속" % self._secondary_skip_count
          )
      return {"candidates": 0, "passed": 0, "skipped": True, "reason": "ws_disconnected"}
  ```
- 정상 실행 시 `self._secondary_skip_count = 0` 리셋 (기존 로직 끝에)
- 검증: 코드 리뷰 확인

**Step 4: scheduler.py -- WS 재연결 실패 시 텔레그램 긴급 알림 콜백 등록**
- `_market_open()` 메서드에서 `self._ws_client.connect()` 호출 전에:
  ```
  self._ws_client.set_on_ws_failure(self._on_ws_reconnect_failure)
  ```
- 새 메서드 `_on_ws_reconnect_failure(self)`:
  ```
  async def _on_ws_reconnect_failure(self):
      logger.error("WS 재연결 최대 실패 -- 장중 실시간 파이프라인 중단")
      await self._send_failure_alert("ws_reconnect", "WebSocket 재연결 7회 실패. 장중 2차 스크리닝 중단 상태.")
  ```
- 기존 `_send_failure_alert(step, error)` 재사용
- 검증: 코드 리뷰 확인

**Step 5: scheduler.py -- 재연결 후 체결강도 웜업 연결**
- `_ws_client`의 on_data 콜백 체인에서 직접 처리하기보다, _reconnect 성공 후 웜업 설정이 필요
- 방법: `KISWebSocketClient`에 `self._on_reconnect_success: Callable | None = None` 추가 + `set_on_reconnect_success()` 메서드
- _reconnect() 성공 직후 (구독 복원 완료 후) 콜백 호출
- scheduler._market_open()에서 등록:
  ```
  self._ws_client.set_on_reconnect_success(self._on_ws_reconnect_success)
  ```
- 새 메서드 `_on_ws_reconnect_success(self)`:
  ```
  async def _on_ws_reconnect_success(self):
      self._trade_strength.set_warmup_all(5.0)
      logger.info("WS 재연결 성공: 체결강도 5초 웜업 설정")
  ```
- 주의: kis_ws.py에 on_reconnect_success 콜백 추가 필요 (Task 2 파일에 추가 변경)
- 검증: 코드 리뷰 확인

**Step 6: main.py -- WSSubscriptionManager 생성 시 환경 기반 max_subscriptions 전달**
- main.py에서 WSSubscriptionManager 생성부를 찾아 `max_subscriptions=env.max_ws_subscriptions` 전달
- 기존: `WSSubscriptionManager(ws_client=ws_client)` (기본값 35 사용)
- 변경: `WSSubscriptionManager(ws_client=ws_client, max_subscriptions=env.max_ws_subscriptions)`
- env는 `get_current_environment()`에서 이미 가져오고 있을 것 (확인 필요)
- 검증: `docker compose exec backend python -c "print('main import OK')"` (import 에러 없음)

**Step 7: 커밋**
```
git add backend/modules/collector/ws_manager.py backend/modules/collector/scheduler.py backend/modules/collector/trade_strength.py backend/main.py backend/core/clients/kis_ws.py
git commit -m "feat(phase5.2-sprint1): task3 -- 캐시 TTL 10초 + 2차 스크리닝 WS 가드 + 체결강도 웜업 + WS 실패 알림"
```

**완료 기준:**
- ✅ REALTIME_CACHE_TTL == 10
- ✅ 체결강도 웜업 5초 동작
- ✅ 2차 스크리닝 WS 미연결 시 스킵 + 연속 3회 텔레그램 경고
- ✅ WS 재연결 실패 시 텔레그램 긴급 알림
- ✅ WSSubscriptionManager max가 환경 기반으로 주입

---

### Task 4: 테스트 업데이트 + 통합 검증

**Files:**
- Modify: `backend/tests/test_kis_ws.py` (재연결 딜레이/실패 콜백/close code 테스트 추가, 기존 백오프 테스트 수정)
- Create: `backend/tests/test_ws_stability.py` (환경별 구독 제한 + 2차 스크리닝 WS 가드 + 체결강도 웜업 통합 테스트)

**Step 1: test_kis_ws.py -- 기존 테스트 수정**
- `test_connect_websocket_url`: ping_interval=30에 ping_timeout=10 추가 검증
  - 기존: `mock_connect.assert_awaited_once_with(PAPER.ws_url, ping_interval=30)`
  - 변경: `mock_connect.assert_awaited_once_with(PAPER.ws_url, ping_interval=30, ping_timeout=10)`
- `test_reconnect_exponential_backoff`: 백오프 값 변경
  - 기존: `assert sleep_calls == [1, 2, 4, 8, 16]` (5회, BACKOFF_BASE=1)
  - 변경: `assert sleep_calls == [2, 4, 8, 16, 32, 64, 128]` (7회, BACKOFF_BASE=2)
  - MAX_RECONNECT_ATTEMPTS=7이므로 `assert len(sleep_calls) == 7`
- `test_reconnect_resubscribes`: 구독 복원 딜레이 검증
  - asyncio.sleep mock에서 호출 횟수 확인 (종목 간 딜레이 호출 존재)
- 검증: `docker compose exec backend pytest tests/test_kis_ws.py -v`
- 예상: PASS

**Step 2: test_kis_ws.py -- 신규 테스트 추가**
- `test_reconnect_calls_failure_callback`: 최대 실패 후 on_ws_failure 콜백 호출 검증
  - client.set_on_ws_failure(mock_callback) 등록 후 전체 실패 시 mock_callback 호출 확인
- `test_reconnect_calls_success_callback`: 재연결 성공 시 on_reconnect_success 콜백 호출 검증
- `test_receive_loop_logs_close_code`: ConnectionClosed 예외에서 code/reason 로깅 검증
- 검증: `docker compose exec backend pytest tests/test_kis_ws.py -v`
- 예상: PASS

**Step 3: test_ws_stability.py -- 통합 테스트 생성**
- `test_trade_strength_warmup`: set_warmup 후 get_strength가 50.0 반환, 시간 경과 후 정상값 반환
- `test_trade_strength_set_warmup_all`: set_warmup_all이 모든 기존 종목에 웜업 적용
- `test_scheduler_secondary_screen_ws_guard`: WS 미연결 시 _secondary_screen이 스킵 반환
- `test_scheduler_secondary_screen_skip_counter`: 연속 3회 스킵 시 텔레그램 경고 발송 검증
- `test_ws_manager_env_max_subscriptions`: PAPER 환경에서 25종목 상한 적용 검증
- 검증: `docker compose exec backend pytest tests/test_ws_stability.py -v`
- 예상: PASS

**Step 4: 전체 pytest 회귀 검증**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (기존 테스트 회귀 없음)

**Step 5: 커밋**
```
git add backend/tests/test_kis_ws.py backend/tests/test_ws_stability.py
git commit -m "feat(phase5.2-sprint1): task4 -- 재연결 딜레이/실패 콜백/WS 가드/웜업 테스트"
```

**완료 기준:**
- ✅ 기존 test_kis_ws.py 수정 후 통과
- ✅ 신규 test_ws_stability.py 전체 통과
- ✅ pytest 전체 회귀 없음 (751 passed)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS |
| KISEnvironment 필드 | `docker compose exec backend python -c "from core.clients.kis_config import PAPER; print(PAPER.max_ws_subscriptions, PAPER.ws_reconnect_delay)"` | `25 0.5` |
| 재연결 상수 | `docker compose exec backend python -c "from core.clients.kis_ws import MAX_RECONNECT_ATTEMPTS, BACKOFF_BASE; print(MAX_RECONNECT_ATTEMPTS, BACKOFF_BASE)"` | `7 2` |
| 캐시 TTL | `docker compose exec backend python -c "from modules.collector.scheduler import REALTIME_CACHE_TTL; print(REALTIME_CACHE_TTL)"` | `10` |
| 체결강도 웜업 | `docker compose exec backend python -c "from modules.collector.trade_strength import TradeStrengthCalculator; tc=TradeStrengthCalculator(); tc.set_warmup('005930'); print(tc.get_strength('005930'))"` | `50.0` |
