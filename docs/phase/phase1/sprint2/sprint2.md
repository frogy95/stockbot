# Sprint 2: 한투 API 연동 + 토큰 관리 + 모의/실전 전환 (Phase 1)

**Goal:** 한투 REST/WebSocket 클라이언트를 구현하고, 토큰 자동 갱신(Redis 캐싱), Rate Limit 스로틀러(토큰 버킷), 모의/실전 환경 전환을 완성하여 Phase 2 데이터 수집의 기반을 확립한다.

**Architecture:** `core/clients/` 패키지 아래에 KIS 환경 설정(`kis_config.py`), REST 클라이언트(`kis_rest.py`), WebSocket 클라이언트(`kis_ws.py`), 토큰 매니저(`token_manager.py`), Rate Limit 스로틀러(`throttler.py`)를 배치한다. 환경 전환은 `TRADING_ENV` 환경변수 > DB settings 테이블 계층 구조로 동작하며, 모든 클라이언트가 `KISEnvironment` 데이터클래스를 통해 도메인/키/tr_id/Rate Limit을 일괄 참조한다. 토큰은 Redis에 캐싱하고 만료 2시간 전 자동 갱신한다.

**Tech Stack:** Python 3.12, FastAPI, httpx (async HTTP), websockets, redis.asyncio, APScheduler, pydantic (스키마), pytest + pytest-asyncio

