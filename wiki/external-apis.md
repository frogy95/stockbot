# 외부 API 의존성

StockBot이 의존하는 모든 외부 API 요약.

## API 목록

| API | 용도 | Rate Limit | 환경변수 |
|-----|------|-----------|---------|
| 한국투자증권 (실전) | 시세 + 주문 | 초당 ~20건 | `KIS_APP_KEY`, `KIS_APP_SECRET` |
| 한국투자증권 (모의) | 개발/테스트 | 초당 ~1건 | `KIS_MOCK_APP_KEY`, `KIS_MOCK_APP_SECRET` |
| 공공데이터포털 | 전 종목 일봉 | 일 1,000건 | `DATA_GO_KR_API_KEY` |
| Open Dart | 재무/공시 | 일 10,000건 | `DART_API_KEY` |
| 네이버 검색 | 뉴스 센티멘트 | 일 25,000건 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| Telegram Bot | 알림/승인 | 초당 30건 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

## API별 상세

- [[kis-api]] — 한국투자증권 REST/WebSocket API 상세
- [[public-data-sources]] — 공공데이터포털/DART/네이버 상세
- [[telegram-integration]] — 텔레그램 봇 상세

## Rate Limit 관리

| 위험도 | API | 관리 방법 |
|--------|-----|---------|
| 높음 | 공공데이터포털 (일 1,000건) | 장전 1회 일괄 처리 |
| 중간 | KIS 모의 (초당 1건) | 스로틀링 내장 |
| 낮음 | KIS 실전 (초당 ~20건) | 자연 발생 요청만 |
| 낮음 | DART (일 10,000건) | 분기 수집만 |
| 낮음 | 네이버 (일 25,000건) | 일 1~2회 배치 |

## 인증 방식

| API | 인증 |
|-----|------|
| KIS | OAuth 2.0 (App Key/Secret → Access Token, 자동 갱신) |
| 공공데이터포털 | API Key (쿼리 파라미터) |
| DART | API Key (쿼리 파라미터) |
| 네이버 | Client ID/Secret (헤더) |
| Telegram | Bot Token (URL 경로) |

## 클라이언트 구현

`backend/core/clients/` 하위에 각 API별 클라이언트 모듈:
- `kis_rest.py`: KIS REST API
- `kis_ws.py`: KIS WebSocket (→ [[websocket-management]])
- `public_data.py`: 공공데이터포털
- `dart.py`: Open DART
- `naver.py`: 네이버 검색

## 장애 대응

- 공공데이터포털 장애: 전일 데이터로 1차 스크리닝 대체 (데이터 최신성 저하)
- KIS API 장애: 매매 중단 + 텔레그램 알림
- 텔레그램 장애: 반자동 모드 임시 완전자동 전환 필요 (수동 설정)
