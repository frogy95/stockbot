# Sprint 1: 시간가중 거래량 보정 + 5분봉 수집 선행 구축 (Phase 6.1)

**Goal:** momentum_breakout 전략의 거래량 조건을 시간가중 보정 + 돌파 강도 연동으로 개선하고, Phase 7용 5분봉 거래량 수집 파이프라인을 선행 구축하여 데이터 축적 시작

**Architecture:** momentum_breakout.py에 calc_market_progress() 유틸 추가 + 거래량 조건 블록 교체 (선형 보정 + 3단계 임계값). volume_aggregator.py 신규 모듈로 WS 체결 이벤트마다 Redis 5분봉 슬롯에 INCRBY 누적. 조회 엔드포인트 추가.

**Tech Stack:** Python 3.12, FastAPI, Redis 7 (INCRBY), pytest-asyncio, zoneinfo

**Sprint 기간:** 2026-04-13 ~ 2026-04-13
**이전 스프린트:** Phase 6 Sprint 2 (pytest PASS, PR #108)
**브랜치명:** `phase6.1-sprint1`
**상태:** ✅ 완료 (2026-04-13)

---

## 제외 범위

- 5분봉 데이터를 전략에서 사용하는 것 (Phase 7 범위)
- 비선형(U자형) 보정 (Phase 9 범위)
- 동시간대 Z-score (Phase 8 범위)
- 프론트엔드 변경 (전략 내부 로직 변경이므로 API 응답 형식 불변)
- DB 스키마 변경 / Alembic 마이그레이션 (Redis만 사용)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | calc_market_progress 유틸 + 단위 테스트 | 백엔드 | — |

### Phase 2 (순차 — Task 1 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | momentum_breakout 전략 수정 + 기존 테스트 업데이트 + 역산 테스트 | 백엔드 | — |

### Phase 3 (병렬 가능 — Task 1,2와 파일 소유권 무관)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | volume_aggregator 신규 모듈 + 단위 테스트 | 백엔드 | — |

### Phase 4 (순차 — Task 3 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | scheduler 연동 + 조회 API + 통합 검증 | 백엔드 | — |

> **참고**: Task 2와 Task 3은 파일 소유권이 겹치지 않으므로 병렬 가능하나, Task 2가 calc_market_progress에 의존하므로 Task 1 완료 후 시작. Task 3은 Task 1 완료 즉시 시작 가능.

---

### Task 1: calc_market_progress 유틸 + 단위 테스트

**Files:**
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (상수 정의 + calc_market_progress 함수 추가, 기존 generate_signal 미수정)
- Create: `backend/tests/test_market_progress.py`

**Step 1: 테스트 작성**
- `backend/tests/test_market_progress.py` 생성
- 테스트 케이스:
  - `test_progress_market_open`: 09:00 시점 -> 0.0 (하한 0.15 적용 전 raw 값)
  - `test_progress_midday`: 12:15 시점 -> 195/390 = 0.5
  - `test_progress_market_close`: 15:30 시점 -> 1.0
  - `test_progress_before_market`: 08:00 시점 -> MIN_MARKET_PROGRESS (0.15)
  - `test_progress_after_market`: 16:00 시점 -> 1.0
  - `test_progress_min_floor`: 09:30 시점 -> 30/390 = 0.077 -> 하한 0.15 적용
  - `test_progress_at_0958`: 09:58 시점 -> 58/390 = 0.149 -> 하한 0.15 적용 (경계)
  - `test_progress_at_1000`: 10:00 시점 -> 60/390 = 0.154 > 0.15 -> 그대로
- 각 테스트에서 `datetime.now`를 mock하여 특정 시각 주입
- `from modules.trading.strategies.momentum_breakout import calc_market_progress, MARKET_OPEN, MARKET_CLOSE, MARKET_MINUTES, MIN_MARKET_PROGRESS`
- 검증: `docker compose exec backend pytest tests/test_market_progress.py -v`
- 예상: FAIL (함수 미존재)

**Step 2: calc_market_progress 구현**
- `backend/modules/trading/strategies/momentum_breakout.py` 상단에 추가:
  - `from datetime import datetime, time` + `from zoneinfo import ZoneInfo`
  - 상수: `MARKET_OPEN = time(9, 0)`, `MARKET_CLOSE = time(15, 30)`, `MARKET_MINUTES = 390`
  - 상수: `MIN_MARKET_PROGRESS = 0.15`, `MIN_VOLUME_FLOOR = 0.5`
  - `calc_market_progress(now_kst: datetime | None = None) -> float` 함수
    - `now_kst`이 None이면 `datetime.now(ZoneInfo("Asia/Seoul"))` 사용 (테스트 주입용)
    - 장 전: `MIN_MARKET_PROGRESS` 반환
    - 장 후: `1.0` 반환
    - 장중: `max(elapsed / MARKET_MINUTES, MIN_MARKET_PROGRESS)` 반환
    - `elapsed = (now.hour * 60 + now.minute) - (9 * 60)` (분 단위)
- 검증: `docker compose exec backend pytest tests/test_market_progress.py -v`
- 예상: 8 passed

**Step 3: 커밋**
```
git add backend/modules/trading/strategies/momentum_breakout.py backend/tests/test_market_progress.py
git commit -m "feat(phase6.1-sprint1): task1 — calc_market_progress 유틸 + 단위 테스트"
```

**완료 기준:**
- ✅ test_market_progress.py 9개 테스트 통과
- ✅ 기존 테스트 회귀 없음 (momentum_breakout.py에 함수만 추가, 기존 로직 미수정)

---

### Task 2: momentum_breakout 전략 수정 + 기존 테스트 업데이트

**Files:**
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (generate_signal 메서드 수정)
- Modify: `backend/tests/test_momentum_breakout.py` (기존 테스트 수정 + 신규 테스트 추가)

**Step 1: 전략 수정**
- `generate_signal()` 메서드의 거래량 조건 블록(현재 38~42줄) 교체:
  ```
  # 기존:
  #   if snapshot.prev_volume == 0: return None
  #   volume_ratio = snapshot.volume / snapshot.prev_volume
  #   if volume_ratio < 2.0: return None
  
  # 변경:
  if snapshot.prev_volume == 0:
      return None
  
  # 절대 거래량 하한
  if snapshot.volume < snapshot.prev_volume * MIN_VOLUME_FLOOR:
      return None
  
  # 시간가중 보정
  progress = calc_market_progress()
  effective_progress = max(progress, MIN_MARKET_PROGRESS)
  adjusted_ratio = snapshot.volume / (snapshot.prev_volume * effective_progress)
  
  # 돌파 강도 연동 임계값
  breakout_pct = (snapshot.current_price - breakout_ref) / breakout_ref * 100
  if breakout_pct >= 5.0:
      volume_threshold = 1.5
  elif breakout_pct >= 3.0:
      volume_threshold = 1.8
  else:
      volume_threshold = 2.0
  
  if adjusted_ratio < volume_threshold:
      return None
  ```
- volume_score 변경 (현재 59줄): `volume_score = min(adjusted_ratio / 5.0, 1.0)`
- reason dict 확장 (현재 93~102줄): 기존 `volume_ratio` 유지 + `adjusted_ratio`, `volume_threshold`, `breakout_pct`, `market_progress` 추가
  ```python
  reason={
      ...,
      "volume_ratio": round(snapshot.volume / snapshot.prev_volume, 2),
      "adjusted_ratio": round(adjusted_ratio, 2),
      "volume_threshold": volume_threshold,
      "breakout_pct": round(breakout_pct, 2),
      "market_progress": round(progress, 4),
  }
  ```

**Step 2: 기존 테스트 수정**
- `_make_snapshot` 기본값 유지 — 기존 테스트에서 `calc_market_progress`를 mock하여 progress=1.0 (장 마감 기준)으로 고정해야 기존 기대값 유지
- **방법**: 각 기존 테스트에서 `@patch("modules.trading.strategies.momentum_breakout.calc_market_progress", return_value=1.0)` 데코레이터 추가
  - `test_breakout_buy_signal`: progress=1.0에서 volume_ratio=4.0, adjusted_ratio=4.0 -> breakout_pct=3.55% -> threshold=1.8 -> 통과. 기존 assertion 유지.
  - `test_low_volume_returns_none`: volume=15M/pvol=10M=1.5, progress=1.0 -> adjusted=1.5, breakout_pct=3.55% -> threshold=1.8 -> 1.5 < 1.8 -> None. 기존 assertion 유지.
  - `test_confidence_weighted_average`: progress=1.0, adjusted_ratio=4.0 -> volume_score = min(4.0/5.0, 1.0) = 0.8. 기존 수동 검증도 `adjusted_ratio / 5.0` 기반으로 수정.
  - `test_low_confidence_returns_none`: volume=20M/pvol=10M=2.0, progress=1.0 -> adjusted=2.0, breakout_pct=0.014% -> threshold=2.0 -> 통과(딱 경계). confidence 계산 확인 필요 — volume_score=min(2.0/5.0,1.0)=0.4 (기존과 동일)
  - `test_reason_dict_structure`: 신규 필드 `adjusted_ratio`, `volume_threshold`, `breakout_pct`, `market_progress` assertion 추가
- 나머지 테스트(no_breakout, low_trade_strength, gap, atr_filter, stop_loss 등): 거래량 조건 이전에 탈락하거나 progress mock 불필요한 경우도 있으나, 일관성을 위해 전체 mock 적용

**Step 3: 신규 테스트 추가**
- `test_morning_adjusted_ratio_pass`: 10:30 시점(progress=90/390=0.231), volume=2.5M, pvol=10M -> raw ratio=0.25, adjusted=0.25/0.231=1.08 -> breakout_pct=7.6% -> threshold=1.5 -> 1.08 < 1.5 -> None
- `test_062040_isupetasis_scenario`: 062040 이수페타시스 역산 (Phase 문서 데이터)
  - 13:17 KST -> progress=257/390=0.659
  - current_price=169900, prev_high=157900 -> breakout_pct=7.6% -> threshold=1.5
  - volume=1080856, prev_volume=968175 -> raw=1.116, adjusted=1080856/(968175*0.659)=1.694
  - MIN_VOLUME_FLOOR: 1.116 >= 0.5 -> 통과
  - adjusted=1.694 >= 1.5 -> 통과! 신호 생성 확인
  - `calc_market_progress`를 mock하여 13:17 시각 주입
- `test_breakout_pct_thresholds`: 돌파 강도별 3단계 확인
  - breakout_pct >= 5.0% -> threshold=1.5
  - breakout_pct = 3.5% -> threshold=1.8
  - breakout_pct = 1.0% -> threshold=2.0
- `test_min_volume_floor_blocks`: volume/prev_volume = 0.4 < 0.5 -> None (progress 무관)
- `test_min_volume_floor_passes`: volume/prev_volume = 0.6 >= 0.5 -> 다음 조건으로 진행
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py -v`
- 예상: 기존 10개 + 신규 5개 = 15 passed

**Step 4: 커밋**
```
git add backend/modules/trading/strategies/momentum_breakout.py backend/tests/test_momentum_breakout.py
git commit -m "feat(phase6.1-sprint1): task2 — 시간가중 보정 + 돌파 강도 연동 임계값 적용"
```

**완료 기준:**
- ✅ test_momentum_breakout.py 16개 테스트 통과 (기존 11 + 신규 5)
- ✅ test_market_progress.py 9개 테스트 통과 (회귀 확인)
- ✅ 062040 이수페타시스 역산 시나리오 PASS

---

### Task 3: volume_aggregator 신규 모듈 + 단위 테스트

**Files:**
- Create: `backend/modules/collector/volume_aggregator.py`
- Create: `backend/tests/test_volume_aggregator.py`

**Step 1: 테스트 작성**
- `backend/tests/test_volume_aggregator.py` 생성
- 테스트 케이스:
  - `test_calc_5min_slot_0900`: 09:00 -> slot 0
  - `test_calc_5min_slot_0935`: 09:35 -> slot 7
  - `test_calc_5min_slot_1230`: 12:30 -> slot 42
  - `test_calc_5min_slot_1530`: 15:30 -> slot 77 (clamped)
  - `test_calc_5min_slot_before_market`: 08:30 -> slot 0 (clamped)
  - `test_calc_5min_slot_after_market`: 16:00 -> slot 77 (clamped)
  - `test_make_redis_key`: stock_code=062040, date=20260413, slot=7 -> `vol5m:062040:20260413:7`
  - `test_aggregate_execution_increments`: AsyncMock RedisClient로 aggregate_execution 호출 2회 -> 동일 슬롯에 volume 누적 검증
  - `test_aggregate_execution_buy_sell_split`: sell_or_buy="2"(매수) -> buy_vol 증가, "1"(매도) -> sell_vol 증가
  - `test_get_recent_slots_returns_data`: 최근 12슬롯 조회 함수 검증
- FakeRedis 또는 AsyncMock 사용 (기존 테스트 패턴과 동일)
- 검증: `docker compose exec backend pytest tests/test_volume_aggregator.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: volume_aggregator 모듈 구현**
- `backend/modules/collector/volume_aggregator.py` 생성
- 상수:
  - `VOL5M_TTL = 60 * 60 * 24 * 30` (30일)
  - `MARKET_OPEN_MINUTES = 9 * 60` (09:00 = 540분)
  - `SLOT_COUNT = 78` (09:00~15:30 = 390분 / 5분)
  - `SLOT_MINUTES = 5`
- 함수:
  - `calc_5min_slot(hour: int, minute: int) -> int`:
    - `elapsed = (hour * 60 + minute) - MARKET_OPEN_MINUTES`
    - `return max(0, min(SLOT_COUNT - 1, elapsed // SLOT_MINUTES))`
  - `make_redis_key(stock_code: str, date_str: str, slot: int) -> str`:
    - `return f"vol5m:{stock_code}:{date_str}:{slot}"`
- 클래스 `VolumeAggregator`:
  - `__init__(self, redis: RedisClient)`: Redis 클라이언트 보관
  - `async def aggregate_execution(self, stock_code: str, exec_time: str, volume: int, sell_or_buy: str) -> None`:
    - `exec_time` 형식: "HHMMSS" (KIS WS 체결 데이터의 time 필드)
    - hour, minute 파싱 -> `calc_5min_slot(hour, minute)` -> slot
    - 오늘 날짜 (KST) -> date_str (YYYYMMDD)
    - Redis key 생성
    - 기존 값 GET -> JSON 파싱 (없으면 초기값)
    - buy_vol/sell_vol/total_vol/trade_count 업데이트
    - SET + TTL
    - **참고**: RedisClient에 INCRBY/HINCRBY 미노출이므로, GET-수정-SET 패턴 사용 (단일 프로세스이므로 race condition 없음)
  - `async def get_recent_slots(self, stock_code: str, count: int = 12) -> list[dict]`:
    - 현재 시각 기준 최근 `count`개 슬롯 데이터 조회
    - 각 슬롯의 Redis 값을 GET -> JSON 파싱 -> 리스트 반환
    - 빈 슬롯은 `{"slot": N, "buy_vol": 0, "sell_vol": 0, "total_vol": 0, "trade_count": 0}` 반환
  - `async def get_first_seen_date(self) -> str | None`:
    - `vol5m:*` 패턴 SCAN -> 가장 오래된 date_str 반환 (축적 현황 확인용)
    - 키가 없으면 None
- 검증: `docker compose exec backend pytest tests/test_volume_aggregator.py -v`
- 예상: 10 passed

**Step 3: 커밋**
```
git add backend/modules/collector/volume_aggregator.py backend/tests/test_volume_aggregator.py
git commit -m "feat(phase6.1-sprint1): task3 — 5분봉 거래량 집계 모듈 + 단위 테스트"
```

**완료 기준:**
- ✅ test_volume_aggregator.py 10개 테스트 통과
- ✅ calc_5min_slot 경계값 검증 완료
- ✅ Redis GET-수정-SET 패턴 동작 확인

---

### Task 4: scheduler 연동 + 조회 API + 통합 검증

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (_process_realtime_data에 aggregator 호출 추가, __init__에 aggregator 파라미터 추가)
- Modify: `backend/api/routes/collector.py` (vol5m 조회 엔드포인트 추가)
- Modify: `backend/main.py` (VolumeAggregator 인스턴스 생성 + scheduler에 주입)
- Create: `backend/tests/test_scheduler_vol5m.py` (통합 테스트)

**Step 1: scheduler 수정**
- `backend/modules/collector/scheduler.py` 수정:
  - import 추가: `from modules.collector.volume_aggregator import VolumeAggregator`
  - `CollectorScheduler.__init__`에 `volume_aggregator: VolumeAggregator | None = None` 파라미터 추가
  - `self._volume_aggregator = volume_aggregator`
  - `_process_realtime_data` 메서드의 H0STCNT0 분기에서, 체결강도 업데이트 뒤에 volume_aggregator 호출 추가:
    ```python
    # 5분봉 거래량 집계 (Phase 7용 선행 수집)
    if self._volume_aggregator:
        try:
            await self._volume_aggregator.aggregate_execution(
                execution.stock_code,
                execution.time,
                execution.volume,
                execution.sell_or_buy,
            )
        except Exception:
            logger.debug("vol5m 집계 실패 (무시)", exc_info=True)
    ```
  - **주의**: try/except로 감싸서 집계 실패가 실시간 처리를 방해하지 않도록 함

**Step 2: main.py 수정**
- `backend/main.py`의 lifespan에서 VolumeAggregator 인스턴스 생성:
  - import: `from modules.collector.volume_aggregator import VolumeAggregator`
  - `volume_aggregator = VolumeAggregator(redis_client)` 생성
  - `CollectorScheduler(...)` 호출 시 `volume_aggregator=volume_aggregator` 전달
  - `app.state.volume_aggregator = volume_aggregator` (API 엔드포인트에서 사용)

**Step 3: 조회 API 추가**
- `backend/api/routes/collector.py`에 엔드포인트 추가:
  ```python
  @router.get("/collector/vol5m/{stock_code}")
  async def get_vol5m(stock_code: str, request: Request):
      """5분봉 거래량 슬롯 조회 (최근 12개 버킷, Phase 7 디버깅용)."""
      aggregator = getattr(request.app.state, "volume_aggregator", None)
      if aggregator is None:
          raise HTTPException(status_code=503, detail="VolumeAggregator 미초기화")
      slots = await aggregator.get_recent_slots(stock_code, count=12)
      first_seen = await aggregator.get_first_seen_date()
      return {
          "stock_code": stock_code,
          "slots": slots,
          "vol5m_first_seen_date": first_seen,
      }
  ```

**Step 4: 통합 테스트**
- `backend/tests/test_scheduler_vol5m.py` 생성
- 테스트 케이스:
  - `test_process_realtime_data_calls_aggregator`: AsyncMock volume_aggregator를 scheduler에 주입, H0STCNT0 메시지 수신 시 aggregate_execution 호출 검증
  - `test_process_realtime_data_aggregator_failure_ignored`: aggregator가 예외를 발생시켜도 나머지 처리 정상 동작 검증
  - `test_aggregator_none_skips`: volume_aggregator=None이면 호출 안 함 (기존 동작 무변경)
- 검증: `docker compose exec backend pytest tests/test_scheduler_vol5m.py -v`
- 예상: 3 passed

**Step 5: 전체 pytest 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 기존 테스트 + 신규 26개 전부 통과

**Step 6: 커밋**
```
git add backend/modules/collector/scheduler.py backend/modules/collector/volume_aggregator.py backend/api/routes/collector.py backend/main.py backend/tests/test_scheduler_vol5m.py
git commit -m "feat(phase6.1-sprint1): task4 — scheduler 5분봉 연동 + vol5m 조회 API + 통합 테스트"
```

**완료 기준:**
- ✅ test_scheduler_vol5m.py 3개 테스트 통과
- ✅ 전체 pytest 통과 (798 passed, 0 failed, 회귀 없음)
- ✅ `curl http://localhost:8000/api/v1/collector/vol5m/005930` HTTP 200, 슬롯 12개 + first_seen_date 정상 응답

---

## Redis 키 스키마

```
vol5m:{stock_code}:{YYYYMMDD}:{slot_index}
       |            |           |
       |            |           +-- 5분봉 슬롯 (0~77, 09:00~15:30)
       |            +------------- 거래일 (예: 20260413)
       +-------------------------- 종목 코드 (예: 062040)

값: JSON {"buy_vol": int, "sell_vol": int, "total_vol": int, "trade_count": int}
TTL: 30일 (2,592,000초)

슬롯 매핑:
  slot 0  = 09:00~09:04
  slot 1  = 09:05~09:09
  ...
  slot 42 = 12:30~12:34
  ...
  slot 77 = 15:25~15:29

메모리 추정: 30종목 x 78슬롯 x 30일 = 70,200키 x ~100B = ~7MB
```

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| 시간가중 테스트 | `docker compose exec backend pytest tests/test_market_progress.py -v` | 8 passed |
| 전략 테스트 | `docker compose exec backend pytest tests/test_momentum_breakout.py -v` | 15 passed |
| 5분봉 테스트 | `docker compose exec backend pytest tests/test_volume_aggregator.py -v` | 10 passed |
| 스케줄러 연동 테스트 | `docker compose exec backend pytest tests/test_scheduler_vol5m.py -v` | 3 passed |
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 통과, 회귀 없음 |
| vol5m API | `curl -s http://localhost:8000/api/v1/collector/vol5m/005930 \| jq .` | `{"stock_code": "005930", "slots": [...], "vol5m_first_seen_date": ...}` |
| reason dict | 장중 매매 신호 로그에서 `adjusted_ratio`, `volume_threshold`, `breakout_pct`, `market_progress` 필드 확인 | 4개 필드 포함 |
