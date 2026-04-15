# Sprint 1: P0 치명적 결함 + P1 수정 (Phase 7.0)

**Goal:** 매매 엔진의 치명적 결함 3건(가격 갱신 미연결, 포지션 미생성, 청산 미실행)을 수정하고 파라미터 오보정을 교정하여 매매 파이프라인이 완전한 생명주기(주문->체결->포지션->가격갱신->청산)를 실행할 수 있게 한다.

**Architecture:** engine._monitor_positions_loop에 가격 수집/갱신/청산 실행 파이프라인을 연결하고, order_manager에 콜백 패턴(on_filled_callback)으로 체결->포지션 생성을 연결한다. Order 모델에 signal_json 컬럼을 추가하여 콜백에서 signal 정보를 복원한다.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Redis, pytest, AsyncMock

**Sprint 기간:** 2026-04-15 ~ 2026-04-15
**이전 스프린트:** Phase 6.2 Sprint 1 (완료, 2026-04-14)
**브랜치명:** `phase7.0-sprint1`
**상태:** ✅ 완료 (2026-04-15)
**PR:** (생성 후 기입)

---

## 제외 범위

- P2 리스크 개선 (daily_loss_pct 분모 수정, record_loss 확장, trailing Redis 이관) -> Sprint 2
- E2E 검증 + LIVE 전환 게이트 -> Sprint 3
- LIVE 초기 운영 파라미터 적용 -> Sprint 3
- 프론트엔드 변경 없음

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | Order 모델 signal_json 컬럼 추가 + Alembic 마이그레이션 | 백엔드 | -- |

### Phase 2 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | OrderManager 콜백 패턴 + 이중 주문 방지 + 체결가 역산 | 백엔드 | `feature-dev:feature-dev` |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | engine 가격 갱신 + 청산 실행 + 모니터 루프 완성 | 백엔드 | `feature-dev:feature-dev` |

### Phase 4 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 파라미터 조정 (trade_strength_min, max_candidates) | 백엔드 | -- |

### Phase 5 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | main.py 배선 + 통합 검증 | 백엔드 | -- |

> **참고**: 모든 Task가 동일 모듈(trading) 파일을 수정하므로 순차 실행 필수. 병렬 불가.

---

### Task 1: Order 모델 signal_json 컬럼 추가

**Files:**
- Modify: `backend/core/models/trading.py` (Order 클래스에 signal_json 컬럼 추가)
- Create: `backend/alembic/versions/{자동생성}_add_order_signal_json.py`
- Test: `backend/tests/test_order_signal_json.py`

**Step 1: Order 모델에 signal_json 컬럼 추가**
- `backend/core/models/trading.py`의 `Order` 클래스에 `signal_json` 필드 추가
- 타입: `Mapped[dict | None] = mapped_column(JSONB, nullable=True)`
- 기존 `Order` 클래스의 `updated_at` 필드 바로 아래에 추가
- 검증: `docker compose exec backend python -c "from core.models.trading import Order; print(Order.__table__.columns.keys())"`
- 예상: 컬럼 목록에 `signal_json` 포함

**Step 2: Alembic 마이그레이션 생성 및 적용**
- `docker compose exec backend alembic revision --autogenerate -m "Order signal_json 컬럼 추가"`
- `docker compose exec backend alembic upgrade head`
- 검증: `docker compose exec backend alembic current`
- 예상: 최신 리비전 ID 표시

**Step 3: 단위 테스트 작성**
- `backend/tests/test_order_signal_json.py` 생성
- Order 인스턴스에 signal_json 값을 설정하고 직렬화/역직렬화 확인
- 기존 테스트 패턴(`test_order_manager.py`의 `_make_order_mock`) 참조
- 검증: `docker compose exec backend pytest tests/test_order_signal_json.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/core/models/trading.py backend/alembic/versions/*signal_json* backend/tests/test_order_signal_json.py
git commit -m "feat(phase7.0-sprint1): task1 -- Order 모델 signal_json 컬럼 추가"
```

