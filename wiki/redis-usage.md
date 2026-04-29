# Redis 활용

Redis 7은 실시간 시세 캐시, 세션, 리스크 상태 관리에 사용된다. `core/redis.py` 참조.

## 용도별 키 구조

### 실시간 시세 캐시

| 키 패턴 | 값 | TTL |
|---------|-----|-----|
| `stock:{code}:price` | 현재가 | 10초 |
| `stock:{code}:orderbook` | 호가 (JSON) | 5초 |
| `stock:{code}:trade_strength` | 체결강도 | 30초 |
| `stock:{code}:volume` | 당일 거래량 | 60초 |

[[websocket-management|WebSocket]]이 수신한 체결 틱 → 이 키들을 업데이트.

### 스크리닝 결과

| 키 패턴 | 값 | TTL |
|---------|-----|-----|
| `screening:candidates:{date}` | 후보 종목 목록 (JSON) | 1일 |
| `screening:realtime:{code}` | 2차 스크리닝 결과 | 60초 |

### 리스크 상태

| 키 | 값 | TTL |
|----|-----|-----|
| `risk:emergency_stop` | `1` / (없음) | 무기한 (수동 삭제) |
| `risk:cooldown` | Unix timestamp (만료 시각) | 쿨다운 기간 |
| `risk:consecutive_loss_count` | 정수 | 1일 |
| `risk:daily_capital` | 당일 투입 자본 | 1일 |

[[risk-management]] 참조.

### 승인 대기 큐 (반자동 모드)

| 키 | 값 | TTL |
|----|-----|-----|
| `signal:pending:{signal_id}` | 신호 JSON | 승인 타임아웃 |

[[telegram-integration]]에서 승인 처리 시 이 키를 통해 신호 확인.

### 세션

| 키 패턴 | 값 | TTL |
|---------|-----|-----|
| `session:{token}` | 사용자 세션 JSON | `JWT_EXPIRY_HOURS` |

## RedisClient

`core/redis.py`의 `RedisClient`가 모든 Redis 연결을 관리:
- 비동기 (`aioredis` 기반)
- 연결 풀링
- key prefix로 네임스페이스 분리

### Phase 8.6 신호 생성 메트릭

| 키 패턴 | 값 | TTL |
|---------|-----|-----|
| `metrics:atr:ceil:{date}` | KOSPI200 동적 ATR 상한 (`min(0.08, P80×1.2)`) | 3거래일 |
| `metrics:atr:dist:{date}` | P10/P20/P50/P80/P95 + sample_n (JSON) | 3거래일 |
| `metrics:atr:ceil_grid:{date}` | shadow 그리드 `{1.0,1.1,1.2,1.3}` × P80 | 3거래일 |
| `metrics:atr:ceil:fallback_count` | ATR 캘리브레이션 정적 폴백 누적 카운터 | 1일 |
| `safe_mode:active` | 안전모드 플래그 (폴백 3단 도달 시) | `SAFE_MODE_TIMEOUT_MIN=120`분 |
| `quant_dist_drift_warn:{date}` | 단면 P80 vs 시계열 P80 차 ≥0.015 카운터 | 1일 |
| `shadow:tier:{name}:{passed\|failed}:{date}` | tier별 독립 shadow 평가 카운터 | 7일 |
| `metrics:quant:sim_vs_real_diff:{date}` | shadow vs 실제 통과율 절대차 (≥0.15 시 알림) | 7일 |
| `auto_rollback:R{1..4}:streak` | 자동 롤백 트리거 연속일수 카운터 | 7일 |
| `circuit_breaker:active` | G3 회로차단기 활성 플래그 | 무기한 (수동 해제) |
| `quota_cap_blocked:{date}` | 일일 신호 한도 / 동시 보유 회로 차단 카운터 | 1일 |

[[tier-architecture]] / [[risk-management]] 참조.

## 5분봉 집계 (Phase 9 Sprint 0+)

Phase 9 Sprint 0부터 5분봉 가속도 지표 계산을 위해 추가 키:

| 키 패턴 | 값 | TTL |
|---------|-----|-----|
| `candle5m:{code}:{timestamp}` | OHLCV JSON | 1거래일 |

`volume_aggregator.py`가 체결 틱을 5분봉으로 집계하여 저장.

## 메모리 관리

- TTL 기반 자동 만료로 메모리 제어
- 장 마감 후 실시간 시세 키 자연 만료
- Railway Redis 용량: 512MB (기본)
