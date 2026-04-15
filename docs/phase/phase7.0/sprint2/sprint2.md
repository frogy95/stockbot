# Sprint 2: P2 리스크 개선 (Phase 7.0)

**Goal:** 리스크 관리의 3가지 결함(daily_loss 분모 오류, record_loss 누락, trailing_highs 인메모리 소실)을 수정하여 매매 엔진의 리스크 판단 정확성과 서버 재시작 복원력을 확보한다.

**Architecture:** risk_manager의 daily_loss 분모를 "활성 포지션 원금"에서 "당일 시작 잔고(Redis 캐시)"로 교체하고, position_manager의 close_position에서 손실 기록 조건을 realized_pnl < 0 전체로 확장하며, trailing_highs를 인메모리 dict에서 Redis JSON 키로 이관한다. 추가로 engine._execute_exit에 Redis 기반 in-flight 플래그를 도입하여 중복 매도를 방지한다.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Redis, pytest, AsyncMock

**Sprint 기간:** 2026-04-15 ~ (사용자 검토 후 구현)
**이전 스프린트:** Sprint 1 (pytest 817 passed, PR #132)
**브랜치명:** `phase7.0-sprint2`

---

## 제외 범위

- E2E 검증 + LIVE 전환 게이트 -> Sprint 3
- LIVE 초기 운영 파라미터 적용 (확정 파라미터 #15~#22) -> Sprint 3
- 프론트엔드 변경 없음
- DB 스키마 변경 없음 (Redis 키와 코드 로직만 변경)
- RedisClient에 HSET/HGET 메서드 추가하지 않음 (기존 get/set + JSON 직렬화 방식 사용 — simplicity first)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | RedisClient 래퍼 확장 (hset/hget/hdel/hgetall) + daily_loss 분모 수정 | 백엔드 | `feature-dev:feature-dev` |

### Phase 2 (순차 — Task 1의 Redis 래퍼에 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | record_loss 트리거 확장 + trailing_highs Redis 이관 | 백엔드 | `feature-dev:feature-dev` |

### Phase 3 (순차 — Task 2에 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | eod_liquidator trailing_highs 삭제 + in-flight 중복 매도 방지 | 백엔드 | -- |

### Phase 4 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 통합 검증 + 기존 테스트 회귀 확인 | 백엔드 | -- |

> **참고**: 모든 Task가 trading 모듈의 동일 파일(risk_manager, position_manager, engine, eod_liquidator)을 수정하므로 순차 실행 필수.

---

### Task 1: daily_loss_pct 분모 수정 — 당일 시작 잔고 기반

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/core/redis.py` (RedisClient에 hset/hget/hdel/hgetall 메서드 추가)
- Modify: `backend/modules/trading/risk_manager.py` (check_daily_loss, reset_daily_counters, record_loss 수정)
- Create: `backend/tests/test_risk_daily_capital.py`

**Step 1: 테스트 작성**
- `backend/tests/test_risk_daily_capital.py` 생성
- 기존 `test_risk_manager.py`의 픽스처 패턴(mock_redis, mock_session_factory, risk_manager) 재사용
- 다음 테스트 작성:
  - `test_reset_daily_counters_caches_daily_capital`: `reset_daily_counters()` 호출 시 KIS REST `get_balance()` 잔고를 Redis `risk:daily_capital` 키에 캐시하는지 확인
  - `test_check_daily_loss_uses_cached_capital`: Redis `risk:daily_capital`에 캐시된 값을 분모로 사용하는지 확인 (활성 포지션 원금 쿼리 대신)
  - `test_check_daily_loss_fallback_when_no_cache`: Redis 캐시 미스 시 기존 방식(활성 포지션 원금 합계)으로 폴백하는지 확인
  - `test_daily_loss_blocks_after_full_exit`: 전액 청산 후(포지션 0) 재진입 시에도 daily_loss가 캐시된 시작 잔고 기준으로 판단하여 차단하는지 확인
  - `test_record_loss_emergency_uses_cached_capital`: `record_loss()` 내부의 비상 정지 체크도 캐시된 시작 잔고를 분모로 사용하는지 확인
- 검증: `docker compose exec backend pytest tests/test_risk_daily_capital.py -v`
- 예상: FAIL (아직 구현 전)

**Step 2: RedisClient에 HSET 관련 래퍼 메서드 추가**
- `backend/core/redis.py`의 `RedisClient` 클래스에 다음 메서드 추가:
  - `async def hset(self, key: str, field: str, value: str) -> None` — `self._redis.hset(key, field, value)`
  - `async def hget(self, key: str, field: str) -> str | None` — `self._redis.hget(key, field)`
  - `async def hdel(self, key: str, field: str) -> bool` — `bool(await self._redis.hdel(key, field))`
  - `async def hgetall(self, key: str) -> dict[str, str]` — `await self._redis.hgetall(key)`
- 모든 메서드에 `if not self._redis: return` 가드 추가 (기존 패턴 동일)
- Task 2의 trailing_highs Redis HSET에서도 사용

**Step 3: RiskManager.__init__에 rest_client 파라미터 추가**
- 현재 `__init__(self, session_factory, redis_client)` — rest_client 없음
- 수정: `__init__(self, session_factory, redis_client, rest_client=None)`
- `self._rest_client = rest_client`로 저장
- `reset_daily_counters()`에서 잔고 조회에 사용

**Step 4: reset_daily_counters() 수정 — 잔고 캐시 추가**
- 기존 코드: 연속 손절/쿨다운/비상 정지 Redis 키만 삭제
- 추가 로직:
  1. `self._rest_client`가 존재하면 `await self._rest_client.get_balance()`로 가용 잔고 조회
  2. 가용 잔고 + 활성 포지션 원금 합계 = 당일 시작 잔고 (total_capital)
  3. `await self._redis.set("risk:daily_capital", str(total_capital))` — TTL 없음 (당일만 유효, 다음 장 시작 시 덮어쓰기)
  4. rest_client 없거나 잔고 조회 실패 시: Redis 캐시 설정 안 함 (check_daily_loss에서 폴백 사용)

**Step 5: check_daily_loss() 수정 — 분모를 캐시된 시작 잔고로 교체**
- 현재 코드 (166~206줄): 분모 = `sum(PositionRecord.avg_price * PositionRecord.quantity)` (활성 포지션 원금)
- 수정:
  1. `cached = await self._redis.get("risk:daily_capital")` 조회
  2. cached 존재 시: `total_capital = int(cached)` 사용
  3. cached 없으면: 기존 방식(포지션 원금 합계)으로 폴백 — 하위 호환
  4. `total_capital == 0`이면 `return False` (변경 없음)
  5. `loss_pct = (total_pnl / total_capital) * 100` (변경 없음)
- 분자(미실현+실현 손익 합산)는 변경 없음

**Step 6: record_loss() 내부의 비상 정지 체크도 동일하게 수정**
- 현재 코드 (308~337줄): 비상 정지 판단 분모도 활성 포지션 원금
- 수정: check_daily_loss()와 동일하게 Redis 캐시 우선 + 포지션 원금 폴백
- `_get_daily_capital()` private 메서드 추출하여 check_daily_loss()와 record_loss() 양쪽에서 재사용

**Step 7: 검증**
- 검증: `docker compose exec backend pytest tests/test_risk_daily_capital.py tests/test_risk_manager.py -v`
- 예상: 전체 PASS (신규 + 기존)

**Step 8: 커밋**
```
git add backend/core/redis.py backend/modules/trading/risk_manager.py backend/tests/test_risk_daily_capital.py
git commit -m "feat(phase7.0-sprint2): task1 -- daily_loss 분모를 당일 시작 잔고(Redis 캐시)로 수정"
```

**완료 기준:**
- ⬜ reset_daily_counters가 잔고를 Redis `risk:daily_capital`에 캐시
- ⬜ check_daily_loss가 캐시된 시작 잔고를 분모로 사용
- ⬜ 캐시 미스 시 기존 포지션 원금 폴백 동작
- ⬜ 전액 청산 후에도 시작 잔고 기준으로 daily_loss 판단
- ⬜ record_loss 비상 정지 체크도 동일 분모 사용
- ⬜ 기존 test_risk_manager.py 회귀 없음

---

### Task 2: record_loss 트리거 확장 + trailing_highs Redis 이관

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/trading/position_manager.py` (close_position, __init__, update_prices 수정)
- Create: `backend/tests/test_position_risk_trailing.py`

**Step 1: 테스트 작성**
- `backend/tests/test_position_risk_trailing.py` 생성
- 기존 `test_position_manager.py`의 픽스처 패턴 재사용
- 다음 테스트 작성:
  - **record_loss 확장 관련:**
  - `test_close_position_trailing_loss_calls_record_loss`: exit_reason="trailing"이고 realized_pnl < 0일 때 record_loss() 호출 확인
  - `test_close_position_eod_loss_calls_record_loss`: exit_reason="eod"이고 realized_pnl < 0일 때 record_loss() 호출 확인
  - `test_close_position_timeout_loss_calls_record_loss`: exit_reason="timeout"이고 realized_pnl < 0일 때 record_loss() 호출 확인
  - `test_close_position_profit_does_not_call_record_loss`: realized_pnl > 0일 때 record_loss() 미호출 확인 (exit_reason 무관)
  - `test_close_position_profit_resets_consecutive_loss`: realized_pnl > 0일 때 연속 손절 카운터 리셋(Redis `risk:consecutive_loss_count` 삭제) 확인
  - **trailing_highs Redis 관련:**
  - `test_update_prices_stores_trailing_high_in_redis`: trailing_activated 종목의 고점이 Redis HSET에 저장되는지 확인
  - `test_init_loads_trailing_highs_from_redis`: PositionManager 생성 시(또는 load_trailing_highs 호출 시) Redis에서 trailing_highs를 복원하는지 확인
  - `test_close_position_removes_trailing_high_from_redis`: 청산 시 Redis HSET에서 해당 종목 제거 확인
  - `test_trailing_highs_survives_restart`: Redis에 저장 후 새 PositionManager 인스턴스가 이전 trailing_highs를 복원하는지 확인 (시뮬레이션)
- 검증: `docker compose exec backend pytest tests/test_position_risk_trailing.py -v`
- 예상: FAIL (아직 구현 전)

**Step 2: close_position() 수정 — record_loss 조건 확장**
- 현재 코드 (254~256줄):
  ```python
  if exit_reason == "stop_loss":
      await self._risk_manager.record_loss()
  ```
- 수정:
  ```python
  if realized_pnl < 0:
      await self._risk_manager.record_loss()
  else:
      # 수익 청산 시 연속 손절 카운터 리셋
      await self._redis.delete("risk:consecutive_loss_count")
  ```
- 이렇게 하면 trailing/eod/timeout 손실도 record_loss()를 트리거
- 수익 청산 시 연속 손절 카운터를 리셋하여 정상 매매 재개 보장

**Step 3: trailing_highs 저장소를 Redis로 이관**
- **REDIS_TRAILING_HIGHS_KEY** = `"trailing_highs"` 상수 추가
- `__init__` 수정:
  - `self._trailing_highs: dict[str, int] = {}` 유지 (로컬 캐시 겸용)
  - 로컬 캐시는 Redis 동기화의 write-through 캐시 역할
- `async def load_trailing_highs(self) -> None` 신규 메서드:
  - `data = await self._redis.hgetall(REDIS_TRAILING_HIGHS_KEY)`
  - `self._trailing_highs = {k: int(v) for k, v in data.items()}`
  - main.py에서 PositionManager 생성 후 호출

**Step 4: update_prices() 수정 — trailing_highs Redis 동기화**
- 현재 코드 (112~114줄): 인메모리 dict만 업데이트
  ```python
  if new_price > prev_high:
      self._trailing_highs[pos.stock_code] = new_price
  ```
- 수정: Redis HSET 동기화 추가
  ```python
  if new_price > prev_high:
      self._trailing_highs[pos.stock_code] = new_price
      await self._redis.hset(REDIS_TRAILING_HIGHS_KEY, pos.stock_code, str(new_price))
  ```

**Step 5: close_position() 수정 — trailing_highs Redis 삭제**
- 현재 코드 (252줄): `self._trailing_highs.pop(position.stock_code, None)`
- 수정: Redis에서도 삭제
  ```python
  self._trailing_highs.pop(position.stock_code, None)
  await self._redis.hdel(REDIS_TRAILING_HIGHS_KEY, position.stock_code)
  ```

**Step 6: main.py에 load_trailing_highs 호출 추가**
- `backend/main.py`에서 `position_manager = PositionManager(...)` 직후:
  ```python
  await position_manager.load_trailing_highs()
  ```
- 서버 재시작 시 Redis에서 trailing_highs 자동 복원

**Step 7: 검증**
- 검증: `docker compose exec backend pytest tests/test_position_risk_trailing.py tests/test_position_manager.py -v`
- 예상: 전체 PASS (신규 + 기존)

**Step 8: 커밋**
```
git add backend/modules/trading/position_manager.py backend/tests/test_position_risk_trailing.py backend/main.py
git commit -m "feat(phase7.0-sprint2): task2 -- record_loss 확장 + trailing_highs Redis 이관"
```

**완료 기준:**
- ⬜ realized_pnl < 0이면 exit_reason 무관하게 record_loss() 호출
- ⬜ 수익 청산 시 연속 손절 카운터 리셋
- ⬜ trailing_highs가 Redis HSET에 동기화
- ⬜ 서버 재시작 시 Redis에서 trailing_highs 복원
- ⬜ 기존 test_position_manager.py 회귀 없음

---

### Task 3: eod_liquidator trailing_highs 삭제 + in-flight 중복 매도 방지

**Files:**
- Modify: `backend/modules/trading/eod_liquidator.py` (liquidate_all에 Redis trailing_highs 삭제 추가)
- Modify: `backend/modules/trading/engine.py` (_execute_exit에 in-flight 플래그 추가)
- Create: `backend/tests/test_eod_trailing_cleanup.py`
- Create: `backend/tests/test_engine_inflight.py`

**Step 1: 테스트 작성**
- `backend/tests/test_eod_trailing_cleanup.py` 생성:
  - `test_liquidate_all_deletes_trailing_highs_redis`: liquidate_all() 완료 후 Redis `trailing_highs` 키가 삭제되는지 확인
- `backend/tests/test_engine_inflight.py` 생성:
  - `test_execute_exit_sets_inflight_flag`: _execute_exit 진입 시 Redis `exit:inflight:{stock_code}` 키가 설정되는지 확인
  - `test_execute_exit_skips_if_inflight`: 이미 in-flight 플래그가 있는 종목은 _execute_exit가 스킵하는지 확인
  - `test_execute_exit_clears_inflight_on_success`: 청산 성공 시 in-flight 플래그가 삭제되는지 확인
  - `test_execute_exit_clears_inflight_on_failure`: 청산 실패 시에도 in-flight 플래그가 삭제되는지 확인 (다음 루프 재시도 가능)
- 검증: `docker compose exec backend pytest tests/test_eod_trailing_cleanup.py tests/test_engine_inflight.py -v`
- 예상: FAIL (아직 구현 전)

**Step 2: eod_liquidator.liquidate_all() 수정**
- 현재 코드 (120~123줄): `await session.execute(delete(PositionRecord))` 후 커밋
- 추가: 커밋 직후 (123줄 이후):
  ```python
  await self._redis.delete("trailing_highs")
  ```
- PositionRecord 전체 삭제 후 trailing_highs도 정리 (정합성)

**Step 3: engine._execute_exit() 수정 — in-flight 중복 매도 방지**
- 미해결 사항 #7: 5초 모니터 루프에서 동일 종목 중복 매도 가능성
- 구현:
  1. 메서드 진입 시 Redis `exit:inflight:{stock_code}` 키 체크
     - 존재하면 `logger.info("in-flight 청산 진행 중 — 스킵: %s", stock_code)` 후 return
  2. 키 미존재 시 `await self._redis.set(f"exit:inflight:{stock_code}", "1", ttl=30)` 설정
     - TTL 30초: 최악 시나리오(3회 폴링 x 2초 = 6초)보다 넉넉하게 설정, 비정상 종료 시에도 자동 만료
  3. 청산 완료 또는 실패 후 `finally` 블록에서 `await self._redis.delete(f"exit:inflight:{stock_code}")` 삭제

**Step 4: 검증**
- 검증: `docker compose exec backend pytest tests/test_eod_trailing_cleanup.py tests/test_engine_inflight.py tests/test_engine_monitor.py -v`
- 예상: 전체 PASS

**Step 5: 커밋**
```
git add backend/modules/trading/eod_liquidator.py backend/modules/trading/engine.py backend/tests/test_eod_trailing_cleanup.py backend/tests/test_engine_inflight.py
git commit -m "feat(phase7.0-sprint2): task3 -- eod trailing 정리 + in-flight 중복 매도 방지"
```

**완료 기준:**
- ⬜ liquidate_all() 후 Redis `trailing_highs` 키 삭제
- ⬜ _execute_exit 진입 시 in-flight 플래그 설정/체크
- ⬜ 동일 종목 중복 매도 방지 확인
- ⬜ in-flight 플래그가 성공/실패 후 삭제됨
- ⬜ 기존 test_engine_monitor.py 회귀 없음

---

### Task 4: 통합 검증 + 기존 테스트 회귀 확인

**Files:**
- Modify: `backend/tests/test_risk_manager.py` (기존 테스트에서 check_daily_loss 분모 변경에 영향받는 케이스 수정)
- Modify: `backend/tests/test_position_manager.py` (기존 close_position 테스트에서 record_loss 호출 조건 변경 반영)

**Step 1: 기존 test_risk_manager.py 호환성 확인 및 수정**
- `test_daily_loss_exceeded_blocks_trade` (TC-1): check_daily_loss가 Redis 캐시를 먼저 조회하므로, mock_redis.get에 `risk:daily_capital` 반환값 추가 필요
  - Redis에서 `risk:daily_capital` = None 반환하도록 설정하면 기존 폴백 경로 테스트 유지
  - 또는 `risk:daily_capital` = "5000000"을 반환하여 캐시 경로 테스트 추가
- `test_all_checks_pass_allows_trade` (TC-9): 동일하게 Redis 캐시 반환값 설정 필요
- 검증: `docker compose exec backend pytest tests/test_risk_manager.py -v`
- 예상: PASS (수정 후)

**Step 2: 기존 test_position_manager.py 호환성 확인 및 수정**
- `test_close_position_records_trade_history_and_deletes_position` (TC-8): exit_reason="take_profit", exit_price=10200 > avg_price=10000 → realized_pnl > 0 → record_loss 미호출 확인 (변경 없이 통과)
- `test_close_position_calls_record_loss_on_stop_loss` (TC-8 보완): exit_reason="stop_loss", exit_price=9800 < avg_price=10000 → realized_pnl < 0 → record_loss 호출 (기존과 동일 결과, 통과)
- trailing_highs 관련: mock_redis에 hset/hget/hdel/hgetall 반환값 설정 필요
  - mock_redis.hdel = AsyncMock(return_value=True)
  - mock_redis.hgetall = AsyncMock(return_value={})
- 검증: `docker compose exec backend pytest tests/test_position_manager.py -v`
- 예상: PASS (수정 후)

**Step 3: 전체 pytest 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 기존 passed + 신규 테스트 passed (기존 무관 실패 4건은 동일)

**Step 4: main.py RiskManager 배선 확인**
- `backend/main.py` 125줄: `risk_manager = RiskManager(session_factory, redis_client)`
- 수정: `risk_manager = RiskManager(session_factory, redis_client, rest_client=rest_client)`
- rest_client는 122줄에서 이미 생성됨 — 순서 문제 없음
- 검증: `docker compose exec backend python -c "from modules.trading.risk_manager import RiskManager; print('ok')"`

**Step 5: 커밋**
```
git add backend/tests/test_risk_manager.py backend/tests/test_position_manager.py backend/main.py
git commit -m "feat(phase7.0-sprint2): task4 -- 통합 검증 + 기존 테스트 호환성 수정"
```

**완료 기준:**
- ⬜ 기존 test_risk_manager.py 전체 PASS
- ⬜ 기존 test_position_manager.py 전체 PASS
- ⬜ pytest 전체 통과 (기존 + 신규)
- ⬜ main.py에 rest_client 배선 완료

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 기존 + 신규 전체 passed |
| daily_loss 캐시 | `docker compose exec backend python -c "from modules.trading.risk_manager import RiskManager; print('daily_capital cache ready')"` | 정상 임포트 |
| trailing Redis 이관 | `docker compose exec backend python -c "from modules.trading.position_manager import PositionManager; print('trailing_highs redis ready')"` | 정상 임포트 |
| RedisClient HSET | `docker compose exec backend python -c "from core.redis import RedisClient; r = RedisClient('redis://'); print(hasattr(r, 'hset'), hasattr(r, 'hgetall'))"` | True True |
| risk_manager rest_client | main.py에서 RiskManager 생성 시 rest_client 전달 확인 | 코드 리뷰 |
| in-flight 플래그 | test_engine_inflight.py 4개 테스트 | 4 passed |