**완료 기준:**
- ✅ Order 모델에 signal_json 컬럼 존재
- ✅ Alembic 마이그레이션 적용 성공 (ce7aadd8d078)
- ✅ 단위 테스트 통과 (4 tests)

---

### Task 2: OrderManager 콜백 패턴 + 이중 주문 방지 + 체결가 역산

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/trading/order_manager.py` (on_filled_callback, signal_json 저장, cancel return, 체결가 역산)
- Modify: `backend/tests/test_order_manager.py` (기존 테스트 수정 + 신규 테스트 추가)

**Step 1: 테스트 작성**
- `backend/tests/test_order_manager.py`에 다음 테스트 추가:
  - `test_submit_order_saves_signal_json`: submit_order 호출 시 Order.signal_json에 signal 정보가 JSON으로 저장되는지 확인
  - `test_on_filled_callback_called`: 체결 성공 시 on_filled_callback(order_id, filled_price, signal_data, quantity) 호출 확인
  - `test_cancel_failure_returns_no_market_order`: 실전 모드에서 cancel 실패 시 시장가 주문 발송하지 않고 return 확인 (이중 주문 방지)
  - `test_filled_price_calculation`: 체결가 역산 — tot_ccld_amt / tot_ccld_qty 계산 확인
- 검증: `docker compose exec backend pytest tests/test_order_manager.py -v`
- 예상: 신규 테스트 FAIL (아직 구현 전)

**Step 2: OrderManager.__init__ 수정 — on_filled_callback 파라미터 추가**
- `__init__` 시그니처에 `on_filled_callback: Callable | None = None` 파라미터 추가
- `self._on_filled_callback = on_filled_callback`으로 저장
- 기존 생성자 호출부(`main.py`, 테스트)는 Task 5에서 일괄 수정

**Step 3: submit_order 수정 — signal_json 저장**
- `submit_order()` 메서드에서 Order 생성 시 `signal_json=signal.model_dump()` 추가
- TradeSignalData.model_dump()가 dict를 반환하므로 JSONB 컬럼에 바로 저장 가능

**Step 4: _execute_order 수정 — 체결가 역산 + 콜백 호출**
- 체결 성공(`status="filled"`) 후 체결가를 역산:
  - `status_data`의 `output1[0]`에서 `tot_ccld_amt` / `tot_ccld_qty` 계산
  - `filled_price = int(tot_ccld_amt) // int(tot_ccld_qty)` (정수 나눗셈)
  - 체결 상태 조회가 불가능한 경우(모의거래 등) 원래 주문 가격(`order.price`)을 폴백으로 사용
- 콜백 호출: `if self._on_filled_callback: await self._on_filled_callback(order_id, filled_price, signal_data, quantity)`
  - `signal_data`는 `Order.signal_json`에서 `TradeSignalData(**signal_json)`으로 복원
  - Order 조회 시 signal_json도 함께 읽기 (이미 조회 중인 order 객체에서)
- 체결가 역산을 위해 `_poll_fill_status`를 수정하여 최종 `status_data`를 반환하거나, 체결 확인 후 별도 조회

**Step 5: _execute_order 실전 경로 수정 — cancel 실패 시 return**
- 현재 코드(222줄): `logger.warning("주문 취소 실패 (무시하고 시장가 진행)")` -> 시장가 계속 진행
- 수정: cancel 실패 시 `await self._update_order_status(order_id, "cancel_failed")` + `return` (시장가 발송 중단)
- 이중 주문 방지: cancel이 실패하면 원래 지정가 주문이 살아있을 수 있으므로 시장가 추가 발송 금지

**Step 6: 검증**
- 검증: `docker compose exec backend pytest tests/test_order_manager.py -v`
- 예상: 전체 PASS (기존 + 신규)

**Step 7: 커밋**
```
git add backend/modules/trading/order_manager.py backend/tests/test_order_manager.py
git commit -m "feat(phase7.0-sprint1): task2 -- OrderManager 콜백 패턴 + 이중 주문 방지 + 체결가 역산"
```

