# 리스크 관리

모든 매매 전 리스크 체크를 수행하고 비상 정지를 관리. `trading/risk_manager.py` 구현.

## 리스크 체크 흐름

모든 주문 실행 전 `RiskManager.check()` 통과 필수:

```python
result: RiskCheckResult = await risk_manager.check(stock_code, signal)
if not result.allowed:
    # 주문 차단 + 이유 로깅
```

## 리스크 파라미터

DB `settings` 테이블에 저장 (운영 중 변경 가능).

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `daily_max_loss_pct` | -3.0% | 일일 최대 손실 한도 |
| `max_position_count` | 5 | 동시 보유 최대 종목 수 |
| `max_leverage_position_count` | 2 | 레버리지/인버스 ETF 최대 보유 수 |
| `emergency_stop_pct` | -4.0% | 비상 정지 손실 임계값 |
| `consecutive_loss_stop` | 3 | 연속 손실 정지 횟수 |
| `cooldown_trigger_count` | 2 | 쿨다운 트리거 횟수 |
| `cooldown_duration_min` | 60 | 쿨다운 지속 시간 (분) |

## Redis 기반 실시간 상태

| Redis 키 | 설명 |
|---------|------|
| `risk:emergency_stop` | 비상 정지 플래그 |
| `risk:cooldown` | 쿨다운 활성화 여부 |
| `risk:consecutive_loss_count` | 연속 손실 카운터 |
| `risk:daily_capital` | 당일 투입 자본금 |

## 비상 정지

`emergency_stop_pct` 초과 손실 발생 시:
1. `risk:emergency_stop` 플래그 설정
2. 모든 신호 차단
3. 보유 포지션 전량 청산 요청
4. 텔레그램 긴급 알림 — [[telegram-integration]]

비상 정지 해제는 수동으로만 가능 (대시보드 또는 API).

## 쿨다운

연속 손실 `cooldown_trigger_count`회 발생 시:
- `cooldown_duration_min`분간 신규 진입 차단
- 쿨다운 중 텔레그램 알림
- 쿨다운 만료 후 자동 재개

## 장중 설정 변경 제한

`RiskSettingsLocked` 예외: 장 시작(09:00) ~ 장 마감(15:30) 중에는 리스크 파라미터 변경 차단. 장 마감 후 또는 장 시작 전에만 변경 가능.

## RiskCheckResult

```python
class RiskCheckResult:
    allowed: bool
    reason: str | None
    risk_level: str  # "normal", "warning", "blocked", "emergency"
```

차단된 경우 `reason`에 사유 기록.

## 포지션 수 체크

[[position-management|포지션 관리]]와 연계:
- 신규 진입 전 현재 `open` 포지션 수 확인
- `max_position_count` 초과 시 진입 차단
