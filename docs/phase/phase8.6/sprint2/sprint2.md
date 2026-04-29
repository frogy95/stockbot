# Sprint 2: 병렬 OR tier 분리 + ATR 분위수 캘리브레이션 (Phase 8.6)

**Goal:** 직렬 AND 게이트로 묶여 있던 3 tier(`gap_open`/`prev_high`/`prev_close`)를 **병렬 OR 다중 진입 경로**로 구조 재설계하고, 고정 ATR 5% 상한을 **KOSPI200 분위수 기반 동적 상한 + 하한 0.025**로 전환하여 분기 D의 "곱셈 0" 결함을 제거한다.

**Architecture:**
- `MomentumBreakoutStrategy.generate_signal()`을 tier 분기 → 공통 게이트 직렬 구조에서, **tier별 독립 sub-게이트**(각각 ATR / breakout / 시간가드 중 필요한 것만 적용)를 평가한 뒤 **하나라도 통과하면 신호 발행**하는 구조로 분리한다.
- 매일 09:00 KOSPI200 ATR 20일 평균 분포의 80퍼센타일을 산출하여 `ATR_CEIL_DYNAMIC = min(0.08, P80×1.2)`를 Redis에 캐싱한다 (`metrics:atr:ceil:{date}`). 폴백 종목은 항상 `ATR_CEIL_FALLBACK=0.05` 고정.
- 모든 신규 동작은 env 토글(`PARALLEL_OR_TIER_ENABLED`, `ATR_CALIBRATION_ENABLED`)로 1줄 원복 가능. 토글 OFF 시 Sprint 1 종료 시점 동작 100% 복원.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Redis (asyncio), APScheduler CronTrigger, Next.js 16 (shadcn/ui), pytest-asyncio.