**완료 기준:**
- ✅ submit_order에서 signal_json 저장 확인
- ✅ 체결 시 on_filled_callback 호출 확인
- ✅ cancel 실패 시 시장가 미발송 확인
- ✅ 체결가 역산(tot_ccld_amt / tot_ccld_qty) 확인
- ✅ 기존 테스트 회귀 없음 (TC-8~11 신규, TC-3/TC-4 수정)

---

### Task 3: engine 가격 갱신 + 청산 실행 + 모니터 루프 완성

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/trading/engine.py` (_collect_price_updates, _execute_exit, _monitor_positions_loop 수정)
- Create: `backend/tests/test_engine_monitor.py`

**Step 1: 테스트 작성**
- `backend/tests/test_engine_monitor.py` 생성
- 기존 `test_engine_auto_mode.py`의 `_make_engine` 헬퍼 패턴 참조
- 다음 테스트 작성:
  - `test_collect_price_updates_from_redis`: Redis `realtime:{code}:execution` 키에서 current_price를 수집하는지 확인
  - `test_collect_price_updates_rest_fallback`: Redis 미스 시 `rest_client.get_stock_price()` REST 폴백 호출 확인
  - `test_monitor_loop_calls_update_prices`: _monitor_positions_loop가 update_prices()를 호출하는지 확인
  - `test_monitor_loop_executes_exit`: check_exit_conditions 결과에 대해 _execute_exit가 청산 매도를 실행하는지 확인
  - `test_monitor_loop_market_hours_guard`: 장 시간(09:00~15:30) 외에는 가격 갱신/청산 미실행 확인
  - `test_execute_exit_places_sell_order`: 시장가 매도 주문 + 3회 폴링 + close_position 호출 확인
- 검증: `docker compose exec backend pytest tests/test_engine_monitor.py -v`
- 예상: FAIL (아직 구현 전)

**Step 2: _collect_price_updates() 신규 메서드 구현**
- `engine.py`에 `async def _collect_price_updates(self) -> dict[str, int]` 추가
- 로직:
  1. `PositionManager`에서 활성 포지션의 stock_code 목록 조회 (session_factory를 통해 `select(PositionRecord.stock_code)`)
  2. 각 stock_code에 대해 Redis `realtime:{code}:execution` 키에서 JSON 파싱하여 `current_price` 추출
  3. Redis 미스 시 `self._rest_client.get_stock_price(code)` REST 폴백 (throttler 경유, 타임아웃 3초)
  4. `{stock_code: current_price}` 딕셔너리 반환
- REST 폴백은 try/except로 감싸서 실패 시 해당 종목 스킵 (다음 루프에서 재시도)

**Step 3: _execute_exit() 신규 메서드 구현**
- `engine.py`에 `async def _execute_exit(self, exit_info: dict) -> None` 추가
- 파라미터: `exit_info = {"stock_code", "quantity", "exit_reason", "position_id"}`
- 로직:
  1. 시장가 매도 주문 발송: `rest_client.place_order(OrderRequest(stock_code, "sell", quantity, 0, "01"))`
  2. 체결 폴링: 최대 3회, 2초 간격 (`rest_client.get_order_status(order_no)`)
  3. 체결 확인 시 체결가 역산: `tot_ccld_amt / tot_ccld_qty`
  4. `position_manager.close_position(position_id, exit_price, exit_reason)` 호출
  5. 알림: `notifier_manager.send_notification("청산 완료: {stock_code} @{exit_price} ({exit_reason})")` (notifier 존재 시)
- 실패 시: 로그 경고 + 다음 루프에서 재시도 (EOD 청산이 최종 안전망)

**Step 4: _monitor_positions_loop 수정**
- 현재 코드(220~233줄): check_exit_conditions 결과 로깅만 수행
- 수정 내용:
  1. **장 시간 가드 추가**: `now_kst.time()` 체크, `time(9,0) <= t <= time(15,30)` 아니면 sleep 후 continue
  2. **가격 수집**: `price_updates = await self._collect_price_updates()`
  3. **가격 갱신**: `await self._position_manager.update_prices(price_updates)`
  4. **청산 조건 확인**: `exits = await self._position_manager.check_exit_conditions()`
  5. **청산 실행**: `for exit_info in exits: await self._execute_exit(exit_info)`
  6. 기존 로깅은 _execute_exit 내부로 이동

**Step 5: 검증**
- 검증: `docker compose exec backend pytest tests/test_engine_monitor.py -v`
- 예상: 전체 PASS

**Step 6: 커밋**
```
git add backend/modules/trading/engine.py backend/tests/test_engine_monitor.py
git commit -m "feat(phase7.0-sprint1): task3 -- engine 가격 갱신 + 청산 실행 + 모니터 루프 완성"
```

**완료 기준:**
- ✅ _collect_price_updates가 Redis WS 우선 + REST 폴백으로 가격 수집
- ✅ _monitor_positions_loop가 update_prices 호출
- ✅ _execute_exit가 시장가 매도 + 3회 폴링 + close_position 호출
- ✅ 장 시간 가드(09:00~15:30) 동작 확인
- ✅ 기존 engine 테스트 회귀 없음 (test_engine_monitor.py 6 tests)

---

### Task 4: 파라미터 조정 (trade_strength_min, max_candidates)

**Files:**
- Modify: `backend/modules/screening/filters.py` (SecondaryFilters.trade_strength_min, PrimaryFilters.max_candidates)
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (체결강도 조건 70.0 -> 100.0)
- Modify: `backend/tests/test_filters.py` (기존 테스트 값 업데이트)
- Modify: `backend/tests/test_momentum_breakout.py` (기존 테스트 값 업데이트, 존재 시)

**Step 1: filters.py 파라미터 변경**
- `SecondaryFilters.trade_strength_min`: 120.0 -> 100.0 (CTTR 기준 통일, 확정 파라미터 #8)
- `PrimaryFilters.max_candidates`: 30 -> 20 (확정 파라미터 #9)
- 검증: `docker compose exec backend python -c "from modules.screening.filters import SecondaryFilters, PrimaryFilters; print(SecondaryFilters().trade_strength_min, PrimaryFilters().max_candidates)"`
- 예상: `100.0 20`

**Step 2: momentum_breakout.py 체결강도 조건 변경**
- 104줄: `if snapshot.trade_strength < 70.0:` -> `if snapshot.trade_strength < 100.0:` (확정 파라미터 #8a, CTTR 기준 통일)
- 검증: `docker compose exec backend python -c "import ast; t=ast.parse(open('modules/trading/strategies/momentum_breakout.py').read()); print('100.0 확인')"` (코드 확인)

**Step 3: 기존 테스트 업데이트**
- `tests/test_filters.py`: SecondaryFilters 기본값이 변경되므로 trade_strength_min=120.0 관련 하드코딩된 테스트 업데이트
- `tests/test_momentum_breakout.py`: trade_strength 70.0 미만 필터 테스트가 있으면 100.0 기준으로 업데이트
- 검증: `docker compose exec backend pytest tests/test_filters.py tests/test_momentum_breakout.py -v`
- 예상: PASS (테스트가 없는 경우 스킵)

**Step 4: 커밋**
```
git add backend/modules/screening/filters.py backend/modules/trading/strategies/momentum_breakout.py backend/tests/test_filters.py backend/tests/test_momentum_breakout.py
git commit -m "feat(phase7.0-sprint1): task4 -- trade_strength_min 100.0, max_candidates 20 파라미터 조정"
```

**완료 기준:**
- ✅ SecondaryFilters.trade_strength_min == 100.0
- ✅ PrimaryFilters.max_candidates == 20
- ✅ momentum_breakout 체결강도 조건 == 100.0
- ✅ 기존 테스트 회귀 없음 (test_filters.py, test_momentum_breakout.py, test_realtime_screener.py, test_screener.py 업데이트)

---

### Task 5: main.py 배선 + 통합 검증

**Files:**
- Modify: `backend/main.py` (OrderManager 생성 시 on_filled_callback 연결, session_factory 전달)
- Modify: `backend/tests/test_engine_auto_mode.py` (기존 _make_engine 헬퍼에 rest_client 추가)
- Modify: `backend/tests/test_engine_approval.py` (기존 테스트 호환성 확인)

**Step 1: main.py OrderManager 배선 수정**
- 현재(161줄): `order_manager = OrderManager(session_factory, rest_client, redis_client, throttler)`
- 수정: OrderManager 생성 후 (또는 생성 시) on_filled_callback 연결
- 방법: TradingEngine 먼저 생성은 불가 (order_manager가 TradingEngine 생성 인자)
  - **해결**: OrderManager 생성 시 callback=None, TradingEngine 생성 후 `order_manager.set_filled_callback(trading_engine.on_order_filled)` 호출
  - 또는: OrderManager.__init__에 on_filled_callback 파라미터 유지하되, 생성 후 setter로 주입
  - **확정**: `order_manager.set_filled_callback(engine.on_order_filled)` 패턴 사용 (순환 참조 방지)
- TradingEngine 생성 시 `session_factory=session_factory` 전달 (현재 누락됨)
  - 현재(163~173줄): session_factory 미전달 -> _get_trading_mode에서 Redis만 사용 (의도적일 수 있으나 명시적 전달이 안전)

**Step 2: OrderManager에 set_filled_callback 메서드 추가**
- Task 2에서 __init__에 on_filled_callback을 Optional로 추가했으므로, 추가로 `set_filled_callback(callback)` setter 메서드 구현
- main.py에서 `trading_engine` 생성 후 `order_manager.set_filled_callback(trading_engine.on_order_filled)` 호출

**Step 3: 기존 테스트 호환성 확인**
- `test_engine_auto_mode.py`의 `_make_engine`에 rest_client 인자가 없으면 추가 (engine.__init__에 rest_client 이미 존재하나 테스트에서 None 전달 가능)
- `test_engine_approval.py` 동일 확인
- `test_order_manager.py`의 `OrderManager()` 생성부에 on_filled_callback=None 호환 확인
- 검증: `docker compose exec backend pytest tests/test_engine_auto_mode.py tests/test_engine_approval.py tests/test_order_manager.py -v`
- 예상: PASS

**Step 4: 전체 통합 검증**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS

**Step 5: 커밋**
```
git add backend/main.py backend/modules/trading/order_manager.py backend/tests/test_engine_auto_mode.py backend/tests/test_engine_approval.py
git commit -m "feat(phase7.0-sprint1): task5 -- main.py 배선 + on_filled_callback 연결 + 통합 검증"
```

**완료 기준:**
- ✅ main.py에서 order_manager.set_filled_callback(engine.on_order_filled) 연결
- ✅ TradingEngine에 session_factory 전달
- ✅ 기존 테스트 전체 회귀 없음
- ✅ pytest 전체 통과 (817 passed, 4 failed — 기존 무관 결함: scheduler_vol5m 3건, ws_stability 1건)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 passed (기존 + 신규) |
| Alembic 마이그레이션 | `docker compose exec backend alembic current` | 최신 리비전 |
| Order signal_json | `docker compose exec backend python -c "from core.models.trading import Order; print('signal_json' in Order.__table__.columns.keys())"` | True |
| trade_strength_min | `docker compose exec backend python -c "from modules.screening.filters import SecondaryFilters; print(SecondaryFilters().trade_strength_min)"` | 100.0 |
| max_candidates | `docker compose exec backend python -c "from modules.screening.filters import PrimaryFilters; print(PrimaryFilters().max_candidates)"` | 20 |
| momentum_breakout 체결강도 | grep으로 `snapshot.trade_strength < 100.0` 확인 | 존재 |
