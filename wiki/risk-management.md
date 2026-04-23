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
| `daily_max_trade_count` | 10 | 일일 최대 신규 진입 횟수 (Phase 8 Sprint 2) |
| `no_entry_start` / `no_entry_end` | 09:00 / 09:30 | 관망 시간대 (진입 불가) |
| `no_new_entry_time` | 14:30 | 신규 진입 차단 시각 |
| `risk_lock_during_trading` | true | 장중 리스크 설정 변경 잠금 |

### 환경변수 오버라이드

`DAILY_MAX_TRADE_COUNT_OVERRIDE` (int | None) — 설정 시 DB 값을 무시하고 오버라이드. Sprint 3 이전 LIVE 초기 안전장치로 `3`으로 제한하여 운용. `core/config.py` 참조.

## Redis 기반 실시간 상태

| Redis 키 | 설명 | TTL |
|---------|------|-----|
| `risk:emergency_stop` | 비상 정지 플래그 | 영구 (수동 해제) |
| `risk:cooldown` | 쿨다운 활성화 | `cooldown_duration_min`분 |
| `risk:consecutive_loss_count` | 연속 손실 카운터 | 영구 (장 시작 전 리셋) |
| `risk:daily_capital` | 당일 시작 잔고 (손실률 분모) | 영구 (장 시작 전 갱신) |
| `risk:daily_trade_count` | 일일 신규 진입 카운터 | 86400초 (최초 증가 시에만 설정) |
| `risk:leverage_position_count` | 활성 레버리지 포지션 수 | 영구 |

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

## 일일 거래 횟수 한도 (Phase 8 Sprint 2)

`daily_max_trade_count` 한도를 넘으면 신규 진입 차단:

1. engine이 주문 제출 전 `check_daily_trade_limit()` 호출
2. 체결 콜백(`on_filled_callback`)에서 `incr_daily_trade_count()`로 Redis 카운터 증가 (체결 성공분만)
3. 최초 증가 시 TTL 86400초 설정 — 이후 증가는 TTL을 갱신하지 않아 "당일 N건" 의미를 유지

환경변수 `DAILY_MAX_TRADE_COUNT_OVERRIDE`로 DB 값을 오버라이드할 수 있다 (Sprint 3 전 LIVE 초기 제한용).

## 카운터 리셋

### 자동 리셋 (장 시작 전)

`reset_daily_counters()`가 APScheduler 장전 잡으로 호출되어:
- `consecutive_loss`, `cooldown`, `emergency_stop`, `daily_trade_count` 삭제
- KIS 잔고 조회 후 `daily_capital = 가용 현금 + 활성 포지션 원금` 캐시 갱신

### 수동 리셋 API

```
POST /api/v1/trading/risk/reset
```

운영 중 비상 정지/쿨다운 해제 등 즉시 리셋이 필요할 때 사용. 프론트엔드 대시보드에 리셋 버튼(2단계 확인 다이얼로그) 제공 — `frontend/components/risk/reset-button.tsx`. Hotfix PR #153(risk-counter-reset)에서 도입 후 Phase 8 Sprint 2에서 UI 완성.

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
