# 텔레그램 연동

`python-telegram-bot` 라이브러리 기반. `modules/notifier/` 구현.

## 역할

1. **알림 발송**: 신호 생성, 주문 체결, 리스크 이벤트, 일일 리포트
2. **승인 처리**: 반자동 모드에서 사용자 응답 수신 및 처리

## 환경변수

| 변수 | 설명 |
|------|------|
| `TELEGRAM_BOT_TOKEN` | BotFather에서 발급 |
| `TELEGRAM_CHAT_ID` | 수신자 chat ID (1인 사용자) |
| `TELEGRAM_WEBHOOK_URL` | 웹훅 URL (Railway 백엔드 URL) |

## 알림 유형

### 신호 알림 (반자동 모드)

```
📈 매수 신호 발생

종목: 삼성전자 (005930)
전략: 모멘텀 돌파
신뢰도: 0.78
진입가: 72,500원
근거: 전일 고가 돌파, 거래량 전일比 2.3배

[✅ 승인] [❌ 거부]
```

인라인 버튼으로 응답. 응답 대기 타임아웃: 설정값(기본 3분).

### 주문 체결 알림

```
✅ 매수 체결

종목: 삼성전자 (005930)
체결가: 72,600원 / 14주
투자금: 1,016,400원
```

### 리스크 이벤트

```
🚨 비상 정지 활성화

일일 손실: -4.2% (임계값: -4.0%)
모든 신규 진입 차단
보유 포지션 청산 시작
```

### 일일 리포트 (장 마감 후)

- 당일 거래 건수, 실현 손익
- 종목별 수익률
- 누적 손익

## 승인 처리 흐름

```
신호 생성 → TradeSignal(pending) 저장
  → 텔레그램 메시지 발송 (인라인 버튼)
  → Redis에 pending 신호 캐시
  → 사용자 응답 대기

사용자 응답:
  승인 → TradeSignal(approved) → [[order-execution|주문 실행]]
  거부 → TradeSignal(rejected) → 폐기
  타임아웃 → TradeSignal(rejected) → 폐기
```

## 웹훅 vs Polling

- 프로덕션: 웹훅 방식 (Railway 엔드포인트)
- 로컬 개발: polling 방식 (웹훅 URL 없음)
- `TELEGRAM_WEBHOOK_URL` 설정 여부로 자동 전환

## Rate Limit

Telegram Bot API: 초당 30건. 단독 사용자이므로 한도 초과 거의 없음.
