# 포지션 관리

보유 포지션의 생명주기 전체를 추적. `trading/position_manager.py` 구현.

## 포지션 생명주기

```
주문 체결
  → PositionRecord 생성 (status=open)
  → 장중: 현재가 업데이트 (미실현 손익 계산)
  → 청산 트리거 (손절/익절/장 마감)
  → 매도 주문 체결
  → PositionRecord 갱신 (status=closed)
  → TradeHistory 기록
```

## PositionRecord 구조

| 필드 | 설명 |
|------|------|
| `stock_code` | 종목 코드 |
| `stock_name` | 종목명 |
| `entry_price` | 평균 매수가 |
| `quantity` | 보유 수량 |
| `current_price` | 현재가 (실시간 갱신) |
| `unrealized_pnl` | 미실현 손익 |
| `status` | `open` / `closed` |
| `entry_time` | 진입 시각 |
| `exit_time` | 청산 시각 |
| `exit_price` | 청산가 |
| `realized_pnl` | 실현 손익 |

## 실시간 가격 갱신

장중 주기적으로 보유 종목 현재가 업데이트:
- [[redis-usage|Redis]]의 실시간 시세 → PositionRecord 갱신
- 미실현 손익 재계산 → 대시보드 표시

## 동시 포지션 제한

[[risk-management|RiskManager]]가 최대 포지션 수를 관리:
- `max_position_count` (기본 5개)
- 레버리지/인버스 ETF: `max_leverage_position_count` (기본 2개)

신규 진입 전 현재 보유 포지션 수 체크.

## 장 마감 청산

`eod_liquidator.py`:
- 15:30 전 보유 포지션 전량 시장가 청산
- 단타 전략이므로 오버나이트 포지션 보유 없음
- 청산 실패 시 알림 발송

## 포지션 히스토리

청산된 포지션은 `trade_history` 테이블로 이동:
- `analyzer` 모듈이 성과 분석에 활용
- 일일 리포트, 기간별 수익률 계산 기반

## 대시보드 표시

**포지션 페이지**: 현재 보유 종목, 평균가, 현재가, 미실현 손익 실시간 표시.
