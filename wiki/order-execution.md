# 주문 실행

승인된 매매 신호를 실제 주문으로 변환하여 KIS API에 제출. `trading/order_manager.py` 구현.

## 주문 흐름

```
TradeSignal (status=approved 또는 full_auto)
  → [[risk-management|리스크 체크]] (통과 필수)
  → [[position-sizing|포지션 사이징]] (투자금 계산)
  → KIS REST API 주문 제출
  → 체결 확인 (polling 또는 WebSocket)
  → [[position-management|포지션 생성/업데이트]]
  → TradeSignal status → executed
  → [[telegram-integration|텔레그램 알림]]
```

## 주문 유형

| 주문 | 설명 |
|------|------|
| 시장가 매수 | 즉시 체결, 슬리피지 위험 있음 |
| 지정가 매수 | 목표가 지정, 미체결 위험 |
| 시장가 매도 | 즉시 청산 |
| 지정가 매도 | 손절/익절 목표가 지정 |

현재는 기본적으로 시장가 주문 사용.

## KIS REST 주문 API

- 환경별 `tr_id` 접두사 다름 — [[kis-api]] 참조
- 모의: `V`, 실전: `T`
- 주문 수량: [[position-sizing|PositionSizer]]가 계산

## 체결 확인

주문 후 체결 확인 방식:
1. **주문 직후**: REST API로 주문번호 수신
2. **체결 대기**: REST polling (`inquire-daily-ccld`) 또는 WebSocket 체결 이벤트
3. **미체결 처리**: 일정 시간 후 미체결 시 취소

## 청산 (매도) 트리거

포지션 청산은 여러 경로에서 발생:
- **손절**: `risk_manager`가 일일 손실 임계값 감지 → 강제 청산
- **익절**: 전략 목표 달성 시 신호 생성 → 매도 주문
- **장 마감 청산**: `eod_liquidator.py`가 15:30 전 전량 청산
- **수동 청산**: 대시보드 또는 텔레그램에서 수동 명령

## 오류 처리

- **주문 실패**: 재시도 1회 후 알림 발송
- **미체결 타임아웃**: 취소 후 시장가 재주문 (설정에 따라)
- **API 에러**: TradeSignal status → `failed`, 알림 발송

## 모의거래 Rate Limit

모의 환경에서는 초당 1건 스로틀링이 내장되어 있어 연속 주문 시 자동 대기.
