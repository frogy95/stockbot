# Phase 3 검토 리포트 — 윤에이피 (API 개발자)

> **검토일**: 2026-03-30
> **검토 대상**: Phase 3 아키텍처 초안 (매매 엔진 + 기본 알림)

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| 한투 주문 API 활용 | ✅ 통과 |
| 주문 체결 확인 방식 | ⚠️ 주의 |
| 텔레그램 웹훅 설정 | ✅ 통과 |
| Redis 승인 키 설계 | ✅ 통과 |
| Rate Limit 우선순위 | ⚠️ 추가 필요 |

## 2. 항목별 검증 결과

### 한투 주문 API
- `KISRestClient`에 `place_order()`, `cancel_order()`, `get_order_status()`, `get_balance()`, `get_positions()`가 이미 구현됨.
- 모의/실전 tr_id 분기도 `order_tr_prefix`로 처리됨. 추가 구현 불필요.
- 주문 응답의 `ODNO`(주문번호)를 orders 테이블에 저장하여 추적.

### 주문 체결 확인
- **모의거래에서는 웹소켓 체결 통보 미지원**. REST 폴링만 가능.
- `get_order_status()` 2초 간격 폴링, 최대 30초 (15회). 미체결 시 상태를 "timeout"으로.
- 실전에서는 웹소켓 체결 통보(`H0STCNT0`의 체결 데이터) 활용 가능하나, 모의와 실전 일관성을 위해 **MVP는 REST 폴링 통일** 권고.
- 체결 폴링 로직은 별도 비동기 태스크로 분리 (주문 API 응답은 즉시 반환).

### 텔레그램 웹훅
- Railway에서 HTTPS 자동 제공. 웹훅 URL: `https://api.stockbot.choiji.kr/api/v1/telegram/webhook`
- `python-telegram-bot` 라이브러리의 `Application.run_webhook()` 또는 FastAPI 엔드포인트에서 직접 처리.
- 권고: FastAPI 엔드포인트에서 직접 처리 (기존 앱 구조와 일관).
- 봇 토큰은 환경변수(`TELEGRAM_BOT_TOKEN`), 웹훅 URL은 환경변수(`TELEGRAM_WEBHOOK_URL`).

### Redis 승인 키 설계
- 키 패턴: `approval:{signal_id}` (order_id보다 signal_id가 적절 — 주문 전 승인이므로)
- 값: JSON `{signal_id, stock_code, signal_type, confidence, created_at, token}`
- TTL: 장중 30초, 마감전 15초 (Phase 1 확정값)
- 만료 시: Redis keyspace notification으로 감지 -> 자동 거부 처리 -> 텔레그램 알림
- 일회용 토큰: UUID4, 승인 요청마다 생성. 토큰 불일치 시 거부.

### Rate Limit 우선순위
- 현재 `TokenBucketThrottler`는 단순 FIFO. 주문이 시세 조회에 밀릴 수 있음.
- **우선순위 큐 추가 권고**: 주문(우선순위 1) > 체결확인(2) > 시세조회(3)
- 단, MVP에서는 단순하게 주문 시 스로틀러 bypass 옵션으로 구현 가능 (주문 빈도가 낮으므로).

## 3. 파라미터 조정 권고

| 항목 | 원래값 | 권고값 | 근거 |
|------|--------|--------|------|
| 체결 폴링 간격 | 미설정 | **2초, 최대 15회(30초)** | 모의거래 호환 |
| 웹훅 처리 | 미설정 | **FastAPI 엔드포인트 직접 처리** | 기존 구조 일관성 |
| 스로틀러 주문 우선 | 없음 | **주문 시 bypass 옵션** | 주문 지연 방지 |
| 텔레그램 웹훅 URL | 미설정 | **환경변수 TELEGRAM_WEBHOOK_URL** | 환경별 분리 |

## 4. 리스크 및 대안

- **체결 폴링 실패**: 30초 내 체결 확인 불가 시, 주문이 실제로 체결되었을 수 있음. 다음 잔고 조회 시 동기화하는 reconciliation 로직 필요.
- **텔레그램 웹훅 장애**: Railway 재배포 시 웹훅 URL이 변경될 수 있음. 앱 시작 시 `setWebhook` API를 자동 호출하여 갱신.
- **동시 주문 경합**: 여러 신호가 동시에 발생하면 Rate Limit 초과 위험. 주문 큐(asyncio.Queue)로 순차 실행 권고.
- **환경변수 추가**: `TELEGRAM_WEBHOOK_URL` 환경변수를 `.env.example`과 Railway에 추가 필요.
