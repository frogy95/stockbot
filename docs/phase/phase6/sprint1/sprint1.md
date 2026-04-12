# Sprint 1: 치명적 버그 수정 + 최소 방어 (Phase 6)

**Goal:** 2026-04-10 프로덕션 장애의 근본 원인 5건(WS ConcurrencyError, 좀비 연결, 가드 조건 오류, 장중 연결 실패 무시, recovery 판단 오류)을 수정하고, is_trading_day 가드 + WS open_timeout + subscribe None 가드로 최소 방어를 추가한다.

**Architecture:** kis_ws.py의 `_reconnect()`에 기존 `_receive_task` cancel+await 패턴을 적용하고 구독 복원을 try/except로 감싸서 좀비 연결을 방지한다. ws_manager.py의 가드 조건을 `and`에서 `or`로 변경한다. scheduler.py의 `_market_open()`에 텔레그램 알림을, `_market_open_recovery()`에 `_ws_client.connected` 판단을, `_run_scheduled_pipeline()`과 `_market_open()`에 `is_trading_day()` 가드를 추가한다.

**Tech Stack:** Python 3.12, asyncio, websockets, APScheduler, pytest

**Sprint 기간:** 2026-04-12 ~ 2026-04-12
**상태:** ✅ 완료
**이전 스프린트:** Phase 5.2 Sprint 1 (WS 재연결 안정화, PR #106)
**브랜치명:** `phase6-sprint1`

---

## 제외 범위

- KIS REST 재시도/백오프 (Sprint 2)
- recovery 단계적 재시도 09:05/09:10/09:15 (Sprint 2)
- `_premarket_collect()` 예외 경로 KIS 폴백 (Sprint 2)
- 나머지 핸들러 `is_trading_day()` 가드 — `_market_close`, `_premarket_retry`, `_market_open_recovery` (Sprint 2)
- WS 완전 실패 시 REST 폴백 가격 감시 (Phase 6.1)
- 프론트엔드 변경 없음

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | kis_ws.py _reconnect() ConcurrencyError + 좀비 연결 + open_timeout + subscribe None 가드 | 백엔드 | `systematic-debugging` |

### Phase 2 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | ws_manager.py 가드 조건 and -> or | 백엔드 | -- |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | scheduler.py _market_open() 에러 처리 + _market_open_recovery() 판단 기준 + is_trading_day() 가드 | 백엔드 | -- |

### Phase 4 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 통합 검증 (기존 테스트 회귀 + 신규 테스트 전체 실행) | 전체 | -- |

> Task 1 -> Task 2 -> Task 3 순차 실행. Task 1은 kis_ws.py만, Task 2는 ws_manager.py만, Task 3는 scheduler.py만 수정하므로 파일 소유권 충돌 없으나, Task 3의 `_market_open_recovery()`가 `_ws_client.connected`를 참조하므로 Task 1 완료 후 실행한다.

---

### Task 1: kis_ws.py _reconnect() ConcurrencyError + 좀비 연결 + open_timeout + subscribe None 가드

**skill:** `systematic-debugging`

**Files:**
- Modify: `backend/core/clients/kis_ws.py` (4개 버그 수정)
- Modify: `backend/tests/test_kis_ws.py` (신규 테스트 4건 추가)

**Step 1: 테스트 작성 (4건)**
- `backend/tests/test_kis_ws.py`에 다음 테스트 추가:

1. `test_reconnect_cancels_existing_receive_task`:
   - `connect()` 후 `_receive_task`가 존재하는 상태에서 `_reconnect()` 호출
   - 기존 `_receive_task.cancel()`이 호출되었는지 확인
   - 기존 task await(CancelledError 처리)가 완료되었는지 확인
   - 재연결 후 `_receive_task`가 새 task인지 확인

2. `test_reconnect_starts_receive_loop_on_subscription_failure`:
   - 구독이 있는 상태에서 `_reconnect()` 호출
   - websockets.connect 성공, subscribe에서 Exception 발생
   - subscribe 실패에도 불구하고 `_receive_task`가 생성되었는지 확인 (좀비 방지)
   - `_connected`가 True인지 확인

3. `test_ws_connect_open_timeout`:
   - `connect()` 호출 시 `websockets.connect()`에 `open_timeout=10`이 전달되는지 확인
   - `_reconnect()` 내부의 `websockets.connect()` 호출에도 `open_timeout=10`이 전달되는지 확인

4. `test_ws_subscribe_none_guard`:
   - `_ws=None` 상태(미연결)에서 `subscribe("005930")` 호출
   - AttributeError 없이 조용히 return (예외 미발생)
   - `_subscriptions`에 추가되지 않는지 확인

- 검증: `docker compose exec backend pytest tests/test_kis_ws.py -v -k "test_reconnect_cancels or test_reconnect_starts or test_ws_connect_open or test_ws_subscribe_none"`
- 예상: FAIL (기능 미구현)

**Step 2: _reconnect() ConcurrencyError 수정 (확정 파라미터 #1)**
- `backend/core/clients/kis_ws.py`의 `_reconnect()` 메서드 시작 부분에 기존 `_receive_task` cancel+await 추가
- `disconnect()` 메서드(78~87줄)의 cancel+await 패턴을 그대로 적용:
  ```
  if self._receive_task is not None:
      self._receive_task.cancel()
      try:
          await self._receive_task
      except asyncio.CancelledError:
          pass
      self._receive_task = None
  ```
- 이 코드를 `_reconnect()` 시작부 `subscriptions_snapshot = set(self._subscriptions)` 직전에 삽입
- 검증: `docker compose exec backend pytest tests/test_kis_ws.py::test_reconnect_cancels_existing_receive_task -v`
- 예상: PASS

**Step 3: _reconnect() 좀비 연결 수정 (확정 파라미터 #5)**
- `_reconnect()` 내부의 구독 복원 코드(199~211줄)를 try/except로 감싸기
- 구독 복원 실패 시에도 `_receive_task = asyncio.create_task(self._receive_loop())`는 반드시 실행
- 구독 복원 실패 시 텔레그램 경고를 위해 `_on_ws_failure` 콜백은 호출하지 않되, 로그에 경고 기록
- 구조 변경:
  ```
  # 구독 복원 try/except (좀비 방지)
  try:
      # 기존 구독 복원 로직 (199~211줄)
  except Exception:
      logger.exception("구독 복원 실패 — 수신 루프는 시작")

  # 수신 루프는 구독 복원 성공/실패 관계없이 항상 시작
  self._receive_task = asyncio.create_task(self._receive_loop())
  ```
- 검증: `docker compose exec backend pytest tests/test_kis_ws.py::test_reconnect_starts_receive_loop_on_subscription_failure -v`
- 예상: PASS

**Step 4: connect()와 _reconnect()에 open_timeout=10 추가 (확정 파라미터 #11)**
- `connect()` 메서드(69~73줄)의 `websockets.connect()` 호출에 `open_timeout=10` 추가:
  ```
  self._ws = await websockets.connect(
      self._env.ws_url,
      ping_interval=30,
      ping_timeout=10,
      open_timeout=10,
  )
  ```
- `_reconnect()` 메서드 내부의 `websockets.connect()` 호출(191~195줄)에도 동일하게 `open_timeout=10` 추가
- 검증: `docker compose exec backend pytest tests/test_kis_ws.py::test_ws_connect_open_timeout -v`
- 예상: PASS

**Step 5: subscribe()에 _ws None 가드 추가 (확정 파라미터 #12)**
- `subscribe()` 메서드(95~100줄) 시작부에 `_ws is None` 가드 추가:
  ```
  async def subscribe(self, stock_code: str, tr_id: str = "H0STCNT0") -> None:
      if self._ws is None:
          logger.warning("WS 미연결 상태에서 구독 시도: %s (%s)", stock_code, tr_id)
          return
      msg = self._build_subscription_message(stock_code, tr_id, tr_type="1")
      ...
  ```
- `unsubscribe()`에도 동일 가드 추가 (102~107줄):
  ```
  async def unsubscribe(self, stock_code: str, tr_id: str = "H0STCNT0") -> None:
      if self._ws is None:
          logger.warning("WS 미연결 상태에서 구독 해제 시도: %s (%s)", stock_code, tr_id)
          return
      ...
  ```
- 가드 통과 시 `_subscriptions`에 추가하지 않음 (subscribe의 경우)
- 검증: `docker compose exec backend pytest tests/test_kis_ws.py::test_ws_subscribe_none_guard -v`
- 예상: PASS

**Step 6: 기존 테스트 회귀 확인**
- 검증: `docker compose exec backend pytest tests/test_kis_ws.py -v`
- 예상: 전체 PASS (기존 `test_connect_websocket_url`이 open_timeout 추가로 인해 assert 수정 필요 — `mock_connect.assert_awaited_once_with(PAPER.ws_url, ping_interval=30, ping_timeout=10, open_timeout=10)`)

**Step 7: 커밋**
```
git add backend/core/clients/kis_ws.py backend/tests/test_kis_ws.py
git commit -m "feat(phase6-sprint1): task1 -- _reconnect() ConcurrencyError/좀비 수정 + open_timeout + subscribe None 가드"
```

**완료 기준:**
- ✅ `test_reconnect_cancels_existing_receive_task` PASS
- ✅ `test_reconnect_starts_receive_loop_on_subscription_failure` PASS
- ✅ `test_ws_connect_open_timeout` PASS
- ✅ `test_ws_subscribe_none_guard` PASS
- ✅ 기존 test_kis_ws.py 전체 회귀 PASS

---

### Task 2: ws_manager.py 가드 조건 and -> or

**Files:**
- Modify: `backend/modules/collector/ws_manager.py` (45줄, 74줄 가드 조건 변경)
- Modify: `backend/tests/test_ws_manager.py` (신규 테스트 1건 추가)

**Step 1: 테스트 작성 (1건)**
- `backend/tests/test_ws_manager.py`에 추가:

1. `test_ws_manager_guard_or_condition`:
   - `_ws`가 유효하지만 `connected=False`인 상태에서 subscribe 시도
   - `or` 조건이므로 차단되어 False 반환 확인
   - `_ws=None`이지만 `connected=True`인 상태에서 subscribe 시도 (비정상)
   - `or` 조건이므로 차단되어 False 반환 확인
   - 기존 `test_ws_none_guard`는 `connected=False, ws_is_none=True`(둘 다 False) 케이스만 테스트하므로, 이 테스트는 "한쪽만 False"인 케이스를 커버

- 검증: `docker compose exec backend pytest tests/test_ws_manager.py -v -k "test_ws_manager_guard_or"`
- 예상: FAIL (현재 `and` 조건이므로 한쪽만 False면 통과)

**Step 2: 가드 조건 변경 (확정 파라미터 #2)**
- `backend/modules/collector/ws_manager.py` 45줄:
  - 변경 전: `if self._ws._ws is None and not self._ws.connected:`
  - 변경 후: `if self._ws._ws is None or not self._ws.connected:`
- 74줄도 동일 변경:
  - 변경 전: `if self._ws._ws is None and not self._ws.connected:`
  - 변경 후: `if self._ws._ws is None or not self._ws.connected:`
- 검증: `docker compose exec backend pytest tests/test_ws_manager.py -v`
- 예상: 전체 PASS

**Step 3: 커밋**
```
git add backend/modules/collector/ws_manager.py backend/tests/test_ws_manager.py
git commit -m "feat(phase6-sprint1): task2 -- ws_manager 가드 조건 and -> or 수정"
```

**완료 기준:**
- ✅ `test_ws_manager_guard_or_condition` PASS
- ✅ 기존 test_ws_manager.py 전체 회귀 PASS

---

### Task 3: scheduler.py _market_open() 에러 처리 + _market_open_recovery() 판단 기준 + is_trading_day() 가드

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (3개소 수정)
- Create: `backend/tests/test_scheduler_phase6.py` (신규 테스트 3건)

**Step 1: 테스트 작성 (3건)**
- `backend/tests/test_scheduler_phase6.py` 생성 (기존 test_scheduler.py의 `_make_scheduler` 패턴 재사용):

1. `test_market_open_failure_sends_telegram`:
   - `_make_scheduler()` 생성 후 `_telegram_bot` 설정
   - `ws_client.connect`가 Exception 발생하도록 mock
   - `_market_open()` 호출
   - `_telegram_bot.send_notification`이 호출되었는지 확인
   - 메시지에 `[장애]`와 `market_open` 문자열 포함 확인

2. `test_market_open_recovery_checks_connected`:
   - `_make_scheduler()` 생성
   - `ws_client.connected = False`, `ws_manager.count = 5` (구독은 있으나 연결 끊김)
   - `_market_open_recovery()` 호출
   - `ws_client.connect`가 호출되었는지 확인 (기존 코드는 count>0이면 스킵하므로 실패)

3. `test_scheduled_pipeline_skips_non_trading_day`:
   - `_make_scheduler()` 생성
   - `is_trading_day()`를 mock하여 False 반환
   - `_run_scheduled_pipeline()` 호출
   - `run_premarket_pipeline()`이 호출되지 않았는지 확인 (Redis PIPELINE_RUNNING_KEY 설정 안 됨)

- 검증: `docker compose exec backend pytest tests/test_scheduler_phase6.py -v`
- 예상: FAIL (기능 미구현)

**Step 2: _market_open() 에러 처리 개선 (확정 파라미터 #3)**
- `backend/modules/collector/scheduler.py`의 `_market_open()` 메서드(722~737줄):
  - 변경 전 (736~737줄):
    ```
    except Exception:
        logger.exception("WS 연결 실패")
    ```
  - 변경 후:
    ```
    except Exception as e:
        logger.exception("WS 연결 실패")
        await self._send_failure_alert("market_open", str(e))
    ```
- 검증: `docker compose exec backend pytest tests/test_scheduler_phase6.py::test_market_open_failure_sends_telegram -v`
- 예상: PASS

**Step 3: _market_open_recovery() 판단 기준 변경 (확정 파라미터 #4, #15)**
- `backend/modules/collector/scheduler.py`의 `_market_open_recovery()` 메서드(739~756줄):
  - 변경 전 (741~743줄):
    ```
    if self._ws_manager.count > 0:
        logger.info("market_open 복구 불필요: ws_subscriptions=%d", self._ws_manager.count)
        return
    ```
  - 변경 후:
    ```
    if self._ws_client.connected:
        logger.info("market_open 복구 불필요: ws_connected=True, subscriptions=%d", self._ws_manager.count)
        return
    ```
  - 744줄 로그도 업데이트:
    ```
    logger.warning("market_open 복구 시작: ws_connected=False (subscriptions=%d)", self._ws_manager.count)
    ```
- 검증: `docker compose exec backend pytest tests/test_scheduler_phase6.py::test_market_open_recovery_checks_connected -v`
- 예상: PASS

**Step 4: is_trading_day() 가드 추가 (확정 파라미터 #14)**
- `backend/modules/collector/scheduler.py` 상단에 import 추가:
  ```
  from core.trading_calendar import is_trading_day
  ```
- `_run_scheduled_pipeline()` 메서드(271~283줄) 시작부에 가드 추가:
  ```
  async def _run_scheduled_pipeline(self) -> None:
      """08:00 CronTrigger용 장전 파이프라인. 락 선점 후 체인 실행."""
      today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
      if not is_trading_day(today):
          logger.info("비거래일 스킵: step=premarket_pipeline date=%s", today)
          return
      existing = await self._redis.get(PIPELINE_RUNNING_KEY)
      ...
  ```
- `_market_open()` 메서드(722줄) 시작부에 가드 추가:
  ```
  async def _market_open(self) -> None:
      """09:00 WS 연결 + 구독 시작 + 2차 스크리닝 활성화."""
      today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
      if not is_trading_day(today):
          logger.info("비거래일 스킵: step=market_open date=%s", today)
          return
      logger.info("장중 시작: WS 연결")
      ...
  ```
- 검증: `docker compose exec backend pytest tests/test_scheduler_phase6.py::test_scheduled_pipeline_skips_non_trading_day -v`
- 예상: PASS

**Step 5: 기존 테스트 회귀 확인**
- 검증: `docker compose exec backend pytest tests/test_scheduler.py tests/test_scheduler_telegram_alert.py tests/test_scheduler_dependency.py tests/test_scheduler_retry.py -v`
- 예상: 전체 PASS

**Step 6: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler_phase6.py
git commit -m "feat(phase6-sprint1): task3 -- _market_open 텔레그램 알림 + recovery connected 판단 + is_trading_day 가드"
```

**완료 기준:**
- ✅ `test_market_open_failure_sends_telegram` PASS
- ✅ `test_market_open_recovery_checks_connected` PASS
- ✅ `test_scheduled_pipeline_skips_non_trading_day` PASS
- ✅ 기존 scheduler 테스트 전체 회귀 PASS

---

### Task 4: 통합 검증

**Files:**
- 수정 없음 (검증만 수행)

**Step 1: pytest 전체 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (신규 8건 포함)

**Step 2: 커밋 (필요 시)**
- 회귀 수정이 있었다면 해당 파일 커밋

**완료 기준:**
- ✅ pytest 전체 통과 (771 passed, 0 failed)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| kis_ws 테스트 | `docker compose exec backend pytest tests/test_kis_ws.py -v` | 전체 PASS (기존 + 신규 4건) |
| ws_manager 테스트 | `docker compose exec backend pytest tests/test_ws_manager.py -v` | 전체 PASS (기존 + 신규 1건) |
| scheduler Phase 6 테스트 | `docker compose exec backend pytest tests/test_scheduler_phase6.py -v` | 3 passed |
| 기존 scheduler 회귀 | `docker compose exec backend pytest tests/test_scheduler.py tests/test_scheduler_telegram_alert.py tests/test_scheduler_dependency.py tests/test_scheduler_retry.py -v` | 전체 PASS |
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS |
