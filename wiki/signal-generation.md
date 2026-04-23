# 매매 신호 생성

2차 스크리닝 통과 종목에 전략을 적용하여 `TradeSignal`을 생성. `trading/signal_generator.py` 구현.

## 생성 프로세스

```
screened_candidates (2차 스크리닝 결과)
  → 중복 신호 체크 (같은 종목 pending 신호 존재 시 스킵)
  → MarketSnapshot 조립 (DB + Redis 데이터)
  → 전략 적용 (strategy.generate_signal)
  → 신뢰도 필터 (MIN_CONFIDENCE = 0.6)
  → TradeSignal DB 저장
  → [[trading-modes|모드에 따라]] 승인 요청 또는 즉시 주문
```

## MarketSnapshot

전략에 입력되는 종목 상태 스냅샷:

| 필드 | 설명 |
|------|------|
| `stock_code` | 종목 코드 |
| `current_price` | 현재가 |
| `prev_close` | 전일 종가 |
| `prev_high` | 전일 고가 |
| `open_price` | 당일 시가 |
| `high` | 당일 고가 |
| `volume` | 당일 거래량 |
| `prev_volume` | 전일 거래량 |
| `trade_strength` | 체결강도 |
| `orderbook_ratio` | 호가잔량 비율 |

## 전략 인터페이스

```python
class Strategy(ABC):
    @property
    def name(self) -> str: ...

    async def generate_signal(
        self, snapshot: MarketSnapshot
    ) -> TradeSignalData | RejectedSignal:
        # 성공: TradeSignalData
        # 탈락: RejectedSignal(stage, detail) — 사유가 구조화되어 로그/알림에 활용
        ...
```

현재 구현: [[momentum-breakout-strategy]]

`RejectedSignal.stage`는 차단 지점을 식별한다 (`breakout`, `volume_threshold`, `trade_strength`, `atr_filter`, `confidence`, `prev_close_time_guard` 등). engine은 6지점 구조화 로그로 기록하고 선택적으로 텔레그램 알림을 발송한다.

## TradeSignal 구조

| 필드 | 설명 |
|------|------|
| `stock_code` | 종목 코드 |
| `signal_type` | `buy` / `sell` |
| `confidence` | 신뢰도 (0.0~1.0) |
| `strategy_name` | 전략 이름 |
| `reason` | 신호 근거 (JSON, `breakout_tier` 포함) |
| `status` | `pending` / `approved` / `rejected` / `executed` |
| `suggested_price` | 제안 진입가 |

`reason.breakout_tier`(`gap_open` / `prev_high` / `prev_close`)는 engine에서 [[position-sizing|포지션 사이징]] 시 반 포지션 분기에 사용된다.

## 신뢰도 임계값

```python
MIN_CONFIDENCE = 0.6  # signal_generator.py
```

0.6 미만 신호는 생성하지 않음. 임계값은 추후 전략별로 개별 설정 예정.

## 중복 방지

같은 종목에 이미 `status=pending` 신호가 있으면 새 신호 생성 스킵.
진행 중인 포지션이 있는 종목도 신호 생성 제외 ([[risk-management]] 체크).

## 신호 이후 흐름

- 반자동: [[telegram-integration|텔레그램 승인 요청]] → 응답 대기
- 완전자동: 즉시 [[order-execution|주문 실행]]
