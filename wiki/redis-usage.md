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

## 5분봉 집계 (Phase 7.1+)

Phase 7.1부터 5분봉 가속도 지표 계산을 위해 추가 키:

| 키 패턴 | 값 | TTL |
|---------|-----|-----|
| `candle5m:{code}:{timestamp}` | OHLCV JSON | 1거래일 |

`volume_aggregator.py`가 체결 틱을 5분봉으로 집계하여 저장.

## 메모리 관리

- TTL 기반 자동 만료로 메모리 제어
- 장 마감 후 실시간 시세 키 자연 만료
- Railway Redis 용량: 512MB (기본)
