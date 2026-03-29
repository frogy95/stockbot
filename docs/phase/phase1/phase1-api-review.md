# Phase 1 검토 리포트 — 윤에이피 (API 개발자)

**검토일**: 2026-03-29
**검토 대상**: Phase 1 아키텍처 초안 (한투 API 연동 중심)

---

## 1. 요약

| 영역 | 판정 |
|------|------|
| 한투 REST 클라이언트 설계 | ✅ 통과 |
| 한투 WebSocket 클라이언트 설계 | ⚠️ 주의 — 구현 범위 한정 필요 |
| 토큰 자동 갱신 로직 | ✅ 통과 |
| Rate Limit 스로틀링 | ✅ 통과 |
| 모의/실전 전환 구조 | ⚠️ 주의 — 설정 계층 명확화 필요 |
| 에러 핸들링 전략 | ⚠️ 주의 — Phase 0.5 발견 사항 반영 필수 |

## 2. 항목별 검증 결과

### 한투 REST 클라이언트

**구현 권고 구조**:

```python
# modules/collector/sources/kis.py 또는 core/clients/kis_rest.py
class KISRestClient:
    """한투 REST API 클라이언트"""

    # 인증
    async def get_access_token(self) -> str
    async def get_hashkey(self, body: dict) -> str

    # 시세
    async def get_stock_price(self, stock_code: str) -> dict        # 현재가
    async def get_orderbook(self, stock_code: str) -> dict           # 호가 10단계
    async def get_minute_chart(self, stock_code: str, period: str) -> dict  # 분봉

    # 주문 (Phase 1에서는 기본 구조만)
    async def place_order(self, order: OrderRequest) -> OrderResponse
    async def cancel_order(self, order_no: str) -> dict
    async def get_order_status(self, order_no: str) -> dict

    # 계좌
    async def get_balance(self) -> dict      # 잔고
    async def get_positions(self) -> dict    # 보유 종목
```

**핵심 포인트**:
- `tr_id` 매핑은 **딕셔너리 상수**로 관리. 모의/실전별 접두사(V/T) 자동 전환.
- 모든 API 호출에 **retry 데코레이터** 적용 (최대 3회, 지수 백오프).
- `FID_COND_MRKT_DIV_CODE`는 KOSPI/KOSDAQ/ETF 모두 `J` (Phase 0.5 확인).

### 한투 WebSocket 클라이언트

**Phase 1 범위 한정 권고**:

- Sprint 2에서는 **연결/인증/구독/수신/재연결** 기본 프레임만 구현.
- 데이터 파싱(시세/호가/체결 → 구조체 변환)은 Phase 2에서.
- 구독 관리(종목 추가/제거)는 Phase 2에서.

```python
# core/clients/kis_ws.py
class KISWebSocketClient:
    """한투 WebSocket 클라이언트"""

    async def connect(self) -> None
    async def disconnect(self) -> None
    async def subscribe(self, stock_code: str, data_type: str) -> None
    async def unsubscribe(self, stock_code: str, data_type: str) -> None
    async def _on_message(self, message: str) -> None     # 기본 수신 핸들러
    async def _reconnect(self) -> None                     # 자동 재연결 + 재구독
```

**주의사항**:
- 웹소켓 포트: 모의 `31000`, 실전 `21000` — `TRADING_ENV`에 따라 자동 전환.
- 재연결 시 **기존 구독 목록 복원** 필수 (Phase 0.5: 재연결 0.016초이나 재구독 필요).
- 웹소켓 최대 구독 종목 수 제한 확인 필요 (문서상 40종목/세션).

### 토큰 자동 갱신

**구현 권고**:

```
1. 서버 부팅 시: Redis에서 기존 토큰 확인
2. 토큰 없거나 만료 임박(2시간 전) → 신규 발급
3. 발급 실패 시: 1분 대기 후 재시도 (발급 Rate Limit 1분당 1회)
4. Redis 저장: key=kis:access_token, TTL=23시간
5. APScheduler로 6시간마다 갱신 체크
```

- **환경변수 APP_KEY/SECRET은 코드에 절대 하드코딩 금지** (Phase 0.5에서도 .env 관리).
- 토큰 발급 실패 시 **텔레그램 긴급 알림** (Phase 3에서 구현, Phase 1에서는 로그만).

### Rate Limit 스로틀링

**구현 권고: 토큰 버킷 알고리즘**

| 환경 | 기본 간격 | 버스트 허용 | 에러 시 백오프 |
|------|----------|-----------|--------------|
| 모의 (paper) | **1.5초** | 없음 | 3초 → 6초 → 12초 (지수) |
| 실전 (live) | **0.07초** (초당 14건, 70%) | 5건 버스트 | 0.5초 → 1초 → 2초 |

