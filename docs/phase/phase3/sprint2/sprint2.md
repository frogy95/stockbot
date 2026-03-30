# Sprint 2: 매매 전략 + 주문 실행 (Phase 3)

**Goal:** 모멘텀 브레이크아웃 전략으로 매매 신호를 생성하고, 최우선 지정가->시장가 폴백 주문을 실행하며, 포지션의 손절/익절/트레일링/보합 청산을 자동 관리하는 매매 엔진 핵심 파이프라인을 완성한다.

**Architecture:** Strategy ABC 인터페이스 위에 모멘텀 브레이크아웃 전략을 구현하고, signal_generator가 2차 스크리닝 결과에 전략을 적용하여 trade_signals 테이블에 저장한다. order_manager는 asyncio.Queue 기반 순차 주문 처리 + 체결 폴링을 담당한다. position_manager는 활성 포지션을 주기적으로 모니터링하며 손절/익절/트레일링/보합 조건에 따라 청산한다. engine이 전체 흐름(스크리닝->전략->리스크->주문)을 오케스트레이션한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncio.Queue, pytest-asyncio, httpx

**Sprint 기간:** 2026-03-30 ~ 2026-03-30
**상태:** ✅ 완료 (2026-03-30)
**이전 스프린트:** Sprint 1 (pytest 통과, PR #32)
**브랜치명:** `phase3-sprint2`
**PR:** https://github.com/frogy95/stockbot/pull/33

---

## 제외 범위

- 텔레그램 알림/승인 (Sprint 3)
- 프론트엔드 대시보드 (Phase 4)
- 정식 백테스팅 프레임워크 (Phase 5)
- 완전 자동 모드 (Phase 5)
- 네이버 센티멘트/DART 공시 팩터 통합 (Phase 5)
- 실전 환경 최우선 지정가 주문 (모의에서는 시장가만, Sprint 3 이후 실전 전환 시 활성화)

## 실행 플랜

의존성 그래프: Task 1(Strategy ABC) -> Task 2(모멘텀 브레이크아웃) -> Task 3(신호 생성기) -> Task 4/5(병렬: 주문 매니저/포지션 매니저) -> Task 6(매매 엔진) -> Task 7(API 확장 + main.py) -> Task 8(통합 테스트)

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | Strategy ABC 인터페이스 정의 | 백엔드 | -- |
| Task 2 | 모멘텀 브레이크아웃 전략 구현 | 백엔드 | -- |
| Task 3 | 신호 생성기 (스크리닝 결과 -> 전략 적용 -> trade_signals 저장) | 백엔드 | -- |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 주문 매니저 (최우선 지정가->시장가 폴백 + 체결 폴링 + 큐) | 백엔드 | -- |
| Task 5 | 포지션 매니저 (손절/익절/트레일링/보합 청산 모니터링) | 백엔드 | -- |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | 매매 엔진 오케스트레이터 (스크리닝->전략->리스크->주문 통합) | 백엔드 | `feature-dev:feature-dev` |
| Task 7 | 신호/주문/포지션 조회 API 확장 + main.py 등록 | 백엔드 | -- |
| Task 8 | 통합 테스트 | 백엔드 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 Task 4, Task 5를 병렬 구현합니다.

---

### Task 1: Strategy ABC 인터페이스

**Files:**
- Create: `backend/modules/trading/strategy.py`
- Test: `backend/tests/test_strategy_abc.py`

**Step 1: 테스트 작성**
- `backend/tests/test_strategy_abc.py` 생성
- 테스트 케이스:
  1. Strategy ABC를 상속하지 않고 인스턴스화 시도 시 TypeError
  2. Strategy ABC를 올바르게 상속한 클래스가 `generate_signal()` 구현 시 인스턴스화 성공
  3. `generate_signal()`의 반환 타입이 `TradeSignalData | None`인지 검증
- 검증: `docker compose exec backend pytest tests/test_strategy_abc.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: Strategy ABC 구현**
- `backend/modules/trading/strategy.py` 생성
- **TradeSignalData** (Pydantic BaseModel):
  - `stock_code: str`
  - `signal_type: str` ("buy" / "sell")
  - `strategy_name: str`
  - `confidence: float` (0~1)
  - `reason: dict` (신호 근거 상세)
  - `entry_price: int`
  - `stop_loss: int`
  - `take_profit: int`
- **MarketSnapshot** (Pydantic BaseModel) -- 전략에 전달할 시장 데이터 스냅샷:
  - `stock_code: str`
  - `stock_name: str`
  - `stock_type: str` ("STOCK" / "ETF")
  - `current_price: int`
  - `open_price: int`
  - `high: int`
  - `low: int`
  - `prev_close: int`
  - `prev_high: int` (전일 고가)
  - `volume: int` (당일 누적)
  - `prev_volume: int` (전일 거래량)
  - `change_rate: float`
  - `trade_strength: float` (체결강도)
  - `total_bid_volume: int`
  - `total_ask_volume: int`
  - `recent_highs: list[int]` (최근 5일 고가, ATR 계산용)
  - `recent_lows: list[int]` (최근 5일 저가)
  - `recent_closes: list[int]` (최근 5일 종가)
- **Strategy** (ABC):
  - `@property name(self) -> str`: 전략 이름
  - `@abstractmethod async def generate_signal(self, snapshot: MarketSnapshot) -> TradeSignalData | None`: 시장 데이터로부터 매매 신호 생성. 조건 미달 시 None 반환.
- 검증: `docker compose exec backend pytest tests/test_strategy_abc.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/strategy.py backend/tests/test_strategy_abc.py
git commit -m "feat(phase3-sprint2): task1 -- Strategy ABC 인터페이스 + TradeSignalData/MarketSnapshot 스키마"
```

**완료 기준:**
- ✅ pytest test_strategy_abc.py 통과
- ✅ ABC 상속 강제 검증

---

### Task 2: 모멘텀 브레이크아웃 전략

**Files:**
- Create: `backend/modules/trading/strategies/__init__.py`
- Create: `backend/modules/trading/strategies/momentum_breakout.py`
- Test: `backend/tests/test_momentum_breakout.py`

**Step 1: 테스트 작성**
- `backend/tests/test_momentum_breakout.py` 생성
- 테스트 케이스 (MarketSnapshot을 직접 구성하여 주입):
  1. **전일 고가 돌파 + 거래량 200%+ + 체결강도 70+ -> 매수 신호 생성**: confidence > 0.6 검증
  2. **전일 고가 미돌파 -> None 반환**: current_price < prev_high
  3. **거래량 조건 미달 -> None 반환**: volume/prev_volume < 2.0
  4. **체결강도 조건 미달 -> None 반환**: trade_strength < 70
  5. **갭 3%+ 시 당일 고가 기준 전환**: open_price가 prev_close 대비 3%+ 갭, 돌파 기준이 당일 high로 전환
  6. **ATR 5일 상위 20% 제외**: ATR이 지정 임계값 초과 시 None 반환
  7. **신뢰도 가중 평균 검증**: 모멘텀30/거래량30/체결강도20/호가20 가중치로 계산된 confidence 값 정확성
  8. **신뢰도 0.6 미만 -> None 반환**: 각 팩터가 낮아 합산 confidence < 0.6일 때
  9. **손절/익절 가격 계산 검증**: 일반 종목 -2%/+3%, 레버리지 -1.5%/+3%
  10. **reason dict 구조 검증**: 각 팩터 점수와 조건 충족 여부가 reason에 포함
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py -v`
- 예상: FAIL

**Step 2: 모멘텀 브레이크아웃 전략 구현**
- `backend/modules/trading/strategies/__init__.py` 생성 (빈 파일)
- `backend/modules/trading/strategies/momentum_breakout.py` 생성
- **MomentumBreakoutStrategy(Strategy)**:
  - `name`: `"momentum_breakout"`
  - 기존 `modules/screening/factors.py`의 `calc_volatility_factor` 재활용하여 ATR 계산
  - `async def generate_signal(self, snapshot: MarketSnapshot) -> TradeSignalData | None`:
    1. **돌파 기준 결정**: 갭 비율 = (open_price - prev_close) / prev_close. 갭 3%+ 시 `breakout_ref = high` (당일 고가), 그 외 `breakout_ref = prev_high` (전일 고가)
    2. **돌파 조건**: current_price > breakout_ref
    3. **거래량 조건**: volume / prev_volume >= 2.0 (prev_volume == 0 이면 조건 미달)
    4. **체결강도 조건**: trade_strength >= 70.0
    5. **ATR 필터**: `calc_volatility_factor(recent_highs, recent_lows, recent_closes)` 호출. ATR 상위 20% 기준은 settings에서 `atr_filter_percentile` 로드 (기본 80). ATR이 현재가 대비 일정 비율(기본 5%) 초과 시 제외
    6. **신뢰도 계산**:
       - `momentum_score`: (current_price - breakout_ref) / breakout_ref * 100, 정규화 0~1 (cap at 5%)
       - `volume_score`: min(volume / prev_volume / 5.0, 1.0) (거래량비 5배 이상이면 만점)
       - `strength_score`: min((trade_strength - 50) / 50, 1.0) (50~100 범위를 0~1로)
       - `orderbook_score`: min(total_bid_volume / max(total_ask_volume, 1) / 2.0, 1.0) (비율 2.0이면 만점)
       - `confidence = momentum_score * 0.3 + volume_score * 0.3 + strength_score * 0.2 + orderbook_score * 0.2`
    7. **최소 임계값**: confidence < 0.6 이면 None
    8. **손절/익절 계산**: 레버리지 여부(stock_name에 "레버리지" 또는 "2X" 포함)에 따라:
       - 일반: stop_loss = entry_price * 0.98, take_profit = entry_price * 1.03
       - 레버리지: stop_loss = entry_price * 0.985, take_profit = entry_price * 1.03
    9. **TradeSignalData 반환**: reason에 각 팩터 점수, 돌파 기준, 갭 비율 포함
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/strategies/ backend/tests/test_momentum_breakout.py
git commit -m "feat(phase3-sprint2): task2 -- 모멘텀 브레이크아웃 전략 (5분봉 돌파 + 다팩터 신뢰도)"
```

**완료 기준:**
- ✅ 10개 테스트 케이스 통과
- ✅ 신뢰도 가중 평균 공식 정확성 검증
- ✅ ATR 필터 동작 확인

---

### Task 3: 신호 생성기

**Files:**
- Create: `backend/modules/trading/signal_generator.py`
- Test: `backend/tests/test_signal_generator.py`

**Step 1: 테스트 작성**
- `backend/tests/test_signal_generator.py` 생성
- 테스트 케이스 (DB + Redis mock):
  1. **2차 스크리닝 통과 종목에 전략 적용 -> trade_signals 저장**: 전략이 신호를 반환하면 DB에 TradeSignal 레코드 생성 확인
  2. **전략이 None 반환 -> trade_signals 미저장**: 조건 미달 종목은 무시
  3. **신뢰도 0.6 미만 필터**: 전략이 confidence 0.5 반환 시 저장하지 않음
  4. **동일 종목 중복 신호 방지**: 같은 종목에 대해 status="pending" 신호가 이미 존재하면 새 신호 생성하지 않음
  5. **MarketSnapshot 조립 검증**: Redis 실시간 데이터 + DB 과거 데이터로 MarketSnapshot을 올바르게 구성하는지 확인
- 검증: `docker compose exec backend pytest tests/test_signal_generator.py -v`
- 예상: FAIL

**Step 2: 신호 생성기 구현**
- `backend/modules/trading/signal_generator.py` 생성
- **SignalGenerator** 클래스:
  - `__init__(self, session_factory, redis_client, strategy: Strategy)`: 의존성 주입
  - `async def generate_signals(self, screened_candidates: list[dict]) -> list[TradeSignalData]`:
    1. 각 후보 종목에 대해 `_build_snapshot()` 호출하여 MarketSnapshot 조립
    2. `strategy.generate_signal(snapshot)` 호출
    3. 결과가 None이 아니고 confidence >= 0.6이면:
       - 동일 종목 pending 신호 중복 체크 (DB 조회)
       - 중복 없으면 TradeSignal 모델로 DB 저장 (status="pending")
    4. 생성된 신호 목록 반환
  - `async def _build_snapshot(self, candidate: dict) -> MarketSnapshot`:
    - candidate dict에서 stock_code, stock_name, stock_type, current_price, volume, prev_volume, trade_strength, total_bid/ask_volume 추출
    - Redis에서 실시간 시세 추가 데이터(open_price, high, low) 조회: 키 패턴 `realtime:{stock_code}`
    - DB market_data 테이블에서 최근 5일 고/저/종가 조회: recent_highs, recent_lows, recent_closes
    - DB market_data에서 전일 고가(prev_high), 전일 종가(prev_close) 추출
- 검증: `docker compose exec backend pytest tests/test_signal_generator.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/signal_generator.py backend/tests/test_signal_generator.py
git commit -m "feat(phase3-sprint2): task3 -- 신호 생성기 (스크리닝 결과 -> 전략 적용 -> trade_signals 저장)"
```

**완료 기준:**
- ✅ 5개 테스트 케이스 통과
- ✅ 중복 신호 방지 로직 검증
- ✅ MarketSnapshot 조립 정확성 확인

---

### Task 4: 주문 매니저

**Files:**
- Create: `backend/modules/trading/order_manager.py`
- Test: `backend/tests/test_order_manager.py`

**Step 1: 테스트 작성**
- `backend/tests/test_order_manager.py` 생성
- 테스트 케이스 (KISRestClient mock):
  1. **시장가 주문 실행 + 즉시 체결**: place_order 호출 -> 체결 확인 -> orders 테이블 status="filled"
  2. **최우선 지정가 주문 -> 3초 후 미체결 -> 시장가 폴백**: 첫 주문 지정가 -> 3초 대기 -> 미체결 확인 -> 취소 -> 시장가 재주문
  3. **체결 폴링 (2초 x 최대 15회)**: get_order_status 반복 호출, 체결 시 루프 종료
  4. **체결 폴링 30초 초과 -> timeout 처리**: 15회 반복 후 미체결 -> status="timeout" 기록
  5. **주문 큐 순차 실행**: 3건 동시 요청 -> 순차 처리 확인 (동시 실행 아님)
  6. **스로틀러 bypass 확인**: 주문 시 throttler.acquire() 호출하되, bypass 옵션이 있으면 건너뜀
  7. **모의거래 환경에서는 시장가만 사용**: TRADING_ENV=paper 시 최우선 지정가 건너뛰고 즉시 시장가
- 검증: `docker compose exec backend pytest tests/test_order_manager.py -v`
- 예상: FAIL

**Step 2: 주문 매니저 구현**
- `backend/modules/trading/order_manager.py` 생성
- **OrderManager** 클래스:
  - `__init__(self, session_factory, rest_client: KISRestClient, redis_client, throttler: TokenBucketThrottler)`: 의존성 주입
  - `_queue: asyncio.Queue` (주문 요청 큐)
  - `_worker_task: asyncio.Task | None` (백그라운드 워커)
  - `async def start(self)`: 워커 태스크 시작
  - `async def stop(self)`: 워커 태스크 종료
  - `async def submit_order(self, signal: TradeSignalData, position_size: PositionSize) -> Order`:
    - orders 테이블에 status="submitted" 레코드 생성
    - 큐에 주문 요청 enqueue
    - Order 레코드 반환
  - `async def _worker(self)`:
    - 큐에서 주문을 꺼내 `_execute_order()` 호출 (순차)
  - `async def _execute_order(self, order_id: int)`:
    1. 모의거래 판별: `settings.TRADING_ENV == "paper"`이면 시장가만 사용
    2. 실전: 최우선 지정가 주문 (order_division="05") -> place_order 호출
    3. 3초 대기 후 체결 확인 (`_poll_fill_status`)
    4. 미체결 시: cancel_order -> 시장가 재주문 (order_division="01")
    5. 체결 폴링 실행
  - `async def _poll_fill_status(self, order_no: str, max_polls: int = 15, interval: float = 2.0) -> bool`:
    - get_order_status 반복 호출
    - 체결 확인 시 True 반환, orders 테이블 status="filled", filled_at 기록
    - max_polls 초과 시 False 반환, orders 테이블 status="timeout"
  - `async def _reconcile_timeout(self, order_id: int)`:
    - timeout 주문에 대해 다음 잔고 조회 시 reconciliation (미해결 사항 #2 기본 처리)
    - positions 테이블과 한투 잔고 비교하여 불일치 시 로그 경고
- 검증: `docker compose exec backend pytest tests/test_order_manager.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/order_manager.py backend/tests/test_order_manager.py
git commit -m "feat(phase3-sprint2): task4 -- 주문 매니저 (최우선 지정가->시장가 폴백 + 체결 폴링 + asyncio.Queue)"
```

**완료 기준:**
- ✅ 7개 테스트 케이스 통과
- ✅ 주문 큐 순차 실행 확인
- ✅ 모의거래 시장가 전환 로직 검증

---

### Task 5: 포지션 매니저

**Files:**
- Create: `backend/modules/trading/position_manager.py`
- Test: `backend/tests/test_position_manager.py`

**Step 1: 테스트 작성**
- `backend/tests/test_position_manager.py` 생성
- 테스트 케이스:
  1. **매수 체결 -> 포지션 생성**: orders status="filled" 매수 -> positions 테이블에 레코드 생성
  2. **손절 트리거**: current_price가 avg_price 대비 -2% 이하 -> 매도 신호 발생, exit_reason="stop_loss"
  3. **익절 트리거**: current_price가 avg_price 대비 +3% 이상 -> 매도 신호 발생, exit_reason="take_profit"
  4. **트레일링 스탑 활성화**: current_price가 avg_price 대비 +2% 이상 도달 -> trailing_activated=True
  5. **트레일링 스탑 트리거**: trailing_activated=True 상태에서 고점 대비 -1% 하락 -> 매도, exit_reason="trailing"
  6. **보합 청산**: 진입 30분 경과 + 수익률 +1% 미만 -> 매도, exit_reason="timeout"
  7. **레버리지 ETF 별도 손절/익절**: 레버리지 종목은 stop_loss=-1.5%, take_profit=+3%
  8. **매도 완료 -> trade_history 기록 + positions 삭제**: 포지션 청산 시 trade_history에 기록 후 positions에서 삭제
  9. **포지션 가격 업데이트**: 실시간 가격 수신 시 current_price, unrealized_pnl 갱신
- 검증: `docker compose exec backend pytest tests/test_position_manager.py -v`
- 예상: FAIL

**Step 2: 포지션 매니저 구현**
- `backend/modules/trading/position_manager.py` 생성
- **PositionManager** 클래스:
  - `__init__(self, session_factory, redis_client, risk_manager: RiskManager)`: 의존성 주입
  - `_trailing_highs: dict[str, int]` (종목별 트레일링 고점 추적, 메모리)
  - `async def open_position(self, signal: TradeSignalData, quantity: int, filled_price: int)`:
    - positions 테이블에 새 레코드 생성
    - stop_loss, take_profit은 signal에서 가져옴
    - entry_time = now, strategy_name = signal.strategy_name
  - `async def update_prices(self, price_updates: dict[str, int])`:
    - price_updates: {stock_code: current_price}
    - positions 테이블의 current_price, unrealized_pnl 갱신
    - trailing_activated 체크: current_price >= avg_price * 1.02 이면 True 설정
    - _trailing_highs 업데이트
  - `async def check_exit_conditions(self) -> list[dict]`:
    - 모든 활성 포지션 순회:
      1. **손절**: current_price <= stop_loss -> exit_reason="stop_loss"
      2. **익절**: current_price >= take_profit -> exit_reason="take_profit"
      3. **트레일링**: trailing_activated=True이고 current_price <= trailing_high * 0.99 -> exit_reason="trailing"
      4. **보합**: entry_time + 30분 경과하고 (current_price - avg_price) / avg_price < 0.01 -> exit_reason="timeout"
    - 청산 대상 목록 반환: [{stock_code, quantity, exit_reason, position_id}]
  - `async def close_position(self, position_id: int, exit_price: int, exit_reason: str)`:
    - positions 테이블에서 해당 포지션 조회
    - trade_history에 기록: realized_pnl, pnl_rate, holding_duration_sec 계산
    - positions에서 삭제
    - risk_manager.record_loss() 호출 (손절인 경우)
    - _trailing_highs에서 해당 종목 제거
- 검증: `docker compose exec backend pytest tests/test_position_manager.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/position_manager.py backend/tests/test_position_manager.py
git commit -m "feat(phase3-sprint2): task5 -- 포지션 매니저 (손절/익절/트레일링/보합 청산 모니터링)"
```

**완료 기준:**
- ✅ 9개 테스트 케이스 통과
- ✅ 트레일링 스탑 활성화/트리거 로직 검증
- ✅ 보합 청산 30분 타임아웃 검증

---

### Task 6: 매매 엔진 오케스트레이터

**skill:** `feature-dev:feature-dev`

**Files:**
- Create: `backend/modules/trading/engine.py`
- Test: `backend/tests/test_trading_engine.py`

**Step 1: 테스트 작성**
- `backend/tests/test_trading_engine.py` 생성
- 테스트 케이스 (각 모듈을 mock/stub으로 주입):
  1. **정상 흐름**: 스크리닝 결과 수신 -> signal_generator가 신호 생성 -> risk_manager.can_trade() True -> position_sizer.calculate() -> order_manager.submit_order() 호출 확인
  2. **리스크 차단**: risk_manager.can_trade() False 반환 시 주문 미실행
  3. **신호 없음**: signal_generator가 빈 리스트 반환 시 주문 미실행
  4. **포지션 모니터링 루프**: engine.monitor_positions() 호출 -> position_manager.check_exit_conditions() -> 청산 대상에 대해 매도 주문 실행
  5. **시간대 정책 적용**: 골든타임(09:30~10:30)에는 타임아웃 20초, 일반(10:30~14:00)에는 30초
  6. **14:30 이후 신규 진입 차단**: eod_liquidator.is_entry_blocked() True 시 신호 무시
- 검증: `docker compose exec backend pytest tests/test_trading_engine.py -v`
- 예상: FAIL

**Step 2: 매매 엔진 구현**
- `backend/modules/trading/engine.py` 생성
- **TradingEngine** 클래스:
  - `__init__(self, signal_generator, order_manager, position_manager, risk_manager, position_sizer, eod_liquidator, redis_client)`: 모든 모듈 주입
  - `_running: bool` (엔진 실행 상태)
  - `_monitor_task: asyncio.Task | None` (포지션 모니터링 루프)
  - `async def start(self)`:
    - order_manager.start() 호출
    - 포지션 모니터링 루프 시작 (_monitor_task)
    - _running = True
  - `async def stop(self)`:
    - _running = False
    - 모니터링 태스크 취소
    - order_manager.stop() 호출
  - `async def process_screening_results(self, screened_candidates: list[dict])`:
    1. eod_liquidator.is_entry_blocked() 체크 -> True면 return
    2. signal_generator.generate_signals(screened_candidates) 호출
    3. 각 신호에 대해:
       a. risk_manager.can_trade(is_leverage) 체크 -> 차단 시 신호 status="rejected" 업데이트
       b. position_sizer.calculate(stock_code, entry_price, balance) 호출
       c. quantity == 0이면 skip
       d. order_manager.submit_order(signal, position_size) 호출
       e. 주문 체결 대기 (비동기 -- 워커가 처리)
  - `async def _monitor_positions_loop(self, interval: float = 5.0)`:
    - while _running:
      1. Redis에서 실시간 가격 수집 -> position_manager.update_prices() 호출
      2. position_manager.check_exit_conditions() 호출
      3. 청산 대상에 대해 매도 주문 생성 + order_manager 큐에 enqueue
      4. 체결 완료 시 position_manager.close_position() 호출
      5. asyncio.sleep(interval)
  - `async def on_order_filled(self, order_id: int, filled_price: int)`:
    - 매수 주문 체결 콜백
    - position_manager.open_position() 호출
  - `def _get_approval_timeout(self) -> int`:
    - 현재 시각 기반: 09:30~10:30 -> 20초, 그 외 -> 30초, 14:00~14:30 -> 15초
    - (Sprint 3에서 텔레그램 승인 시 사용, 지금은 구조만)
- 검증: `docker compose exec backend pytest tests/test_trading_engine.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/engine.py backend/tests/test_trading_engine.py
git commit -m "feat(phase3-sprint2): task6 -- 매매 엔진 오케스트레이터 (스크리닝->전략->리스크->주문 통합)"
```

**완료 기준:**
- ✅ 6개 테스트 케이스 통과
- ✅ 정상 흐름 E2E 검증 (mock 기반)
- ✅ 리스크 차단 시 주문 미실행 확인

---

### Task 7: 신호/주문 조회 API 확장 + main.py 등록

**Files:**
- Modify: `backend/api/routes/trading.py` (기존 라우터에 신호/주문 조회 엔드포인트 추가)
- Modify: `backend/main.py` (매매 엔진 관련 모듈 초기화 추가)
- Test: `backend/tests/test_trading_api_sprint2.py`

**Step 1: 테스트 작성**
- `backend/tests/test_trading_api_sprint2.py` 생성
- 테스트 케이스:
  1. `GET /api/v1/trading/signals?date=2026-03-30` -> 200, 해당 날짜 매매 신호 목록
  2. `GET /api/v1/trading/signals?status=pending` -> 200, 상태별 필터링
  3. `GET /api/v1/trading/orders?date=2026-03-30` -> 200, 해당 날짜 주문 목록
  4. `GET /api/v1/trading/engine-status` -> 200, 매매 엔진 상태 (running, queue_size, active_positions)
- 검증: `docker compose exec backend pytest tests/test_trading_api_sprint2.py -v`
- 예상: FAIL

**Step 2: API 라우터 확장**
- `backend/api/routes/trading.py` 수정 (기존 엔드포인트 유지, 아래 추가):
  - `GET /signals`: trade_signals 테이블 조회 (query params: date, status)
  - `GET /orders`: orders 테이블 조회 (query params: date, status)
  - `GET /engine-status`: app.state.trading_engine 상태 반환 (running 여부, 큐 크기, 활성 포지션 수)

**Step 3: main.py 수정**
- import 추가:
  - `from modules.trading.strategy import Strategy`
  - `from modules.trading.strategies.momentum_breakout import MomentumBreakoutStrategy`
  - `from modules.trading.signal_generator import SignalGenerator`
  - `from modules.trading.order_manager import OrderManager`
  - `from modules.trading.position_manager import PositionManager`
  - `from modules.trading.engine import TradingEngine`
- lifespan 내부에 추가 (기존 매매 모듈 초기화 블록 뒤):
  ```
  strategy = MomentumBreakoutStrategy()
  signal_generator = SignalGenerator(session_factory, redis_client, strategy)
  order_manager = OrderManager(session_factory, rest_client, redis_client, throttler)
  position_manager = PositionManager(session_factory, redis_client, risk_manager)
  trading_engine = TradingEngine(
      signal_generator=signal_generator,
      order_manager=order_manager,
      position_manager=position_manager,
      risk_manager=risk_manager,
      position_sizer=position_sizer,
      eod_liquidator=eod_liquidator,
      redis_client=redis_client,
  )
  await trading_engine.start()
  app.state.trading_engine = trading_engine
  ```
- shutdown 블록에 추가: `await trading_engine.stop()`
- 검증: `docker compose exec backend pytest tests/test_trading_api_sprint2.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/api/routes/trading.py backend/main.py backend/tests/test_trading_api_sprint2.py
git commit -m "feat(phase3-sprint2): task7 -- 신호/주문 조회 API + main.py 매매 엔진 등록"
```

**완료 기준:**
- ✅ 4개 API 엔드포인트 응답 정상
- ✅ main.py 매매 엔진 초기화/종료 흐름 확인

---

### Task 8: 통합 테스트

**Files:**
- Create: `backend/tests/test_phase3_sprint2_integration.py`

**Step 1: 통합 테스트 작성**
- `backend/tests/test_phase3_sprint2_integration.py` 생성
- 테스트 시나리오 (KISRestClient mock, datetime mock):
  1. **전체 매매 사이클**: 2차 스크리닝 결과 -> engine.process_screening_results() -> 신호 생성 -> 리스크 통과 -> 주문 실행 -> 체결 -> 포지션 생성 -> trade_signals/orders/positions 테이블 검증
  2. **손절 시나리오**: 포지션 생성 -> 가격 하락 시뮬레이션 -> check_exit_conditions() -> 매도 주문 -> trade_history에 exit_reason="stop_loss" 기록
  3. **리스크 차단 시나리오**: 일일 손실 한도 초과 상태에서 신호 수신 -> 주문 미실행 확인
  4. **보합 청산 시나리오**: 포지션 생성 -> 30분 경과 + 수익률 < 1% -> 청산 확인
  5. **ATR 필터 시나리오**: ATR이 높은 종목 데이터 -> 전략이 None 반환 확인
- 검증: `docker compose exec backend pytest tests/test_phase3_sprint2_integration.py -v`
- 예상: PASS

**Step 2: 전체 pytest 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 기존 테스트 + 신규 테스트 모두 PASS (기존 테스트 회귀 없음)

**Step 3: 커밋**
```
git add backend/tests/test_phase3_sprint2_integration.py
git commit -m "feat(phase3-sprint2): task8 -- Sprint 2 통합 테스트 (매매 사이클/손절/리스크/보합/ATR)"
```

**완료 기준:**
- ✅ 5개 통합 테스트 시나리오 통과 (49 passed)
- ✅ 기존 테스트 회귀 없음 (462 passed, 4 failed 기존 이슈)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 기존 + 신규 모두 passed |
| 신호 조회 API | `curl -s http://localhost:8000/api/v1/trading/signals \| jq .` | 배열 응답 (빈 또는 데이터) |
| 주문 조회 API | `curl -s http://localhost:8000/api/v1/trading/orders \| jq .` | 배열 응답 |
| 엔진 상태 API | `curl -s http://localhost:8000/api/v1/trading/engine-status \| jq .` | `{"running": true, "queue_size": 0, ...}` |
| 리스크 상태 API | `curl -s http://localhost:8000/api/v1/trading/risk-status \| jq .` | 기존과 동일 (회귀 없음) |
| 포지션 조회 API | `curl -s http://localhost:8000/api/v1/trading/positions \| jq .` | 기존과 동일 (회귀 없음) |
