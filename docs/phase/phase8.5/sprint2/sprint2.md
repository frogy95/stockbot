# Sprint 2: 풀 하한 폴백 + 동적 MIN_VOLUME_FLOOR (Phase 8.5)

**Goal:** 2차 스크리닝 통과 < 3건일 때 1차 통과 종목 상위 score로 보강(최대 5종목)하고, `MIN_VOLUME_FLOOR`를 tier·gap 기반 동적 분기(0.4 / 0.5 / 0.6 + HARD 0.3)로 전환하여 2차 풀과 전략 게이트의 교차 가능 집합을 **양수화**한다. 폴백 종목은 position 50% + 손절 -1.5% + 하락 -3% 제외로 품질 불확실성을 보상한다.

**Architecture:** 모든 파라미터는 `core/config.py`에 env 변수로 선언하여 **1줄 롤백**을 보장한다. `realtime_screener.screen()`은 기존 반환 경로에 fallback 보강 로직을 추가하되, 각 후보 dict에 `is_fallback` / `raw_score` / `percentile_rank` 메타데이터를 주입한다. `momentum_breakout.py`의 `MIN_VOLUME_FLOOR` 상수는 `_resolve_min_volume_floor(snapshot, tier, gap_rate)` 순수 함수로 교체되며, shadow 경로(`_shadow_evaluate`)도 **동일 함수를 사용**하여 본체/그림자 일관성을 보장한다. `engine.py`는 `is_fallback` 플래그를 소비하여 포지션·손절을 조정한다. 16:10 자동 롤백 job이 2거래일 연속 신호 0건을 감지하면 Redis override + Telegram 경고를 발생시킨다 (settings 영구 변경 X).

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 (async) / Redis 7 / APScheduler / pytest-asyncio / Next.js 16 / React 19 / Tailwind 4 / SWR

