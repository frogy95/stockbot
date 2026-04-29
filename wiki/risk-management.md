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

DB `settings` 테이블에 저장 (운영 중 변경 가능). LIVE 4대 파라미터는 **Phase 7.0 코드 잠금** (아래 참조).

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `daily_max_loss_pct` | -3.0% (Paper) / **-2.0% (LIVE 잠금)** | 일일 최대 손실 한도 |
| `max_position_count` | 5 (Paper) / **2 (LIVE 잠금)** | 동시 보유 최대 종목 수 |
| `max_leverage_position_count` | 2 | 레버리지/인버스 ETF 최대 보유 수 |
| `emergency_stop_pct` | -4.0% (Paper) / **-3.0% (LIVE 잠금)** | 비상 정지 손실 임계값 |
| `consecutive_loss_stop` | 3 | 연속 손실 정지 횟수 |
| `cooldown_trigger_count` | 2 | 쿨다운 트리거 횟수 |
| `cooldown_duration_min` | 60 | 쿨다운 지속 시간 (분) |
| `daily_max_trade_count` | 10 | 일일 최대 신규 진입 횟수 (Phase 8 Sprint 2) |
| `no_entry_start` / `no_entry_end` | 09:00 / 09:30 | 관망 시간대 (진입 불가) |
| `no_new_entry_time` | 14:30 | 신규 진입 차단 시각 |
| `risk_lock_during_trading` | true | 장중 리스크 설정 변경 잠금 |

### 환경변수 오버라이드

`DAILY_MAX_TRADE_COUNT_OVERRIDE` (int | None) — 설정 시 DB 값을 무시하고 오버라이드. Sprint 3 이전 LIVE 초기 안전장치로 `3`으로 제한하여 운용. `core/config.py` 참조.

## Phase 7.0 LIVE 파라미터 코드 잠금 (Phase 8.6 Sprint 1)

분기 D 같은 사고 시에도 LIVE 자금이 보호되도록 4대 파라미터를 `core/constants.py`에 `Final` 상수 + 런타임 assert 이중 가드로 잠금. monkeypatch / env override 시도 시 모듈 import 시점에 `AssertionError`로 차단.

```python
# backend/core/constants.py
LIVE_MAX_POSITION_COUNT:   Final[int]   = 2
LIVE_POSITION_SIZE_PCT:    Final[float] = 5.0
LIVE_DAILY_MAX_LOSS_PCT:   Final[float] = -2.0
LIVE_EMERGENCY_STOP_PCT:   Final[float] = -3.0

assert LIVE_MAX_POSITION_COUNT == 2, "Phase 7.0 잠금 위반: ..."
# ...
```

회귀 방지: `tests/core/test_phase70_locked_constants.py`(5 tests PASS). sprint-review가 PR 머지 전 `git diff develop...HEAD -- backend/modules/trading/executor.py ...` grep 0줄을 강제.

## DoR 가드레일 G1~G3 (Phase 8.6 Sprint 1)

분기 D 재발 시 LIVE 자금 보호를 위한 3대 가드레일. Phase 8.6 Sprint 2 착수의 차단 해제 조건이었으며 2026-04-29 PR #181로 충족.

### G1 — 폴백 신호율(M-F2) 산출

`is_fallback` 메타데이터를 **신호 → 주문 → 체결 → 일별 집계** 전 경로에 전파:

- `signals.fallback BOOLEAN`
- `orders.fallback BOOLEAN`
- `daily_screening_metrics.fallback_signal_rate FLOAT`
- API: `GET /api/v1/metrics/fallback-signal-rate`
- 일별 폴백 신호 비율 = `폴백 종목 신호 수 / 폴백 발동 종목 수`

### G2 — 자동 롤백 R1~R4 다중 트리거 OR

기존 `auto_rollback_2d_zero_signals` 단일 트리거 → 4종 OR. `modules/safety/auto_rollback.py`(`AutoRollbackEvaluator`, 13 tests PASS), 16:10 스케줄러 잡으로 평가.

| 트리거 | 조건 | env 토글 |
|--------|------|---------|
| R1 | 신호 0건 **3거래일 연속** (기존 2일 → 3일 강화) | `AUTO_ROLLBACK_R1_ENABLED` |
| R2 | 폴백 발동률 ≥ 50% **3거래일 연속** | `AUTO_ROLLBACK_R2_ENABLED` |
| R3 | tier 다양성 1종 **5거래일 연속** | `AUTO_ROLLBACK_R3_ENABLED` |
| R4 | 폴백 신호 비중 ≥ 70% **1거래일** | `AUTO_ROLLBACK_R4_ENABLED` |

발동 시 Phase 8.6 변경분만 비활성화 (`PARALLEL_OR_TIER_ENABLED=false` 등 일괄 OFF). Phase 8.5 폴백은 별도 결정.

### G3 — 1차→2차 통과율 회로차단기

`modules/safety/circuit_breaker.py`(9 tests PASS). 일별 2차 통과율(폴백 제외) **< 10% 3거래일 연속** 시 본 Phase 변경분 자동 비활성화 + Phase 8.5 폴백 차단. 임계는 `CIRCUIT_BREAKER_*` env로 조정 가능.

**OR 모드 보정** (Sprint 2): 병렬 OR 직후 통과율이 N배가 되어 G3 오발동을 막기 위해 "체결 손실 누적" 임계로 일시 전환 OR `G3_OR_MODE_MULT` 보정 계수 적용.

### Phase 8.6 상태 API

`GET /api/v1/metrics/phase86-status` — 자동 롤백 활성 여부, 회로차단기 상태, 폴백 메트릭 통합 응답.

## 안전모드 (Phase 8.6 Sprint 2)

ATR 캘리브레이션 폴백 3단(직전일 캐시 → HARD 정적 → 안전모드) 도달 시:

- Redis `safe_mode:active` 키 설정
- engine이 신호 발행 `SAFE_MODE_TIMEOUT_MIN=120`분간 중단
- 텔레그램 알림 발송

상세: [[tier-architecture#폴백-3단]].

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
