# Sprint 1.5: 전략 필터 shadow evaluation (Phase 8.5)

**Goal:** `MomentumBreakoutStrategy.generate_signal()`의 각 stage를 **순차 short-circuit과 독립적으로 병렬 평가**하여 필터별 pass/fail 카운터를 별도 Redis 네임스페이스에 기록한다. Sprint 2(풀 하한 폴백 + 동적 `MIN_VOLUME_FLOOR`) 의사결정 근거 데이터를 확보한다.

**Architecture:** Sprint 1 `_metrics.py` 패턴을 계승하여 `record_shadow_stage()` 헬퍼를 추가한다. `generate_signal()` 진입 시점에 **주문 결정 이전에** 각 stage 조건을 독립적으로 평가하는 `_shadow_evaluate()` 메서드를 호출. shadow 평가는 snapshot만 읽고 side-effect는 Redis counter 기록뿐. 예외는 전량 내부 흡수 → 주문 경로에 영향 0. TDD 회귀 테스트로 "주문 경로 불변" 증명.

**Tech Stack:** Python 3.12 / FastAPI / Redis 7 (async) / pytest-asyncio / Next.js 16 / React 19 / Tailwind 4 / SWR

**Sprint 기간:** 2026-04-23 ~ 2026-04-23 (당일 배포)
**상태:** ✅ 완료 (2026-04-23)
**이전 스프린트:** Phase 8.5 Sprint 1 (✅ 완료, PR #162)
**다음 스프린트:** Phase 8.5 Sprint 2 (풀 하한 폴백 + 동적 `MIN_VOLUME_FLOOR`)
**브랜치명:** `chore/phase8.5-shadow-evaluation` (bash-guard self-mod 차단으로 chore/ prefix 사용)
**PR:** https://github.com/frogy95/stockbot/pull/168

---

## 제외 범위

이 스프린트에서 **하지 않는 것**:

- 각 필터값 분포 히스토그램 (adjusted_ratio, breakout_pct, confidence의 값 분포) — Option B, 별도 Sprint
- 폴백 발동 통계 카드 실구현 — Sprint 2 범위
- `MIN_VOLUME_FLOOR` / `pass_threshold` / `prev_close_time_guard` 등 **임계값 조정** — Sprint 2 범위
- 2차 스크리닝 풀 하한 폴백 — Sprint 2 범위
- shadow 카운터 → DB 일별 집계 batch (APScheduler 16:00) — Redis 7일 TTL만으로 관찰, 필요 시 Sprint 2에서 추가
- Alembic 마이그레이션 — 신규 테이블 없음 (Redis 전용)

**핵심 제약 (절대 불변)**:

- `generate_signal()`의 **반환값·반환 시점·stage 판정 순서·임계값**을 절대 변경하지 않는다. shadow 평가는 기존 `_reject`/성공 반환 경로와 **완전히 병렬**로 추가되며, 기존 `record_stage()` 호출은 그대로 유지한다.
- shadow 평가 내부 예외는 `_metrics.py` 패턴과 동일하게 logger.warning으로 흡수. 어떤 예외도 `generate_signal()` 상위로 전파되면 안 된다.
- shadow 평가는 `TradeSignalData` / `SignalGenerator` / `engine` / `order_manager`를 **절대 import/호출하지 않는다** (Sprint 1 `_metrics.py` 순수성 원칙 계승).
- 기존 `STRATEGY_STAGE_PREFIX`(Sprint 1 도입) 키는 네임스페이스/스키마를 변경하지 않는다. shadow 카운터는 **신규 네임스페이스** `metrics:shadow:stage`를 사용한다.

---

## 의미 차이 문서화 (중요)

| 항목 | `STRATEGY_STAGE_PREFIX` (Sprint 1 기존) | `SHADOW_STAGE_PREFIX` (Sprint 1.5 신규) |
|------|------------------------------------------|------------------------------------------|
| 키 형태 | `metrics:strategy:stage:{date}:{stage}:{hh:mm}` | `metrics:shadow:stage:{date}:{stage}:{pass\|fail}:{hh:mm}` |
| `pass` 의미 | **모든 stage 통과하여 신호 발생** (1회만 incr) | **해당 stage 단독 조건 충족** (stage마다 독립 평가) |
| reject 의미 | **첫 번째 실패 stage만 기록** (short-circuit) | **모든 stage를 독립 평가, stage마다 pass/fail 중 하나 기록** |
| 누락 종목 수 | 첫 실패 후 나머지 stage는 표본 0 | 모든 stage가 전체 표본 확보 |
| 용도 | 실제 주문 경로 관측성 (병목 식별) | 개별 필터 교정 필요성 판단 (데이터 기반 튜닝) |

두 카운터는 **서로 다른 질문에 답한다**. 기존 heatmap 카드는 "실제로 어디서 컷됐는가"를, shadow 카드는 "각 필터를 독립적으로 봤을 때 얼마나 컷하는가"를 보여준다.

---

## Tier 결정 중복 처리 방침

shadow 평가에서도 `breakout_ref` 결정은 `gap_rate` 기반 tier 분기(gap_open / prev_high / prev_close)가 필요하다. 처리 방침:

- `_resolve_tier(snapshot, gap_rate)`는 **순수 함수**(snapshot만 읽음, side-effect 없음)이므로 shadow 평가에서 **중복 호출 허용**.
- `_now_kst()`는 한 번만 호출하여 shadow/real 평가에 공유 (두 경로의 시간 기준 일치 보장).
- `prev_close_time_guard`(13:00 이후 prev_close tier 차단)는 shadow에서도 **독립 평가**. 이 조건은 사실상 "tier가 prev_close이면서 13:00 이후인지"만 보므로 다른 필터들과 직교한다.

---

## 평가 대상 8개 Shadow Stage

| # | Stage | 독립 평가 조건 |
|---|-------|---------------|
| 1 | `prev_close_time_guard` | `tier == "prev_close" and now_kst >= 13:00` → fail |
| 2 | `breakout` | `current_price > breakout_ref` → pass |
| 3 | `prev_volume_zero` | `prev_volume > 0` → pass |
| 4 | `min_volume_floor` | `volume >= prev_volume * 0.5` → pass (prev_volume=0이면 평가 skip) |
| 5 | `volume_threshold` | `adjusted_ratio >= volume_threshold` → pass (동적 threshold 재계산) |
| 6 | `trade_strength` | `trade_strength >= 100.0` → pass |
| 7 | `atr_filter` | `atr / current_price <= 0.05` → pass |
| 8 | `confidence` | 4팩터 재계산 후 `confidence >= 0.6` → pass (tier cap 적용) |

> **skip 규칙**: 계산 불가 시점(예: prev_volume=0일 때 min_volume_floor 이하, breakout_ref=0일 때 volume_threshold 이하)은 해당 stage를 **기록하지 않음** (`fail`도 `pass`도 아님). 이렇게 해야 표본이 오염되지 않는다.

---

## 실행 플랜

의존성 그래프:

```
Task 1 (TDD 회귀 테스트 작성 — shadow 추가로 주문 경로 불변 증명)
  └─> Task 2 (shadow 헬퍼 + metrics_keys + _shadow_evaluate 구현)
        └─> Task 3 (metrics API + 프론트 카드)
              └─> Task 4 (통합 검증 + 커밋)
```

### Phase 1 (순차 — TDD)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | **회귀 테스트 선작성**: 기존 `test_momentum_breakout.py`의 반환값이 shadow 추가 후에도 바이트 단위 동일함을 증명하는 fixture 확장 | 백엔드 | `systematic-debugging` |

### Phase 2 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | `record_shadow_stage()` 헬퍼, `SHADOW_STAGE_PREFIX`, `_shadow_evaluate()` 구현 | 백엔드 | — |

### Phase 3 (병렬 가능 — 파일 소유권 분리)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3a | `/api/v1/metrics/shadow-heatmap` API 추가 | 백엔드 | — |
| Task 3b | `components/diagnostics/shadow-heatmap-card.tsx` 신규 + `/diagnostics` 페이지에 배치 | 프론트엔드 | `frontend-design` |

### Phase 4 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | pytest 전체 통과 + `curl` API 확인 + Playwright UI 스모크 + 커밋 | 전체 | — |

---

### Task 1: 회귀 테스트 선작성 (주문 경로 불변 증명)

**skill:** `systematic-debugging`

**목적**: Task 2 구현 전에 "shadow 추가가 기존 반환값에 영향 주지 않음"을 실패하는 테스트로 고정한다. TDD로 회귀 안전망 확보.

**Files:**
- Modify: `backend/tests/test_momentum_breakout_metrics.py` (신규 테스트 클래스 추가)

**Step 1: 기존 테스트 재확인**
- `backend/tests/test_momentum_breakout.py`와 `backend/tests/test_momentum_breakout_metrics.py`를 읽어 FakeRedis/FakeSession/snapshot fixture 재사용 지점 파악
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py tests/test_momentum_breakout_metrics.py -v`
- 예상: 기존 테스트 전체 PASS

**Step 2: shadow 비활성(None redis) 시 기존 반환 동일성 테스트 추가**
- `TestShadowEvaluationInvariance` 클래스 추가
- 각 stage별 snapshot으로 `generate_signal()` 호출 → 반환값이 Sprint 1 이전과 **완전히 동일**한지 바이트 단위 비교
  - `test_shadow_does_not_affect_breakout_reject`: `current_price <= breakout_ref` snapshot → `RejectedSignal(stage="breakout")` 그대로
  - `test_shadow_does_not_affect_success_signal`: 모든 조건 통과 snapshot → `TradeSignalData` + confidence/reason dict 완전 동일
  - `test_shadow_exception_does_not_propagate`: `record_shadow_stage`가 예외 던져도 상위 반환값 영향 없음 (monkeypatch로 예외 주입)
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout_metrics.py::TestShadowEvaluationInvariance -v`
- 예상: **FAIL (아직 shadow 구현 없으므로 `record_shadow_stage` 미존재) — 또는 PASS이지만 shadow 카운터 비어있음 검증 누락**

**Step 3: shadow 카운터 증가 검증 테스트 추가**
- `test_shadow_records_all_8_stages_regardless_of_short_circuit`:
  - snapshot: `current_price <= breakout_ref`로 기존 경로가 즉시 `breakout`에서 reject하는 케이스
  - FakeRedis로 `generate_signal()` 호출 후 `counters` 조사
  - shadow 네임스페이스(`metrics:shadow:stage:*`) 키가 **breakout 외 stage들에 대해서도 존재**하는지 검증
  - 기존 `metrics:strategy:stage:*`(Sprint 1) 키는 **breakout 1건만** 존재하는지 검증 (기존 동작 유지 확인)
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout_metrics.py -v -k "shadow"`
- 예상: FAIL (구현 전)

**Step 4: 커밋**
```
git add backend/tests/test_momentum_breakout_metrics.py
git commit -m "test(phase8.5-sprint1.5): task1 — shadow evaluation 회귀 테스트 선작성 (TDD RED)"
```

**완료 기준:**
- ✅ 회귀 테스트 4개가 추가되고, TDD RED 상태로 커밋됨 (커밋: 694de7c)
- ✅ 기존 테스트 전체는 여전히 PASS (shadow 관련 수정 없음)

---

### Task 2: shadow 헬퍼 + stage 독립 평가 구현

**skill:** — (`karpathy-guidelines` CLAUDE.md 전역 자동 적용)

**Files:**
- Modify: `backend/core/metrics_keys.py` (상수 + 헬퍼 함수 추가)
- Modify: `backend/modules/trading/strategies/_metrics.py` (`record_shadow_stage` 추가)
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (`_shadow_evaluate` 추가, `generate_signal()` 진입부에서 1회 호출)

**Step 1: `metrics_keys.py`에 상수 + 키 생성 함수 추가**
- `SHADOW_STAGE_PREFIX = "metrics:shadow:stage"` 추가
- `SHADOW_TRACKED_STAGES`: 기존 `TRACKED_STAGES`에서 `"pass"`, `"no_data"` 제외한 8개 stage tuple
- `shadow_stage_counter_key(d, stage, outcome, hour_min) -> str`:
  - 반환: `f"{SHADOW_STAGE_PREFIX}:{_date_str(d)}:{stage}:{outcome}:{hour_min}"` (outcome ∈ {"pass","fail"})
- 검증: 신규 테스트 `backend/tests/test_metrics_keys.py`에서 키 포맷 단위 테스트 추가 (기존 파일 있으면 class만 추가)
- 예상: PASS

**Step 2: `_metrics.py`에 `record_shadow_stage()` 추가**
- 시그니처: `async def record_shadow_stage(redis_client, stage: str, passed: bool, now_kst: datetime | None = None) -> None`
- 동작:
  - `redis_client is None` → return
  - `stage not in SHADOW_TRACKED_STAGES` → logger.debug 후 return (안전장치)
  - outcome = "pass" if passed else "fail"
  - key = `shadow_stage_counter_key(today, stage, outcome, hour_min)`
  - `await redis_client.incr(key, ttl=STAGE_COUNTER_TTL)` (TTL 7일, 기존 상수 재사용)
  - **TOP_REJECT 리스트에는 기록하지 않음** (shadow는 카운터만)
  - 모든 예외는 `logger.warning("record_shadow_stage failed ...", exc_info=True)`로 흡수
- 검증: `backend/tests/test_momentum_breakout_metrics.py`에 단위 테스트 추가 (FakeRedis로 counters 확인 + 예외 흡수 확인)
- 예상: PASS

**Step 3: `momentum_breakout.py`에 `_shadow_evaluate()` 메서드 추가**
- 시그니처: `async def _shadow_evaluate(self, snapshot: MarketSnapshot, now_kst: datetime) -> None`
- 동작 (모든 계산은 snapshot + now_kst만 사용, 기존 상수/로직과 일치):
  1. `gap_rate`, `(breakout_ref, tier)` 계산 (`_resolve_tier` 재사용)
  2. `prev_close_time_guard`: `tier=="prev_close" and now_kst.time() >= PREV_CLOSE_TIER_BLOCK_TIME` → fail, else pass
  3. `breakout`: `current_price > breakout_ref` → pass, else fail
  4. `prev_volume_zero`: `prev_volume > 0` → pass, else fail
  5. `prev_volume == 0`이면 이후 volume 관련 stage **skip** (기록 안 함)
  6. `min_volume_floor`: `volume >= prev_volume * MIN_VOLUME_FLOOR` → pass/fail
  7. `volume_threshold`: `adjusted_ratio` 재계산 + tier별 동적 threshold(기존 로직 복제) → pass/fail
     - `breakout_ref <= 0`이면 skip
  8. `trade_strength`: `>= 100.0` → pass/fail
  9. `atr_filter`: `calc_volatility_factor` 호출 (기존 import 재사용) → `atr/current_price <= 0.05` → pass/fail
     - `current_price <= 0`이면 skip
  10. `confidence`: 4팩터 재계산(tier momentum_multiplier 포함) → cap 적용 후 `>= MIN_CONFIDENCE` → pass/fail
- 전체 메서드를 `try/except Exception: logger.warning(..., exc_info=True)` 감쌈 — 어떤 예외도 상위로 전파 금지
- 검증: Step 2 커밋 포함 후 TDD RED 테스트 실행 → GREEN 전환
- 예상: `tests/test_momentum_breakout_metrics.py` 전체 PASS

**Step 4: `generate_signal()` 진입부에 shadow 호출 1줄 추가**
- `generate_signal()`의 **첫 줄**(gap_rate 계산 직전)에 아래 추가:
  ```python
  now_kst = _now_kst()
  await self._shadow_evaluate(snapshot, now_kst)
  ```
- 기존 `_reject()`/`record_stage(...pass...)` 호출의 `now_kst=_now_kst()`도 재사용하도록 변수 공유 (선택 — 기존 동작 동일하므로 리팩토링 생략 가능)
- **주의**: gap_rate/tier 계산은 shadow 내부에서 한 번, 기존 코드에서 또 한 번 발생 → 성능 영향 미미(순수 계산), 허용
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py tests/test_momentum_breakout_metrics.py -v`
- 예상: 모든 테스트 PASS (GREEN)

**Step 5: simplify 후 커밋**
```
git add backend/core/metrics_keys.py backend/modules/trading/strategies/_metrics.py backend/modules/trading/strategies/momentum_breakout.py backend/tests/test_metrics_keys.py backend/tests/test_momentum_breakout_metrics.py
git commit -m "feat(phase8.5-sprint1.5): task2 — shadow evaluation 헬퍼 + 8 stage 독립 평가 구현 (TDD GREEN)"
```

**완료 기준:**
- ✅ Task 1의 회귀 테스트 4개 전부 GREEN (커밋: 0f6157e)
- ✅ 기존 `test_momentum_breakout.py` 전체 회귀 PASS
- ✅ shadow 카운터가 Redis에 `metrics:shadow:stage:{date}:{stage}:{pass|fail}:{hm}` 키로 기록됨

---

### Task 3a: `/api/v1/metrics/shadow-heatmap` API

**Files:**
- Modify: `backend/api/routes/metrics.py` (엔드포인트 1개 추가)
- Modify: `backend/tests/test_metrics_api.py` 또는 신규 — shadow API 테스트 (기존 파일 있으면 class 추가)

**Step 1: 응답 모델 정의**
- `ShadowStageCell(BaseModel)`: `stage: str`, `hour_min: str`, `pass_count: int`, `fail_count: int`, `pass_rate: float` (0.0~1.0, 표본 0이면 None)
- `ShadowHeatmapResponse(BaseModel)`: `date: str`, `cells: list[ShadowStageCell]`

**Step 2: 엔드포인트 구현**
- `GET /api/v1/metrics/shadow-heatmap?date=today`
- 동작:
  - `SHADOW_STAGE_PREFIX:{date}:*` 스캔
  - suffix 파싱: `{stage}:{outcome}:{hh}:{mm}`
  - (stage, hour_min) 키로 pass/fail 합산 후 pass_rate 계산
  - 기존 `stage_heatmap` 엔드포인트의 `scan_keys`/`get` 패턴 그대로 재사용
- DB fallback은 이번 Sprint에서 제외 (Redis 7일 TTL만으로 충분, DB 집계 batch는 Sprint 2 이후)

**Step 3: 테스트 추가**
- `test_shadow_heatmap_returns_pass_rate_per_stage`: FakeRedis에 pass/fail 카운터 직접 세팅 후 API 응답 검증
- 검증: `docker compose exec backend pytest tests/test_metrics_api.py -v -k "shadow"`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/api/routes/metrics.py backend/tests/test_metrics_api.py
git commit -m "feat(phase8.5-sprint1.5): task3a — shadow-heatmap API 엔드포인트 추가"
```

**완료 기준:**
- ✅ `curl -s http://localhost:8000/api/v1/metrics/shadow-heatmap | jq .` 정상 JSON 응답 (커밋: 94c8e27)
- ✅ pytest 통과

---

### Task 3b: 프론트 `ShadowHeatmapCard` 컴포넌트

**skill:** `frontend-design`

**Files:**
- Create: `frontend/components/diagnostics/shadow-heatmap-card.tsx`
- Modify: `frontend/app/(dashboard)/diagnostics/page.tsx` (카드 배치 추가)
- Modify: `frontend/lib/api.ts` 또는 `frontend/lib/metrics.ts` (타입 정의 및 fetch 함수 — 기존 패턴 참조)

**Step 1: 디자인 탐색**
- 기존 `stage-heatmap-card.tsx` 구조/스타일 확인
- shadow는 각 셀에 **pass/fail 2채널 시각화** — 예: 셀을 pass_rate 기반 색상(빨강=낮음, 초록=높음) + 툴팁에 `pass / fail / pass_rate %` 표시
- 폭은 기존 heatmap과 동일 그리드 (10분 버킷 × stage 8행)

**Step 2: 구현**
- SWR로 `/api/v1/metrics/shadow-heatmap` 폴링 (30초, 기존 refreshInterval 패턴 재사용)
- stage 축: Task 2의 `SHADOW_TRACKED_STAGES` 순서와 맞춰 하드코딩 또는 API 응답 순서 신뢰
- 시간 축: 기존 `stage-heatmap-card.tsx`의 `HOUR_MINS` 상수 재사용 (09:00~15:20 10분 버킷)
- 셀 색상: `pass_rate`가 null이면 회색(표본 0), 숫자이면 `hsl((pass_rate*120), 70%, 50%)` 등 HSL 보간
- 한국 증시 색상 관례와 상충하지 않음 (pass/fail은 상승/하락이 아니므로 빨강=낮음, 초록=높음 직관 사용)

**Step 3: `diagnostics/page.tsx` 배치**
- 기존 4개 카드 아래 새 행에 `<ShadowHeatmapCard />` 추가
- 카드 제목: "Shadow 필터 평가 (Phase 8.5 Sprint 1.5)"
- 부제: "각 필터를 독립 평가한 pass/fail 분포 — 실제 주문 경로와 무관"

**Step 4: 타입 체크 + 커밋**
- 검증: `cd frontend && npx tsc --noEmit`
- 예상: 에러 없음
```
git add frontend/components/diagnostics/shadow-heatmap-card.tsx frontend/app/(dashboard)/diagnostics/page.tsx frontend/lib/
git commit -m "feat(phase8.5-sprint1.5): task3b — Shadow 필터 heatmap 카드 추가"
```

**완료 기준:**
- ✅ `/diagnostics` 페이지에서 Shadow Heatmap 카드 렌더링 (커밋: 61edfb6)
- ✅ 시간대별 셀에 pass/fail 툴팁 표시

---

### Task 4: 통합 검증 + Sprint 1.5 마무리

**Files:**
- Modify: `deploy.md` (수동 검증 플레이스홀더만)
- Modify: `ROADMAP.md`, `docs/index.json`, sprint-planner MEMORY.md — sprint-close agent에서 처리 (Task에서는 생략)

**Step 1: 백엔드 pytest 전체**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전 sprint 회귀 없음 (Sprint 1 기존 테스트 전체 PASS + 신규 테스트 PASS)

**Step 2: API curl 확인**
- ```
  curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/metrics/shadow-heatmap | jq .
  curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/metrics/stage-heatmap | jq .
  ```
- 예상: 둘 다 200 + JSON. shadow의 `cells` 배열은 실제 호출 시 채워짐 (전략 호출 안 되면 빈 배열)

**Step 3: Playwright 스모크**
- `/diagnostics` 페이지 접속 → 5개 카드 모두 렌더링되는지 스크린샷
- 저장: `docs/phase/phase8.5/sprint1.5/diagnostics-page.png`

**Step 4: 프론트엔드 타입 체크**
- 검증: `cd frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 5: 주문 경로 불변 재확인**
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py tests/test_momentum_breakout_metrics.py -v`
- 예상: 전 테스트 PASS (회귀 0건)

**Step 6: 커밋 + sprint-close 안내**
```
git add deploy.md docs/phase/phase8.5/sprint1.5/
git commit -m "docs(phase8.5-sprint1.5): task4 — 통합 검증 스크린샷 + deploy.md 업데이트"
```
- 사용자에게 sprint-close agent 호출 안내

**완료 기준:**
- ✅ pytest 전체 PASS (shadow 4개 + 기존 회귀 GREEN, 커밋: c1e32a2)
- ✅ shadow-heatmap API 응답 정상 (JWT 인증 포함 200 확인)
- ✅ `/diagnostics` UI에 신규 카드 렌더링 확인
- ✅ `test_momentum_breakout*.py` 회귀 0건

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS, 신규 테스트 4~5개 추가 |
| 주문 경로 불변 | `pytest tests/test_momentum_breakout.py -v` | Sprint 1 이전과 동일 PASS |
| shadow API | `curl .../metrics/shadow-heatmap` | 200 + JSON `cells[]` |
| 기존 heatmap API | `curl .../metrics/stage-heatmap` | Sprint 1과 동일 응답 (변경 없음) |
| 프론트 타입체크 | `cd frontend && npx tsc --noEmit` | 에러 없음 |
| Playwright | `/diagnostics` 접속 | 5개 카드 (기존 4 + shadow 1) 렌더링 |
| Redis 키 샘플 | `docker compose exec redis redis-cli --scan --pattern 'metrics:shadow:*' | head` | 키 존재 확인 (전략 실행 후) |

---

## 미해결 사항 / 리스크

### ⚠️ 리스크

1. **tier 결정 중복 계산으로 인한 미세 CPU 오버헤드** — `_shadow_evaluate`와 `generate_signal` 본체에서 `_resolve_tier`/`calc_volatility_factor`가 각각 1회씩 호출됨. 5분봉 signal_generator 30초 주기 + 풀 ≤5 종목이므로 무시 가능. Sprint 2 이후 프로파일링 필요 시 shadow 결과를 dict로 반환하여 본체에서 재사용하는 리팩토링 가능 — 이번 Sprint에서는 **하지 않는다** (주문 경로 변경 금지 원칙).
2. **shadow 평가 버그가 카운터 왜곡을 일으킬 수 있음** — Task 1 TDD로 shadow 실패가 주문 경로에 영향 없음은 증명되나, shadow 카운터 자체의 정확성은 단위 테스트 표본에 의존. Sprint 2 의사결정 전 2거래일 관찰에서 pass_rate 수치가 상식적인지 수동 확인 필요 (deploy.md에 기재).
3. **shadow 카드를 운영자가 "실제 필터 통계"로 오독할 가능성** — 카드 부제 명시 + Phase 8.5 Sprint 1.5 명칭 병기로 완화. sprint-review에서 UI 카피 검증.

### 제외 결정

- `prev_close_time_guard`는 shadow에서 독립 평가 채택 (사용자 요구 반영). 시간 조건이므로 다른 필터와 무관하게 평가 의미가 있음.
- Option B(필터값 분포 히스토그램)는 본 Sprint 제외. shadow 평가 내부에서 계산된 `adjusted_ratio`/`breakout_pct`/`confidence`는 **기록하지 않음** — Sprint 2 이후 필요 시 별 Sprint에서 추가.

---

## 참고 파일

- Sprint 1 설계 원칙: `backend/modules/trading/strategies/_metrics.py`
- 기존 전략: `backend/modules/trading/strategies/momentum_breakout.py`
- 키 규약: `backend/core/metrics_keys.py`
- 기존 API: `backend/api/routes/metrics.py`
- 기존 카드: `frontend/components/diagnostics/stage-heatmap-card.tsx`
- 기존 테스트 fixture: `backend/tests/test_momentum_breakout_metrics.py`
- Phase 루트: `docs/phase/phase8.5/phase8.5.md`
- Sprint 1: `docs/phase/phase8.5/sprint1/sprint1.md`
