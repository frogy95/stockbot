# Sprint 1: 관측성 강화 (Phase 8.5)

**Goal:** 2차 스크리닝 `total_score` 분포 · 전략 stage 탈락/통과 heatmap · 탈락 상위 종목 실시간 리스트 · 가상 신호 로그를 수집하여, Phase 8.5 Sprint 2 및 Phase 10.1에서 파라미터 조정을 **데이터 기반**으로 의사결정할 수 있는 관측 인프라를 선제 배포한다.

**Architecture:** Redis counter(INCR) 기반 경량 메트릭 수집 → APScheduler 16:00 일별 집계 job → PostgreSQL 영구 저장 → 신규 `/api/v1/metrics` 라우터 → Next.js 대시보드 "신호 진단" 섹션 카드 4종. 기존 흐름(screener/strategy)에 **읽기 전용 측면 기록**만 삽입하여 트레이딩 로직을 건드리지 않는다. 가상 신호(13:00~14:00 `prev_close_time_guard` 가정 발동)는 별도 테이블 INSERT만 수행하고 주문 경로와 완전 분리된다.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 async / APScheduler / Redis 7 / Alembic / Next.js 16 App Router / React 19 / Tailwind 4 / SWR(polling)

**Sprint 기간:** 2026-04-22 ~ 2026-04-22
**상태:** ✅ 완료 (2026-04-22)
**이전 스프린트:** Phase 8 Sprint 2 (✅ 완료, PR #157)
**브랜치명:** `phase8.5-sprint1`
**PR:** https://github.com/frogy95/stockbot/pull/162

---

## 제외 범위

이 스프린트에서 **하지 않는 것**:

- 2차 스크리닝 풀 하한 폴백 (`passed_count < 3` 시 보강) — Sprint 2 범위
- 동적 `MIN_VOLUME_FLOOR` (0.4 / 0.5 / 0.6 분기) — Sprint 2 범위
- `MIN_VOLUME_FLOOR_HARD = 0.3` 절대 하한 — Sprint 2 범위
- `is_fallback` 플래그, 50% 포지션, 하락 -3% 제외, 손절 -1.5% 등 폴백 부가 로직 — Sprint 2 범위
- 자동 롤백 트리거 스케줄러 (16:10 2거래일 0건 감시) — Sprint 2 범위
- `pass_threshold` 조정 — 분포 데이터 확보 후 Sprint 2 이후 결정
- `prev_close_time_guard` 13:00 → 14:00 연장 — 검토팀 전원 거부, 영구 범위 제외
- 시간대 슬라이딩 `MIN_VOLUME_FLOOR` — 검토팀 전원 거부, 영구 범위 제외
- Phase 8.6 Sprint 1 (구 Phase 8 Sprint 3) DoD 재정의 문서 작업 (phase8.6.md 수정) — Phase 8.5 Sprint 2 완료 후

**핵심 제약**:

- 기존 `realtime_screener.screen()` / `MomentumBreakoutStrategy.generate_signal()`의 **분기 조건·임계값·반환 구조를 절대 변경하지 않는다**. 카운터 기록은 항상 기존 분기 판정 **이후** 측면 추가(post-decision side-effect) 방식.
- 가상 신호 로깅은 **SELECT/INSERT만 수행**. `TradeSignalData` 생성 금지, `signal_generator`·`engine`·`order_manager` 경로 호출 금지. 테스트로 "주문 0건" 검증 필수.
- 카드 4(폴백 발동 통계)는 Sprint 1에서 **빈 카드 + "Coming Soon (Sprint 2)" 표시**만.

---

## 실행 플랜

의존성 그래프:

```
Task 1 (Alembic)
  └─> Task 2 (Redis counter 유틸)
       ├─> Task 3 (screener score 히스토그램)
       ├─> Task 4 (strategy stage 카운터 + 가상 신호)
       └─> Task 5 (16:00 일별 집계 batch)
              └─> Task 6 (metrics API)
                     └─> Task 7 (프론트 신호 진단 섹션)
                            └─> Task 8 (통합 검증)
```

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | Alembic 마이그레이션 3종 (`screening_metrics_daily`, `strategy_metrics_daily`, `virtual_signals`) | 백엔드 | — |
| Task 2 | `core/redis.py`에 `incr` / `mget` 유틸 추가 + `core/metrics_keys.py` 키 규약 모듈 | 백엔드 | — |

### Phase 2 (병렬 가능 — 파일 소유권 분리)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | `realtime_screener.py`에 `total_score` 히스토그램 기록 (10점 bucket × 10 + >=75 별도) | 백엔드 | — |
| Task 4 | `momentum_breakout.py` stage 카운터 + 가상 신호 로깅 (13:00~14:00 `prev_close_time_guard` 한정) | 백엔드 | `systematic-debugging` |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | 16:00 KST APScheduler job: Redis counter → DB 일별 집계 이관 + TTL/삭제 | 백엔드 | — |
| Task 6 | `/api/v1/metrics/*` 라우터 4종 (score-histogram / stage-heatmap / top-rejects / virtual-signals) | 백엔드 | — |

### Phase 4 (병렬 가능 — 프론트 단독)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 7 | 대시보드 "신호 진단 (Phase 8.5)" 섹션 카드 4개 | 프론트엔드 | `frontend-design` |

### Phase 5 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 8 | E2E 통합 검증 (pytest + curl + Playwright) + 가상 신호 주문 미발생 검증 | 전체 | `verification-before-completion` |

> **팀 실행**: Phase 2는 백엔드 전담으로 동시 실행 가능하지만, 동일 모듈 임포트 범위가 좁아 순차 실행도 1시간 내 완료 가능. 기본 전략은 순차 권장.

---

## Task 1: Alembic 마이그레이션 3종

**Files:**
- Create: `backend/alembic/versions/{auto}_phase8_5_sprint1_metrics_tables.py`
- Create: `backend/core/models/metrics.py` (신규 모델 3종)
- Modify: `backend/core/models/__init__.py` (모델 임포트 추가 — 파일 존재 여부 확인 필요. 없으면 스킵)

**Step 1: 모델 정의**
- `backend/core/models/metrics.py` 생성:
  - `ScreeningMetricsDaily` (테이블 `screening_metrics_daily`)
    - `id` PK int autoincrement
    - `metric_date` Date, unique (UniqueConstraint를 `__table_args__`로 명시 — Phase 1 학습)
    - `bucket` String(16) (예: `"0-10"`, `"10-20"`, ..., `"70-80"`, `">=75"`)
    - `count` Integer default 0
    - `created_at`, `updated_at` (server_default `func.now()`, onupdate `func.now()`)
    - UniqueConstraint(`metric_date`, `bucket`)
  - `StrategyMetricsDaily` (테이블 `strategy_metrics_daily`)
    - `id`, `metric_date`, `stage` String(64) (예: `"breakout"`, `"min_volume_floor"`, `"prev_close_time_guard"`, `"volume_threshold"`, `"trade_strength"`, `"atr_filter"`, `"confidence"`, `"pass"` 등), `hour_min_bucket` String(8) (예: `"09:30"`, 10분 bucket), `count` Integer, 타임스탬프
    - UniqueConstraint(`metric_date`, `stage`, `hour_min_bucket`)
  - `VirtualSignal` (테이블 `virtual_signals`)
    - `id`, `observed_at` DateTime (UTC, `server_default=func.now()`)
    - `stock_code` String(8) 인덱스
    - `stock_name` String(64)
    - `virtual_stage` String(64) — 현재는 `"prev_close_time_guard_bypass"` 고정
    - `breakout_ref` Integer
    - `current_price` Integer
    - `gap_rate` Numeric(6, 4)
    - `prev_close` Integer
    - `detail` JSON (전략이 `_reject`에 넣었던 detail dict 복사)
    - `would_execute` Boolean default False (현재는 로깅만 — 추후 전략 조건 전체 통과 여부 판정 시 사용; Sprint 1에서는 항상 False 저장)

**Step 2: Alembic 마이그레이션 생성**
- 명령: `docker compose exec backend alembic revision --autogenerate -m "phase8.5 sprint1 관측성 테이블 3종 추가"`
- 생성된 파일 검증:
  - upgrade()에 `op.create_table("screening_metrics_daily", ...)`, `"strategy_metrics_daily"`, `"virtual_signals"` 3개 포함
  - downgrade()에 `op.drop_table(...)` 3개
  - 불필요한 기존 테이블 변경이 섞이지 않았는지 확인 (있으면 제거)

**Step 3: 마이그레이션 적용**
- 검증: `docker compose exec backend alembic upgrade head`
- 예상: `INFO  [alembic.runtime.migration] Running upgrade ... -> {revision}, phase8.5 sprint1 관측성 테이블 3종 추가`
- 확인:
  ```bash
  docker compose exec db psql -U postgres -d stockbot -c "\dt" | grep -E "metrics_daily|virtual_signals"
  ```
- 예상: 3개 테이블 출력

**Step 4: 커밋**
```
git add backend/core/models/metrics.py backend/alembic/versions/*phase8_5_sprint1_metrics*.py
git commit -m "feat(phase8.5-sprint1): task1 — 관측성 테이블 3종 Alembic 마이그레이션"
```

**완료 기준:**
- ✅ `alembic upgrade head` 성공
- ✅ 3개 테이블 생성 확인
- ✅ UniqueConstraint 정상 동작 (중복 INSERT 실패 테스트)

---

## Task 2: Redis 메트릭 유틸 + 키 규약

**Files:**
- Create: `backend/core/metrics_keys.py` (키 규약 단일 진입점)
- Modify: `backend/core/redis.py` (`incr`, `mget` 메서드 추가)
- Test: `backend/tests/core/test_metrics_keys.py`

**Step 1: 테스트 작성**
- `backend/tests/core/test_metrics_keys.py`:
  - `score_histogram_key(date, bucket)` → `"metrics:secondary:score:2026-04-22:70-80"`
  - `stage_counter_key(date, stage, hour_min)` → `"metrics:strategy:stage:2026-04-22:min_volume_floor:09:30"`
  - `score_bucket_for(score: float)` → 점수 → bucket 라벨 변환 (`0.0→"0-10"`, `75.0→">=75"` 및 `"70-80"` 동시 반환 규약)
  - `hour_min_bucket_for(dt: datetime)` → 10분 단위 내림 (`09:37 → "09:30"`)
- 검증: `docker compose exec backend pytest tests/core/test_metrics_keys.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 키 규약 모듈 구현**
- `backend/core/metrics_keys.py`:
  - 상수: `SECONDARY_SCORE_PREFIX = "metrics:secondary:score"`, `STRATEGY_STAGE_PREFIX = "metrics:strategy:stage"`, `TOP_REJECT_PREFIX = "metrics:strategy:top_reject"` (최근 5건 리스트 key)
  - `score_bucket_for(score)` 반환 규약:
    - 점수가 75 이상이면 **동시에 2개 bucket 기록**: `">=75"` + 해당 10점 bucket (예: 80.0 → `[">=75", "80-90"]`)
    - 75 미만은 단일 10점 bucket (0.0 → `["0-10"]`)
  - `hour_min_bucket_for(dt)` — KST 가정, `dt.minute // 10 * 10` 포맷
  - `stages()` → 추적 대상 stage 리스트 (`momentum_breakout`의 `_reject` 호출 stage 전수 + `"pass"`)
- 검증: `docker compose exec backend pytest tests/core/test_metrics_keys.py -v`
- 예상: PASS

**Step 3: Redis 메서드 추가**
- `backend/core/redis.py` `RedisClient` 클래스에 추가:
  - `async def incr(self, key: str, amount: int = 1, ttl: int | None = None) -> int`
    - `await self._redis.incrby(key, amount)` 호출, ttl 제공 시 `expire` 적용 (최초 생성 시에만)
  - `async def mget(self, keys: list[str]) -> list[str | None]`
- 검증:
  ```bash
  docker compose exec backend python -c "
  import asyncio
  from core.redis import redis_client
  async def t():
      await redis_client.connect()
      await redis_client.delete('test:incr')
      n = await redis_client.incr('test:incr', ttl=60)
      print('incr=', n)
      n = await redis_client.incr('test:incr')
      print('incr=', n)
      await redis_client.delete('test:incr')
      await redis_client.disconnect()
  asyncio.run(t())
  "
  ```
- 예상: `incr= 1` / `incr= 2`

**Step 4: 커밋**
```
git add backend/core/metrics_keys.py backend/core/redis.py backend/tests/core/test_metrics_keys.py
git commit -m "feat(phase8.5-sprint1): task2 — 메트릭 Redis 유틸 + 키 규약"
```

**완료 기준:**
- ✅ `test_metrics_keys.py` 전체 PASS
- ✅ `incr` 메서드 동작 수동 검증
- ✅ TTL이 최초 생성 시에만 적용 (기존 키 TTL 유지 확인)

---

## Task 3: 2차 스크리닝 score 히스토그램 기록

**Files:**
- Modify: `backend/modules/screening/realtime_screener.py` (`screen()` 반환 직전에 히스토그램 기록)
- Test: `backend/tests/modules/screening/test_realtime_screener_metrics.py` (신규, 기존 `test_realtime_screener.py`는 건드리지 않음)

**Step 1: 테스트 작성**
- 테스트 케이스:
  1. `scored = [{"score": 82.5}, {"score": 40.0}, {"score": 75.0}]` 투입 시 Redis에 기록된 bucket 카운트:
     - `">=75"` → 2 (82.5, 75.0)
     - `"80-90"` → 1
     - `"70-80"` → 1 (75.0)
     - `"40-50"` → 1
  2. `scored = []` (빈 리스트) → Redis 호출 0건 (기존 반환 동작 유지)
  3. `redis_client is None` (미주입) → silent skip, 예외 없음
- 검증: `docker compose exec backend pytest tests/modules/screening/test_realtime_screener_metrics.py -v`
- 예상: FAIL

**Step 2: 히스토그램 기록 로직 추가**
- `realtime_screener.py` 수정:
  - `save_results()` 호출 **이후** (line 201~202 근처) 별도 메서드 `_record_score_histogram(scored)` 호출
  - 신규 메서드:
    ```
    async def _record_score_histogram(self, scored: list[dict]) -> None
    ```
    - `self.redis_client is None` 이면 return
    - `from core.metrics_keys import score_histogram_key, score_bucket_for`
    - KST 오늘 날짜 문자열 산출 (`date.today()` 금지 — `datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date().isoformat()`)
    - 각 item의 `item.get("score", 0.0)`로 `score_bucket_for` 호출, 반환된 bucket 리스트 각각에 대해 `redis_client.incr(key, ttl=86400*7)` 실행
    - 전체 try/except로 감싸 메트릭 실패가 스크리닝 본연 경로를 깨지 않도록 로깅만 하고 continue
  - `screen()` 반환 직전에 이 메서드 호출 (await)

**검증:**
- `docker compose exec backend pytest tests/modules/screening/test_realtime_screener_metrics.py -v`
- 예상: PASS
- 기존 테스트 회귀 확인: `docker compose exec backend pytest tests/modules/screening/ -v`
- 예상: 전체 PASS

**Step 3: 커밋**
```
git add backend/modules/screening/realtime_screener.py backend/tests/modules/screening/test_realtime_screener_metrics.py
git commit -m "feat(phase8.5-sprint1): task3 — 2차 스크리닝 score 히스토그램 Redis 기록"
```

**완료 기준:**
- ✅ 신규 테스트 PASS
- ✅ 기존 `test_realtime_screener.py` 회귀 없음
- ✅ `>=75` 와 10점 bucket이 **동시에** 기록되는지 검증 (중요)

---

## Task 4: 전략 stage 카운터 + 가상 신호 로깅

**skill:** `systematic-debugging` (가상 신호가 실제 주문으로 절대 이어지지 않음을 확증하기 위해 reject/pass 경로 전수 추적)

**Files:**
- Modify: `backend/modules/trading/strategies/momentum_breakout.py`
- Create: `backend/modules/trading/strategies/_metrics.py` (stage 카운터/가상 신호 기록 헬퍼 — 전략 순수성 유지)
- Test: `backend/tests/modules/trading/strategies/test_momentum_breakout_metrics.py` (신규)

**Step 1: 테스트 작성**
- 주요 케이스:
  1. **가상 신호 기록 케이스**: KST 13:30, `prev_close` tier (gap < 3% 이고 current_price <= prev_high), `_reject` 호출 → `virtual_signals` 테이블 1건 INSERT
  2. **가상 신호 미기록 (시간창 밖)**: KST 12:59 동일 조건 → 기존 반환(정상 `prev_close_time_guard` 거부만 발생, virtual_signals INSERT 0건)
  3. **가상 신호 미기록 (tier 다름)**: KST 13:30, `prev_high` tier → virtual_signals INSERT 0건
  4. **stage 카운터**: 어느 경로로든 `_reject` 호출 → `metrics:strategy:stage:{date}:{stage}:{hour_min}` 카운터 +1
  5. **주문 미발생 확증**: 가상 신호 기록 시에도 `generate_signal()` 반환값은 반드시 `RejectedSignal` 타입 (TradeSignalData 아님) — 기존 단위 테스트 assert 유지
  6. **시간 주입**: `_now_kst()` monkeypatch로 13:00~14:00 시뮬레이션
- 검증: `docker compose exec backend pytest tests/modules/trading/strategies/test_momentum_breakout_metrics.py -v`
- 예상: FAIL

**Step 2: 메트릭 헬퍼 모듈 구현**
- `backend/modules/trading/strategies/_metrics.py`:
  - `async def record_stage(redis_client, stage: str, now_kst: datetime | None = None) -> None`
    - redis None이면 return, try/except 로깅만
  - `async def record_virtual_signal(session_factory, snapshot, detail: dict) -> None`
    - `session_factory()` 로 새 세션 오픈 → `VirtualSignal` INSERT → commit → close
    - 실패 시 에러 로그만, 전략 경로에 예외 전파 금지
- **중요**: 이 모듈은 `TradeSignalData`를 import하지 않는다. `OrderManager`/`SignalGenerator` import 금지. 린트·코드리뷰 체크 포인트.

**Step 3: 전략 수정 (post-decision 측면 기록)**
- `momentum_breakout.py`:
  - 클래스 초기화에 optional 의존성 주입:
    - `__init__(self, redis_client=None, session_factory=None)` — 기본값 None 유지 (기존 테스트 회귀 방지)
  - `_reject()` 내부 **반환 직전**에:
    - `record_stage(self.redis_client, stage, _now_kst())` await
    - `if stage == "prev_close_time_guard" and time(13, 0) <= _now_kst().time() < time(14, 0):` → `record_virtual_signal(self.session_factory, snapshot, detail)` await
    - 두 호출 모두 `record_*` 내부에서 예외를 흡수하므로 `_reject`는 항상 `RejectedSignal` 반환
  - 성공 경로: `TradeSignalData` 반환 직전에 `record_stage(..., stage="pass")` 추가
- `backend/main.py` 수정:
  - `MomentumBreakoutStrategy()` 생성 시 `redis_client=redis_client, session_factory=session_factory` 주입
  - (현재 `main.py` line 38 근처 `MomentumBreakoutStrategy` import 확인 후 생성 지점 수정)

**검증:**
- `docker compose exec backend pytest tests/modules/trading/strategies/ -v` → 기존 + 신규 모두 PASS
- 수동 검증 (Redis TTL 설정):
  ```bash
  docker compose exec backend pytest tests/modules/trading/strategies/test_momentum_breakout_metrics.py -v -s
  ```
- 예상: 가상 신호 기록 케이스에서 `virtual_signals` 테이블 1건 증가, `signals`/`orders` 테이블 변화 0건 (명시적 count assert)

**Step 4: 커밋**
```
git add backend/modules/trading/strategies/momentum_breakout.py backend/modules/trading/strategies/_metrics.py backend/main.py backend/tests/modules/trading/strategies/test_momentum_breakout_metrics.py
git commit -m "feat(phase8.5-sprint1): task4 — 전략 stage 카운터 + 가상 신호 로깅 (주문 미발생)"
```

**완료 기준:**
- ✅ 가상 신호 기록되는 동안 `RejectedSignal` 타입 반환 유지
- ✅ `signals` / `orders` 테이블 INSERT 0건 (테스트에서 count assert)
- ✅ 13:00 이전 / 14:00 이후엔 virtual_signals 기록 안 됨
- ✅ stage 카운터 key 포맷 Task 2 규약과 일치

---

## Task 5: 16:00 일별 집계 배치

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (신규 APScheduler job + 집계 메서드)
- Test: `backend/tests/modules/collector/test_scheduler_metrics_rollup.py` (신규)

**Step 1: 테스트 작성**
- Redis에 가짜 카운터 5~10개 세팅 후 집계 메서드 호출 → DB에 정확히 이관되는지 검증:
  1. `screening_metrics_daily` INSERT 건수 = 히스토그램 bucket 종류 수
  2. `strategy_metrics_daily` INSERT 건수 = stage × hour_min 조합 수
  3. 재실행 시 UniqueConstraint로 upsert (ON CONFLICT ... DO UPDATE `count = EXCLUDED.count`)
  4. 집계 후 Redis 원본 키 TTL 유지 (삭제 안 함 — 7일 후 자동 만료)
- 검증: `docker compose exec backend pytest tests/modules/collector/test_scheduler_metrics_rollup.py -v` → FAIL

**Step 2: 집계 메서드 구현**
- `scheduler.py`에 추가:
  - `async def _rollup_daily_metrics(self) -> None`
    - KST 오늘 날짜 결정 (`datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()`)
    - `self._redis.scan_keys(f"metrics:secondary:score:{date}:*")` 로 score 키 전수 조회 → 각 key `get` → bucket 추출 → INSERT ... ON CONFLICT DO UPDATE (postgresql `insert().on_conflict_do_update`)
    - `self._redis.scan_keys(f"metrics:strategy:stage:{date}:*")` 로 stage 키 전수 조회 → stage, hour_min 파싱 → UPSERT
    - 전체 트랜잭션 1개 세션으로 처리
    - 시작/완료/실패 로그 기록
  - `start()` 내 신규 `add_job`:
    ```
    self._scheduler.add_job(
        self._rollup_daily_metrics,
        CronTrigger(hour=16, minute=0, timezone=tz),
        id="metrics_rollup",
        replace_existing=True,
    )
    ```
    - 기존 16:00 포털 보조 수집 (`_portal_supplementary_collect`, scheduler.py line 353~)과 **다른 job id**로 공존하도록 배치 (둘 다 16:00이지만 APScheduler가 순차 실행 — 충돌 없음).
    - 만약 실제 순차 처리 순서를 보장하려면 `minute=1`로 1분 오프셋 권장. **확정: `minute=5`로 설정** (포털 수집 완료 후 안전하게 집계).

**검증:**
- `docker compose exec backend pytest tests/modules/collector/test_scheduler_metrics_rollup.py -v` → PASS
- `docker compose exec backend pytest tests/modules/collector/ -v` → 기존 회귀 없음
- 수동 트리거 (개발 중): scheduler에 테스트용 `trigger_metrics_rollup()` 퍼블릭 메서드 추가 검토 (선택, Sprint 1에서는 테스트로 충분)

**Step 3: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/modules/collector/test_scheduler_metrics_rollup.py
git commit -m "feat(phase8.5-sprint1): task5 — 16:05 메트릭 일별 집계 배치"
```

**완료 기준:**
- ✅ 신규 테스트 PASS
- ✅ UniqueConstraint upsert 정상 동작 (재실행 시 중복 INSERT 없음)
- ✅ 기존 scheduler 테스트 회귀 없음
- ✅ `_rollup_daily_metrics` 실패 시 예외 전파 없이 로깅만 (스케줄러 중단 방지)

---

## Task 6: metrics API 라우터

**Files:**
- Create: `backend/api/routes/metrics.py`
- Modify: `backend/main.py` (router include)
- Test: `backend/tests/api/test_metrics_routes.py`

**Step 1: 테스트 작성 (TestClient)**
- `GET /api/v1/metrics/score-histogram?days=7` → 오늘 Redis + 지난 7일 DB 합산, 각 bucket `{bucket, count_today, count_7d_avg}` 배열
- `GET /api/v1/metrics/stage-heatmap?date=today` → `{stage, hour_min, count}` 배열 (오늘은 Redis, 과거는 DB)
- `GET /api/v1/metrics/top-rejects?limit=5` → 최근 `_reject` 이벤트 5건 (Redis LIST `metrics:strategy:top_reject` — Task 4에서 `LPUSH ... LTRIM 0 4`로 유지; Task 4 구현 범위에 추가 필요)
- `GET /api/v1/metrics/virtual-signals?days=7` → 최근 7일 `virtual_signals` 테이블 조회
- 인증: `get_current_user` 의존성 적용 (다른 라우터 패턴 따름)
- 검증: `docker compose exec backend pytest tests/api/test_metrics_routes.py -v` → FAIL

**Step 2: 라우터 구현**
- `backend/api/routes/metrics.py`:
  - `router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"], dependencies=[Depends(get_current_user)])`
  - 응답 Pydantic 스키마 정의
  - 4개 엔드포인트 구현 (Redis + DB 병합 로직)
- `main.py`:
  - `from api.routes.metrics import router as metrics_router`
  - `app.include_router(metrics_router)`
- **Task 4 보강**: `_metrics.py`의 `record_stage`에서 `stage != "pass"` 경우 `redis_client.lpush("metrics:strategy:top_reject", json.dumps({code, stage, breakout_ref, current_price, detail}))` + `ltrim 0 4` 호출 추가 (Task 4 커밋 후 추가 커밋 가능). → 이 보강은 **Task 6의 Step 2 내에서 함께 수정하고 커밋**한다.

**검증:**
- `docker compose exec backend pytest tests/api/test_metrics_routes.py -v` → PASS
- curl 수동 검증:
  ```bash
  TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | jq -r .access_token)
  curl -s http://localhost:8000/api/v1/metrics/score-histogram -H "Authorization: Bearer $TOKEN" | jq .
  curl -s http://localhost:8000/api/v1/metrics/stage-heatmap -H "Authorization: Bearer $TOKEN" | jq .
  curl -s http://localhost:8000/api/v1/metrics/top-rejects -H "Authorization: Bearer $TOKEN" | jq .
  curl -s http://localhost:8000/api/v1/metrics/virtual-signals -H "Authorization: Bearer $TOKEN" | jq .
  ```
- 예상: 각 4개 엔드포인트 200 OK, 스키마 정상

**Step 3: 커밋**
```
git add backend/api/routes/metrics.py backend/main.py backend/modules/trading/strategies/_metrics.py backend/tests/api/test_metrics_routes.py
git commit -m "feat(phase8.5-sprint1): task6 — metrics API 4종 + top_reject 리스트"
```

**완료 기준:**
- ✅ 4개 엔드포인트 200 OK
- ✅ 인증 미첨부 시 401
- ✅ 빈 DB/Redis 상태에서도 200 + 빈 배열 (404 금지)

---

## Task 7: 프론트엔드 "신호 진단 (Phase 8.5)" 섹션

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(dashboard)/diagnostics/page.tsx`
- Create: `frontend/components/diagnostics/score-histogram-card.tsx`
- Create: `frontend/components/diagnostics/stage-heatmap-card.tsx`
- Create: `frontend/components/diagnostics/top-rejects-card.tsx`
- Create: `frontend/components/diagnostics/fallback-stats-card.tsx` (Sprint 1: placeholder만)
- Modify: `frontend/lib/api.ts` (metrics 4종 fetch 함수 추가)
- Modify: `frontend/components/layout/sidebar.tsx` 또는 기존 네비게이션 (메뉴 항목 "신호 진단" 추가 — 파일명은 기존 구조 확인 후 결정)

**Step 1: API 클라이언트**
- `lib/api.ts` 에 4개 함수 추가: `getScoreHistogram`, `getStageHeatmap`, `getTopRejects`, `getVirtualSignals`

**Step 2: 카드 컴포넌트**
- **카드 1 (score-histogram-card)**: 세로 막대 차트
  - 10점 bucket (0-10 ~ 90-100) + `>=75` 별도 표시
  - 오늘 카운트 + 7일 평균 오버레이 (recharts 또는 기존 차트 라이브러리 재사용; 없으면 단순 div bar)
  - 한국 색상 관례: 고득점(>=75) 빨강, 저득점 회색
- **카드 2 (stage-heatmap-card)**: x=10분 bucket, y=stage
  - 각 셀 색 농도 = 카운트 로그 스케일
  - stage 목록: `pass`, `breakout`, `min_volume_floor`, `prev_close_time_guard`, `volume_threshold`, `trade_strength`, `atr_filter`, `confidence`, `prev_volume_zero`
- **카드 3 (top-rejects-card)**: 리스트 (종목코드/stage/이격률 `(current_price - breakout_ref) / breakout_ref`)
  - 5초 폴링 (`usePolling` 재사용)
- **카드 4 (fallback-stats-card)**: 빈 카드 + "Coming Soon (Phase 8.5 Sprint 2)" 중앙 표시, opacity 50%

**Step 3: 페이지 조립**
- `/diagnostics` 라우트, 4카드 그리드 레이아웃 (2x2 또는 1x4 반응형)
- 기존 dashboard page 스타일 준수 (dark mode, mono font, border 등)

**Step 4: 사이드바 메뉴 추가**
- 기존 네비게이션에 "신호 진단" 링크 추가 (아이콘: 임의 선택, emoji 금지)

**검증:**
- `cd frontend && npx tsc --noEmit` → 에러 없음
- `docker compose up frontend -d` 후 http://localhost:3000/diagnostics 접속 → 4카드 표시 확인
- Playwright 스냅샷 (Task 8에서 종합 수행)

**Step 5: 커밋**
```
git add frontend/app/\(dashboard\)/diagnostics/ frontend/components/diagnostics/ frontend/lib/api.ts frontend/components/layout/
git commit -m "feat(phase8.5-sprint1): task7 — 신호 진단 대시보드 4카드"
```

**완료 기준:**
- ✅ tsc 에러 없음
- ✅ /diagnostics 페이지 렌더링 (빈 데이터 상태에서도 크래시 없음)
- ✅ 카드 4는 "Coming Soon" 표시만 (실제 데이터 바인딩 금지)
- ✅ 사이드바 메뉴 추가

---

## Task 8: E2E 통합 검증

**skill:** `verification-before-completion`

**Files:**
- Create: `docs/phase/phase8.5/sprint1/test-plan.md`
- Create: `docs/phase/phase8.5/sprint1/test-result.md`

**Step 1: 테스트 계획 문서화**
- `test-plan.md`: 아래 검증 항목을 체크리스트로 명시 (GFM 대신 이모지)

**Step 2: 자동 검증 실행**
- `docker compose exec backend pytest -v` → 전체 PASS
- `cd frontend && npx tsc --noEmit` → 에러 없음
- API curl 수동 (Task 6과 동일) → 4 endpoint 200 OK
- Playwright:
  - `/login` → 로그인
  - `/diagnostics` → 4카드 snapshot 저장 → `docs/phase/phase8.5/sprint1/screenshot-diagnostics.png`
  - 기존 대시보드 페이지 회귀 확인

**Step 3: 가상 신호 격리 검증 (필수)**
- `signals` 테이블 기준 count 측정 → 전략 `_reject` 경로 타격 시뮬레이션 스크립트 실행 → 재측정
- 예상: `signals` / `orders` 테이블 count 불변, `virtual_signals` count 증가
- 스크립트 예:
  ```
  docker compose exec backend python -c "
  import asyncio, datetime
  from zoneinfo import ZoneInfo
  # monkeypatch _now_kst → 13:30, prev_close tier snapshot 생성 후 전략 호출
  # snapshot/리턴/DB 비교 (상세는 테스트 picker 참고)
  "
  ```
- pytest 케이스로 대체 가능: `test_momentum_breakout_metrics.py`의 "주문 미발생" assert가 근거

**Step 4: 관측성 실데이터 1시간 스모크 (권장)**
- 배포 당일 14:00 이후 1시간 관찰 → 스케줄러 16:05 집계 수동 트리거 또는 다음날 16:05 자연 트리거 대기
- DB 조회:
  ```bash
  docker compose exec db psql -U postgres -d stockbot -c "SELECT * FROM screening_metrics_daily ORDER BY metric_date DESC LIMIT 20;"
  docker compose exec db psql -U postgres -d stockbot -c "SELECT * FROM strategy_metrics_daily ORDER BY metric_date DESC LIMIT 20;"
  docker compose exec db psql -U postgres -d stockbot -c "SELECT * FROM virtual_signals ORDER BY observed_at DESC LIMIT 20;"
  ```

**Step 5: 결과 기록 + 커밋**
- `test-result.md` 작성 (검증 매트릭스 ✅/⬜ 표시)
- 스크린샷 포함
```
git add docs/phase/phase8.5/sprint1/test-plan.md docs/phase/phase8.5/sprint1/test-result.md docs/phase/phase8.5/sprint1/screenshot-*.png
git commit -m "test(phase8.5-sprint1): task8 — E2E 통합 검증 + 가상 신호 격리 확증"
```

**완료 기준:**
- ✅ pytest 전체 PASS (기존 + 신규)
- ✅ tsc 에러 없음
- ✅ 4 API 200 OK
- ✅ /diagnostics 페이지 렌더링 + 스크린샷
- ✅ 가상 신호 1건 이상 기록되는 시나리오에서 `signals`/`orders` 테이블 count 불변 (명시적 assert)

---

## 최종 검증 계획 (dev-process.md §5 Sprint 컬럼 준수)

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS (신규 ~20 cases 추가) |
| TypeScript 타입체크 | `cd frontend && npx tsc --noEmit` | 에러 없음 |
| API curl (변경분) | `/api/v1/metrics/*` 4종 | 200 OK |
| 데모 모드 API | 기존 테스트 스크립트 재실행 | 회귀 없음 |
| Playwright UI (변경분) | /diagnostics 접속 + 4카드 렌더 | 스크린샷 저장 |
| Alembic 마이그레이션 | `docker compose exec backend alembic upgrade head` | head 반영 |
| 가상 신호 격리 | pytest `test_momentum_breakout_metrics.py` | signals 테이블 count 불변 assert PASS |
| Redis counter TTL | 수동 `TTL metrics:secondary:score:*` | ≤ 604800초 (7일) |
| 스케줄러 16:05 job 등록 | `python -c "from modules.collector.scheduler import ..."` | job_id `metrics_rollup` 존재 |

---

## 리스크 및 완화

- ⚠️ **Task 4 가상 신호 경로가 실수로 TradeSignalData를 생성**: `_metrics.py`에서 `TradeSignalData` import를 물리적으로 금지 + Task 8에서 `signals`/`orders` count assert 로 방어.
- ⚠️ **Redis scan 비용**: 일별 집계는 16:05에 1회만, 최대 ~500 keys → 무시 가능.
- ⚠️ **16:00 포털 수집과 16:05 집계 job 충돌**: 5분 오프셋 + 서로 독립 테이블.
- ⚠️ **기존 테스트 회귀**: `MomentumBreakoutStrategy()` 생성자에 optional 인자 추가했으므로 기존 테스트 변경 불필요. 반드시 `docker compose exec backend pytest tests/modules/trading/ -v` 로 회귀 확인.

---

## 사용자 다음 단계

1. 이 문서 검토 후 수정 의견 전달, 또는
2. `/sprint-dev 8.5-1` 로 sprint-dev 호출하여 구현 착수