- `asyncio.Semaphore` + `asyncio.sleep` 조합.
- Rate Limit 에러 감지: 응답 메시지에 `"초당 거래건수를 초과"` 포함 시 백오프.
- **별도 스로틀러 인스턴스**: REST용, 토큰발급용 각각 분리.

### 모의/실전 전환 구조

**설정 계층 권고 (우선순위 높은 순)**:

```
1. 환경변수 TRADING_ENV (Docker/시스템 레벨)
2. settings 테이블 trading_env (런타임 레벨)
3. 전환 시 검증:
   - 환경변수가 'paper'이면 DB가 'live'여도 paper로 강제
   - 환경변수가 'live'이면 DB 값 참조 (추가 안전장치)
```

**전환 시 변경 항목 매핑**:

| 항목 | 모의 | 실전 |
|------|------|------|
| REST 도메인 | openapivts.koreainvestment.com:29443 | openapi.koreainvestment.com:9443 |
| WS URL | ops.koreainvestment.com:31000 | ops.koreainvestment.com:21000 |
| 주문 tr_id 접두사 | V | T |
| 시세 tr_id | 동일 | 동일 |
| APP_KEY/SECRET | KIS_MOCK_* | KIS_* |
| 계좌번호 | KIS_MOCK_ACCOUNT_NO | KIS_ACCOUNT_NO |
| Rate Limit | 1.5초 | 0.07초 |

이 매핑을 **Enum + dataclass**로 관리:

```python
@dataclass(frozen=True)
class KISEnvironment:
    rest_domain: str
    ws_url: str
    order_tr_prefix: str
    app_key_env: str
    app_secret_env: str
    account_env: str
    rate_limit_interval: float

PAPER = KISEnvironment(...)
LIVE = KISEnvironment(...)
```

### 에러 핸들링 (Phase 0.5 발견 사항 반영)

| 에러 | 감지 방법 | 대응 |
|------|----------|------|
| 잘못된 종목 (HTTP 200, 빈 데이터) | `stck_prpr == "0"` 체크 | 종목 마스터 테이블과 이중 검증 |
| 만료 토큰 (HTTP 500, EGW00121) | 에러코드 매칭 | 자동 재발급 → 재시도 (1회) |
| Rate Limit 초과 | 메시지 문자열 매칭 | 지수 백오프 |
| 장외 주문 거부 (rt_cd=1) | rt_cd 체크 | 장상태 사전 확인 강화 |
| 웹소켓 끊김 | on_close 이벤트 | 자동 재연결 + 재구독 |

## 3. 파라미터 조정 권고

| 항목 | 원래 설계 | 확정 권고 | 근거 |
|------|----------|----------|------|
| WS 구현 범위 | 전체 | **연결/인증/재연결만 (Sprint 2)** | 파싱/구독관리는 Phase 2 |
| KIS 클라이언트 위치 | modules/collector/sources/kis.py | **core/clients/kis_rest.py + kis_ws.py** | 수집뿐 아니라 주문에서도 사용, core에 배치 |
| 설정 계층 | TRADING_ENV 환경변수만 | **환경변수 > DB (환경변수 우선)** | 안전장치 이중화 |
| Rate Limit 구현 | 미정 | **토큰 버킷 (asyncio 기반)** | 비동기 환경에 적합 |
| 토큰 갱신 주기 | 미정 | **6시간마다 체크, 만료 2시간 전 갱신** | 24시간 유효, 여유 있게 |
| 에러 재시도 | 미정 | **최대 3회, 지수 백오프** | 과도한 재시도 방지 |

## 4. 리스크 및 대안

- **리스크 1**: 한투 API가 예고 없이 응답 구조를 변경하는 경우가 있다. **응답 파싱 시 필드 없음에 대한 방어 코드** 필수 (`.get()` 사용, KeyError 방지).
- **리스크 2**: 웹소켓 40종목 구독 제한. Phase 2에서 1차 스크리닝 후보가 40개를 초과하면 **복수 세션 또는 우선순위 기반 구독 로테이션** 필요. Phase 1에서는 인지만.
- **리스크 3**: 모의거래 환경에서 주문 관련 테스트가 평일 장중에만 가능. Sprint 2 일정에 **평일 장중 테스트 시간**을 확보해야 한다.
- **권고**: Phase 0.5의 exploration/ 코드는 참조만 하고 **Phase 1에서 완전히 재작성**. 탐색 코드를 프로덕션에 가져오면 기술 부채가 된다.