**Sprint 기간:** 2026-04-29 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 8.6 Sprint 1 (DoR G1·G2·G3 + Phase 7.0 잠금 + 폴백 5종 + 09~11시 floor 0.3, 13 + 9 + 5 tests PASS, PR #181 머지)
**브랜치명:** `phase8.6-sprint2`

---

## 제외 범위

- ❌ **`volume_surge` tier 신설** — Sprint 3에서 호가창 스트림 인프라와 함께 도입
- ❌ **시간대 필터 11:30~13:00 floor 0.7 / 14:30+ 진입 금지** — Sprint 3에서 도입 (Sprint 2의 09~11시 슬라이딩만 유지)
- ❌ **Walk-forward 60일 백테스트** — Sprint 4
- ❌ **시뮬↔실측 KS 자동 감지** — Sprint 4
- ❌ **Phase 7.0 LIVE 파라미터 변경** — 코드 잠금 유지 (`max_position=2`, `position_size=5%`, `daily_max_loss=-2%`, `emergency_stop=-3%`)
- ❌ **2차 스크리닝 pass_threshold(75) 변경** — 분기 D 진단상 임계는 무결, 구조 변경이 우선
- ❌ **신호 우선순위 큐 / 일일 신호 한도 10건 강화** — Phase 7.2 한도 그대로 유지 (Sprint 3 이후 모니터링)

---

## 사용자 확정 필요 항목

> 본 Sprint 착수 전에 사용자 답변이 필요한 항목 (Phase 문서 §9.3 미해결 사항 + Sprint 2 신규 발견):

1. **ATR 캘리브레이션 데이터 소스**: KOSPI200 종목 일봉(20일 평균 ATR)을 어디서 읽을지 — `market_data` 테이블의 `source IN ('data_go_kr', 'kis_daily')` 사용 OK? KOSPI200 마스터는 `stocks.is_kospi200=True` 플래그 또는 별도 리스트(파일/DB)로 관리할지 결정 필요.
2. **9:00 캘리브레이션 잡 실패 시 폴백 정책**: KOSPI200 분위수 산출 실패 시 → (a) 직전 영업일 캐시 재사용 (TTL 7일), (b) `ATR_CEIL_HARD=0.08` 정적 사용, (c) tier 분리 자체 비활성화. **권고: (a)→(b) 순차 폴백** (자동 비활성화는 분기 D 회귀 위험).
3. **`gap_open` tier ATR 우회 시 하한 적용 여부**: ATR 상한은 우회하나 **하한 0.025는 적용**할지(=극저변동 종목은 gap_open이어도 거름) — 권고: **하한은 적용** (분기 D는 상한 문제, 하한은 단타 부적합 종목 차단 목적이라 일관 적용).
4. **병렬 OR 결합 시 신호 메타데이터**: 한 종목이 동시에 2 tier(예: gap_open + prev_high) 통과 시 → (a) 우선순위 큐(gap_open > prev_high > prev_close)로 단일 신호, (b) tier 합산 후 단일 신호에 `matched_tiers=["gap_open","prev_high"]` 기록. **권고: (b)** (G-D 페어와이즈 상관 측정용 데이터 보존).
5. **ATR 캘리브레이션 윈도우 크기**: Phase 문서 "20일 평균"이 (a) 각 종목별 ATR 20일 이동평균을 KOSPI200 단면으로 모은 분포인지, (b) 직전 20일간 매일의 KOSPI200 ATR 단면 분포를 모두 합친 분포인지 — 권고: **(a)** (종목 단면 평활화 후 분위수 — 분포 안정).

위 5개 답변 전까지는 **Step 1(테스트 작성)까지만 진행**하고 Step 2 이후는 사용자 확정을 받아 진행한다.

---

## 신규 환경변수 (deploy.md 수동 검증 항목)

Sprint 2에서 추가되는 Railway 환경변수 (총 6개):

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `PARALLEL_OR_TIER_ENABLED` | `true` | 병렬 OR tier 분기 활성화. `false` 시 Sprint 1 직렬 동작 복원 |
| `ATR_CALIBRATION_ENABLED` | `true` | 09:00 ATR 캘리브레이션 잡 활성화. `false` 시 `ATR_CEIL_HARD` 정적 사용 |
| `ATR_FLOOR` | `0.025` | ATR 하한 (모든 tier 공통, 폴백 종목 포함). 박퀀트 §3.1 |
| `ATR_CEIL_HARD` | `0.08` | ATR 상한 절대 한계 (동적 상한이 이 값 초과 금지) |
| `ATR_CEIL_FALLBACK` | `0.05` | 폴백 종목 ATR 상한 (동적 미적용, 리스크 §3 G4) |
| `ATR_CALIBRATION_WINDOW_DAYS` | `20` | KOSPI200 ATR 평균 윈도우 (Phase §5.2 #6) |

**deploy.md 수동 검증 추가 항목** (sprint-close 시 기록):
- `Railway 환경변수 추가 확인: PARALLEL_OR_TIER_ENABLED, ATR_CALIBRATION_ENABLED, ATR_FLOOR, ATR_CEIL_HARD, ATR_CEIL_FALLBACK, ATR_CALIBRATION_WINDOW_DAYS`

---

## 실행 플랜

### Phase 1 (순차 — 인프라 / config 선행)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | env 추가 + ATR 상수 잠금 | 백엔드 | — |

### Phase 2 (순차 — Task 2가 Task 3의 전제, Task 3가 Task 4의 전제)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | ATR 캘리브레이션 모듈 + 09:00 잡 | 백엔드 | `feature-dev:feature-dev` |
| Task 3 | 병렬 OR tier 분리 (`MomentumBreakoutStrategy` 재구조화) | 백엔드 | `feature-dev:feature-dev` |
| Task 4 | tier 페어와이즈 상관 메트릭 + M-G-D 카운터 | 백엔드 | — |

### Phase 3 (병렬 가능 — Task 5/6는 파일 미겹침)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | tier-correlation-card UI | 프론트엔드 | `frontend-design` |
| Task 6 | atr-distribution-card UI | 프론트엔드 | `frontend-design` |

### Phase 4 (순차 — 통합 검증)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 7 | 통합 회귀 + Paper 1거래일 + deploy.md 환경변수 등록 | 전체 | `verification-before-completion` |

> **팀 실행**: "Phase 3을 팀으로 실행해줘"라고 요청하면 프론트엔드 팀원이 Task 5·6을 병렬 구현. 백엔드 Task 1~4는 의존성 직렬이므로 단일 작업자 권장.

---

## Task 상세

### Task 1: env 추가 + ATR 상수 분리

**Files:**
- Modify: `backend/core/config.py` (env 6종 추가)
- Modify: `backend/.env.example` (동일 6종 + 주석)
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (`ATR_FILTER_PCT=0.05` 상수 → `_resolve_atr_ceil(snapshot, tier, redis_client, is_fallback)` 함수로 추출, 기존 동작 유지)
- Test: `backend/tests/strategies/test_atr_resolver.py` (신규)

**Step 1: 테스트 작성**
- `tests/strategies/test_atr_resolver.py` 생성
- 검증 케이스:
  - `is_fallback=True` → `ATR_CEIL_FALLBACK=0.05` 반환 (동적 미적용)
  - `tier="gap_open"` → ATR 우회 (반환값 = `float("inf")`)
  - `tier IN ("prev_high", "prev_close")` + Redis `metrics:atr:ceil:2026-04-30="0.072"` → `0.072` 반환
  - Redis 키 부재 시 → `ATR_CEIL_HARD=0.08` 폴백
  - `ATR_CALIBRATION_ENABLED=false` → 동적 미적용, `ATR_CEIL_HARD` 사용
  - `ATR_FLOOR=0.025` 하한 — 모든 tier(gap_open 포함)에서 ATR < 0.025 시 `False` 반환
- 검증: `docker compose exec backend pytest tests/strategies/test_atr_resolver.py -v`
- 예상: FAIL (`_resolve_atr_ceil` 미존재)

**Step 2: config 환경변수 추가**
- `core/config.py` Settings 클래스에 6종 필드 추가 (Phase 8.6 Sprint 2 주석)
- `.env.example`에 동일 키 + 한글 주석 작성
- 검증: `docker compose exec backend python -c "from core.config import settings; print(settings.ATR_FLOOR, settings.ATR_CEIL_HARD)"`
- 예상: `0.025 0.08`

**Step 3: ATR resolver 함수 추출**
- `modules/trading/strategies/momentum_breakout.py`에 `async def _resolve_atr_ceil(snapshot, tier, redis_client, is_fallback) -> float | None` 추가
- 반환값 의미: `None` = 우회(상한 미적용), `float` = 상한값
- 기존 `ATR_FILTER_PCT = 0.05` 상수는 유지(Sprint 1 회귀 방지) + 새 함수가 호출자(Step 4 Task 3에서 사용)에 우선 적용
- 검증: `docker compose exec backend pytest tests/strategies/test_atr_resolver.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/core/config.py backend/.env.example backend/modules/trading/strategies/momentum_breakout.py backend/tests/strategies/test_atr_resolver.py
git commit -m "feat(phase8.6-sprint2): task1 — ATR resolver 함수 추출 + env 6종 추가 (병렬 OR 사전 작업)"
```

**완료 기준:**
- ⬜ pytest `test_atr_resolver.py` 6 케이스 PASS
- ⬜ 기존 `test_momentum_breakout.py` 회귀 0건 (PARALLEL_OR_TIER_ENABLED=true 기본값에서도 직렬 동작 유지 — Task 3 전까지)
- ⬜ `.env.example` 6종 추가 확인

---

### Task 2: ATR 캘리브레이션 모듈 + 09:00 스케줄 잡

**skill:** `feature-dev:feature-dev` (KIS 일봉 / KOSPI200 마스터 / Redis / Scheduler 4개 모듈 통합)

**Files:**
- Create: `backend/modules/screening/atr_calibration.py`
- Modify: `backend/modules/collector/scheduler.py` (09:00 잡 등록)
- Modify: `backend/modules/collector/scheduler.py` start() 에 `_atr_calibration` job 추가
- Test: `backend/tests/screening/test_atr_calibration.py`

**Step 1: 테스트 작성**
- `tests/screening/test_atr_calibration.py` 생성
- 검증 케이스:
  - `compute_kospi200_atr_p80(session, lookback_days=20)` — 모의 KOSPI200 50종목 일봉 데이터로 ATR 분포 계산, P80 산출 정확성
  - `np.percentile([각 종목 20일 평균 ATR/close], 80) * 1.2` 결과가 `min(0.08, ...)`로 캡됨
  - 데이터 부족(≥10종목 미만 + lookback 미달) → `None` 반환 + 직전일 Redis 캐시 폴백
  - Redis `metrics:atr:ceil:2026-04-30` 키에 결과 저장 (TTL 7일)
  - `ATR_CALIBRATION_ENABLED=false` → 잡 자체 no-op
- 검증: `docker compose exec backend pytest tests/screening/test_atr_calibration.py -v`
- 예상: FAIL

**Step 2: ATR 캘리브레이션 구현**
- `atr_calibration.py`:
  - `_load_kospi200_codes(session)` — `stocks.is_kospi200=True` 또는 마스터 파일/리스트 (사용자 확정 #1)
  - `_compute_atr_ratio(daily_rows, window=14)` — ATR ÷ close (재사용: `screening/factors.py`의 `calc_volatility_factor`)
  - `compute_kospi200_atr_p80(session, lookback_days=20)` — 단면 분포 → P80
  - `run_atr_calibration(session_factory, redis_client)` — 메인 진입점, Redis 저장 + 직전 캐시 폴백
- 검증: `docker compose exec backend pytest tests/screening/test_atr_calibration.py -v`
- 예상: PASS

**Step 3: scheduler 잡 등록**
- `modules/collector/scheduler.py`:
  - `start()` 메서드에 `CronTrigger(hour=9, minute=0, second=0, timezone=tz)` 잡 추가 (단, 기존 09:00 잡과 충돌 방지 — 현재 line 330 ETF는 09:00, 신규 ATR 캘리브레이션은 **08:55**로 5분 선행 배치하여 ETF 시세 수집 직전 확보)
  - 잡 함수 `_atr_calibration_job(self)` 신설: `if not settings.ATR_CALIBRATION_ENABLED: return` 가드
- 기존 `test_scheduler.py`의 `test_scheduler_registers_jobs()`에서 job_count 갱신 (사용자 확정 #2 폴백 정책 결정 후 반영)
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v`
- 예상: PASS (job_count +1)

**Step 4: 커밋**
```
git add backend/modules/screening/atr_calibration.py backend/modules/collector/scheduler.py backend/tests/screening/test_atr_calibration.py backend/tests/test_scheduler.py
git commit -m "feat(phase8.6-sprint2): task2 — ATR 캘리브레이션 모듈 + 08:55 KOSPI200 P80 잡"
```

**완료 기준:**
- ⬜ `test_atr_calibration.py` 5 케이스 PASS
- ⬜ scheduler `_atr_calibration_job` 등록 확인 (job_count +1)
- ⬜ Redis 키 `metrics:atr:ceil:{YYYY-MM-DD}` 저장 확인 (수동 trigger 시)
- ⬜ 캐시 폴백 동작 확인(인위 실패 케이스 테스트)

---

### Task 3: 병렬 OR tier 분리 — `MomentumBreakoutStrategy` 재구조화

**skill:** `feature-dev:feature-dev` (전략 핵심 로직 + shadow 평가 + 메트릭 + 회귀 위험 큰 변경)

**Files:**
- Modify: `backend/modules/trading/strategies/momentum_breakout.py`
  - 신규: `_evaluate_gap_open(snapshot, ctx) -> tuple[bool, dict]`
  - 신규: `_evaluate_prev_high(snapshot, ctx) -> tuple[bool, dict]`
  - 신규: `_evaluate_prev_close(snapshot, ctx) -> tuple[bool, dict]`
  - 수정: `generate_signal()` — `PARALLEL_OR_TIER_ENABLED` 분기. true 시 3 tier 모두 평가 후 OR 결합, false 시 기존 직렬 로직 유지
  - 수정: `_shadow_evaluate()` — tier별 독립 pass/fail 카운터 추가 (`shadow:tier:{name}:{passed|failed}`)
- Test: `backend/tests/strategies/test_parallel_or_tier.py` (신규)
- Test: `backend/tests/test_momentum_breakout.py` (회귀 — 토글 OFF 시 동작 동일)

**tier별 sub-게이트 (Phase §5.1 확정):**

| Tier | sub-게이트 | 진입 시간 |
|------|-----------|----------|
| `gap_open` | `gap_rate ≥ 0.03` AND `ATR ≥ ATR_FLOOR(0.025)` AND `current_price > open_price` (돌파) | 09:05 까지는 `gap_open` 우선, 이후 일반 |
| `prev_high` | `current_price > prev_high × 1.001` (breakout) AND `ATR ∈ [ATR_FLOOR, ATR_CEIL_DYNAMIC]` | 13:00 이전 |
| `prev_close` | 13:00 이전 시간 가드만 (ATR / breakout 조건 없음) AND `current_price > prev_close × 1.001` (최소 양봉 조건) | 13:00 이전만 |

**병렬 OR 결합:**
- 3개 tier 평가 → 통과 tier 수 ≥ 1이면 신호 발행
- 신호 메타데이터에 `matched_tiers: list[str]` 기록 (사용자 확정 #4 — 권고 (b) 채택)
- `confidence`는 통과 tier 중 최댓값 사용 (보수적), `reason.matched_tiers`로 추적
- 폴백 종목(`is_fallback=true`)은 `ATR_CEIL_FALLBACK=0.05` 고정 (동적 미적용)

**Step 1: 테스트 작성 — 병렬 OR 시나리오 6종**
- `tests/strategies/test_parallel_or_tier.py`:
  - 케이스 1: `gap_open` 단독 통과 (gap=4%, ATR=0.03) → 신호, `matched_tiers=["gap_open"]`
  - 케이스 2: `prev_high` 단독 통과 (gap=1%, prev_high 돌파, ATR=0.04) → 신호, `matched_tiers=["prev_high"]`
  - 케이스 3: `prev_close` 단독 통과 (오전 11시, gap=0.5%, current > prev_close+0.1%) → 신호, `matched_tiers=["prev_close"]`
  - 케이스 4: 모두 실패 (gap=0.5%, prev_high 미돌파, current ≤ prev_close) → reject
  - 케이스 5: gap_open + prev_high 동시 통과 → `matched_tiers=["gap_open","prev_high"]`
  - 케이스 6: ATR=0.09(상한 초과) — gap_open 우회 통과, prev_high/prev_close fail → 신호, `matched_tiers=["gap_open"]`
  - 케이스 7: ATR=0.020(하한 미달) — 모든 tier fail (gap_open도 하한 적용, 사용자 확정 #3) → reject
  - 케이스 8: 폴백 종목 + ATR=0.06(`ATR_CEIL_FALLBACK=0.05` 초과) → prev_high/prev_close fail (gap_open은 우회 가능) → gap≥3%일 때만 통과
- 검증: `docker compose exec backend pytest tests/strategies/test_parallel_or_tier.py -v`
- 예상: FAIL

**Step 2: tier sub-게이트 함수 분리**
- `momentum_breakout.py`에 3개 함수 추가, 각각 `(passed: bool, detail: dict)` 반환
- `generate_signal()` 분기:
  ```
  if settings.PARALLEL_OR_TIER_ENABLED:
      results = [
          ("gap_open", *await self._evaluate_gap_open(...)),
          ("prev_high", *await self._evaluate_prev_high(...)),
          ("prev_close", *await self._evaluate_prev_close(...)),
      ]
      matched = [name for name, passed, _ in results if passed]
      if not matched:
          return await self._reject(...)
      # 통과 tier 중 confidence 계산 → 신호
  else:
      # 기존 직렬 로직 (Sprint 1 종료 시점)
  ```
- 공통 게이트(`min_volume_floor`, `volume_threshold`, `trade_strength`, `confidence ≥ MIN_CONFIDENCE`)는 **OR 결합 후** 한 번만 적용 (단타 §2의 "단순화" 원칙 — 약한 신호일수록 적은 게이트)
- 검증: `docker compose exec backend pytest tests/strategies/test_parallel_or_tier.py tests/test_momentum_breakout.py -v`
- 예상: PASS (회귀 + 신규 모두)

**Step 3: shadow 평가 tier별 카운터 추가**
- `_shadow_evaluate()` 내 각 tier 독립 평가 결과를 `shadow:tier:{name}:{passed|failed}:{date}` Redis 카운터에 기록
- 기존 stage shadow와 분리(파일 끝부분, side effect 없음)
- 검증: `pytest -v -k shadow`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/trading/strategies/momentum_breakout.py backend/tests/strategies/test_parallel_or_tier.py backend/tests/test_momentum_breakout.py
git commit -m "feat(phase8.6-sprint2): task3 — 병렬 OR tier 분리 (gap_open/prev_high/prev_close 독립 sub-게이트)"
```

**완료 기준:**
- ⬜ `test_parallel_or_tier.py` 8 케이스 PASS
- ⬜ `test_momentum_breakout.py` 기존 회귀 0건 (`PARALLEL_OR_TIER_ENABLED=false` 토글 시 Sprint 1 동작 100% 복원)
- ⬜ tier별 shadow 카운터 Redis 기록 확인

---

### Task 4: tier 페어와이즈 상관 메트릭 + M-G-D API

**Files:**
- Create: `backend/modules/screening/tier_correlation.py`
- Modify: `backend/api/routes/metrics.py` (신규 엔드포인트 2종)
- Test: `backend/tests/screening/test_tier_correlation.py`

**Step 1: 테스트 작성**
- 검증 케이스:
  - `compute_pairwise_correlation(daily_tier_signals, window_days=7)` — tier 발생일 0/1 시퀀스 → Pearson 상관 매트릭스
  - tier별 일별 신호 수 0건 시 상관 계산 skip (분모 0 회피)
  - 7일 누적 상관 ≤ 0.3 목표선 PASS/FAIL 판정
- 검증: `pytest tests/screening/test_tier_correlation.py -v`
- 예상: FAIL

**Step 2: 메트릭 모듈 + 일별 집계**
- Sprint 1 daily_screening_metrics 패턴 재사용. 각 tier별 일별 신호 카운터 수집(`signals.matched_tiers` 컬럼에서 추출 — 신규 컬럼 필요)
- **Alembic 마이그레이션**: `signals.matched_tiers JSON NULL` 추가 (Task 3 신호 메타데이터 영속화)
- 검증: `pytest -v -k tier_correlation`
- 예상: PASS

**Step 3: API 엔드포인트**
- `GET /api/v1/metrics/tier-pass-rate` — tier별 일별 pass 카운트 7일 추이 (Task 5 카드용)
- `GET /api/v1/metrics/tier-correlation` — 페어와이즈 상관 매트릭스 7일 이동
- 검증: `curl -s http://localhost:8000/api/v1/metrics/tier-correlation | jq .`
- 예상: `{"window_days":7, "matrix":{"gap_open-prev_high":0.12, ...}, "max":0.18, "threshold":0.3, "ok":true}`

**Step 4: 커밋**
```
git add backend/modules/screening/tier_correlation.py backend/api/routes/metrics.py backend/tests/screening/test_tier_correlation.py backend/alembic/versions/*.py
git commit -m "feat(phase8.6-sprint2): task4 — tier 페어와이즈 상관 메트릭 + matched_tiers DB 컬럼"
```

**완료 기준:**
- ⬜ `test_tier_correlation.py` 3+ 케이스 PASS
- ⬜ `signals.matched_tiers` Alembic 마이그레이션 적용
- ⬜ `/api/v1/metrics/tier-correlation` 응답 정상

---

### Task 5: tier-correlation-card UI

**skill:** `frontend-design`

**Files:**
- Create: `frontend/components/diagnostics/tier-correlation-card.tsx`
- Create: `frontend/components/diagnostics/tier-pass-rate-card.tsx`
- Modify: `frontend/app/(dashboard)/diagnostics/page.tsx` (카드 등록)

**Step 1: 카드 구현**
- `tier-correlation-card.tsx`:
  - `useSWR("/api/v1/metrics/tier-correlation", fetcher, { refreshInterval: 60000 })`
  - 페어와이즈 상관 3×3 히트맵 (recharts 또는 단순 grid)
  - 목표선 0.3 표시 + max 값 강조 (≤0.3 녹색, >0.3 주황)
  - 7일 이동 라인차트 (페어별 색상)
- `tier-pass-rate-card.tsx`:
  - tier별 일별 pass 카운트 막대그래프 (gap_open/prev_high/prev_close)
  - "tier 다양성 ≥ 3종 활성" 5일 누적 상태 인디케이터(G-C 게이트)

**Step 2: 통합 + 검증**
- diagnostics/page.tsx에 카드 추가 (기존 fallback-signal-rate-card.tsx 옆)
- 검증: `cd frontend && npx tsc --noEmit && npm run dev` → 브라우저 `/diagnostics` 확인
- 예상: 카드 정상 렌더, API 응답 시각화

**Step 3: 커밋**
```
git add frontend/components/diagnostics/tier-correlation-card.tsx frontend/components/diagnostics/tier-pass-rate-card.tsx frontend/app/(dashboard)/diagnostics/page.tsx
git commit -m "feat(phase8.6-sprint2): task5 — tier 상관 + tier pass rate 카드 (G-C·G-D 시각화)"
```

**완료 기준:**
- ⬜ `npx tsc --noEmit` 에러 0건
- ⬜ `/diagnostics` 카드 2종 정상 렌더
- ⬜ G-C(3종 활성) / G-D(상관 ≤ 0.3) 게이트 색상 인디케이터 동작

---

### Task 6: atr-distribution-card UI

**skill:** `frontend-design`

**Files:**
- Create: `frontend/components/diagnostics/atr-distribution-card.tsx`
- Modify: `backend/api/routes/metrics.py` (`GET /api/v1/metrics/atr-calibration`)
- Modify: `frontend/app/(dashboard)/diagnostics/page.tsx`

**Step 1: API 엔드포인트**
- `GET /api/v1/metrics/atr-calibration`:
  - 응답: `{"date": "2026-04-30", "p50": 0.038, "p80": 0.062, "p95": 0.085, "ceil_dynamic": 0.074, "ceil_hard": 0.08, "fallback_ceil": 0.05, "calibrated_at": "2026-04-30T08:55:01+09:00"}`
  - Redis `metrics:atr:ceil:{date}` + `metrics:atr:dist:{date}` 읽기 (Task 2에서 분포 메트릭도 함께 저장)

**Step 2: 카드 구현**
- KOSPI200 ATR 단면 분포 히스토그램 (P50·P80·P95 라인)
- 동적 CEIL과 HARD 0.08 비교 (라인)
- 폴백 CEIL 0.05 별도 라인
- "ATR 분위수 캘리브레이션 09:00 정상" 상태 (G-3 게이트 입력)
- 검증: `npx tsc --noEmit` + 브라우저 확인
- 예상: 정상 렌더

**Step 3: 커밋**
```
git add frontend/components/diagnostics/atr-distribution-card.tsx backend/api/routes/metrics.py frontend/app/(dashboard)/diagnostics/page.tsx
git commit -m "feat(phase8.6-sprint2): task6 — ATR 분포 카드 + /metrics/atr-calibration API"
```

**완료 기준:**
- ⬜ `/api/v1/metrics/atr-calibration` 응답 정상
- ⬜ 카드 렌더 정상

---

### Task 7: 통합 회귀 + Paper 1거래일 + deploy.md 환경변수 등록

**skill:** `verification-before-completion`

**Step 1: 전체 회귀**
- `docker compose exec backend pytest -v` (전체 통과 확인)
- `cd frontend && npx tsc --noEmit`
- `PARALLEL_OR_TIER_ENABLED=false` env 토글 후 회귀 — Sprint 1 동작 100% 복원 확인

**Step 2: Paper 1거래일 관찰 (수동)**
- 다음 영업일 09:00 ATR 캘리브레이션 잡 정상 동작 확인 (Redis 키 + 로그)
- 본 신호 1건 이상 발생 + `matched_tiers` 메타데이터 정상 기록
- tier 다양성 ≥ 2종 활성 (당일 1일은 G-C 5일 누적의 1일분)
- 자동 롤백 R1~R4 발동 없음 확인

**Step 3: deploy.md 업데이트**
- "Railway 환경변수 추가 확인: PARALLEL_OR_TIER_ENABLED, ATR_CALIBRATION_ENABLED, ATR_FLOOR, ATR_CEIL_HARD, ATR_CEIL_FALLBACK, ATR_CALIBRATION_WINDOW_DAYS" 항목 추가
- "Paper 1거래일 ATR 캘리브레이션 잡 + 병렬 OR tier 신호 발생 확인" 수동 검증 항목 추가

**Step 4: 커밋 + 회고**
```
git add deploy.md docs/phase/phase8.6/sprint2/
git commit -m "chore(phase8.6-sprint2): task7 — 통합 회귀 + deploy.md env 6종 등록"
```

**완료 기준:**
- ⬜ pytest 전체 PASS
- ⬜ npx tsc --noEmit 에러 0건
- ⬜ env 토글 OFF 시 회귀 0건
- ⬜ Paper 1거래일 본 신호 ≥ 1건 + tier 다양성 ≥ 2종 (수동, deploy.md 기록)
- ⬜ deploy.md 환경변수 6종 등록 항목 추가

---

## 최종 검증 계획 (Sprint 2 종료 시점)

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | All PASS (신규 ~25개 + 기존 회귀) |
| 프론트 타입체크 | `cd frontend && npx tsc --noEmit` | 에러 없음 |
| ATR 캘리브레이션 잡 | `docker compose exec backend python -c "from modules.screening.atr_calibration import run_atr_calibration; ..."` | Redis `metrics:atr:ceil:{date}` 저장 |
| 병렬 OR 동작 (단위) | `pytest tests/strategies/test_parallel_or_tier.py -v` | 8 PASS |
| 병렬 OR 토글 OFF 회귀 | `PARALLEL_OR_TIER_ENABLED=false pytest tests/test_momentum_breakout.py -v` | Sprint 1 동작 동일 |
| tier 상관 API | `curl -s http://localhost:8000/api/v1/metrics/tier-correlation \| jq .` | matrix 키 존재, ok=true (목표선 0.3) |
| ATR 분포 API | `curl -s http://localhost:8000/api/v1/metrics/atr-calibration \| jq .` | p50/p80/p95/ceil_dynamic 키 존재 |
| Diagnostics UI 카드 3종 | 브라우저 `/diagnostics` 확인 | tier-correlation / tier-pass-rate / atr-distribution 카드 렌더 |
| Paper 1거래일 (수동) | 다음 영업일 16:00 deploy.md 기록 | 본 신호 ≥ 1건, tier ≥ 2종 |

---

## 재사용 자산

- Phase 4.7 (3팩터 분리) — tier sub-게이트 분리 구조 패턴
- Phase 4.8 Sprint 1 (KIS 일봉 보조 수집) — KOSPI200 일봉 데이터 소스로 `market_data` 재사용
- Phase 6.1 (5분봉 vol5m Redis) — Redis 캐시 + TTL 패턴
- Phase 8.5 Sprint 2.5 (`OverrideBanner`) — env 토글 시각화 패턴
- Phase 8.6 Sprint 1 (`shadow_evaluate` 카운터, `_resolve_min_volume_floor`) — tier별 shadow 카운터 동일 패턴 적용
- Phase 8.6 Sprint 1 (daily_screening_metrics 일별 집계) — tier 상관 일별 집계에 동일 패턴

---

## 알려진 리스크 (Sprint 2 한정)

| # | 리스크 | 완화 |
|---|--------|------|
| L1 | 병렬 OR로 일일 신호가 10건 한도(Phase 7.2)를 자주 초과 → 자금 분산 | Phase 8.6 Sprint 3에서 tier 우선순위 큐 도입 (현 Sprint는 한도 그대로, R4 폴백 비중 ≥70% 자동 롤백으로 1차 방어) |
| L2 | KOSPI200 ATR 캘리브레이션 데이터 부족 (휴장 인접 / KIS 분봉 누락) | Task 2 폴백 정책 (사용자 확정 #2): 직전일 캐시 → ATR_CEIL_HARD 정적 사용, 자동 비활성화 X |
| L3 | `gap_open` ATR 우회로 분기 D 시뮬-실측 괴리가 다른 형태로 재발 | Sprint 4의 KS 검정 자동 감지 + 본 Sprint Task 4의 tier 상관 메트릭으로 1주 안에 감지 |
| L4 | Alembic 마이그레이션 (`signals.matched_tiers`) 프로덕션 적용 누락 | deploy.md "alembic upgrade head" 수동 검증 항목 + Railway 자동 배포 후 확인 |
| L5 | `ATR_FLOOR=0.025`가 박스권 저변동 종목 다수 거름 → 기본 신호도 줄어듬 | shadow 카운터로 `atr_floor` fail 비율 모니터링, 5거래일 평균 fail율 ≥ 60%면 0.020으로 완화 검토 (Sprint 3 결정) |

---

## 회귀 가드 (Phase 7.0 LIVE 파라미터 코드 잠금 — Sprint 1 G9 계승)

본 Sprint 어떤 변경에서도 다음은 수정 금지 (Sprint 1 Task 1 Final 상수 잠금 그대로):

- `MAX_POSITION = 2`
- `POSITION_SIZE_PCT = 0.05` (5%)
- `DAILY_MAX_LOSS_PCT = -0.02` (-2%)
- `EMERGENCY_STOP_PCT = -0.03` (-3%)

위 4개 변경 시도 시 빌드 실패 (Sprint 1 5개 회귀 테스트로 보장).

---

## 완료 후 다음 단계

Sprint 2 완료 → 사용자에게 다음 안내:

1. **Sprint 3 착수 (`volume_surge` tier 신설 + 시간 필터)** — 권장
2. **Paper 5거래일 관찰만 진행 후 Sprint 3** — Sprint 2 안정성 확인 우선
3. **Sprint 2 결과 보고 후 파라미터 튜닝** — `ATR_FLOOR=0.020`, P80 대신 P85 등 검토

> 본 문서는 사용자 확정 5개 항목 답변 후 Step 2부터 본 구현 진행. 답변 전까지 Task 1 Step 1(테스트 작성)까지만 가능.
