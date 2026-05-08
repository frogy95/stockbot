# Sprint 3: `volume_surge` tier 신설 + 시간 필터 본 가드 (Phase 8.6)

**Goal:** 단타 1순위 패턴(거래량 급증)을 4번째 진입 tier로 도입하고, Sprint 2의 임시 시간가드(`TEMP_TIME_GUARD_SPRINT2`)를 본 가드(시간대 분기 + 점심 floor 0.7 + 14:30+ 신규 진입 금지)로 승격한다. 동시에 Sprint 2 잔존 부채(scheduler 잡 검증, ATR_COVERAGE_GAP_MAX 원복, R3 활성화)를 정리하고, 일일 신호 우선순위 큐로 병렬 OR 폭증을 방지한다.

**Architecture:**
- `volume_surge` tier는 기존 `MomentumBreakoutStrategy.generate_signal()` 본 흐름과 분리된 **신규 전략 클래스 `VolumeSurgeStrategy`** (`backend/modules/trading/strategies/volume_surge.py`)로 구현. RealtimeScreener 결과 dict + Redis 호가창(`realtime:{code}:orderbook`) + 5분봉 거래량(`vol5m:{code}:{date}:{slot}`)을 입력으로 받는다.
- 진입 조건: `vol_5m / mean(vol_5m, last_4_slots) ≥ 5.0` AND `total_bid_volume / total_ask_volume ≥ 2.0` AND `current_price ≥ prev_close × 1.005` AND `09:30 ≤ now < 14:00`. 모든 조건 충족 시 신호 발행 (기본 `VOLUME_SURGE_DRY_RUN=true` — DB 기록 + 텔레그램 dry_run 알림만, 실제 주문 미진입).
- 시간대 본 가드는 신규 모듈 `backend/modules/trading/strategies/_time_filter.py`로 분리. `momentum_breakout.py`/`volume_surge.py` 양쪽이 `should_block_entry(now_kst, tier) -> tuple[bool, str]`를 호출. Sprint 2의 `TEMP_TIME_GUARD_SPRINT2` 코드 블록(line 589~602)은 본 가드 호출로 교체 후 env 제거.
- 신호 우선순위 큐: 동일 틱에서 다수 tier 동시 매칭 시 `volume_surge > prev_high > gap_open > prev_close` 순으로 단일 신호만 발행 (일일 신호 한도 10건 보호).
- 모든 신규 동작은 env 토글로 1줄 원복 (`VOLUME_SURGE_ENABLED`, `VOLUME_SURGE_DRY_RUN`, `TIME_FILTER_ENABLED`, `SIGNAL_PRIORITY_QUEUE_ENABLED`). `volume_surge`는 dry_run 기본값 + LIVE 토글 게이트(Sprint 4 G-Bt1·G-Bt2·G-Bt3) 미충족 시 dry_run 강제 유지.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Redis (asyncio), APScheduler, Next.js 16 (shadcn/ui), pytest-asyncio.