**상태:** ✅ 완료 (2026-04-23)
**Sprint 기간:** 2026-04-23 ~ 2026-04-23
**이전 스프린트:** Phase 8.5 Sprint 1.5 (✅ 완료, 2026-04-23, PR #168)
**다음 스프린트:** Phase 8.6 Sprint 1 (E2E + LIVE 전환 게이트, Phase 8.5 관찰 5거래일 후 착수)
**브랜치명:** `phase8.5-sprint2`
**PR:** (생성 예정)

---

## 착수 배경 (2026-04-23 실측)

Sprint 1.5 shadow evaluation 데이터 결과:

- **신호 0건 / 전략 거부 208건** — 1.5거래일 관찰 조건(배포 당일 + 다음 거래일 종일) 충족
- shadow heatmap으로 확인된 병목: `volume_threshold` / `atr_filter` / `confidence` 3중 구조가 복합 작용
- 2차 스크리닝 풀 통과 1종목 고정 (073490) — 풀 자체가 비어있어 교차 집합 항상 0
- "계속 그랬어" (사용자 관측): 수 거래일 동일 패턴 지속

Phase 8.5 확정 판정: **Sprint 2 착수 조건 충족**. 풀 하한 폴백(확정 #1~#8)과 동적 `MIN_VOLUME_FLOOR`(확정 #10~#13)를 동시 배포하여 교차 가능 집합을 양수화한다.

---

## 제외 범위

이 스프린트에서 **하지 않는 것**:

- **2차 `pass_threshold` 완화** — 확정 #9: 75.0 유지, 임계값 자체는 분포 데이터 확인 후 별도 판단
- **시간대 슬라이딩 `MIN_VOLUME_FLOOR`** — 확정 #14: 전원 거부
- **`prev_close_time_guard` 13:00→14:00 연장** — 확정 #15: 전원 거부, 13:00 유지
- **필터값 분포 히스토그램(adjusted_ratio, breakout_pct, confidence 수치)** — Sprint 1.5 제외 결정 그대로
- **DB 테이블 신규 추가** — Alembic 마이그레이션 없음 (모든 새 데이터는 기존 `factors` JSON 컬럼 또는 Redis)
- **Phase 10.1 하이브리드 전체 흡수** — MVP(풀 하한 폴백)만 본 Sprint, 고도화는 Phase 10.1에서
- **자동 롤백의 완전 자동 원복** — 관리자 확인 대기 방식 (권고 #3)

**핵심 제약 (절대 불변)**:

- `_shadow_evaluate`의 stage 판정이 본체(`generate_signal`)와 **동일한 `_resolve_min_volume_floor` 함수**를 사용해야 한다. 그림자/본체 불일치는 즉시 관측 데이터를 오염시킨다.
- Sprint 1에서 확정된 `STAGE_STRATEGY_PREFIX` / `SHADOW_STAGE_PREFIX` 키 규약은 변경하지 않는다.
- env 변수 기본값은 **모든 신기능 ON** (`MIN_VOLUME_FLOOR_MODE=dynamic`, `SECONDARY_POOL_FALLBACK_ENABLED=True`). 롤백은 배포 후 env 1줄 변경.

---

## 확정 파라미터 요약 (Phase 8.5 문서 #1~#26 중 Sprint 2 대상)

### env 변수 (Task 1에서 선언 — `core/config.py`)

| env 변수 | 기본값 | 확정 # | 의미 |
|---------|--------|--------|------|
| `MIN_VOLUME_FLOOR_MODE` | `"dynamic"` | #23 | `legacy` = 0.5 고정, `dynamic` = 조건부 |
| `MIN_VOLUME_FLOOR_HARD` | `0.3` | #13 | 어떤 분기도 이 이하 금지 (절대 하한) |
| `SECONDARY_POOL_FALLBACK_ENABLED` | `True` | #23 | 폴백 자체 활성화 |
| `SECONDARY_POOL_FALLBACK_THRESHOLD` | `3` | #1 | `passed_count < 3` 시 폴백 발동 |
| `SECONDARY_POOL_MAX` | `5` | #3 | 폴백 포함 풀 상한 |
| `FALLBACK_DROP_EXCLUDE_PCT` | `-3.0` | #7 | 전일 대비 -3% 이하 폴백 제외 |
| `FALLBACK_POSITION_SIZE_RATIO` | `0.5` | #6 | 폴백 종목 포지션 사이즈 × 0.5 |
| `FALLBACK_STOP_LOSS_PCT` | `-1.5` | #8 | 폴백 종목 손절 -1.5% (일반 -2%) |

### 동적 `MIN_VOLUME_FLOOR` 반환 규칙 (`_resolve_min_volume_floor`)

| 조건 | 반환 | 확정 # |
|------|------|--------|
| `gap_rate >= 0.05` OR `(current_price >= breakout_ref * 1.03)` (강한 돌파) | `0.4` | #11 |
| `tier == "prev_close"` (약한 신호) | `0.6` | #12 |
| 그 외 (기본 `gap_open` / `prev_high` tier) | `0.5` | #10 |
| 반환값 < HARD(0.3) 시 | HARD 강제 + `logger.warning` | #13 |

---

## 실행 플랜

의존성 그래프:

```
Task 1 (env 변수 선언 + .env.example 동기화)
  ├─> Task 2 (_resolve_min_volume_floor 함수화, shadow 경로도 동일 함수 사용)
  ├─> Task 3 (screener 풀 하한 폴백)
  │     └─> Task 4 (engine is_fallback 분기)
  └─> Task 5 (scheduler 자동 롤백 job)
        Task 6 (프론트 폴백 통계 카드 + ⚠️ 배지)
        Task 7 (Sprint 1 M1/M2 수정)
              └─> Task 8 (통합 검증 + 커밋)
```

Task 1은 의존성의 시작점. Task 2/3/5/6/7은 Task 1 이후 병렬 가능(파일 소유권 분리). Task 4는 Task 3 완료 후 순차. Task 8은 전체 마무리.

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | `core/config.py` env 변수 8종 선언 + `.env.example` 동기화 | 백엔드 | — |

### Phase 2 (병렬 가능 — 파일 소유권 분리)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | `momentum_breakout.py` `_resolve_min_volume_floor` 순수 함수 + shadow 경로 일관화 | 백엔드 | `systematic-debugging` |
| Task 3 | `realtime_screener.py` 풀 하한 폴백 + 메타데이터 주입 | 백엔드 | — |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | `engine.py` `is_fallback` 분기 (position_size × 0.5, 손절 -1.5%) | 백엔드 | — |

### Phase 4 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | `scheduler.py` 16:10 자동 롤백 job + Redis override + Telegram 경고 | 백엔드 | — |
| Task 6 | 프론트: 폴백 발동 통계 카드 활성화 + 결과 리스트 ⚠️ 배지 | 프론트엔드 | `frontend-design` |
| Task 7 | Sprint 1 M1(TOP_REJECT_SIZE env 승격 또는 API limit 상한) + M2(stage-heatmap 09:00~09:20 표시) | 백엔드 + 프론트 | — |

### Phase 5 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 8 | pytest + API curl + Playwright + tsc + 커밋 + sprint-close 안내 | 전체 | — |

> **팀 실행**: "Phase 4를 팀으로 실행해줘"라고 요청하면 백엔드(Task 5, Task 7 백엔드 부분)와 프론트엔드(Task 6, Task 7 프론트 부분) 팀원이 병렬 구현한다.

---

### Task 1: env 변수 8종 선언 + `.env.example` 동기화

**Files:**
- Modify: `backend/core/config.py` (Settings 클래스에 필드 8개 추가)
- Modify: `.env.example` (8개 변수 + 한글 주석 추가)

**Step 1: `core/config.py` Settings에 필드 추가**
- 위치: 기존 `MIN_CONFIDENCE` / `MAX_DAILY_TRADES` 등 전략 섹션 하단
- 필드 선언 (Pydantic `Field` 사용, 한글 주석):
  ```python
  MIN_VOLUME_FLOOR_MODE: Literal["legacy", "dynamic"] = Field(default="dynamic", description="거래량 하한 결정 방식")
  MIN_VOLUME_FLOOR_HARD: float = Field(default=0.3, ge=0.0, le=1.0, description="어떤 분기도 이 이하 금지")
  SECONDARY_POOL_FALLBACK_ENABLED: bool = Field(default=True, description="2차 풀 하한 폴백 활성화")
  SECONDARY_POOL_FALLBACK_THRESHOLD: int = Field(default=3, ge=1, le=10, description="passed_count < N 시 폴백 발동")
  SECONDARY_POOL_MAX: int = Field(default=5, ge=1, le=20, description="폴백 포함 풀 상한")
  FALLBACK_DROP_EXCLUDE_PCT: float = Field(default=-3.0, description="전일 대비 이 이하는 폴백 제외 (%)")
  FALLBACK_POSITION_SIZE_RATIO: float = Field(default=0.5, gt=0.0, le=1.0, description="폴백 종목 포지션 사이즈 배수")
  FALLBACK_STOP_LOSS_PCT: float = Field(default=-1.5, description="폴백 종목 손절 % (절댓값 작을수록 타이트)")
  ```
- `Literal` 미사용 시 `str`로 fallback, Pydantic 버전에 맞춰 조정
- 검증: `docker compose exec backend python -c "from core.config import settings; print(settings.MIN_VOLUME_FLOOR_MODE, settings.SECONDARY_POOL_FALLBACK_THRESHOLD)"`
- 예상: `dynamic 3`

**Step 2: `.env.example` 동기화**
- 파일 끝 "# Phase 8.5 Sprint 2" 섹션 추가:
  ```
  # --- Phase 8.5 Sprint 2: 풀 하한 폴백 + 동적 MIN_VOLUME_FLOOR ---
  # 거래량 하한 결정 방식 (legacy=0.5 고정 / dynamic=조건부)
  MIN_VOLUME_FLOOR_MODE=dynamic
  # 어떤 분기도 이 이하로 내리지 않는 절대 하한
  MIN_VOLUME_FLOOR_HARD=0.3
  # 2차 스크리닝 통과 < 이 값이면 1차 통과 종목으로 보강
  SECONDARY_POOL_FALLBACK_ENABLED=True
  SECONDARY_POOL_FALLBACK_THRESHOLD=3
  # 폴백 포함 풀 최대 종목 수
  SECONDARY_POOL_MAX=5
  # 전일 대비 이 이하 종목은 폴백 제외
  FALLBACK_DROP_EXCLUDE_PCT=-3.0
  # 폴백 종목 포지션 사이즈 배수 (0.5 = 반 포지션)
  FALLBACK_POSITION_SIZE_RATIO=0.5
  # 폴백 종목 손절 % (-1.5 = -1.5%)
  FALLBACK_STOP_LOSS_PCT=-1.5
  ```
- 검증: `grep -c "MIN_VOLUME_FLOOR\|FALLBACK\|SECONDARY_POOL" .env.example` → 최소 8개

**Step 3: 커밋**
```
git add backend/core/config.py .env.example
git commit -m "feat(phase8.5-sprint2): task1 — 동적 MIN_VOLUME_FLOOR·폴백 env 변수 8종 선언"
```

**완료 기준:**
- ✅ `from core.config import settings`로 8개 필드 모두 접근 가능
- ✅ `.env.example`에 8개 변수 + 한글 주석 존재
- ✅ 기존 테스트 회귀 없음

---

### Task 2: `_resolve_min_volume_floor` 순수 함수 + shadow 경로 일관화

**skill:** `systematic-debugging`

**Files:**
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (상수 → 함수 교체)
- Modify: `backend/tests/test_momentum_breakout.py` (새 함수 단위 테스트)
- Modify: `backend/tests/test_momentum_breakout_metrics.py` (shadow/본체 일관성 테스트)

**Step 1: 순수 함수 선언**
- 위치: `MIN_VOLUME_FLOOR = 0.5` 상수 삭제, 모듈 상단에 함수 추가:
  ```python
  def _resolve_min_volume_floor(
      snapshot: MarketSnapshot,
      tier: str,
      gap_rate: float | None,
      breakout_ref: float,
      *,
      mode: str | None = None,
      hard_floor: float | None = None,
  ) -> float:
      """동적 MIN_VOLUME_FLOOR 계산 (확정 #10~#13).

      반환값은 HARD 하한 이상임이 보장된다.
      """
      resolved_mode = mode if mode is not None else settings.MIN_VOLUME_FLOOR_MODE
      hard = hard_floor if hard_floor is not None else settings.MIN_VOLUME_FLOOR_HARD

      if resolved_mode == "legacy":
          result = 0.5
      else:
          # 강한 돌파 판정: gap >= 5% OR current_price >= breakout_ref * 1.03
          strong_gap = (gap_rate is not None and gap_rate >= 0.05)
          strong_breakout = (
              breakout_ref > 0
              and snapshot.current_price >= breakout_ref * 1.03
          )
          strong = strong_gap or strong_breakout

          if tier == "prev_close":
              result = 0.6  # 약한 신호엔 더 강한 거래량 요구
          elif strong:
              result = 0.4  # 강한 돌파엔 거래량 허용
          else:
              result = 0.5  # 기본

      if result < hard:
          logger.warning(
              "resolved floor %.3f < HARD %.3f, forcing HARD",
              result, hard,
          )
          return hard
      return result
  ```
- 시그니처는 **확정**: `breakout_ref: float`를 필수 파라미터로 받는다 (호출부가 `_resolve_tier` 직후 계산 가능)
- `resolved_mode`/`hard` 변수는 Redis override lookup 지점(Task 5에서 추가 예정)을 위해 분리 보존

**Step 2: 기존 호출부 교체**
- `generate_signal()`의 `MIN_VOLUME_FLOOR` 사용 지점 2곳 (line 215, 377, 384, 385):
  - tier 결정 후 `floor = _resolve_min_volume_floor(snapshot, tier, gap_rate, breakout_ref=breakout_ref)` 계산
  - `snapshot.volume >= snapshot.prev_volume * floor`로 교체
  - `_reject` 시 `factors.floor_ratio`를 계산된 `floor` 값으로 기록
- `_shadow_evaluate()`의 `min_volume_floor` stage 평가도 **동일 함수** 호출 (`MIN_VOLUME_FLOOR` 하드코딩 금지)

**Step 3: 단위 테스트 추가**
- `test_momentum_breakout.py::TestResolveMinVolumeFloor`:
  - `test_legacy_mode_returns_0_5`: mode=legacy → 0.5
  - `test_strong_gap_returns_0_4`: gap_rate=0.06, tier=gap_open → 0.4
  - `test_prev_close_tier_returns_0_6`: tier=prev_close → 0.6
  - `test_default_returns_0_5`: tier=prev_high, gap=0.02 → 0.5
  - `test_hard_floor_enforced`: hard_floor=0.45, default 0.5 → 0.5 (변화 없음); hard_floor=0.7, default 0.5 → 0.7
  - `test_breakout_ref_1_03_trigger`: `current_price >= breakout_ref * 1.03` → 0.4
- `test_momentum_breakout_metrics.py::TestShadowBodyFloorConsistency`:
  - `test_shadow_and_body_use_same_floor`: 동일 snapshot으로 shadow / 본체의 `min_volume_floor` stage 판정 결과 일치
  - monkeypatch로 `_resolve_min_volume_floor`를 spy → 호출 횟수 동일 (본체 1회 + shadow 1회)

**Step 4: 검증**
- `docker compose exec backend pytest tests/test_momentum_breakout.py tests/test_momentum_breakout_metrics.py -v`
- 예상: 신규 6개 PASS + 기존 회귀 GREEN

**Step 5: 커밋**
```
git add backend/modules/trading/strategies/momentum_breakout.py backend/tests/test_momentum_breakout.py backend/tests/test_momentum_breakout_metrics.py
git commit -m "feat(phase8.5-sprint2): task2 — _resolve_min_volume_floor 순수 함수 + shadow 본체 일관화"
```

**완료 기준:**
- ✅ `MIN_VOLUME_FLOOR` 상수 제거 완료
- ✅ shadow/본체가 동일 함수를 통해 동일 값을 반환 (일관성 테스트 GREEN)
- ✅ HARD 하한 강제 동작 테스트 GREEN
- ✅ 기존 `test_momentum_breakout.py` 전체 회귀 PASS

---

### Task 3: `realtime_screener.py` 풀 하한 폴백 + 메타데이터 주입

**Files:**
- Modify: `backend/modules/screening/realtime_screener.py` (`screen()` 결과에 폴백 로직 추가)
- Modify: `backend/tests/test_realtime_screener.py` 또는 신규 — 폴백 케이스 테스트

**Step 1: 폴백 후보 공급 로직 설계**
- `screen()` 반환 직전(`passed` 리스트 확정 후):
  1. `passed_count = len(passed)` 계산
  2. `if not settings.SECONDARY_POOL_FALLBACK_ENABLED: return passed` 가드
  3. `if passed_count >= settings.SECONDARY_POOL_FALLBACK_THRESHOLD: return passed`
  4. 1차 통과 종목 중 `passed`에 포함되지 않은 종목들을 `total_score` 내림차순 정렬
  5. 필터: 각 후보의 `change_rate` (또는 `(current_price - prev_close) / prev_close * 100`)가 `FALLBACK_DROP_EXCLUDE_PCT` 초과인 것만
  6. 모자란 수만큼(`THRESHOLD - passed_count`, 최대 `SECONDARY_POOL_MAX - passed_count`) 보강
  7. 각 폴백 후보 dict에 주입:
     - `is_fallback=True`
     - `raw_score=total_score` (1차 스크리닝 점수 원본)
     - `percentile_rank` = 1차 통과 pool 대비 percentile (상위 몇 % 인지)
  8. 기존 `passed` 후보에도 `is_fallback=False` / `raw_score` 명시 (하위 소비 코드 안전)
- 폴백 발동 시 Redis counter 증가: `metrics:fallback:count:{date}` incr (Sprint 1 패턴 재사용, `FALLBACK_METRICS_PREFIX = "metrics:fallback"`)
  - `metrics:fallback:triggered:{date}` incr
  - `metrics:fallback:codes:{date}` → sadd stock_code
  - TTL 7일

**Step 2: 1차 통과 종목 pool에 접근 경로 확인**
- `screen()` 내에서 `factor_scorer.score_candidates` 결과 전체가 이미 있는지, 아니면 1차 스크리닝 결과를 외부에서 주입받아야 하는지 확인
- 만약 1차 결과가 외부 의존(`primary_screener`)이라면, `screen()` 시그니처에 optional `primary_candidates` 파라미터 추가 고려
  - 단, **시그니처 변경 최소화 원칙** — 기존 호출부(`signal_generator`, scheduler)가 이미 1차 통과 후보를 주입하고 있다면 그대로 활용
  - 호출부 확인: `backend/modules/trading/signal_generator.py` 또는 `scheduler.py`에서 `realtime_screener.screen()` 호출 지점 grep

**Step 3: 단위 테스트 추가**
- `test_fallback_fills_pool_when_passed_below_threshold`:
  - passed=1종목, 1차 pool=5종목 → 폴백 후보 2개 추가되어 최종 3종목
- `test_fallback_excludes_dropped_stocks`:
  - 1차 pool에 `change_rate=-5%` 종목 포함 → 제외 확인
- `test_fallback_respects_pool_max`:
  - passed=0, 1차 pool=10종목 → 최대 `SECONDARY_POOL_MAX=5`까지만 보강
- `test_fallback_disabled_no_boost`:
  - `SECONDARY_POOL_FALLBACK_ENABLED=False` → passed 그대로 반환
- `test_fallback_metadata_present`:
  - 폴백 후보에 `is_fallback=True`, `raw_score`, `percentile_rank` 모두 존재
  - 기존 통과 후보에 `is_fallback=False`
- `test_fallback_counter_incremented`:
  - FakeRedis로 `metrics:fallback:triggered:{today}` 값 1 증가 확인

**Step 4: 검증**
- `docker compose exec backend pytest tests/test_realtime_screener.py -v -k "fallback"`
- 예상: 6개 PASS

**Step 5: 커밋**
```
git add backend/modules/screening/realtime_screener.py backend/tests/test_realtime_screener.py
git commit -m "feat(phase8.5-sprint2): task3 — 2차 풀 하한 폴백 + 메타데이터 + 발동 카운터"
```

**완료 기준:**
- ✅ `passed < THRESHOLD` 시 폴백 후보로 보강
- ✅ `change_rate <= -3%` 종목 제외
- ✅ 풀 상한 `SECONDARY_POOL_MAX` 준수
- ✅ 각 후보에 `is_fallback` / `raw_score` / `percentile_rank` 기록
- ✅ Redis counter `metrics:fallback:*` 증가

---

### Task 4: `engine.py` `is_fallback` 분기

**Files:**
- Modify: `backend/modules/trading/engine.py` (position_sizer 호출 + 손절 설정)
- Modify: `backend/tests/test_engine.py` 또는 `test_engine_fallback.py` 신규

**Step 1: `is_fallback` 분기 지점 파악**
- 기존 engine.py line 214~217: `candidate.get("is_fallback", False) or candidate.get("is_relaxed", False)` 체크 있음
- 현재 동작: 이 분기에서 이미 `is_relaxed` 처리 중이므로, `is_fallback` 전용 분기 로직을 명시적으로 추가
- position_size 계산 경로에서 `if candidate.is_fallback: base_size *= settings.FALLBACK_POSITION_SIZE_RATIO`
- 손절 설정 경로(`position.stop_loss_pct` 등)에서 `if candidate.is_fallback: stop_loss = settings.FALLBACK_STOP_LOSS_PCT`

**Step 2: 테스트 추가**
- `test_fallback_applies_half_position`:
  - candidate with `is_fallback=True`, base size=100 → 실제 size=50
- `test_fallback_applies_tight_stop_loss`:
  - candidate with `is_fallback=True` → 손절 -1.5%
- `test_non_fallback_unchanged`:
  - `is_fallback=False` → 기존 포지션/손절 그대로
- `test_fallback_and_relaxed_combined`:
  - 두 플래그 동시 설정 시 position 배수가 중복 적용되는지 명시적으로 결정
  - **결정**: 둘 다 True면 **더 작은 배수 선택**(보수적) — 예: 0.5 × 0.7 이 아니라 `min(0.5, 0.7)=0.5` (테스트로 고정)

**Step 3: 검증**
- `docker compose exec backend pytest tests/test_engine.py -v -k "fallback"`

**Step 4: 커밋**
```
git add backend/modules/trading/engine.py backend/tests/
git commit -m "feat(phase8.5-sprint2): task4 — engine is_fallback 분기 (position 0.5x + 손절 -1.5%)"
```

**완료 기준:**
- ✅ `is_fallback=True` 시 position × 0.5, 손절 -1.5%
- ✅ 기존 경로 회귀 없음
- ✅ is_fallback + is_relaxed 복합 케이스 명시적 동작

---

### Task 5: 16:10 자동 롤백 job

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (APScheduler job 추가)
- Modify: `backend/tests/test_scheduler.py` 또는 신규 롤백 job 테스트

**Step 1: 롤백 판정 쿼리**
- `signal_count(date) = SELECT COUNT(*) FROM trade_signals WHERE DATE(created_at AT TIME ZONE 'Asia/Seoul') = :date`
- 오늘 = 0 AND 어제(전 영업일) = 0 시 롤백 발동

**Step 2: Redis override 메커니즘**
- Redis key `settings:override:MIN_VOLUME_FLOOR_MODE` = `legacy`
- Redis key `settings:override:SECONDARY_POOL_FALLBACK_ENABLED` = `False`
- TTL 7일, 관리자 확인 후 수동 삭제 (`DEL settings:override:*`)
- **주의**: `core/config.py`의 settings는 환경변수 기반이므로, override 읽기 로직을 `_resolve_min_volume_floor` / `realtime_screener.screen()` 내에서 **Redis 우선, env fallback** 순으로 구현 필요
- 이 override lookup은 Task 2/3의 이미 작성된 함수에 Redis 의존성을 추가하는 소규모 수정 수반 → Task 5 완료 시 Task 2/3 코드에 override lookup 추가 커밋 포함

**Step 3: Telegram 알림**
- `notifier_manager.send_alert(...)` 재사용 (Phase 5.2 패턴)
- 메시지: "⚠️ 자동 롤백 발동 — 2거래일 연속 신호 0건. MIN_VOLUME_FLOOR_MODE=legacy, FALLBACK=False로 강제 전환. 관리자 확인 대기 중."

**Step 4: 테스트**
- `test_auto_rollback_triggered_when_two_zero_days`: FakeDB에 오늘/어제 signal 0건 → Redis override 설정 + Telegram 호출 확인
- `test_auto_rollback_not_triggered_if_any_signal_exists`: 어제 1건, 오늘 0건 → 발동 안 함
- `test_override_respected_by_resolve_min_volume_floor`: Redis에 override 설정 시 `_resolve_min_volume_floor`가 legacy 반환

**Step 5: 검증 + 커밋**
- `docker compose exec backend pytest tests/test_scheduler.py -v -k "rollback"`
```
git add backend/modules/collector/scheduler.py backend/modules/trading/strategies/momentum_breakout.py backend/modules/screening/realtime_screener.py backend/tests/
git commit -m "feat(phase8.5-sprint2): task5 — 16:10 자동 롤백 job + Redis override + Telegram 경고"
```

**완료 기준:**
- ✅ 16:10 CronTrigger job 등록
- ✅ 2거래일 연속 0건 시 Redis override 설정 + Telegram 알림
- ✅ `_resolve_min_volume_floor` / `screen()`이 Redis override 우선 적용

---

### Task 6: 프론트 폴백 통계 카드 활성화 + ⚠️ 배지

**skill:** `frontend-design`

**Files:**
- Create: `backend/api/routes/metrics.py` 또는 기존 — `/api/v1/metrics/fallback-stats` 엔드포인트 추가
- Create: `frontend/components/diagnostics/fallback-stats-card.tsx`
- Modify: `frontend/app/(dashboard)/diagnostics/page.tsx` (카드 배치)
- Modify: `frontend/components/dashboard/screening-list.tsx` 또는 관련 리스트 컴포넌트 — ⚠️ 배지 추가
- Modify: `frontend/lib/api.ts` (`fallbackStats` 경로 + 타입)

**Step 1: 백엔드 API**
- `GET /api/v1/metrics/fallback-stats?date=today`
- 응답: `{date, triggered_count, codes: [...], avg_score: float | null, signal_generated_count: int}`
- Redis에서 `metrics:fallback:triggered:{date}` / `metrics:fallback:codes:{date}` / DB `trade_signals` WHERE factors->>'is_fallback'='true' 조합
- 기존 인증 의존성 재사용 (Sprint 1.5 metrics 라우터 동일 패턴)

**Step 2: 프론트 카드**
- `ShadowHeatmapCard` 디자인 패턴 계승 (Card + CardContent)
- 제목: "폴백 발동 통계 (Sprint 2)"
- 부제: "일별 폴백 횟수 / 폴백 종목 평균 score / 폴백에서 신호 발생 비율"
- SWR 30초 폴링
- 카드 내 레이아웃:
  - 상단 숫자 3개 (triggered / signals / avg_score)
  - 하단 stock_code 리스트 + 각각 ⚠️ 배지

**Step 3: 스크리닝 리스트 ⚠️ 배지**
- 기존 스크리닝 결과 리스트 컴포넌트 (`frontend/components/dashboard/` 하위) 에서 `is_fallback=True` 항목에 `⚠️ FALLBACK` 배지 + 경고색 border
- 한국 증시 색상 관례 피함 — 주황/노랑 사용 (빨강/초록 금지)

**Step 4: 디자인 검증**
- `cd frontend && npx tsc --noEmit`
- Playwright `/diagnostics` 접속 → 카드 렌더링 스크린샷

**Step 5: 커밋**
```
git add backend/api/routes/metrics.py frontend/components/diagnostics/fallback-stats-card.tsx frontend/app/\(dashboard\)/diagnostics/page.tsx frontend/components/dashboard/ frontend/lib/api.ts
git commit -m "feat(phase8.5-sprint2): task6 — 폴백 통계 카드 활성화 + 결과 리스트 ⚠️ 배지"
```

**완료 기준:**
- ✅ `/api/v1/metrics/fallback-stats` 200 응답
- ✅ `/diagnostics` 페이지에 fallback-stats-card 렌더링
- ✅ 스크리닝 결과 리스트에 ⚠️ 배지
- ✅ tsc 에러 없음

---

### Task 7: Sprint 1 미해결 이슈 M1/M2 수정

**Files:**
- Modify: `backend/modules/trading/strategies/_metrics.py` 또는 `backend/core/metrics_keys.py` (TOP_REJECT_SIZE)
- Modify: `backend/api/routes/metrics.py` (limit 상한 또는 env 승격)
- Modify: `frontend/components/diagnostics/stage-heatmap-card.tsx` (HOUR_MINS 09:00~09:20 추가)

**Step 1: M1 결정 — API limit 상한 5로 제한 (단순 방식 채택)**
- `_metrics.py`의 `TOP_REJECT_SIZE=5` 상수는 유지
- `backend/api/routes/metrics.py`의 `top-rejects` 엔드포인트 `limit` 쿼리 파라미터의 `le` 제한을 `50` → `5`로 변경
- 기존 테스트가 limit=50을 기대하면 수정

**Step 2: M2 stage-heatmap 09:00~09:20 표시**
- `frontend/components/diagnostics/stage-heatmap-card.tsx`:
  - `if (h === 9 && m < 30) continue;` 라인 제거
  - 09:00~09:20 (09:00, 09:10, 09:20) 컬럼 추가됨
- `shadow-heatmap-card.tsx`도 동일하게 수정 (두 카드 일관성)

**Step 3: 검증**
- `docker compose exec backend pytest backend/tests/test_metrics_api.py -v -k "top_reject"`
- 예상: limit 상한 5로 정상 동작
- `cd frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 4: 커밋**
```
git add backend/api/routes/metrics.py frontend/components/diagnostics/stage-heatmap-card.tsx frontend/components/diagnostics/shadow-heatmap-card.tsx backend/tests/
git commit -m "fix(phase8.5-sprint2): task7 — M1 top-rejects limit 상한 5 + M2 heatmap 09:00~09:20 표시"
```

**완료 기준:**
- ✅ `/api/v1/metrics/top-rejects?limit=50` 요청 시 422 또는 5로 clamp
- ✅ stage-heatmap / shadow-heatmap 카드에 09:00~09:20 컬럼 표시
- ✅ tsc 에러 없음

---

### Task 8: 통합 검증 + Sprint 2 마무리

**Files:**
- Modify: `deploy.md` (수동 검증 플레이스홀더 추가 — Railway 환경변수 8종 확인 포함)
- Modify: `docs/phase/phase8.5/sprint2/` (검증 스크린샷)
- ROADMAP.md / docs/index.json / MEMORY.md 업데이트는 sprint-close agent 범위

**Step 1: 백엔드 pytest 전체**
- `docker compose exec backend pytest -v`
- 예상: 전 회귀 PASS + 신규 테스트 15개 내외 PASS

**Step 2: API curl 검증**
```bash
TOKEN=$(...)
curl -sH "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/metrics/fallback-stats | jq .
curl -sH "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/metrics/shadow-heatmap | jq .
curl -sH "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/metrics/stage-heatmap | jq .
curl -sH "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/metrics/top-rejects?limit=10" | jq .  # 5로 clamp 확인
```

**Step 3: Playwright 스모크**
- `/diagnostics` 접속 → 6개 카드 (기존 4 + shadow + fallback-stats) 렌더링 스크린샷
- 저장: `docs/phase/phase8.5/sprint2/diagnostics-page.png`
- 스크리닝 리스트 페이지에서 `is_fallback=True` 항목 ⚠️ 배지 확인 (있으면 스크린샷)

**Step 4: 데모 모드 API 검증**
- env `DEMO_MODE=True`로 재기동 후 polling/엔드포인트 접근 확인

**Step 5: 주문 경로 불변 재확인**
- `docker compose exec backend pytest tests/test_momentum_breakout.py tests/test_momentum_breakout_metrics.py tests/test_engine.py tests/test_realtime_screener.py -v`
- 예상: 회귀 0건

**Step 6: `deploy.md` 수동 검증 플레이스홀더**
- Railway 환경변수 8종 추가 확인 항목 기재 (sprint-workflow.md 규칙)
- 자동 롤백 job 실제 동작 확인 항목 기재 (수 거래일 관찰 필요 → 수동)

**Step 7: 커밋 + sprint-close 안내**
```
git add deploy.md docs/phase/phase8.5/sprint2/
git commit -m "docs(phase8.5-sprint2): task8 — 통합 검증 스크린샷 + deploy.md Railway 환경변수 항목 추가"
```
- 사용자에게 sprint-close agent 호출 안내

**완료 기준:**
- ✅ pytest 전체 PASS (956 passed, 1 기존 플레이크 무관)
- ✅ 4개 API 200 + JSON 응답
- ✅ `/diagnostics` 6개 카드 렌더링 스크린샷
- ✅ 주문 경로 회귀 0건
- ✅ deploy.md Railway 환경변수 항목 추가

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS, 신규 ~15개 추가 |
| MIN_VOLUME_FLOOR 단위 테스트 | `pytest tests/test_momentum_breakout.py -v -k "floor"` | 6개 PASS |
| shadow/본체 일관성 | `pytest tests/test_momentum_breakout_metrics.py -v -k "consistency"` | PASS |
| 폴백 단위 테스트 | `pytest tests/test_realtime_screener.py -v -k "fallback"` | 6개 PASS |
| engine 분기 | `pytest tests/test_engine.py -v -k "fallback"` | 4개 PASS |
| 자동 롤백 | `pytest tests/test_scheduler.py -v -k "rollback"` | 3개 PASS |
| fallback-stats API | `curl .../metrics/fallback-stats` | 200 + JSON |
| top-rejects limit | `curl "...top-rejects?limit=10"` | 5개 또는 422 |
| 프론트 타입체크 | `cd frontend && npx tsc --noEmit` | 에러 없음 |
| Playwright | `/diagnostics` 접속 | 6개 카드 렌더링 |
| 주문 경로 불변 | 전체 momentum + engine 테스트 | 회귀 0건 |
| Redis 키 샘플 | `docker compose exec redis redis-cli --scan --pattern 'metrics:fallback:*'` | 키 존재 |

---

## 미해결 사항 / 리스크

### ⚠️ 리스크

1. **폴백 저품질 종목 투입으로 실거래 손실 확대 가능성** (최리스크)
   - 완화: position 0.5x + 손절 -1.5% + -3% 제외 + 자동 롤백 트리거
   - 추가 모니터링: 배포 후 5거래일간 폴백 종목 신호 승률/손실률 수집 (Phase 8.6 Sprint 1 DoD D5 반영)
2. **동적 `MIN_VOLUME_FLOOR` 분기 로직 버그가 shadow와 본체 불일치 유발 가능** (박퀀트)
   - 완화: Task 2 일관성 테스트로 동일 함수 사용 증명 + HARD 0.3 절대 하한
3. **Redis override 메커니즘과 env 기반 settings의 이중 진실 관리 복잡도** (박퀀트)
   - 완화: override lookup은 `_resolve_min_volume_floor` / `screen()` 두 지점에만 한정, 이 외 코드는 env만 참조
   - 문서화: wiki/trading-modes.md에 override 우선순위 명시 (sprint-close에서 확인)
4. **자동 롤백 16:10 job이 거래일 판정에서 주말/공휴일 오인할 가능성**
   - 완화: Phase 4.6 Sprint 2의 `trading_calendar.py` 재사용 — 주말/공휴일은 당일을 판정 대상에서 제외

### 🤔 사용자 확인 필요 항목 (Sprint 2 진행 중 결정)

1. **is_fallback + is_relaxed 복합 케이스 position 배수 정책**: `min(0.5, 0.7)` 권고 — 확정 시 Task 4 테스트 고정
2. **Redis override TTL 7일 vs 무기한**: 7일 권고(관찰 기간 내 재발동 방지), 무기한 시 관리자 수동 DEL 필수
3. **자동 롤백 발동 후 스케줄러 정지 여부**: "관리자 확인 대기"만 수행하고 스케줄러는 계속 돌림 (현재 설계). 중단 원하면 별도 플래그 필요

### 제외 결정

- 2차 `pass_threshold` 완화 (확정 #9: 75.0 유지) — Sprint 3 이후 재평가
- 시간대 슬라이딩 MIN_VOLUME_FLOOR (확정 #14 전원 거부)
- prev_close_time_guard 13:00→14:00 연장 (확정 #15 전원 거부)

---

## 참고 파일

- Phase 루트: `docs/phase/phase8.5/phase8.5.md` (확정 파라미터 #1~#26)
- Sprint 1.5: `docs/phase/phase8.5/sprint1.5/sprint1.5.md` (shadow evaluation 원칙)
- Sprint 1: `docs/phase/phase8.5/sprint1/sprint1.md` (관측성 기반)
- 전략: `backend/modules/trading/strategies/momentum_breakout.py`
- 스크리너: `backend/modules/screening/realtime_screener.py`
- 엔진: `backend/modules/trading/engine.py`
- 설정: `backend/core/config.py`
- 스케줄러: `backend/modules/collector/scheduler.py`
- 거래일 판정: `backend/modules/collector/trading_calendar.py` (Phase 4.6 Sprint 2)
- 프론트 heatmap 카드: `frontend/components/diagnostics/stage-heatmap-card.tsx`, `shadow-heatmap-card.tsx`
