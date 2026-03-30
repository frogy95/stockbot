# Sprint 1: 리스크/자금 관리 모듈 (Phase 3)

**Goal:** 매매 엔진의 안전장치인 리스크 매니저, 포지션 사이저, 당일 청산 강제 모듈을 구현하고, 매매 관련 DB 모델(trade_signals, orders, positions, trade_history)과 리스크 파라미터 시드를 선행 구축한다.

**Architecture:** settings 테이블에 리스크 파라미터를 시드하고, risk_manager가 주문 전 동기적으로 한도/비상 정지/쿨다운/시간대를 체크한다. position_sizer는 잔고와 일반/레버리지 구분에 따라 건당 투자금을 계산한다. eod_liquidator는 APScheduler 크론잡으로 14:50 시장가 강제 매도를 실행한다. 매매 관련 4개 DB 테이블은 Sprint 2에서 사용하지만 마이그레이션을 선행한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, APScheduler, pytest-asyncio

**Sprint 기간:** 2026-03-30 ~ 2026-03-30 ✅ 완료
**이전 스프린트:** Phase 2.6 Sprint 1 (pytest 통과, PR #27)
**브랜치명:** `phase3-sprint1`

---

## 제외 범위

- 매매 전략/신호 생성 (Sprint 2)
- 주문 실행/체결 폴링 (Sprint 2)
- 포지션 매니저 (손절/익절/트레일링 실시간 모니터링, Sprint 2)
- 텔레그램 알림/승인 (Sprint 3)
- 프론트엔드 대시보드 (Phase 4)
- 실제 한투 API 주문 호출 (eod_liquidator는 인터페이스만, 실제 주문은 Sprint 2의 order_manager를 통해)

## 실행 플랜

의존성: Task 1(DB 모델) -> Task 2(시드) -> Task 3/4(병렬) -> Task 5(API) -> Task 6(통합 테스트)

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 매매 관련 DB 모델 4개 테이블 + Alembic 마이그레이션 | 백엔드 | -- |
| Task 2 | 리스크 파라미터 시드 확장 | 백엔드 | -- |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | 리스크 매니저 (한도 체크/비상 정지/쿨다운/시간대 차단) | 백엔드 | -- |
| Task 4 | 포지션 사이저 (건당 투자금 계산) | 백엔드 | -- |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | 당일 청산 강제 (eod_liquidator) | 백엔드 | -- |
| Task 6 | 리스크 상태 조회 API + main.py 등록 | 백엔드 | -- |
| Task 7 | 통합 테스트 | 백엔드 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 Task 3, Task 4를 병렬 구현합니다.

---

### Task 1: 매매 관련 DB 모델 + Alembic 마이그레이션

**Files:**
- Create: `backend/core/models/trading.py`
- Modify: `backend/core/models/__init__.py` (trading 모델 import 추가)
- Create: `backend/alembic/versions/{hash}_매매_테이블_추가_trade_signals_orders_positions_trade_history.py` (autogenerate)
- Test: `backend/tests/test_trading_models.py`

**Step 1: 테스트 작성**
- `backend/tests/test_trading_models.py` 생성
- 4개 테이블(trade_signals, orders, positions, trade_history) 각각에 대해:
  - 모델 인스턴스 생성 + DB insert + select 검증
  - 필수 컬럼 NOT NULL 제약 검증
  - FK 관계 검증 (signal_id -> trade_signals.id 등)
- 검증: `docker compose exec backend pytest tests/test_trading_models.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 모델 구현**
- `backend/core/models/trading.py` 생성
- **TradeSignal** 모델:
  - 테이블명: `trade_signals`
  - 컬럼: `id`(PK), `stock_code`(String(10), FK stocks.stock_code), `signal_type`(String(10), buy/sell), `strategy_name`(String(50)), `confidence`(Float, 0~1), `reason`(JSONB), `entry_price`(Integer), `stop_loss`(Integer), `take_profit`(Integer), `status`(String(20), 기본값 "pending"), `created_at`(DateTime, server_default), `updated_at`(DateTime, onupdate)
- **Order** 모델:
  - 테이블명: `orders`
  - 컬럼: `id`(PK), `signal_id`(Integer, FK trade_signals.id, nullable), `stock_code`(String(10)), `order_type`(String(10), buy/sell), `order_no`(String(20), nullable, 한투 ODNO), `quantity`(Integer), `price`(Integer), `order_division`(String(10)), `status`(String(20), 기본값 "pending_approval"), `submitted_at`(DateTime, nullable), `filled_at`(DateTime, nullable), `created_at`(DateTime, server_default), `updated_at`(DateTime, onupdate)
- **PositionRecord** 모델:
  - 테이블명: `positions`
  - 컬럼: `id`(PK), `stock_code`(String(10), FK stocks.stock_code), `quantity`(Integer), `avg_price`(Integer), `current_price`(Integer, 기본값 0), `unrealized_pnl`(Integer, 기본값 0), `stop_loss`(Integer), `take_profit`(Integer), `trailing_activated`(Boolean, 기본값 False), `entry_time`(DateTime), `strategy_name`(String(50)), `created_at`(DateTime, server_default), `updated_at`(DateTime, onupdate)
  - UniqueConstraint: `stock_code` (활성 포지션은 종목당 1개)
- **TradeHistory** 모델:
  - 테이블명: `trade_history`
  - 컬럼: `id`(PK), `stock_code`(String(10)), `strategy_name`(String(50)), `signal_confidence`(Float, nullable), `entry_price`(Integer), `exit_price`(Integer), `quantity`(Integer), `realized_pnl`(Integer), `pnl_rate`(Float), `holding_duration_sec`(Integer), `entry_time`(DateTime), `exit_time`(DateTime), `exit_reason`(String(30), stop_loss/take_profit/trailing/timeout/eod/manual), `created_at`(DateTime, server_default)

**Step 3: __init__.py에 import 추가**
- `backend/core/models/__init__.py` 수정
- 기존 import 뒤에 추가: `from core.models.trading import TradeSignal, Order, PositionRecord, TradeHistory`

**Step 4: Alembic 마이그레이션 생성 및 적용**
- 검증: `docker compose exec backend alembic revision --autogenerate -m "매매 테이블 추가 trade_signals orders positions trade_history"`
- 검증: `docker compose exec backend alembic upgrade head`
- 검증: `docker compose exec backend pytest tests/test_trading_models.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/core/models/trading.py backend/core/models/__init__.py backend/alembic/versions/ backend/tests/test_trading_models.py
git commit -m "feat(phase3-sprint1): task1 -- 매매 DB 모델 4개 테이블 + Alembic 마이그레이션"
```

**완료 기준:**
- ✅ 4개 테이블 생성 확인 (alembic upgrade head 성공)
- ✅ pytest test_trading_models.py 통과 (19 tests passed)

---

### Task 2: 리스크 파라미터 시드 확장

**Files:**
- Modify: `backend/scripts/seed_settings.py` (SEED_DATA에 신규 파라미터 추가)
- Test: `backend/tests/test_seed_risk_settings.py`

**Step 1: 테스트 작성**
- `backend/tests/test_seed_risk_settings.py` 생성
- seed 실행 후 다음 키가 DB에 존재하는지 검증:
  - `leverage_position_size_pct` = "5.0" (레버리지 건당 비율)
  - `max_leverage_position_count` = "2" (최대 레버리지 포지션)
  - `leverage_take_profit_pct` = "3.0" (레버리지 익절)
  - `trailing_activation_pct` = "2.0" (트레일링 활성화 기준)
  - `emergency_stop_pct` = "-4.0" (비상 정지 한도)
  - `consecutive_loss_stop` = "3" (연속 손절 정지 횟수)
  - `cooldown_trigger_count` = "2" (30분 내 연속 손절 쿨다운 트리거)
  - `cooldown_duration_min` = "60" (쿨다운 시간 분)
  - `eod_force_close_time` = "14:50" (강제 청산 시각)
  - `no_new_entry_time` = "14:30" (신규 진입 차단 시각)
  - `risk_lock_during_trading` = "true" (장중 리스크 설정 변경 불가)
- 기존 시드 키 `leverage_etf_size_pct` 값이 "5.0"으로 변경 (기존 7.0 -> 확정 5.0)
- 기존 시드 키 `force_close_start` 값이 "14:50"으로 변경 (기존 15:00 -> 확정 14:50)
- 기존 시드 키 `leverage_etf_loss_pct` 값이 "-1.5"로 유지 확인
- 검증: `docker compose exec backend pytest tests/test_seed_risk_settings.py -v`
- 예상: FAIL (키 미존재)

**Step 2: seed_settings.py 확장**
- `backend/scripts/seed_settings.py` 수정
- SEED_DATA에 신규 항목 추가 (위 테스트의 키/값 목록)
- 기존 항목 값 수정:
  - `leverage_etf_size_pct`: "7.0" -> "5.0"
  - `force_close_start`: "15:00" -> "14:50"
  - `force_close_end`: "15:20" -> "15:00"
  - `no_entry_start`: "09:00" -> "09:00" (유지)
  - `no_entry_end`: "09:30" -> "09:30" (유지)
- 검증: `docker compose exec backend pytest tests/test_seed_risk_settings.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/scripts/seed_settings.py backend/tests/test_seed_risk_settings.py
git commit -m "feat(phase3-sprint1): task2 -- 리스크 파라미터 시드 확장 (확정 파라미터 반영)"
```

**완료 기준:**
- ✅ 신규 11개 + 기존 수정 3개 시드 데이터 검증 통과 (32개 설정 시드)
- ✅ pytest test_seed_risk_settings.py 통과 (16 tests passed)

---

### Task 3: 리스크 매니저

**Files:**
- Create: `backend/modules/trading/risk_manager.py`
- Test: `backend/tests/test_risk_manager.py`

**Step 1: 테스트 작성**
- `backend/tests/test_risk_manager.py` 생성
- 테스트 케이스 (DB 의존 최소화, settings 값을 직접 주입):
  1. **일일 손실 한도 초과**: 일일 실현+미실현 손실 합이 -3% 이상 시 `can_trade()` False 반환
  2. **최대 포지션 수 초과**: 활성 포지션 5개 이상 시 `can_trade()` False
  3. **최대 레버리지 포지션 초과**: 레버리지 ETF 포지션 2개 이상 시 `can_trade(is_leverage=True)` False
  4. **비상 정지**: 일일 손실이 -4% 이상 시 `check_emergency_stop()` True, 이후 모든 매매 차단
  5. **연속 손절 정지**: 연속 3회 손절 시 `can_trade()` False
  6. **쿨다운**: 30분 내 2연속 손절 시 1시간 매매 차단
  7. **시간대 차단 (관망)**: 09:00~09:30 시 `can_trade()` False
  8. **시간대 차단 (진입 차단)**: 14:30 이후 시 `can_trade()` False
  9. **정상 통과**: 모든 조건 충족 시 `can_trade()` True
  10. **장중 설정 변경 불가**: 장중에 리스크 설정 변경 시도 시 예외 발생
- 검증: `docker compose exec backend pytest tests/test_risk_manager.py -v`
- 예상: FAIL

**Step 2: 리스크 매니저 구현**
- `backend/modules/trading/risk_manager.py` 생성
- **RiskManager** 클래스:
  - `__init__(self, session_factory, redis_client)`: DB session factory + Redis 주입
  - `async def load_settings(self)`: settings 테이블에서 리스크 파라미터 로드, 내부 캐시
  - `async def can_trade(self, is_leverage: bool = False) -> RiskCheckResult`: 모든 리스크 체크 순차 실행, 차단 시 사유 반환
  - `async def check_daily_loss(self) -> bool`: 일일 실현+미실현 합산 손실 체크 (positions 테이블 + trade_history 오늘 분)
  - `async def check_position_limit(self, is_leverage: bool) -> bool`: 활성 포지션 수/레버리지 수 체크
  - `async def check_emergency_stop(self) -> bool`: -4% 이상 손실 시 비상 정지 (Redis 플래그 설정)
  - `async def check_consecutive_loss(self) -> bool`: trade_history에서 최근 연속 손절 횟수 확인
  - `async def check_cooldown(self) -> bool`: Redis에 쿨다운 키 존재 여부 (TTL 3600초)
  - `def check_time_restriction(self) -> bool`: 현재 시각 기반 매매 가능 여부 (09:00~09:30 관망, 14:30~ 진입 차단)
  - `async def record_loss(self)`: 손절 발생 시 호출 — 연속 손절 카운터 증가, 쿨다운 트리거 판단
  - `async def get_risk_status(self) -> dict`: 현재 리스크 상태 요약 (일일 손익, 포지션 수, 비상 정지 여부 등)
- **RiskCheckResult** (Pydantic BaseModel):
  - `allowed: bool`
  - `reason: str | None`
  - `risk_level: str` ("normal", "warning", "blocked", "emergency")
- 검증: `docker compose exec backend pytest tests/test_risk_manager.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/risk_manager.py backend/tests/test_risk_manager.py
git commit -m "feat(phase3-sprint1): task3 -- 리스크 매니저 (한도/비상정지/쿨다운/시간대 차단)"
```

**완료 기준:**
- ✅ 10개 테스트 케이스 모두 통과 (10 tests passed)
- ✅ can_trade()가 모든 리스크 조건을 순차 검증

---

### Task 4: 포지션 사이저

**Files:**
- Create: `backend/modules/trading/position_sizer.py`
- Test: `backend/tests/test_position_sizer.py`

**Step 1: 테스트 작성**
- `backend/tests/test_position_sizer.py` 생성
- 테스트 케이스:
  1. **일반 종목 투자금 계산**: 잔고 1,000만원, 비율 10% -> 투자금 100만원
  2. **레버리지 ETF 투자금 계산**: 잔고 1,000만원, 비율 5% -> 투자금 50만원
  3. **수량 산출**: 투자금 100만원, 현재가 50,000원 -> 수량 20주
  4. **수량 산출 (단주 절사)**: 투자금 100만원, 현재가 33,000원 -> 수량 30주 (33,000 * 30 = 990,000)
  5. **투자금 0 이하**: 잔고 0 시 수량 0 반환
  6. **현재가 0**: 가격 0 시 수량 0 반환 (ZeroDivisionError 방지)
  7. **레버리지 판별**: stock_type이 "ETF"이고 stock_name에 "레버리지" 또는 "2X" 포함 시 레버리지로 판별
- 검증: `docker compose exec backend pytest tests/test_position_sizer.py -v`
- 예상: FAIL

**Step 2: 포지션 사이저 구현**
- `backend/modules/trading/position_sizer.py` 생성
- **PositionSizer** 클래스:
  - `__init__(self, session_factory)`: DB session factory 주입
  - `async def load_settings(self)`: settings 테이블에서 position_size_pct, leverage_position_size_pct 로드
  - `async def calculate(self, stock_code: str, current_price: int, balance_amount: int) -> PositionSize`: 투자금 + 수량 계산
  - `async def is_leverage(self, stock_code: str) -> bool`: stocks 테이블에서 stock_type/stock_name으로 레버리지 판별
  - `def _compute_quantity(self, invest_amount: int, price: int) -> int`: 투자금/가격 절사
- **PositionSize** (Pydantic BaseModel):
  - `invest_amount: int` (투자금)
  - `quantity: int` (주문 수량)
  - `is_leverage: bool`
  - `size_pct: float` (적용된 비율)
- 검증: `docker compose exec backend pytest tests/test_position_sizer.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/position_sizer.py backend/tests/test_position_sizer.py
git commit -m "feat(phase3-sprint1): task4 -- 포지션 사이저 (일반 10%/레버리지 5% 건당 투자금)"
```

**완료 기준:**
- ✅ 7개 테스트 케이스 모두 통과 (10 tests passed)
- ✅ 일반/레버리지 구분 정상 동작

---

### Task 5: 당일 청산 강제 (eod_liquidator)

**Files:**
- Create: `backend/modules/trading/eod_liquidator.py`
- Test: `backend/tests/test_eod_liquidator.py`

**Step 1: 테스트 작성**
- `backend/tests/test_eod_liquidator.py` 생성
- 테스트 케이스:
  1. **14:50 강제 청산 트리거**: 미청산 포지션 존재 시 `liquidate_all()` 호출, 매도 주문 생성 확인
  2. **미청산 포지션 없음**: 포지션 0개 시 아무 동작 없음
  3. **14:30 이후 진입 차단 플래그**: `is_entry_blocked()` True 반환
  4. **14:30 이전**: `is_entry_blocked()` False 반환
  5. **스케줄러 재시작 시 미청산 처리**: `check_and_liquidate_on_startup()` — positions 테이블에 활성 포지션 존재 + 현재 시각이 14:50 이후이면 즉시 청산
  6. **청산 결과 trade_history 기록**: 청산 시 exit_reason="eod" 검증
- mock 대상: KISRestClient.place_order (실제 주문 호출 대신 모킹)
- 검증: `docker compose exec backend pytest tests/test_eod_liquidator.py -v`
- 예상: FAIL

**Step 2: eod_liquidator 구현**
- `backend/modules/trading/eod_liquidator.py` 생성
- **EodLiquidator** 클래스:
  - `__init__(self, session_factory, rest_client, redis_client)`: 의존성 주입
  - `async def liquidate_all(self)`: positions 테이블에서 활성 포지션 조회 -> 각 포지션에 대해 시장가 매도 주문 생성 (orders 테이블 insert + place_order 호출). trade_history에 exit_reason="eod" 기록. 포지션 삭제.
  - `def is_entry_blocked(self) -> bool`: 현재 시각이 14:30 이후인지 판단 (settings의 `no_new_entry_time` 참조)
  - `async def check_and_liquidate_on_startup(self)`: 앱 시작 시 호출 — 현재 시각이 14:50 이후이고 미청산 포지션 존재 시 즉시 `liquidate_all()` 실행
  - `async def register_schedule(self, scheduler: AsyncIOScheduler)`: APScheduler에 14:50 크론잡 등록 (CollectorScheduler와 동일 패턴)
- 검증: `docker compose exec backend pytest tests/test_eod_liquidator.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/eod_liquidator.py backend/tests/test_eod_liquidator.py
git commit -m "feat(phase3-sprint1): task5 -- 당일 청산 강제 (14:50 시장가 매도 + 재시작 처리)"
```

**완료 기준:**
- ✅ 6개 테스트 케이스 모두 통과 (7 tests passed)
- ✅ 14:50 크론잡 등록 패턴 검증
- ✅ 스케줄러 재시작 시 미청산 즉시 처리 검증

---

### Task 6: 리스크 상태 조회 API + main.py 등록

**Files:**
- Create: `backend/api/routes/trading.py`
- Modify: `backend/main.py` (trading 라우터 등록 + eod_liquidator lifespan 초기화)
- Test: `backend/tests/test_trading_api.py`

**Step 1: 테스트 작성**
- `backend/tests/test_trading_api.py` 생성
- 테스트 케이스 (httpx.AsyncClient + FastAPI TestClient 패턴):
  1. `GET /api/v1/trading/risk-status` -> 200, 리스크 상태 JSON 반환 (daily_pnl, position_count, emergency_stop, can_trade 등)
  2. `GET /api/v1/trading/positions` -> 200, 현재 활성 포지션 목록
  3. `GET /api/v1/trading/history?date=2026-03-30` -> 200, 해당 날짜 매매 이력
- 검증: `docker compose exec backend pytest tests/test_trading_api.py -v`
- 예상: FAIL

**Step 2: API 라우터 구현**
- `backend/api/routes/trading.py` 생성
- `router = APIRouter(prefix="/trading", tags=["trading"])`
- 엔드포인트:
  - `GET /risk-status`: app.state.risk_manager.get_risk_status() 호출
  - `GET /positions`: positions 테이블 전체 조회 (DB 직접)
  - `GET /history`: trade_history 테이블 날짜 필터 조회 (query param: date)

**Step 3: main.py 수정**
- import 추가: `from api.routes.trading import router as trading_router`
- import 추가: `from modules.trading.risk_manager import RiskManager`
- import 추가: `from modules.trading.position_sizer import PositionSizer`
- import 추가: `from modules.trading.eod_liquidator import EodLiquidator`
- lifespan 내부에 추가:
  - `risk_manager = RiskManager(session_factory, redis_client)` -> `app.state.risk_manager`
  - `position_sizer = PositionSizer(session_factory)` -> `app.state.position_sizer`
  - `eod_liquidator = EodLiquidator(session_factory, rest_client, redis_client)` -> `app.state.eod_liquidator`
  - `await eod_liquidator.check_and_liquidate_on_startup()`
  - `await eod_liquidator.register_schedule(collector_scheduler._scheduler)`
- 라우터 등록: `app.include_router(trading_router, prefix="/api/v1")`
- 검증: `docker compose exec backend pytest tests/test_trading_api.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/api/routes/trading.py backend/main.py backend/tests/test_trading_api.py
git commit -m "feat(phase3-sprint1): task6 -- 리스크 상태 조회 API + main.py 모듈 등록"
```

**완료 기준:**
- ✅ 3개 API 엔드포인트 응답 정상 (3 tests passed, 200 OK)
- ✅ eod_liquidator 스케줄 등록 확인
- ✅ 재시작 시 미청산 처리 로직 연결

---

### Task 7: 통합 테스트

**Files:**
- Create: `backend/tests/test_phase3_sprint1_integration.py`

**Step 1: 통합 테스트 작성**
- `backend/tests/test_phase3_sprint1_integration.py` 생성
- 테스트 시나리오:
  1. **시드 -> 리스크 매니저 로드 -> can_trade 정상**: seed 실행 -> risk_manager.load_settings() -> can_trade() True (초기 상태)
  2. **포지션 5개 채운 후 can_trade False**: positions에 5개 insert -> can_trade() False (reason: "max_position_count")
  3. **포지션 사이저 계산 정확**: seed 후 잔고 1,000만원, 일반 종목 50,000원 -> 수량 20
  4. **비상 정지 -> 매매 전면 차단**: trade_history에 일일 손실 -4% 이상 데이터 insert -> check_emergency_stop() True -> can_trade() False
  5. **eod_liquidator 미청산 처리**: positions에 2개 insert -> liquidate_all() -> positions 테이블 비어있음, trade_history에 exit_reason="eod" 2건
- mock 대상: KISRestClient.place_order, datetime.now (시간 고정)
- 검증: `docker compose exec backend pytest tests/test_phase3_sprint1_integration.py -v`
- 예상: PASS

**Step 2: 전체 pytest 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 기존 테스트 + 신규 테스트 모두 PASS (기존 테스트 회귀 없음)

**Step 3: 커밋**
```
git add backend/tests/test_phase3_sprint1_integration.py
git commit -m "feat(phase3-sprint1): task7 -- Sprint 1 통합 테스트"
```

**완료 기준:**
- ✅ 5개 통합 테스트 시나리오 통과 (5 tests passed)
- ✅ 기존 테스트 회귀 없음 (pytest -v: 413 passed, 1 failed — 기존 test_stock_crud 중복키 이슈, Sprint 1 무관)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 기존 + 신규 모두 passed |
| Alembic 마이그레이션 | `docker compose exec backend alembic upgrade head` | 4개 테이블 생성 |
| 시드 데이터 | `docker compose exec backend python -m scripts.seed_settings` | 32개+ 설정 시드 완료 |
| 리스크 상태 API | `curl -s http://localhost:8000/api/v1/trading/risk-status \| jq .` | JSON 응답 (can_trade, daily_pnl 등) |
| 포지션 조회 API | `curl -s http://localhost:8000/api/v1/trading/positions \| jq .` | 빈 배열 `[]` |
| 매매 이력 API | `curl -s "http://localhost:8000/api/v1/trading/history?date=2026-03-30" \| jq .` | 빈 배열 `[]` |