**Sprint 기간:** 2026-05-08 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 8.6 Sprint 2 (93 PASS, PR #184, 2026-04-29 머지) — 5/7 1거래일 관찰 CONDITIONAL GO 판정 (KOSPI200 sync 226종 + ATR ceil 0.066963 + safe_mode 미발동 + R1 미발동), 5/8 G2/G3 정식 측정 후 GO 확정 게이트
**브랜치명:** `phase8.6-sprint3`

---

## 착수 게이트 (Sprint 2 종료 후 Sprint 3 시작 전 충족 필수)

다음 항목이 모두 ✅일 때만 Task 1 착수 가능. 미충족 시 사용자에게 보고 후 대기:

- ✅ Sprint 2 PR #184 develop 머지 + 프로덕션 배포 완료
- ✅ Sprint 2 5/7 CONDITIONAL GO 판정 (`.claude/agent-memory/phase8-6-sprint2-observation-check/observation_2026-05-07_final_judgment.md`)
- ⬜ **5/8 장마감 후 GO 확정** (G2 신호 ≥1건 발생 OR 정식 G3 측정값 ≤0.15) — Task 1 착수 전 필수 확인
- ⬜ ATR sample_n ≥ 200 안정적 유지 2영업일 (5/7, 5/8) — Task 6의 `ATR_COVERAGE_GAP_MAX` 원복 게이트
- ⬜ portal_supplement(16:00) / metrics_rollup(16:05) 잡 키 적재 확인 — Task 6의 scheduler 점검 게이트

---

## 제외 범위

- ❌ **Walk-forward 60일 백테스트** — Sprint 4
- ❌ **시뮬-실측 KS / 카이제곱 검정** — Sprint 4 (Sprint 2의 절대차 메트릭만 유지)
- ❌ **LIVE 토글 게이트(G-Bt1·G-Bt2·G-Bt3) 자동 평가 잡** — Sprint 4
- ❌ **`vi_resume` tier 신설** (단타 3순위) — Phase 10.1
- ❌ **테마 모멘텀 가중치 (`theme_momentum`)** — Phase 10.1
- ❌ **피라미딩 / 2차 스크리닝 절대점수↔백분위 하이브리드** — Phase 10.1
- ❌ **Phase 7.0 LIVE 파라미터 변경** (코드 잠금 유지: `max_position=2`, `position_size=5%`, `daily_max_loss=-2%`, `emergency_stop=-3%`)
- ❌ **호가창(5호가 잔량) 수집 인프라 신규 구축** — 이미 Phase 6 KIS WS + `parse_orderbook()` 구현 완료, Redis `realtime:{code}:orderbook` 키 사용 (재사용 only)
- ❌ **5분봉 vol5m 인프라 신규 구축** — Phase 6.1 `VolumeAggregator` 재사용 (`vol5m:{code}:{date}:{slot}` 키)
- ❌ **`VOLUME_SURGE_DRY_RUN=false` LIVE 전환** — Sprint 4 G-Bt1~3 통과 후 Phase 8.7에서 별도 결정

---

## 신규 환경변수 (deploy.md 수동 검증 항목)

Sprint 3에서 추가/제거되는 Railway 환경변수 (총 추가 7종, 제거 1종):

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `VOLUME_SURGE_ENABLED` | `true` | volume_surge tier 활성화. `false` 시 신호 발행 차단 (Kill-switch) |
| `VOLUME_SURGE_DRY_RUN` | `true` | dry_run 모드 (DB 기록 + 알림만, 실제 주문 미진입). Sprint 4 G-Bt1~3 통과 후에만 false |
| `VOLUME_SURGE_VOL_RATIO` | `5.0` | 5분봉 거래량 / 직전 4봉 평균 비율 임계 |
| `VOLUME_SURGE_BID_ASK_RATIO` | `2.0` | 호가창 매수/매도 잔량 비율 임계 |
| `VOLUME_SURGE_PRICE_THRESHOLD` | `0.005` | 전일 종가 대비 가격 상승률 임계 (+0.5%) |
| `VOLUME_SURGE_POSITION_SIZE` | `0.30` | LIVE 진입 시 포지션 크기 (반의 60%, dry_run 단계에서는 미사용 — 메타데이터만 기록) |
| `TIME_FILTER_ENABLED` | `true` | 시간대 본 가드 활성화. `false` 시 Sprint 2 동작 (TEMP_TIME_GUARD_SPRINT2 제거됨) |
| `SIGNAL_PRIORITY_QUEUE_ENABLED` | `true` | 동일 틱 다수 tier 매칭 시 우선순위 큐 적용 |
| `AUTO_ROLLBACK_R3_ENABLED` | `true` | R3(tier 다양성 1종 5거래일 연속) 활성화 — Sprint 1에서 false였던 것을 true로 변경 |
| ~~`TEMP_TIME_GUARD_SPRINT2`~~ | — | **제거** — `TIME_FILTER_ENABLED`로 대체 (코드에서 `settings.TEMP_TIME_GUARD_SPRINT2` 참조 삭제) |
| ~~`ATR_COVERAGE_GAP_MAX`~~ | `30` (원복) | Sprint 2 hotfix에서 200으로 임시 상향, 5/7~5/8 sample_n ≥200 안정 확인 후 30으로 원복 |

**deploy.md 수동 검증 추가 항목** (sprint-close 시 기록):
- `Railway 환경변수 추가 확인: VOLUME_SURGE_ENABLED, VOLUME_SURGE_DRY_RUN, VOLUME_SURGE_VOL_RATIO, VOLUME_SURGE_BID_ASK_RATIO, VOLUME_SURGE_PRICE_THRESHOLD, VOLUME_SURGE_POSITION_SIZE, TIME_FILTER_ENABLED, SIGNAL_PRIORITY_QUEUE_ENABLED`
- `Railway 환경변수 변경 확인: AUTO_ROLLBACK_R3_ENABLED true로 변경, ATR_COVERAGE_GAP_MAX 30으로 원복`
- `Railway 환경변수 제거 확인: TEMP_TIME_GUARD_SPRINT2 (코드 삭제됨)`
- `호가창 수집 가동 확인: Redis SCAN realtime:*:orderbook 결과 ≥10종 + TTL >0`
- `5분봉 거래량 가동 확인: Redis SCAN vol5m:*:$(date +%Y%m%d):* 결과 ≥10종`
- `dry_run 동작 확인: signals 테이블에서 tier="volume_surge" + dry_run=true 조회 시 1건 이상 (Paper 1거래일 후)`

---

## 실행 플랜

### Phase 1 (순차 — 인프라 / config / 시간 필터 모듈 선행)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | env 8종 추가/변경/제거 + `_time_filter.py` 모듈 + `TEMP_TIME_GUARD_SPRINT2` 호출부 교체 | 백엔드 | — |

### Phase 2 (순차 — Task 2 → Task 3 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | `VolumeSurgeStrategy` 신규 클래스 + 호가창/vol5m Redis 조회 + dry_run 모드 + signals 메타데이터 (`tier="volume_surge"`, `dry_run=true`) | 백엔드 | `feature-dev:feature-dev` |
| Task 3 | TradingEngine 통합 — RealtimeScreener 후 momentum_breakout과 volume_surge 병행 평가 + 우선순위 큐 + 일일 한도 10건 보호 회귀 테스트 | 백엔드 | `feature-dev:feature-dev` |

### Phase 3 (병렬 가능 — 백엔드/프론트 분리)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | Sprint 2 잔존 부채 정리 — R3 활성화 + scheduler 잡 키 점검 + ATR_COVERAGE_GAP_MAX 원복 | 백엔드 | — |
| Task 5 | volume-surge-card UI + time-filter-card UI (시간대별 차단 횟수, dry_run 신호 카운트) | 프론트엔드 | `frontend-design` |

### Phase 4 (순차 — 통합 검증 + 런북)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | 통합 회귀 + Kill-switch 런북 + deploy.md 환경변수 등록 + Paper 1거래일 관찰 항목 기록 | 전체 | `verification-before-completion` |

> **팀 실행**: Phase 3에서 Task 4(백엔드 잔존 부채)와 Task 5(프론트 UI)는 파일 소유권 무겹침으로 병렬 가능. "Phase 3을 팀으로 실행해줘" 요청 가능.

---

## Task 상세

### Task 1: env 8종 추가/변경/제거 + 시간 필터 모듈 + TEMP_TIME_GUARD_SPRINT2 교체

**Files:**
- Modify: `backend/core/config.py` (env 8종 추가, `AUTO_ROLLBACK_R3_ENABLED` 기본값 변경, `TEMP_TIME_GUARD_SPRINT2` 필드 제거, `ATR_COVERAGE_GAP_MAX` 기본값 30 원복)
- Modify: `backend/.env.example` (동일 반영 + 한글 주석)
- Create: `backend/modules/trading/strategies/_time_filter.py` (시간대 본 가드)
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (line 588~602 `TEMP_TIME_GUARD_SPRINT2` 블록 → `_time_filter.should_block_entry()` 호출로 교체. `TEMP_GUARD_MORNING_END`, `TEMP_GUARD_AFTERNOON_START` 상수 제거)
- Test: `backend/tests/strategies/test_time_filter.py` (신규)

**Step 1: 테스트 작성**
- `tests/strategies/test_time_filter.py` 검증 케이스:
  - `should_block_entry(09:00, "gap_open")` → `(False, "gap_open_morning_exception")` (gap_open은 09:00~09:05 예외 허용)
  - `should_block_entry(09:06, "gap_open")` → `(True, "morning_lockout")` (09:05~09:10은 gap_open도 차단)
  - `should_block_entry(09:06, "prev_high")` → `(True, "morning_lockout")` (09:00~09:10 신규 진입 차단)
  - `should_block_entry(09:11, "prev_high")` → `(False, "")`
  - `should_block_entry(11:30~13:00, "prev_close")` → `(False, "")` 단 후술 floor 분기에서 0.7 적용 (Task 1 범위 외 — momentum_breakout._resolve_min_volume_floor에서 별도 처리, 본 Task에서는 함수 시그니처만 정의)
  - `should_block_entry(14:30, "volume_surge")` → `(True, "afternoon_lockout")` (14:30+ 신규 진입 금지)
  - `should_block_entry(14:29, "volume_surge")` → `(False, "")`
  - `TIME_FILTER_ENABLED=false` → 모든 시간대에서 `(False, "")` 반환
- 검증: `docker compose exec backend pytest tests/strategies/test_time_filter.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: env 변경**
- `core/config.py` Settings 클래스:
  - 추가: `VOLUME_SURGE_ENABLED: bool = Field(default=True)`, `VOLUME_SURGE_DRY_RUN: bool = Field(default=True)`, `VOLUME_SURGE_VOL_RATIO: float = Field(default=5.0, gt=0)`, `VOLUME_SURGE_BID_ASK_RATIO: float = Field(default=2.0, gt=0)`, `VOLUME_SURGE_PRICE_THRESHOLD: float = Field(default=0.005, ge=0)`, `VOLUME_SURGE_POSITION_SIZE: float = Field(default=0.30, gt=0, le=1.0)`, `TIME_FILTER_ENABLED: bool = Field(default=True)`, `SIGNAL_PRIORITY_QUEUE_ENABLED: bool = Field(default=True)`
  - 변경: `AUTO_ROLLBACK_R3_ENABLED` 기본값 `False` → `True` (Sprint 1에서 보류된 R3 활성화)
  - 변경: `ATR_COVERAGE_GAP_MAX` 기본값 200 → 30 (Sprint 2 hotfix 원복)
  - 제거: `TEMP_TIME_GUARD_SPRINT2` 필드 + Phase 8.6 Sprint 2 v2 주석
- `.env.example` 동일 반영
- 검증: `docker compose exec backend python -c "from core.config import settings; print(settings.VOLUME_SURGE_ENABLED, settings.TIME_FILTER_ENABLED, settings.AUTO_ROLLBACK_R3_ENABLED, settings.ATR_COVERAGE_GAP_MAX)"`
- 예상: `True True True 30`

**Step 3: 시간 필터 모듈 구현**
- `backend/modules/trading/strategies/_time_filter.py` 신규 생성
- `should_block_entry(now_kst: datetime, tier: str) -> tuple[bool, str]` 시그니처
- 분기:
  - `settings.TIME_FILTER_ENABLED is False` → `(False, "")`
  - `09:00 ≤ time < 09:05` AND `tier == "gap_open"` → `(False, "gap_open_morning_exception")`
  - `09:00 ≤ time < 09:10` → `(True, "morning_lockout")`
  - `time ≥ 14:30` → `(True, "afternoon_lockout")`
  - 그 외 → `(False, "")`
- 점심 floor 0.7 분기는 `momentum_breakout._resolve_min_volume_floor()`에서 별도 처리 (별도 함수 추가: `_lunch_floor_adjustment(now_kst, tier) -> float | None`, 11:30~13:00 KST에서 prev_close tier에 0.7 반환)

**Step 4: TEMP_TIME_GUARD_SPRINT2 호출부 교체**
- `momentum_breakout.py`:
  - line 22~30 import에 `from backend.modules.trading.strategies._time_filter import should_block_entry, lunch_floor_adjustment` 추가 (실제 import 경로는 기존 패턴 확인 필요)
  - line 55~56의 `TEMP_GUARD_MORNING_END = time(9, 10)`, `TEMP_GUARD_AFTERNOON_START = time(14, 30)` 상수 제거
  - line 588~602의 `if settings.TEMP_TIME_GUARD_SPRINT2:` 블록을 다음으로 교체:
    ```python
    blocked, reason = should_block_entry(now_kst, breakout_tier)
    if blocked:
        return await self._reject(snapshot, "time_filter", {"now": now_kst.time().isoformat(), "reason": reason, "breakout_tier": breakout_tier})
    ```
  - 단, `breakout_tier`는 이 시점 이후 `_resolve_tier()` 호출 결과로 결정되므로 호출 순서 점검 필요. 현재 line 612에서 `_resolve_tier` 호출 → `should_block_entry`는 line 612 이후로 이동
- `_resolve_min_volume_floor()` 본문 마지막의 09:00~11:00 슬라이딩 분기 직후에 점심 floor 적용 추가:
  ```python
  lunch_adj = lunch_floor_adjustment(effective_now, tier)
  if lunch_adj is not None:
      result = max(result, lunch_adj)
  ```
- 검증: `docker compose exec backend pytest tests/strategies/test_time_filter.py tests/strategies/test_momentum_breakout.py -v`
- 예상: PASS (test_momentum_breakout.py 회귀 0건)

**Step 5: 커밋**
```
git add backend/core/config.py backend/.env.example backend/modules/trading/strategies/_time_filter.py backend/modules/trading/strategies/momentum_breakout.py backend/tests/strategies/test_time_filter.py
git commit -m "feat(phase8.6-sprint3): task1 — env 8종 + 시간 필터 본 가드 + TEMP_TIME_GUARD_SPRINT2 제거"
```

**완료 기준:**
- ⬜ pytest `test_time_filter.py` 8 케이스 PASS
- ⬜ 기존 `test_momentum_breakout.py` 회귀 0건 (TEMP_TIME_GUARD_SPRINT2 제거 후)
- ⬜ `.env.example`에 신규 8종 + 제거 1종 + 변경 2종 반영
- ⬜ `settings.TEMP_TIME_GUARD_SPRINT2` 참조 grep 결과 0건 (코드/테스트 전체)

---

### Task 2: `VolumeSurgeStrategy` 신규 클래스 + dry_run 모드

**skill:** `feature-dev:feature-dev`

**Files:**
- Create: `backend/modules/trading/strategies/volume_surge.py`
- Modify: `backend/modules/trading/strategies/__init__.py` (export 추가)
- Modify: `backend/models/trade_signals.py` (또는 해당 파일) — `dry_run BOOLEAN NULL DEFAULT FALSE` 컬럼 추가
- Create: `backend/alembic/versions/{rev}_add_signals_dry_run.py` (Alembic 마이그레이션)
- Test: `backend/tests/strategies/test_volume_surge.py`

**Step 1: 테스트 작성**
- `tests/strategies/test_volume_surge.py` 검증 케이스 (12+):
  - **Happy path**: vol_5m=10000, mean(last_4)=1500 (×6.67 ≥ 5.0), bid=200, ask=80 (2.5 ≥ 2.0), price=10550, prev_close=10500 (1.0048 ≥ 1.005 — 가까스로 OK), 09:35 KST → 신호 발행 (dry_run=True 메타데이터)
  - vol_ratio < 5.0 → reject "vol_surge_ratio"
  - bid_ask_ratio < 2.0 → reject "vol_surge_orderbook"
  - price < prev_close × 1.005 → reject "vol_surge_price"
  - 09:25 (활성 시간 미진입) → reject "vol_surge_time"
  - 14:01 (활성 시간 종료) → reject "vol_surge_time"
  - 호가창 Redis 키 부재 → reject "vol_surge_orderbook_missing"
  - vol5m Redis 키 부재 (모든 슬롯) → reject "vol_surge_vol5m_missing"
  - 직전 4봉 평균 vol5m 0 → ZeroDivisionError 방지, reject "vol_surge_vol5m_zero"
  - `VOLUME_SURGE_ENABLED=False` → 항상 reject "vol_surge_disabled"
  - `VOLUME_SURGE_DRY_RUN=True` → 신호 발행 시 `signal.dry_run=True` 메타데이터 + `tier="volume_surge"` (실제 주문 미진입은 Task 3에서 검증)
  - 시간 필터 가드 통합: 14:30 → reject "time_filter" (Task 1 모듈 위임)
- 검증: `docker compose exec backend pytest tests/strategies/test_volume_surge.py -v`
- 예상: FAIL

**Step 2: signals.dry_run 컬럼 + Alembic**
- `signals` 테이블에 `dry_run BOOLEAN NULL DEFAULT FALSE` 컬럼 추가 (모델 + 마이그레이션)
- 기존 데이터: 모두 NULL (= False 동작)
- 검증: `docker compose exec backend alembic upgrade head` 후 `\d signals` 확인

**Step 3: `VolumeSurgeStrategy` 구현**
- `volume_surge.py` 신규 클래스 `VolumeSurgeStrategy`:
  - `__init__(self, redis_client, session_factory, telegram_bot=None)`
  - `async def evaluate(self, candidate: dict, now_kst: datetime) -> dict | None` — `candidate`는 RealtimeScreener 결과 dict (stock_code, current_price, prev_close, ...)
  - 분기 순서:
    1. `settings.VOLUME_SURGE_ENABLED` 체크 → False면 reject
    2. 시간 필터: `should_block_entry(now_kst, "volume_surge")` 호출 (Task 1) — True면 reject
    3. 활성 시간 (09:30 ≤ now < 14:00) 체크 — 외부면 reject
    4. 가격 조건: `current_price ≥ prev_close × 1.005` 체크
    5. Redis `realtime:{code}:orderbook` 조회 (TTL 5초 가정) → JSON 파싱하여 `total_bid_volume`, `total_ask_volume` 추출 → 비율 계산, 임계 미달이면 reject
    6. Redis vol5m 조회: 현재 슬롯 + 직전 4봉 (`vol5m:{code}:{date}:{slot}` 패턴, `calc_5min_slot()` 재사용). 직전 4봉 평균 산출, 비율 임계 미달이면 reject
    7. 모든 통과 시 `{"stock_code": ..., "tier": "volume_surge", "dry_run": settings.VOLUME_SURGE_DRY_RUN, "vol_ratio": ..., "bid_ask_ratio": ..., "price_change": ..., "matched_tiers": ["volume_surge"], "confidence": <0~1>}` 반환
- 호가창 JSON 파싱 — Phase 6 KIS WS `parse_orderbook()` 결과 구조 그대로 사용. 키 부재/TTL 만료 시 reject
- 5분봉 vol5m — `VolumeAggregator.make_redis_key(stock_code, date_str, slot)` 재사용. 키 부재 시 reject
- 검증: `docker compose exec backend pytest tests/strategies/test_volume_surge.py -v`
- 예상: 12+ PASS

**Step 4: 커밋**
```
git add backend/modules/trading/strategies/volume_surge.py backend/modules/trading/strategies/__init__.py backend/models/trade_signals.py backend/alembic/versions/*.py backend/tests/strategies/test_volume_surge.py
git commit -m "feat(phase8.6-sprint3): task2 — VolumeSurgeStrategy + signals.dry_run 컬럼"
```

**완료 기준:**
- ⬜ pytest `test_volume_surge.py` 12+ 케이스 PASS
- ⬜ Alembic 마이그레이션 적용 후 `signals.dry_run` 컬럼 존재
- ⬜ `VOLUME_SURGE_DRY_RUN=true` 신호의 `dry_run=true` 메타데이터 검증
- ⬜ 호가창 Redis 키 / vol5m 키 부재 시 graceful reject (예외 미전파)

---

### Task 3: TradingEngine 통합 + 신호 우선순위 큐

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/trading/engine.py` (RealtimeScreener 결과 → momentum_breakout + volume_surge 병행 평가, 우선순위 큐, 일일 한도 보호)
- Modify: `backend/main.py` (lifespan에서 `VolumeSurgeStrategy` 인스턴스 생성 + engine 주입)
- Test: `backend/tests/trading/test_engine_volume_surge_integration.py` (신규)
- Test: `backend/tests/trading/test_signal_priority_queue.py` (신규)

**Step 1: 테스트 작성**
- `test_engine_volume_surge_integration.py`:
  - momentum_breakout만 매칭 → 단일 신호 발행 (기존 동작 회귀)
  - volume_surge만 매칭 → 단일 신호 발행 (`tier="volume_surge"`, `dry_run=true`)
  - 둘 다 매칭 → `volume_surge` 우선 발행 (다른 tier 메타데이터는 `matched_tiers`에 합쳐짐)
  - `VOLUME_SURGE_DRY_RUN=true` → 신호 발행 + DB 기록 + 텔레그램 dry_run 알림 + **실제 주문 미진입** (OrderExecutor.place_order 호출 0회)
  - `VOLUME_SURGE_DRY_RUN=false` (강제 설정 후 회귀) → 실제 주문 진입 (Sprint 4에서 사용)
- `test_signal_priority_queue.py`:
  - 동일 틱 내 4 tier 모두 매칭 → `volume_surge` 1건만 발행
  - 우선순위 순서: volume_surge > prev_high > gap_open > prev_close
  - `SIGNAL_PRIORITY_QUEUE_ENABLED=false` → 모든 tier 신호 발행 (병렬 OR 원래 동작)
  - 일일 한도 10건 도달 시 신호 차단 (Phase 7.2 한도 회귀 — Sprint 1 G3 회로차단기와 별개)
- 검증: `docker compose exec backend pytest tests/trading/test_engine_volume_surge_integration.py tests/trading/test_signal_priority_queue.py -v`
- 예상: FAIL

**Step 2: engine.py 통합**
- `TradingEngine.process_screening_results()`에서 RealtimeScreener 결과 candidate 순회 시:
  - 기존 `MomentumBreakoutStrategy.generate_signal()` 호출 후 결과 보존
  - `VolumeSurgeStrategy.evaluate()` 추가 호출 후 결과 보존
  - 두 결과 중 매칭된 신호를 우선순위 큐(volume_surge > prev_high > gap_open > prev_close)로 정렬, 1건만 채택
  - dry_run=true 신호: DB 기록 + 텔레그램 dry_run 알림만, OrderExecutor.place_order 호출 스킵
- `SIGNAL_PRIORITY_QUEUE_ENABLED=false`이면 우선순위 큐 미적용 (기존 병렬 OR 동작)
- 일일 신호 한도(Phase 7.2 `daily_trade_count` 10건)는 채택 후 카운트, dry_run 신호는 카운트에서 제외 (LIVE 자금 보호 무관)

**Step 3: main.py 주입**
- `app.state.volume_surge_strategy = VolumeSurgeStrategy(redis_client, session_factory, telegram_bot)`
- `app.state.trading_engine = TradingEngine(..., volume_surge_strategy=app.state.volume_surge_strategy, ...)`

**Step 4: 검증**
- 검증: `docker compose exec backend pytest tests/trading/ -v`
- 예상: 신규 테스트 PASS + 기존 테스트 회귀 0건

**Step 5: 커밋**
```
git add backend/modules/trading/engine.py backend/main.py backend/tests/trading/test_engine_volume_surge_integration.py backend/tests/trading/test_signal_priority_queue.py
git commit -m "feat(phase8.6-sprint3): task3 — TradingEngine volume_surge 통합 + 우선순위 큐"
```

**완료 기준:**
- ⬜ 우선순위 큐 단일 신호 발행 회귀 테스트 PASS
- ⬜ dry_run 신호의 OrderExecutor.place_order 호출 0회 검증
- ⬜ 일일 한도 10건 도달 시 신호 차단 (dry_run 제외) 회귀 테스트 PASS
- ⬜ `SIGNAL_PRIORITY_QUEUE_ENABLED=false` 토글 동작 검증

---

### Task 4: Sprint 2 잔존 부채 정리 — R3 활성화 + scheduler 잡 점검 + ATR_COVERAGE_GAP_MAX 원복

**Files:**
- Modify: `backend/modules/safety/auto_rollback.py` (R3 동작 검증, env 토글 의존)
- Modify: `backend/modules/collector/scheduler.py` (portal_supplement 16:00 / metrics_rollup 16:05 잡의 Redis 키명 추적 + 누락 시 INFO 로그 추가)
- Test: `backend/tests/safety/test_auto_rollback_r3.py` (신규 또는 Sprint 1 테스트 확장)
- Test: `backend/tests/collector/test_scheduler_portal_metrics_jobs.py` (신규 — 잡 등록 + 키 적재 확인)

**Step 1: 테스트 작성**
- `test_auto_rollback_r3.py`:
  - tier 다양성 1종 (예: prev_high만) 5거래일 연속 → R3 발동 → 본 Phase 변경분 비활성화
  - tier 다양성 2종 이상 → R3 미발동
  - `AUTO_ROLLBACK_R3_ENABLED=false` → 항상 미발동
  - 4거래일 연속 후 5일째 다양성 회복 → R3 미발동 (연속 카운터 리셋)
- `test_scheduler_portal_metrics_jobs.py`:
  - `_setup_portal_supplement_job()` 등록 시 `scheduler:last_portal_supplement` 키 적재 확인 (mock Redis)
  - `_setup_metrics_rollup_job()` 등록 시 `scheduler:last_metrics_rollup` 키 적재 확인
  - 두 잡의 cron trigger가 16:00 / 16:05 KST인지 확인
- 검증: `docker compose exec backend pytest tests/safety/test_auto_rollback_r3.py tests/collector/test_scheduler_portal_metrics_jobs.py -v`
- 예상: FAIL

**Step 2: R3 활성화 검증**
- Sprint 1에서 이미 R3 트리거 로직은 구현 완료 (Task 4 R1~R4). `AUTO_ROLLBACK_R3_ENABLED` 기본값을 `True`로 변경(Task 1)한 상태에서 동작만 검증
- 필요 시 `auto_rollback.py`의 R3 분기에서 `AUTO_ROLLBACK_R3_ENABLED` 체크 정확성 확인

**Step 3: scheduler 잡 키명 추적**
- 5/7 16:07 시점에 `scheduler:last_portal_supplement` / `scheduler:last_metrics_rollup` 키가 None이었던 원인 진단:
  - 잡이 등록되지 않았는지 (코드 누락)
  - 잡이 실행됐으나 키 명을 다른 패턴으로 적재하는지 (`scheduler:last_*` 패턴 vs 다른 패턴)
- 진단 후 두 가지 중 하나:
  - (A) 잡 미등록이면 신규 등록
  - (B) 키명 패턴 불일치면 통일
- 어느 쪽이든 INFO 로그 추가하여 다음 거래일 검증 용이하게

**Step 4: ATR_COVERAGE_GAP_MAX 원복**
- Task 1에서 이미 기본값 30으로 원복. 추가 검증: ATR 캘리브레이션 테스트가 30 기준에서도 PASS하는지 회귀

**Step 5: 커밋**
```
git add backend/modules/safety/auto_rollback.py backend/modules/collector/scheduler.py backend/tests/safety/test_auto_rollback_r3.py backend/tests/collector/test_scheduler_portal_metrics_jobs.py
git commit -m "fix(phase8.6-sprint3): task4 — R3 활성화 검증 + portal/metrics 잡 점검 + ATR coverage gap 30 원복"
```

**완료 기준:**
- ⬜ R3 활성화 회귀 테스트 PASS (5거래일 연속 1종 → 발동)
- ⬜ portal_supplement / metrics_rollup 잡 키 적재 확인 (단위 테스트 + Paper 1거래일 16:10 시점 키 존재 확인 — Task 6에서)
- ⬜ ATR sample_n ≥ 200 안정 유지 5거래일 회귀 (실측 데이터 기반)

---

### Task 5: 프론트엔드 — volume-surge-card UI + time-filter-card UI

**skill:** `frontend-design`

**Files:**
- Create: `frontend/components/diagnostics/volume-surge-card.tsx`
- Create: `frontend/components/diagnostics/time-filter-card.tsx`
- Modify: `frontend/app/(dashboard)/diagnostics/page.tsx` (두 카드 추가)
- Modify: `frontend/lib/api.ts` (필요 시 API 호출 추가)
- Create: `backend/api/routes/metrics.py` 내 `GET /api/v1/metrics/volume-surge-stats` (일별 dry_run 신호 카운트 + 7일 이동) 신규 엔드포인트
- Create: `backend/api/routes/metrics.py` 내 `GET /api/v1/metrics/time-filter-stats` (시간대별 차단 횟수 — `time_filter` reject 카운터 집계) 신규 엔드포인트
- Test: `backend/tests/api/test_metrics_volume_surge.py` (신규)
- Test: `backend/tests/api/test_metrics_time_filter.py` (신규)

**Step 1: 백엔드 API 추가**
- `GET /api/v1/metrics/volume-surge-stats`:
  - 응답: `{"date": "2026-05-08", "dry_run_count": 5, "real_count": 0, "ma7_dry_run": 4.2}` 형식
  - 데이터 소스: `signals` 테이블에서 `tier="volume_surge"` AND `created_at::date = today` 집계
- `GET /api/v1/metrics/time-filter-stats`:
  - 응답: `{"morning_lockout": 12, "afternoon_lockout": 8, "gap_open_morning_exception": 3}` 일별 카운트
  - 데이터 소스: signal_rejections 테이블 또는 Redis 카운터(`metrics:time_filter:{reason}:{date}`)
  - Redis 카운터 방식 채택 권장 (DB 부하 회피)
- Pydantic 응답 모델 + pytest 통과 확인

**Step 2: 프론트엔드 카드**
- `volume-surge-card.tsx`:
  - 일별 dry_run 신호 수 + 7일 이동평균 라인 차트 (recharts 또는 기존 차트 라이브러리)
  - `VOLUME_SURGE_DRY_RUN=true` 배너 (Phase 8.5 OverrideBanner 패턴 재사용)
  - LIVE 토글 게이트 상태 (Sprint 4 G-Bt1~3 미구현이지만 placeholder 텍스트 "LIVE 토글 게이트 미준비 — Sprint 4 후 활성")
- `time-filter-card.tsx`:
  - 시간대별 차단 횟수 (morning_lockout / afternoon_lockout / gap_open_morning_exception 3종 막대 그래프)
  - 7일 이동 추이
- `diagnostics/page.tsx`에 두 카드 추가 (기존 tier-correlation-card / tier-pass-rate-card 옆)

**Step 3: 검증**
- 검증: `docker compose exec backend pytest tests/api/test_metrics_volume_surge.py tests/api/test_metrics_time_filter.py -v`
- 검증: `cd frontend && npx tsc --noEmit`
- Playwright (Task 6에서 통합)

**Step 4: 커밋**
```
git add backend/api/routes/metrics.py backend/tests/api/test_metrics_*.py frontend/components/diagnostics/volume-surge-card.tsx frontend/components/diagnostics/time-filter-card.tsx frontend/app/\(dashboard\)/diagnostics/page.tsx frontend/lib/api.ts
git commit -m "feat(phase8.6-sprint3): task5 — volume-surge-card + time-filter-card UI + 신규 metrics API 2종"
```

**완료 기준:**
- ⬜ pytest API 신규 테스트 PASS
- ⬜ frontend tsc 타입 에러 0건
- ⬜ /diagnostics 페이지에서 2종 카드 정상 렌더링 (Task 6 Playwright 검증)

---

### Task 6: 통합 회귀 + Kill-switch 런북 + Paper 1거래일 관찰

**skill:** `verification-before-completion`

**Files:**
- Modify: `deploy.md` (Sprint 3 배포 항목 + Kill-switch 런북 + 환경변수 검증 항목)
- Modify: `docs/phase/phase8.6/sprint3/sprint3.md` (관찰 결과 추가)

**Step 1: pytest 전체 통과**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS, Sprint 2 대비 신규 테스트 추가됨 (test_time_filter.py 8 + test_volume_surge.py 12 + test_engine_volume_surge_integration.py 5+ + test_signal_priority_queue.py 4+ + test_auto_rollback_r3.py 4+ + test_scheduler_portal_metrics_jobs.py 3+ + test_metrics_volume_surge.py 2+ + test_metrics_time_filter.py 2+ ≈ **40+ 신규 PASS**)

**Step 2: TypeScript 타입 체크**
- 검증: `cd frontend && npx tsc --noEmit`
- 예상: 0 에러

**Step 3: Playwright 회귀**
- /diagnostics 페이지에서 다음 4종 카드 정상 렌더링:
  - tier-correlation-card (Sprint 2)
  - tier-pass-rate-card (Sprint 2)
  - volume-surge-card (Sprint 3)
  - time-filter-card (Sprint 3)
- 스크린샷 저장: `docs/phase/phase8.6/sprint3/screenshot-diagnostics.png`

**Step 4: Kill-switch 런북 deploy.md 등록**
- deploy.md에 다음 추가:
  ```
  ## Phase 8.6 Sprint 3 Kill-switch 런북

  ### volume_surge 신호 폭증 시
  ```
  railway variables --set "VOLUME_SURGE_ENABLED=false"
  # 즉시 적용 — 신호 발행 차단, 실행 중 dry_run 신호는 그대로 종료
  ```

  ### 시간 필터 오작동 시
  ```
  railway variables --set "TIME_FILTER_ENABLED=false"
  # Sprint 2 동작과 동등 (시간대 차단 미적용)
  ```

  ### dry_run → LIVE 토글 (Sprint 4 G-Bt1~3 통과 후에만)
  ```
  railway variables --set "VOLUME_SURGE_DRY_RUN=false"
  # ⚠️ Sprint 4 walk-forward + Bootstrap CI 하한 ≥1 + Paper 5거래일 G-A·G-B 충족 동시 확인 필수
  ```

  ### 우선순위 큐 비활성화 (병렬 OR 폭증 회복 시)
  ```
  railway variables --set "SIGNAL_PRIORITY_QUEUE_ENABLED=false"
  # 모든 tier 동시 발행 (일일 한도 10건 도달 시 자동 차단)
  ```
  ```

**Step 5: Paper 1거래일 관찰 항목 (sprint-close 후 24시간)**
- deploy.md 수동 검증 항목 ⬜으로 추가:
  - `volume_surge dry_run 신호 1건 이상: 다음 영업일 장마감 후 SQL 확인 — SELECT COUNT(*) FROM signals WHERE tier='volume_surge' AND dry_run=true AND created_at::date = current_date`
  - `호가창 Redis 키 적재 확인: redis-cli SCAN 0 MATCH "realtime:*:orderbook" COUNT 50 결과 ≥10종`
  - `5분봉 vol5m 적재 확인: redis-cli SCAN 0 MATCH "vol5m:*:$(date +%Y%m%d):*" COUNT 100 결과 ≥10종`
  - `시간 필터 차단 카운터 0이 아님: redis-cli GET "metrics:time_filter:morning_lockout:$(date +%Y-%m-%d)" ≥1`
  - `R3 자동 롤백 미발동: GET "auto_rollback:active" 결과 None`
  - `portal_supplement / metrics_rollup 잡 키 16:10 시점 적재 확인 (Task 4)`

**Step 6: 커밋**
```
git add deploy.md docs/phase/phase8.6/sprint3/sprint3.md docs/phase/phase8.6/sprint3/screenshot-diagnostics.png
git commit -m "docs(phase8.6-sprint3): task6 — 통합 회귀 + Kill-switch 런북 + 환경변수 8종 검증 항목"
```

**완료 기준:**
- ⬜ pytest 전체 PASS (40+ 신규 + Sprint 2 회귀 0건)
- ⬜ tsc 0 에러
- ⬜ Playwright /diagnostics 4종 카드 렌더링 확인
- ⬜ deploy.md Kill-switch 런북 4종 + 환경변수 검증 6종 등록
- ⬜ Paper 1거래일 관찰 항목 6종 ⬜으로 등록 (실제 측정은 sprint-close 후 24시간)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS, 신규 40+ PASS |
| TypeScript | `cd frontend && npx tsc --noEmit` | 에러 없음 |
| Alembic 적용 | `docker compose exec backend alembic upgrade head` | head로 갱신 (signals.dry_run 컬럼 추가) |
| 환경변수 로드 | `docker compose exec backend python -c "from core.config import settings; print(settings.VOLUME_SURGE_ENABLED, settings.TIME_FILTER_ENABLED, settings.AUTO_ROLLBACK_R3_ENABLED, settings.ATR_COVERAGE_GAP_MAX); assert not hasattr(settings, 'TEMP_TIME_GUARD_SPRINT2')"` | `True True True 30` + AssertionError 없음 |
| volume_surge 단위 | `pytest tests/strategies/test_volume_surge.py -v` | 12+ PASS |
| 시간 필터 단위 | `pytest tests/strategies/test_time_filter.py -v` | 8 PASS |
| 우선순위 큐 | `pytest tests/trading/test_signal_priority_queue.py -v` | 4+ PASS |
| R3 활성화 | `pytest tests/safety/test_auto_rollback_r3.py -v` | 4+ PASS |
| /diagnostics 카드 | Playwright 스크린샷 | 4종 카드 렌더링 |
| Kill-switch 회귀 | `VOLUME_SURGE_ENABLED=false` 환경에서 pytest | volume_surge 신호 발행 0건 |

---

## 미해결 사항 / 리스크

### ⚠️ 알려진 리스크

1. **호가창 Redis TTL 5초 가정의 정확성**
   - Phase 6에서 Redis TTL이 정확히 5초인지 확인 필요. Task 2 Step 1 테스트 작성 전 `grep -rn "EXPIRE\|setex" backend/modules/collector/ws_manager.py backend/modules/collector/sources/kis_realtime.py`로 검증
   - 완화: 실제 TTL과 무관하게 키 부재/만료 시 graceful reject 로직 채택

2. **5분봉 vol5m 직전 4봉 평균 0 가능성** (장 시작 직후 09:30)
   - 09:30 시점에는 vol5m 슬롯 0~5만 적재됨. 직전 4봉 평균이 작거나 0 가능
   - 완화: 평균 0이면 `vol_surge_vol5m_zero`로 reject (테스트 케이스에 포함)
   - 추가: volume_surge 활성 시작 시각이 09:30이지만 의미 있는 평균 산출은 09:50 이후일 것 — 운영 관찰로 검증

3. **dry_run → LIVE 전환 인적 오류 위험**
   - `VOLUME_SURGE_DRY_RUN=false`를 Sprint 4 G-Bt1~3 통과 전에 잘못 설정 시 LIVE 자금 위험
   - 완화: deploy.md Kill-switch 런북에 ⚠️ 명시 + Sprint 4 토글 시 텔레그램 2단계 확인 (Sprint 4 범위)

4. **TEMP_TIME_GUARD_SPRINT2 제거 시 기존 테스트 회귀 가능성**
   - momentum_breakout.py의 line 588~602 블록 제거 + 호출부 교체 시 테스트가 `settings.TEMP_TIME_GUARD_SPRINT2` 참조 시 실패
   - 완화: Task 1 Step 4에서 `grep -rn "TEMP_TIME_GUARD_SPRINT2"` 결과 0건 확인 후 커밋

5. **신호 우선순위 큐 일일 한도 10건 회귀**
   - Phase 7.2 한도 10건은 dry_run 신호 카운트 제외해야 자금 보호 무관하게 작동
   - 완화: Task 3 단위 테스트에 dry_run 신호 카운트 제외 회귀 테스트 포함

### 🤔 사용자 최종 결정 필요 항목

1. **volume_surge dry_run → LIVE 전환을 Sprint 3 종료 후 자동 토글로 자동화할지** (현재 본문은 Sprint 4 + 수동 토글 권고, 사용자 의사 확인 필요)
2. **5분봉 vol5m 평균 산출 윈도우(직전 4봉 = 20분)를 늘릴지** (단타 §2 패턴 1은 "직전 20분 평균"이라 현재 구현이 일치, 단 평균 0 빈발 시 직전 8봉 = 40분으로 확장 검토)

---

## 사용자 다음 단계 안내

```
📋 다음 단계를 선택해주세요:
1. /sprint-dev 8.6-3 으로 구현 시작 (5/8 GO 확정 후)
2. 검토 후 수동 진행

먼저 다음 게이트 충족 확인 필수:
- 5/8 장마감 후 G2 신호 ≥1건 발생 OR G3 정식 측정값 ≤0.15
- ATR sample_n ≥ 200 안정 유지 2영업일
- portal_supplement / metrics_rollup 잡 키 적재 확인

docs/phase/phase8.6/sprint3/sprint3.md를 검토하시고, 게이트 충족 후 진행하세요.
```

---

## 구현 완료 기록

**구현 기간**: 2026-05-08
**브랜치**: `phase8.6-sprint3`

### Task 커밋 SHA

| Task | 커밋 SHA | 설명 |
|------|----------|------|
| Task 1 | `294d4bb` | env 8종 + 시간 필터 본 가드 + TEMP_TIME_GUARD_SPRINT2 제거 |
| Task 2 | `47157de` | VolumeSurgeStrategy + signals.dry_run 컬럼 |
| Task 3 | `1c58fe3` | TradingEngine volume_surge 통합 + 우선순위 큐 |
| Task 4 | `f8c422d` | R3 활성화 검증 + portal/metrics 잡 점검 + ATR coverage gap 30 원복 |
| Task 5 | `bb9f3f9` | volume-surge-card + time-filter-card UI + 신규 metrics API 2종 |
| Task 6 | (본 커밋) | 통합 회귀 + Kill-switch 런북 + 환경변수 8종 검증 항목 |

### 풀 회귀 결과

- **pytest 전체**: 1116 passed, 0 failed (640초)
- **Sprint 3 신규 테스트**: 43 PASS
  - `tests/strategies/test_time_filter.py`: 8
  - `tests/strategies/test_volume_surge.py`: 12
  - `tests/test_engine_volume_surge_integration.py`: 4
  - `tests/test_signal_priority_queue.py`: 4
  - `tests/safety/test_auto_rollback_r3.py`: 4
  - `tests/api/test_metrics_volume_surge.py`: 3
  - `tests/api/test_metrics_time_filter.py`: 3 (+ scheduler 잡 테스트 별도 집계)
- **tsc**: 0 에러
- **Playwright /diagnostics**: 4종 카드(volume-surge-card, time-filter-card, tier-pass-rate-card, tier-correlation-card) 렌더링 확인 (접근성 스냅샷 기반)
