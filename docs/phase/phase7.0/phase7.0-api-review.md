# Phase 7.0 — 윤에이피 (API 개발자) 검토 리포트

> **검토일**: 2026-04-15
> **검토 대상**: 매매 엔진 치명적 결함 수정 + LIVE 전환 준비

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| P0 결함 #1 가격 갱신 | ✅ 수정 필수 — WS realtime 캐시 활용 + REST 폴백 설계 제안 |
| P0 결함 #2 포지션 생성 | ✅ 수정 필수 — 콜백 패턴으로 순환 참조 방지 |
| P0 청산 실행 | ✅ 수정 필수 — 매도 주문 파이프라인 연결 |
| P1 이중 주문 방지 | ⚠️ 주의 — cancel 실패 시 잔량 확인 로직 필요 |
| P2 트레일링 Redis | ✅ 구현 가능 — Redis HSET 패턴 권장 |
| 체결가 역산 | ⚠️ 주의 — 모의/실전 응답 구조 차이 |

## 2. 항목별 검증 결과

### P0 결함 #1: 가격 갱신 구현 방안

**현재 상태**: WS 수신 데이터가 `realtime:{stock_code}` Redis 키에 JSON으로 저장됨 (scheduler의 ws_handler에서 처리).

**구현 방안**:
```
_monitor_positions_loop 매 루프:
  1. 활성 포지션의 stock_code 목록 조회
  2. 각 stock_code에 대해 Redis realtime:{code} → current_price 추출
  3. WS 데이터 미수신(None 또는 stale>60초) 시 REST get_current_price() 폴백
  4. price_updates dict 구성 → position_manager.update_prices(price_updates) 호출
  5. 이후 check_exit_conditions() 호출
```

**REST 폴백 주의사항**:
- `get_current_price()`는 throttler 필요. 포지션 5건이면 5회 REST 호출.
- throttler.acquire() 호출로 Rate Limit 준수.
- REST 폴백은 WS 미수신 종목만 대상으로 한정.

### P0 결함 #2: 콜백 패턴 설계

**문제**: `OrderManager`가 `TradingEngine`을 참조하면 순환 의존.

**권장 패턴**: 콜백 함수 주입
```python
class OrderManager:
    def __init__(self, ..., on_filled_callback=None):
        self._on_filled = on_filled_callback

    async def _execute_order(self, order_id):
        # ... 체결 확인 후
        if filled and self._on_filled:
            await self._on_filled(order_id, filled_price, signal_data, quantity)
```

**main.py에서 연결**:
```python
order_manager = OrderManager(..., on_filled_callback=engine.on_order_filled)
```

**주의**: `_execute_order`에서 signal 정보가 필요하나 현재 order_id만 전달받음.
- **수정 필요**: `submit_order` 시 signal 정보를 orders 테이블 또는 Redis에 임시 저장.
- 또는 Order 모델에 `signal_data_json` 필드 추가 (Alembic 마이그레이션 필요).

### P0 추가: 청산 매도 주문 파이프라인

**현재 상태**: `check_exit_conditions()` → 청산 대상 리스트 반환 → 로깅만.

**구현 방안**:
```python
async def _monitor_positions_loop(self):
    while self._running:
        # 1. 가격 갱신
        price_updates = await self._collect_price_updates()
        await self._position_manager.update_prices(price_updates)

        # 2. 청산 조건 체크
        exits = await self._position_manager.check_exit_conditions()

        # 3. 청산 실행
        for exit_info in exits:
            await self._execute_exit(exit_info)

        await asyncio.sleep(5)
```

**`_execute_exit` 구현**:
- 시장가 매도 주문 발송 (`rest_client.place_order`)
- 체결 확인 (간단 폴링, 최대 3회)
- `position_manager.close_position()` 호출
- 실패 시 로깅 + 다음 루프에서 재시도 (포지션 유지)

### P1: 이중 주문 방지

**현재 코드** (order_manager.py L218-223):
```python
try:
    await self._rest_client.cancel_order(limit_order_no, cancel_req)
except Exception:
    logger.warning("주문 취소 실패 (무시하고 시장가 진행): order_id=%d", order_id)
```

**수정 방안 A (안전 — 권장)**:
```python
except Exception:
    logger.warning("주문 취소 실패 — 시장가 발송 중단: order_id=%d", order_id)
    await self._update_order_status(order_id, "cancel_failed")
    return  # 이중 주문 방지
```

**수정 방안 B (적극)**:
cancel 후 잔량 확인 → 잔량만 시장가. 그러나 KIS API에서 부분 체결 잔량 조회가 복잡.

**권고**: 방안 A 채택. reconciliation에서 미체결분 후속 처리.

### P2: 트레일링 고점 Redis 이관

**구현 방안**:
```python
# Redis HSET 패턴
REDIS_TRAILING_KEY = "trailing_highs"

# 저장
await redis.hset(REDIS_TRAILING_KEY, stock_code, str(new_high))

# 조회
high_str = await redis.hget(REDIS_TRAILING_KEY, stock_code)

# 삭제 (청산 시)
await redis.hdel(REDIS_TRAILING_KEY, stock_code)

# 전체 조회 (시작 시 로드)
all_highs = await redis.hgetall(REDIS_TRAILING_KEY)
```

- TTL은 HSET 전체에만 적용 가능 → 장 마감 시 `redis.delete(REDIS_TRAILING_KEY)`.

### 체결가 역산

- 모의거래 체결 응답: `output1[0]` 내 `tot_ccld_amt`, `tot_ccld_qty` 필드.
- `filled_price = int(tot_ccld_amt) // int(tot_ccld_qty)` (정수 나눗셈 주의).
- 실전: 동일 필드명이나 값 정밀도 다를 수 있음. 모의에서 검증 후 실전 전환.

## 3. 파라미터 조정 권고

| 항목 | 원래값 | 권고값 | 근거 |
|------|--------|--------|------|
| 포지션 모니터 간격 | 5초 | 5초 유지 | REST 폴백 고려 시 적절 |
| REST 폴백 타임아웃 | 없음 | 3초 | 시세 조회 지연 시 다음 루프로 |
| 청산 매도 폴링 | 없음 | 최대 3회, 2초 간격 | 빠른 청산 + API 부하 균형 |
| 체결 콜백 signal 저장 | 없음 | Order.signal_json 컬럼 추가 | 콜백에서 signal 정보 필요 |

## 4. 리스크 및 대안

- **API 리스크**: 실전 전환 시 `tr_id` 접두사 변경 (`VTTC→TTTC` 매수, `VTTC→TTTC` 매도). 기존 `settings.TRADING_ENV` 기반 자동 전환 확인 필요.
- **Rate Limit**: 포지션 모니터링(5초) + 가격 갱신(REST 폴백) + 청산 매도 = 동시 API 호출 증가. throttler 공유 인스턴스로 통합 관리 필요.
- **순환 참조**: engine↔order_manager 콜백 패턴으로 해결. import 순환은 없으나 런타임 참조 주의.
