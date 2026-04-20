# 한국투자증권 API

KIS(한국투자증권) OpenAPI는 [[data-collection-flow|장중 데이터 수집]]과 [[order-execution|주문 실행]]의 핵심 의존성이다.

## API 종류

| 종류 | 용도 | Rate Limit |
|------|------|-----------|
| REST API | 시세 조회, 주문 실행, 잔고 확인 | 실전: 초당 ~20건 |
| WebSocket | 실시간 체결 스트림 | — |
| 종목 마스터파일 | 전 종목 코드/명칭 다운로드 | 일 1회 |

## 환경별 분리

`TRADING_ENV` 플래그로 완전 분리. [[paper-vs-live]] 참조.

| 항목 | 모의거래 | 실전거래 |
|------|---------|---------|
| 환경변수 | `KIS_MOCK_APP_KEY`, `KIS_MOCK_APP_SECRET`, `KIS_MOCK_ACCOUNT_NO` | `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO` |
| REST 도메인 | `openapivts.koreainvestment.com` | `openapi.koreainvestment.com` |
| tr_id 접두사 | `V` (예: `VTTC0802U`) | `T` (예: `TTTC0802U`) |
| Rate Limit | 초당 1건 스로틀링 내장 | 초당 ~20건 |
| WebSocket URL | `ws://ops.koreainvestment.com:31000` (경로 없음) | `ws://ops.koreainvestment.com:21000/tryitout` (경로 필수) |

**중요**: LIVE WebSocket은 `/tryitout` 경로가 필수이고, PAPER는 다른 서버(포트 31000)이므로 경로가 불필요하다. 누락 시 연결 실패로 수 시간 낭비 가능. [[websocket-management]] 참조.

## 인증 토큰

- OAuth 2.0 방식 (App Key + App Secret → Access Token)
- 토큰 만료 시 자동 갱신
- `core/clients/kis_rest.py`에서 관리

## REST API 주요 엔드포인트

| 용도 | 엔드포인트 |
|------|-----------|
| 현재가 조회 | `GET /uapi/domestic-stock/v1/quotations/inquire-price` |
| 호가 조회 | `GET /uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn` |
| 분봉 조회 | `GET /uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion` |
| 매수 주문 | `POST /uapi/domestic-stock/v1/trading/order-cash` |
| 매도 주문 | `POST /uapi/domestic-stock/v1/trading/order-cash` |
| 잔고 조회 | `GET /uapi/domestic-stock/v1/trading/inquire-balance` |
| 체결 내역 | `GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld` |

## WebSocket 구독

실시간 체결 데이터 수신. `ws_manager.py`에서 연결 관리.
- 구독 코드: `H0STCNT0` (실시간 체결가)
- 연결 유지: 하트비트 + 자동 재연결
- 상세: [[websocket-management]]

## 종목 마스터파일

- `KIS_MST_BASE_URL`에서 일 1회 다운로드
- 전 종목 코드, 명칭, 시장 구분 포함
- 장전 수집 시 갱신

## 에러 처리

- Rate Limit 초과: 자동 retry with exponential backoff
- 토큰 만료: 자동 갱신 후 재시도
- WebSocket 연결 끊김: 자동 재연결 (최대 N회)