**Sprint 기간:** 2026-03-29 ~ 2026-03-29
**상태:** ✅ 완료 (2026-03-29)
**이전 스프린트:** Sprint 1 (24 passed, PR #2)
**브랜치명:** `phase1-sprint2`
**PR:** https://github.com/frogy95/stockbot/pull/3

---

## 제외 범위

- WebSocket 데이터 파싱 (시세/호가/체결 -> 구조체) -- Phase 2
- WebSocket 구독 관리 (종목 동적 추가/제거, 40종목 제한 대응) -- Phase 2
- 체결강도 계산 -- Phase 2
- 장 상태 관리 (시초가/장마감 시간대 로직) -- Phase 2
- 실제 종목 데이터 수집/저장 -- Phase 2
- 프론트엔드 변경 -- 없음
- DB 스키마 변경 -- 없음 (기존 settings 테이블 활용)

---

## 실행 플랜

의존성 그래프:
```
Task 1 (kis_config) -> Task 2 (throttler) -> Task 3 (token_manager) -> Task 4 (kis_rest) -> Task 5 (kis_ws) -> Task 6 (API 엔드포인트) -> Task 7 (통합 테스트)
```

Task 1~3은 기반 모듈이므로 순차, Task 4~5는 파일이 겹치지 않아 병렬 가능.

### Phase 1 (순차 -- 기반 모듈)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | KIS 환경 설정 (모의/실전 매핑) | 백엔드 | -- |
| Task 2 | Rate Limit 스로틀러 (토큰 버킷) | 백엔드 | -- |
| Task 3 | 토큰 매니저 (Redis 캐싱 + 자동 갱신) | 백엔드 | -- |

### Phase 2 (병렬 가능 -- REST/WS 클라이언트)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | KIS REST 클라이언트 | 백엔드 | -- |
| Task 5 | KIS WebSocket 클라이언트 (기본 프레임) | 백엔드 | -- |

### Phase 3 (순차 -- API + 통합)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | Settings CRUD + KIS 테스트 API 엔드포인트 | 백엔드 | -- |
| Task 7 | 통합 테스트 + main.py 라우터 등록 | 백엔드 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 Task 4, Task 5를 병렬 구현합니다.

---

### Task 1: KIS 환경 설정 (모의/실전 매핑)

**Files:**
- Create: `backend/core/clients/__init__.py`
- Create: `backend/core/clients/kis_config.py`
- Test: `backend/tests/test_kis_config.py`

**Step 1: 테스트 작성**
- `backend/tests/test_kis_config.py` 생성
- 테스트 항목:
  - `KISEnvironment` 데이터클래스의 필수 필드 존재 확인 (name, rest_domain, ws_url, order_tr_prefix, app_key_env, app_secret_env, account_env, rate_limit_interval)
  - `PAPER` 상수: name=="paper", rest_domain에 "openapivts" 포함, order_tr_prefix=="V", rate_limit_interval==1.5
  - `LIVE` 상수: name=="live", rest_domain에 "openapi" 포함 및 "vts" 미포함, order_tr_prefix=="T", rate_limit_interval==0.07 (약 초당 14건)
  - `get_environment("paper")` -> PAPER 반환, `get_environment("live")` -> LIVE 반환
  - `get_environment("invalid")` -> ValueError
  - `get_current_environment()` -> settings.TRADING_ENV 기반 반환
- 검증: `docker compose exec backend pytest tests/test_kis_config.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: kis_config.py 구현**
- `backend/core/clients/__init__.py` 빈 파일 생성
- `backend/core/clients/kis_config.py` 생성
- `dataclass(frozen=True)` 기반 `KISEnvironment`:
  - `name: str` -- "paper" / "live"
  - `rest_domain: str` -- 도메인:포트 (HTTPS)
  - `ws_url: str` -- 웹소켓 URL
  - `order_tr_prefix: str` -- "V"(모의) / "T"(실전)
  - `app_key_env: str` -- 환경변수명 (KIS_MOCK_APP_KEY / KIS_APP_KEY)
  - `app_secret_env: str` -- 환경변수명
  - `account_env: str` -- 환경변수명
  - `rate_limit_interval: float` -- 요청 간 최소 간격(초)
  - `@property base_url` -> `https://{rest_domain}`
  - `@property app_key` -> settings에서 해당 환경변수 값 참조
  - `@property app_secret` -> 동일
  - `@property account_no` -> 동일
- 상수 `PAPER`, `LIVE` -- Phase 1 문서의 확정 파라미터 그대로:
  - PAPER: rest_domain="openapivts.koreainvestment.com:29443", ws_url="ws://ops.koreainvestment.com:31000", order_tr_prefix="V", rate_limit_interval=1.5
  - LIVE: rest_domain="openapi.koreainvestment.com:9443", ws_url="ws://ops.koreainvestment.com:21000", order_tr_prefix="T", rate_limit_interval=0.07 (약 1/14초)
- `get_environment(name: str) -> KISEnvironment` -- "paper"->PAPER, "live"->LIVE, else ValueError
- `get_current_environment() -> KISEnvironment` -- `settings.TRADING_ENV` 기반
- 검증: `docker compose exec backend pytest tests/test_kis_config.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/clients/__init__.py backend/core/clients/kis_config.py backend/tests/test_kis_config.py
git commit -m "feat(phase1-sprint2): KIS 환경 설정 -- 모의/실전 전환 매핑 (KISEnvironment)"
```

**완료 기준:**
- ✅ pytest test_kis_config.py 통과
- ✅ PAPER/LIVE 상수값이 Phase 1 문서 확정 파라미터와 일치

---

### Task 2: Rate Limit 스로틀러 (토큰 버킷)

**Files:**
- Create: `backend/core/clients/throttler.py`
- Test: `backend/tests/test_throttler.py`

**Step 1: 테스트 작성**
- `backend/tests/test_throttler.py` 생성
- 테스트 항목:
  - `TokenBucketThrottler(interval=1.0)`: 첫 호출 즉시 통과 (대기 없음)
  - 연속 2회 호출 시 두 번째는 약 1.0초 대기 (0.9~1.2초 범위 허용)
  - `interval=0.1`로 빠른 간격 테스트 -- 3회 연속 호출 후 총 소요시간이 0.15~0.3초 사이
  - `backoff()` 호출 시 interval이 2배로 증가 (지수 백오프)
  - `reset_backoff()` 호출 시 interval이 원래 값으로 복원
  - 최대 백오프: 3단계까지 (interval x2 x4 x8, max 3회)
- 검증: `docker compose exec backend pytest tests/test_throttler.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: throttler.py 구현**
- `backend/core/clients/throttler.py` 생성
- `TokenBucketThrottler` 클래스:
  - `__init__(self, interval: float, max_backoff_steps: int = 3)` -- interval: 요청 간 최소 간격(초), max_backoff_steps: 최대 백오프 단계
  - `_base_interval: float` -- 원래 간격 (reset용)
  - `_current_interval: float` -- 현재 간격 (백오프 적용)
  - `_backoff_count: int` -- 현재 백오프 단계
  - `_last_request_time: float` -- 마지막 요청 시각 (time.monotonic)
  - `_lock: asyncio.Lock` -- 동시 접근 보호
  - `async def acquire(self)` -- 다음 요청까지 필요 시 asyncio.sleep 후 _last_request_time 갱신
  - `def backoff(self)` -- _current_interval *= 2 (max_backoff_steps까지)
  - `def reset_backoff(self)` -- _current_interval = _base_interval, _backoff_count = 0
  - `@property current_interval` -> _current_interval
- 검증: `docker compose exec backend pytest tests/test_throttler.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/clients/throttler.py backend/tests/test_throttler.py
git commit -m "feat(phase1-sprint2): Rate Limit 스로틀러 -- 토큰 버킷 + 지수 백오프"
```

**완료 기준:**
- ✅ pytest test_throttler.py 통과
- ✅ 스로틀러가 지정 간격을 준수하고 백오프가 동작

---

### Task 3: 토큰 매니저 (Redis 캐싱 + 자동 갱신)

**Files:**
- Create: `backend/core/clients/token_manager.py`
- Test: `backend/tests/test_token_manager.py`

**Step 1: 테스트 작성**
- `backend/tests/test_token_manager.py` 생성
- 모든 테스트는 httpx.AsyncClient를 mock하여 실제 API 호출 없이 수행
- 테스트 항목:
  - `get_access_token()` -- 캐시 미스 시 한투 OAuth API 호출 후 Redis에 저장, 토큰 반환
  - `get_access_token()` -- 캐시 히트 시 API 호출 없이 Redis에서 토큰 반환
  - `get_approval_key()` -- WebSocket approval_key 발급 + Redis 캐싱
  - `get_hashkey()` -- hashkey 발급 (캐싱 없음, 매번 호출)
  - `refresh_token()` -- 기존 토큰 무시하고 강제 재발급 후 Redis 업데이트
  - `_should_refresh()` -- Redis TTL 기반으로 만료 2시간 전이면 True
  - 토큰 발급 실패(HTTP 에러) 시 KISAuthError 예외 발생
  - 토큰 발급 Rate Limit 실패(`EGW00133`) 시 60초 대기 후 재시도 로직
- 검증: `docker compose exec backend pytest tests/test_token_manager.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: token_manager.py 구현**
- `backend/core/clients/token_manager.py` 생성
- `KISAuthError(Exception)` -- 인증 실패 커스텀 예외
- `KISTokenManager` 클래스:
  - `__init__(self, env: KISEnvironment, redis: RedisClient)` -- 환경 설정 + Redis 클라이언트 주입
  - `_http: httpx.AsyncClient | None` -- 지연 초기화 (첫 호출 시 생성)
  - Redis 키:
    - `kis:{env.name}:access_token` (TTL: 82800초 = 23시간)
    - `kis:{env.name}:approval_key` (TTL: 82800초 = 23시간)
  - `async def get_access_token(self) -> str` -- Redis 캐시 확인 -> 미스 시 OAuth 토큰 발급 -> Redis 저장 -> 반환
  - `async def get_approval_key(self) -> str` -- WS 접속용 approval_key 발급 + Redis 캐싱
  - `async def get_hashkey(self, body: dict) -> str` -- hashkey 발급 (캐싱 없음)
  - `async def refresh_token(self) -> str` -- 기존 캐시 삭제 후 강제 재발급
  - `async def _should_refresh(self) -> bool` -- Redis TTL 확인, 잔여 TTL < 7200(2시간)이면 True
  - `async def _request_token(self) -> tuple[str, int]` -- `POST /oauth2/tokenP` 호출. 반환: (access_token, expires_in_seconds). body: grant_type="client_credentials", appkey, appsecret
  - `async def _request_approval_key(self) -> str` -- `POST /oauth2/Approval` 호출. body: grant_type="client_credentials", appkey, secretkey
  - `async def _request_hashkey(self, body: dict) -> str` -- `POST /uapi/hashkey` 호출
  - 에러 처리:
    - HTTP 에러 -> KISAuthError
    - `EGW00133` (토큰 발급 Rate Limit) -> 60초 대기 후 1회 재시도
    - `EGW00121` (잘못된 토큰) -> refresh_token() 호출
  - `async def close(self)` -- httpx 클라이언트 종료
- 검증: `docker compose exec backend pytest tests/test_token_manager.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/clients/token_manager.py backend/tests/test_token_manager.py
git commit -m "feat(phase1-sprint2): 토큰 매니저 -- OAuth/approval_key/hashkey + Redis 캐싱"
```

**완료 기준:**
- ✅ pytest test_token_manager.py 통과
- ✅ 토큰 Redis 캐싱 동작 (캐시 히트 시 API 미호출 확인)
- ✅ 에러 시나리오 (Rate Limit, 만료 토큰) 처리 확인

---

### Task 4: KIS REST 클라이언트

**Files:**
- Create: `backend/core/clients/kis_rest.py`
- Test: `backend/tests/test_kis_rest.py`

**Step 1: 테스트 작성**
- `backend/tests/test_kis_rest.py` 생성
- TokenManager와 httpx를 mock하여 단위 테스트 수행
- 테스트 항목:
  - **시세 조회**:
    - `get_stock_price("005930")` -- 정상 응답(rt_cd="0") 시 StockPrice 반환 (현재가, 등락률, 거래량 등)
    - `get_stock_price("999999")` -- 빈 데이터(stck_prpr=="0") 시 KISDataError 예외
    - `get_orderbook("005930")` -- 정상 응답 시 Orderbook 반환 (매수/매도 각 10단계)
  - **주문**:
    - `place_order(OrderRequest)` -- 정상 시 OrderResponse 반환 (주문번호 포함)
    - `cancel_order("order_no", CancelRequest)` -- 정상 시 응답 반환
    - `get_order_status("order_no")` -- 정상 시 주문 상태 dict 반환
  - **계좌**:
    - `get_balance()` -- 잔고 응답 파싱
    - `get_positions()` -- 보유 종목 리스트 파싱
  - **에러 핸들링**:
    - 만료 토큰(EGW00121) -> 토큰 재발급 후 1회 재시도
    - Rate Limit 초과 -> 스로틀러 backoff() 호출 + 재시도 (최대 3회)
    - 장외 주문 거부(rt_cd=1) -> KISOrderError 예외
  - **공통 헤더**:
    - 모든 요청에 authorization, appkey, appsecret, tr_id 헤더 포함 확인
    - 모의 주문 tr_id가 "V"로 시작하는지 확인
- 검증: `docker compose exec backend pytest tests/test_kis_rest.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 스키마 정의 및 REST 클라이언트 구현**
- `backend/core/clients/kis_rest.py` 생성
- Pydantic 스키마 (파일 상단):
  - `StockPrice`: stock_code, price(int), change(int), change_rate(float), volume(int), trade_amount(int), high(int), low(int), open_price(int)
  - `OrderbookItem`: price(int), volume(int)
  - `Orderbook`: asks(list[OrderbookItem]), bids(list[OrderbookItem]), total_ask_volume(int), total_bid_volume(int)
  - `OrderRequest`: stock_code(str), order_type(str "buy"/"sell"), quantity(int), price(int, 0이면 시장가), order_division(str, 기본 "01" 시장가)
  - `OrderResponse`: order_no(str), stock_code(str), message(str)
  - `CancelRequest`: stock_code(str), quantity(int), cancel_type(str, 기본 "02" 취소)
  - `Balance`: total_eval_amount(int), total_profit(int), total_profit_rate(float)
  - `Position`: stock_code(str), stock_name(str), quantity(int), avg_price(int), current_price(int), profit_rate(float)
- `KISDataError(Exception)` -- 데이터 조회 실패 (빈 데이터, 잘못된 종목)
- `KISOrderError(Exception)` -- 주문 실패 (장외 주문, 잔고 부족 등)
- `KISRestClient` 클래스:
  - `__init__(self, env: KISEnvironment, token_manager: KISTokenManager, throttler: TokenBucketThrottler)`
  - `_http: httpx.AsyncClient` -- 지연 초기화
  - 공통 메서드:
    - `async def _get_headers(self, tr_id: str) -> dict` -- authorization(Bearer + token), appkey, appsecret, tr_id, content-type 포함
    - `async def _request(self, method: str, path: str, tr_id: str, params: dict = None, body: dict = None) -> dict` -- 스로틀러 acquire -> 요청 -> 에러 핸들링 -> JSON 반환:
      - `EGW00121` (만료 토큰) -> token_manager.refresh_token() -> 1회 재시도
      - `초당 거래건수를 초과` (Rate Limit) -> throttler.backoff() -> 재시도 (최대 3회)
      - 재시도 성공 후 throttler.reset_backoff()
  - 시세:
    - `async def get_stock_price(self, stock_code: str) -> StockPrice`:
      - `GET /uapi/domestic-stock/v1/quotations/inquire-price`
      - tr_id: `FHKST01010100`
      - params: FID_COND_MRKT_DIV_CODE="J", FID_INPUT_ISCD=stock_code
      - 응답 output에서 stck_prpr=="0"이면 KISDataError
      - 정상 시 StockPrice 파싱 반환
    - `async def get_orderbook(self, stock_code: str) -> Orderbook`:
      - `GET /uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn`
      - tr_id: `FHKST01010200`
  - 주문:
    - `async def place_order(self, order: OrderRequest) -> OrderResponse`:
      - `POST /uapi/domestic-stock/v1/trading/order-cash`
      - tr_id: `{env.order_tr_prefix}TTC0802U`(매수) / `{env.order_tr_prefix}TTC0801U`(매도)
      - body: CANO=account_no[:8], ACNT_PRDT_CD=account_no[8:], PDNO=stock_code, ORD_DVSN=order_division, ORD_QTY=str(quantity), ORD_UNPR=str(price)
      - hashkey 포함 (token_manager.get_hashkey)
      - rt_cd != "0" 시 KISOrderError
    - `async def cancel_order(self, order_no: str, request: CancelRequest) -> dict`:
      - `POST /uapi/domestic-stock/v1/trading/order-rvsecncl`
      - tr_id: `{env.order_tr_prefix}TTC0803U`
    - `async def get_order_status(self, order_no: str) -> dict`:
      - `GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld`
      - tr_id: `{env.order_tr_prefix}TTC8001R`
  - 계좌:
    - `async def get_balance(self) -> Balance`:
      - `GET /uapi/domestic-stock/v1/trading/inquire-balance`
      - tr_id: `{env.order_tr_prefix}TTS3320R`
    - `async def get_positions(self) -> list[Position]` -- 동일 API의 output1 파싱
  - `async def close(self)` -- httpx 클라이언트 종료
- 검증: `docker compose exec backend pytest tests/test_kis_rest.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/clients/kis_rest.py backend/tests/test_kis_rest.py
git commit -m "feat(phase1-sprint2): KIS REST 클라이언트 -- 시세/주문/계좌 + 에러 핸들링"
```

**완료 기준:**
- ✅ pytest test_kis_rest.py 통과
- ✅ 5가지 에러 시나리오 대응 테스트 통과
- ✅ 모의/실전 tr_id 접두사 자동 전환 확인

---

### Task 5: KIS WebSocket 클라이언트 (기본 프레임)

**Files:**
- Create: `backend/core/clients/kis_ws.py`
- Test: `backend/tests/test_kis_ws.py`

**Step 1: 테스트 작성**
- `backend/tests/test_kis_ws.py` 생성
- websockets 라이브러리를 mock하여 단위 테스트 수행
- 테스트 항목:
  - `connect()` -- WebSocket 연결 성공, approval_key 사용 확인
  - `disconnect()` -- 연결 종료
  - `subscribe("005930", "H0STCNT0")` -- 구독 메시지 전송 형식 검증 (header: approval_key, custtype, tr_type="1"; body: tr_id, tr_key)
  - `unsubscribe("005930", "H0STCNT0")` -- 해제 메시지 전송 형식 검증 (tr_type="2")
  - `_on_message()` -- JSON 메시지(서버 응답) 처리, 파이프 구분 데이터(실시간) 처리
  - `_reconnect()` -- 연결 끊김 후 자동 재연결 + 기존 구독 목록 재구독
  - 구독 목록 관리: subscribe 후 `_subscriptions` set에 추가, unsubscribe 후 제거
  - 콜백 등록: `on_data` 콜백이 실시간 데이터 수신 시 호출되는지 확인
- 검증: `docker compose exec backend pytest tests/test_kis_ws.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: kis_ws.py 구현**
- `backend/core/clients/kis_ws.py` 생성
- `KISWebSocketClient` 클래스:
  - `__init__(self, env: KISEnvironment, token_manager: KISTokenManager)`:
    - `_env`, `_token_manager`
    - `_ws: websockets.WebSocketClientProtocol | None`
    - `_subscriptions: set[tuple[str, str]]` -- (stock_code, tr_id) 구독 목록
    - `_connected: bool`
    - `_receive_task: asyncio.Task | None`
    - `_on_data: Callable | None` -- 데이터 수신 콜백
  - `async def connect(self) -> None`:
    - approval_key 발급 (token_manager.get_approval_key)
    - `websockets.connect(env.ws_url, ping_interval=30)`
    - `_connected = True`
    - 수신 루프 시작 (`asyncio.create_task(_receive_loop())`)
  - `async def disconnect(self) -> None`:
    - `_connected = False`
    - 수신 루프 취소
    - WebSocket close
  - `async def subscribe(self, stock_code: str, tr_id: str = "H0STCNT0") -> None`:
    - 구독 메시지 전송: header(approval_key, custtype="P", tr_type="1", content-type="utf-8"), body(input: tr_id, tr_key=stock_code)
    - `_subscriptions.add((stock_code, tr_id))`
  - `async def unsubscribe(self, stock_code: str, tr_id: str = "H0STCNT0") -> None`:
    - 해제 메시지 전송 (tr_type="2")
    - `_subscriptions.discard((stock_code, tr_id))`
  - `async def _receive_loop(self) -> None`:
    - while _connected: recv -> _on_message
    - ConnectionClosed 시 _reconnect() 호출
  - `async def _on_message(self, message: str) -> None`:
    - JSON(서버 응답/확인): 로그 출력
    - 파이프 구분(실시간 데이터): 기본 파싱(tr_id, 원시 데이터) + on_data 콜백 호출
    - Phase 1에서는 상세 파싱 없이 원시 데이터로 콜백 전달
  - `async def _reconnect(self) -> None`:
    - 연결 끊김 감지 후 자동 재연결 시도
    - 재연결 성공 시 `_subscriptions`의 모든 항목 재구독
    - 최대 5회 시도, 재시도 간 지수 백오프 (1, 2, 4, 8, 16초)
  - `def set_on_data(self, callback: Callable) -> None` -- 콜백 등록
  - `@property connected` -> _connected
  - `@property subscription_count` -> len(_subscriptions)
- 검증: `docker compose exec backend pytest tests/test_kis_ws.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/clients/kis_ws.py backend/tests/test_kis_ws.py
git commit -m "feat(phase1-sprint2): KIS WebSocket 클라이언트 -- 연결/구독/재연결 기본 프레임"
```

**완료 기준:**
- ✅ pytest test_kis_ws.py 통과
- ✅ 구독/해제 메시지 형식이 한투 API 스펙과 일치
- ✅ 재연결 시 기존 구독 목록 자동 복원

---

### Task 6: Settings CRUD + KIS 테스트 API 엔드포인트

**Files:**
- Create: `backend/api/routes/settings.py`
- Create: `backend/api/routes/kis.py`
- Test: `backend/tests/test_settings_api.py`
- Test: `backend/tests/test_kis_api.py`

**Step 1: Settings API 테스트 작성**
- `backend/tests/test_settings_api.py` 생성
- httpx.AsyncClient + ASGI Transport 사용 (기존 test_integration.py 패턴 참조)
- 테스트 항목:
  - `GET /api/v1/settings` -- 전체 설정 목록 조회, 21개 항목 반환
  - `GET /api/v1/settings?category=risk` -- 카테고리 필터링
  - `GET /api/v1/settings/{key}` -- 단일 설정 조회 (trading_env -> "paper")
  - `PUT /api/v1/settings/{key}` -- 설정 값 수정 (trading_env: "paper" -> "live" -> "paper" 복원)
  - `GET /api/v1/settings/nonexistent` -- 404
  - `PUT /api/v1/settings/nonexistent` -- 404
- 검증: `docker compose exec backend pytest tests/test_settings_api.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: Settings 라우터 구현**
- `backend/api/routes/settings.py` 생성
- `router = APIRouter(prefix="/settings", tags=["settings"])`
- 엔드포인트:
  - `GET /settings` -- 전체 조회 (category 쿼리 파라미터 옵션). SQLAlchemy select, 선택적 where(category==)
  - `GET /settings/{key}` -- 단일 조회. 미존재 시 HTTPException(404)
  - `PUT /settings/{key}` -- 값 수정 (body: {"value": "new_value"}). updated_at 자동 갱신. 미존재 시 HTTPException(404)
- DB 세션: `Depends(get_db)` 사용 (api/deps.py)
- 검증: `docker compose exec backend pytest tests/test_settings_api.py -v`
- 예상: PASS

**Step 3: KIS 테스트 API 테스트 작성**
- `backend/tests/test_kis_api.py` 생성
- KIS 클라이언트를 mock하여 단위 테스트
- 테스트 항목:
  - `GET /api/v1/kis/status` -- KIS 연결 상태 조회 (환경명, 토큰 존재 여부, WS 연결 상태)
  - `GET /api/v1/kis/price/{stock_code}` -- 시세 조회 (mock 응답 검증)
  - `GET /api/v1/kis/price/999999` -- 잘못된 종목 시 400 에러
- 검증: `docker compose exec backend pytest tests/test_kis_api.py -v`
- 예상: FAIL (모듈 미존재)

**Step 4: KIS 테스트 라우터 구현**
- `backend/api/routes/kis.py` 생성
- `router = APIRouter(prefix="/kis", tags=["kis"])`
- 엔드포인트:
  - `GET /kis/status` -- 현재 환경(paper/live), 토큰 유효 여부(Redis에 토큰 존재?), WS 연결 상태 반환. app.state에서 KIS 클라이언트 참조 (Request.app.state)
  - `GET /kis/price/{stock_code}` -- 시세 조회 프록시 (KIS REST 클라이언트 호출). KISDataError 시 HTTPException(400)
- 검증: `docker compose exec backend pytest tests/test_kis_api.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/api/routes/settings.py backend/api/routes/kis.py backend/tests/test_settings_api.py backend/tests/test_kis_api.py
git commit -m "feat(phase1-sprint2): Settings CRUD API + KIS 시세/상태 테스트 엔드포인트"
```

**완료 기준:**
- ✅ pytest test_settings_api.py 통과
- ✅ pytest test_kis_api.py 통과
- ✅ Settings CRUD 동작 확인

---

### Task 7: 통합 테스트 + main.py 라우터 등록

**Files:**
- Modify: `backend/main.py` (라우터 등록 추가: settings, kis. lifespan에 KIS 클라이언트 초기화 추가)
- Create: `backend/tests/test_sprint2_integration.py`

**Step 1: main.py 수정**
- `backend/main.py` 수정
- import 추가:
  - `from api.routes.settings import router as settings_router`
  - `from api.routes.kis import router as kis_router`
  - `from core.clients.kis_config import get_current_environment`
  - `from core.clients.token_manager import KISTokenManager`
  - `from core.clients.throttler import TokenBucketThrottler`
  - `from core.clients.kis_rest import KISRestClient`
  - `from core.clients.kis_ws import KISWebSocketClient`
- lifespan 수정:
  - startup 순서: Redis 연결 -> KIS 환경 로드 -> TokenManager 생성 -> Throttler 생성 -> RestClient 생성 -> WsClient 생성
  - 초기화된 클라이언트를 `app.state`에 저장:
    - `app.state.kis_env` -- 현재 KISEnvironment
    - `app.state.kis_token_manager` -- KISTokenManager 인스턴스
    - `app.state.kis_rest` -- KISRestClient 인스턴스
    - `app.state.kis_ws` -- KISWebSocketClient 인스턴스
  - shutdown: kis_rest.close() -> kis_ws.disconnect() -> kis_token_manager.close() -> Redis 종료
- 라우터 등록 추가:
  - `app.include_router(settings_router, prefix="/api/v1")`
  - `app.include_router(kis_router, prefix="/api/v1")`
- 검증: main.py 구문 오류 없음 확인

**Step 2: 통합 테스트 작성**
- `backend/tests/test_sprint2_integration.py` 생성
- 테스트 항목:
  - 헬스체크 API 여전히 동작 (`GET /api/v1/health` -> 200)
  - Settings API 동작 (`GET /api/v1/settings` -> 200, 21개 항목)
  - Settings 카테고리 필터 (`GET /api/v1/settings?category=risk` -> risk 항목만)
  - KIS 상태 API 동작 (`GET /api/v1/kis/status` -> 200, 환경명 포함)
  - 기존 Sprint 1 테스트 회귀 없음 확인
  - Swagger UI에 /settings, /kis 라우터 표시 확인 (GET /openapi.json 파싱)
- 검증: `docker compose exec backend pytest tests/test_sprint2_integration.py -v`
- 예상: PASS

**Step 3: 전체 테스트 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: Sprint 1 기존 테스트 + Sprint 2 신규 테스트 전체 통과

**Step 4: 커밋**
```
git add backend/main.py backend/tests/test_sprint2_integration.py
git commit -m "feat(phase1-sprint2): 라우터 등록 + KIS 클라이언트 lifespan 초기화 + 통합 테스트"
```

**완료 기준:**
- ✅ pytest 전체 통과 (Sprint 1 + Sprint 2 테스트, 95개 passed)
- ✅ 새 라우터(/api/v1/settings, /api/v1/kis) Swagger UI에 표시
- ✅ 기존 헬스체크/시드 데이터 테스트 회귀 없음

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | Sprint 1(8) + Sprint 2 신규 테스트 전체 passed |
| 헬스체크 API | `curl -s http://localhost:8000/api/v1/health \| python3 -m json.tool` | `{"status": "healthy", ...}` |
| Settings 목록 | `curl -s http://localhost:8000/api/v1/settings \| python3 -m json.tool` | 21개 설정 항목 |
| Settings 단일 | `curl -s http://localhost:8000/api/v1/settings/trading_env \| python3 -m json.tool` | `{"key": "trading_env", "value": "paper", ...}` |
| KIS 상태 | `curl -s http://localhost:8000/api/v1/kis/status \| python3 -m json.tool` | `{"environment": "paper", ...}` |
| Swagger UI | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs` | 200 |
| 프론트엔드 | `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000` | 200 |
| Docker 컨테이너 | `docker compose ps` | 4컨테이너 모두 Up |
