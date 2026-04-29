# Sprint 2: 병렬 OR tier 분리 + ATR 분위수 캘리브레이션 (Phase 8.6) — v2

**Goal:** 직렬 AND 게이트로 묶여 있던 3 tier(`gap_open`/`prev_high`/`prev_close`)를 **병렬 OR 다중 진입 경로**로 구조 재설계하고, 고정 ATR 5% 상한을 **KOSPI200 분위수 기반 동적 상한 + 하한 0.025**로 전환하여 분기 D의 "곱셈 0" 결함을 제거한다. **시뮬-실측 통과율 절대차 메트릭을 동시 도입**하여 Sprint 4 walk-forward 이전에도 분기 D 회귀를 1주 내 감지한다.

**Architecture:**
- `MomentumBreakoutStrategy.generate_signal()`을 tier 분기 → 공통 게이트 직렬 구조에서, **tier별 독립 sub-게이트**(각각 ATR / breakout / 시간가드 + 거래량 컨펌 / gap 시초가 컷 중 필요한 것만 적용)를 평가한 뒤 **하나라도 통과하면 신호 발행**하는 구조로 분리한다.
- **08:30~08:40** KOSPI200 ATR 분위수를 산출하여 (SMA 또는 EWMA λ=0.94 옵션 분기) IQR ×1.5 트리밍 후 P80을 계산, `ATR_CEIL_DYNAMIC = min(0.08, P80×1.2)`를 Redis에 캐싱한다 (`metrics:atr:ceil:{date}`, TTL **3거래일**). 폴백 종목은 항상 `ATR_CEIL_FALLBACK=0.05` 고정.
- **gap_open tier도 ATR_CEIL_HARD=0.08을 절대 한계로 적용** (완전 우회 금지). prev_close tier는 시간가드 + **5분봉 거래량 컨펌**(양봉 2연속 OR 직전 4봉 평균 ×2) 추가.
- **시뮬-실측 통과율 절대차** `metrics:quant:sim_vs_real_diff:{date}` ≥0.15 시 텔레그램 알림. ATR 상한 곱계수 shadow 그리드 `{1.0, 1.1, 1.2, 1.3}`도 동시 기록.
- 모든 신규 동작은 env 토글로 1줄 원복 가능 (`PARALLEL_OR_TIER_ENABLED`, `ATR_CALIBRATION_ENABLED`, `TEMP_TIME_GUARD_SPRINT2`). 토글 OFF 시 Sprint 1 종료 시점 동작 100% 복원.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Redis (asyncio), APScheduler CronTrigger, Next.js 16 (shadcn/ui), pytest-asyncio.

**Sprint 기간:** 2026-04-29 ~ 2026-04-29
**상태:** ✅ 완료
**이전 스프린트:** Phase 8.6 Sprint 1 (DoR G1·G2·G3 + Phase 7.0 잠금 + 폴백 5종 + 09~11시 floor 0.3, 13 + 9 + 5 tests PASS, PR #181 머지)
**브랜치명:** `phase8.6-sprint2`
**버전:** v2 (2026-04-29 — 전문가 4명 합의 채택안 반영)

---

## 변경 이력

### v1 → v2 차이 (2026-04-29)

**범위 조정 (정프로 PO 합의)**
- ❌ 구 Task 6(ATR 분포 카드) → **Sprint 4로 이관** (walk-forward와 묶을 때 가치)
- ❌ 구 Task 7의 Paper 1거래일 → **Sprint 종료 조건에서 제외**, 관찰 항목으로 deploy.md 기록만 (Sprint 3 착수 게이트로 사용)
- 🔁 `signals.matched_tiers` 컬럼 추가 → 구 Task 4 → **Task 3로 흡수** (메타데이터 생산자와 동일 커밋)
- ➕ `stocks.is_kospi200` 컬럼 신설 Alembic → Task 1에 통합
- 🔁 ATR 분포 카드 → **Task 5에서 제거**, tier 카드만 유지

**신규 추가 (박퀀트)**
- ➕ **시뮬-실측 통과율 절대차 메트릭** Sprint 2에 즉시 도입 (`metrics:quant:sim_vs_real_diff:{date}`, ≥0.15 시 알림)
- ➕ ATR 상한 곱계수 shadow 그리드 `{1.0, 1.1, 1.2, 1.3}` (`metrics:atr:ceil_grid:{date}`, 실 진입은 1.2 사용)
- ➕ ATR 분포 P10/P20/P50/P80/P95 + sample_n 동시 기록 (`metrics:atr:dist:{date}`)
- 🔁 tier 상관: Pearson → **phi coefficient + 조건부 통과율 P(B|A) 병기**
- ➕ 단면 P80 vs 시계열 P80 차 ≥0.015 시 `quant_dist_drift_warn` 카운터
- ➕ 캘리브레이션 데이터 누수 방지 단위 테스트(`trade_date < CURRENT_DATE`)
- ➕ EWMA λ=0.94 옵션 (`ATR_CALIBRATION_METHOD=sma|ewma`)
- ➕ IQR ×1.5 트리밍 (캘리브레이션 입력 분포에서 outlier 제거)

**신규 추가 (김단타)**
- ➕ **임시 시간가드 env**(`TEMP_TIME_GUARD_SPRINT2=true`) 09:00~09:10 / 14:30+ 진입 차단
- ➕ **prev_close tier 거래량 컨펌**: 5분봉 양봉 2연속 OR vol_5m ≥ 직전 4봉 평균 ×2
- ➕ **gap_open 추가 컷**: 시초가 ≥ 현재가 시 거름(매물 흡수 실패)
- 🔁 ATR 캘리브레이션 잡 시각: 08:55 → **08:30~08:40**(KIS 동시호가 부하 회피, 본 구현 08:35)

**신규 추가 (최리스크)**
- ➕ **Kill-switch 런북** deploy.md 명시 (`PARALLEL_OR_TIER_ENABLED=false` 즉시 원복 + NULL 안전성 검증 + curl 1줄)
- ➕ **R1~R4 격리 회귀 테스트** (`matched_tiers` 추가가 폴백 비중 산식 분모/분자에 영향 없음)
- 🔁 **G3 회로차단기 보정**: 통과율 → "체결 손실 누적" 임계로 일시 전환 OR OR 모드 전용 보정 계수
- ➕ **일일 신호 한도(10건) + 동시 보유 2 포지션 회로**가 병렬 OR 직후 강제 적용되는지 단위 테스트(`test_parallel_or_quota_cap.py`)
- ➕ **L5 사전 시뮬레이션**: ATR_FLOOR=0.025 적용 시 Sprint 1 shadow 데이터 fail율 산출 (≥60%면 0.020 시작)
- ➕ **9:00 폴백 3단**: 직전일 캐시 → HARD 0.08 → **안전모드(신호 발행 일시 중단 2시간 + 텔레그램 알림)**
- 🔁 **gap_open tier ATR 상한**: 우회 X, ATR_CEIL_HARD=0.08 절대 한계 적용
- 🔁 **matched_tiers confidence 산식**: 최댓값 → **평균** 변경

**사용자 확정 5종 반영 (전부 채택)**
1. KOSPI200 마스터: `stocks.is_kospi200` 플래그 + 정적 백업 리스트 이중화 + market_data 결측 ≥30종 시 직전일 캐시 폴백
2. 09:00 폴백 3단 (위)
3. gap_open ATR_FLOOR + ATR_CEIL_HARD 동시 적용
4. matched_tiers list[str] + confidence 평균
5. 캘리브레이션 윈도우 종목별 20일 평균 ATR → 단면 P80 + EWMA 옵션 + IQR ×1.5 트리밍

---

## 제외 범위

- ❌ **`volume_surge` tier 신설** — Sprint 3에서 호가창 스트림 인프라와 함께 도입
- ❌ **시간대 필터 11:30~13:00 floor 0.7 / 14:30+ 진입 금지** — Sprint 3에서 본 가드 도입 (Sprint 2는 임시 env 가드 `TEMP_TIME_GUARD_SPRINT2`만 적용)
- ❌ **Walk-forward 60일 백테스트** — Sprint 4
- ❌ **시뮬↔실측 KS 검정** — Sprint 4 (Sprint 2는 절대차 메트릭만 도입)
- ❌ **ATR 분포 카드 UI** — Sprint 4 (walk-forward와 묶음)
- ❌ **Paper 1거래일 종료 게이트** — 관찰 항목으로만 기록, Sprint 3 착수 게이트
- ❌ **Phase 7.0 LIVE 파라미터 변경** — 코드 잠금 유지 (`max_position=2`, `position_size=5%`, `daily_max_loss=-2%`, `emergency_stop=-3%`)
- ❌ **2차 스크리닝 pass_threshold(75) 변경** — 분기 D 진단상 임계는 무결, 구조 변경 우선
- ❌ **신호 우선순위 큐 / 일일 신호 한도 10건 강화** — Phase 7.2 한도 그대로 유지 (Sprint 3 이후 모니터링)

---

## 신규 환경변수 (deploy.md 수동 검증 항목)

Sprint 2에서 추가되는 Railway 환경변수 (총 **10개**):

| 변수 | 기본값 | 용도 |
|------|--------|------|
| `PARALLEL_OR_TIER_ENABLED` | `true` | 병렬 OR tier 분기 활성화. `false` 시 Sprint 1 직렬 동작 복원 (Kill-switch) |
| `ATR_CALIBRATION_ENABLED` | `true` | 08:35 ATR 캘리브레이션 잡 활성화. `false` 시 `ATR_CEIL_HARD` 정적 사용 |
| `ATR_CALIBRATION_METHOD` | `sma` | 캘리브레이션 방식: `sma`(20일 평균) 또는 `ewma`(λ=0.94) |
| `ATR_FLOOR` | `0.025` | ATR 하한 (모든 tier 공통, 폴백 종목 포함). gap_open도 적용 |
| `ATR_CEIL_HARD` | `0.08` | ATR 상한 절대 한계 (gap_open 우회 시에도 적용, 동적 상한도 이 값 초과 금지) |
| `ATR_CEIL_FALLBACK` | `0.05` | 폴백 종목 ATR 상한 (동적 미적용) |
| `ATR_CEIL_MULT` | `1.2` | 동적 상한 곱계수 (P80×mult). shadow 그리드 `{1.0,1.1,1.2,1.3}` 중 실 진입값 |
| `ATR_CALIBRATION_WINDOW_DAYS` | `20` | KOSPI200 ATR 평균 윈도우 |
| `TEMP_TIME_GUARD_SPRINT2` | `true` | 임시 시간가드 (09:00~09:10 / 14:30+ 차단). Sprint 3 본 가드 도입 시 제거 |
| `SAFE_MODE_TIMEOUT_MIN` | `120` | 폴백 3단 안전모드 신호 중단 시간 (분, 기본 2시간) |

**deploy.md 수동 검증 추가 항목** (sprint-close 시 기록):
- `Railway 환경변수 추가 확인: 위 10종`
- `Kill-switch 런북 검증: PARALLEL_OR_TIER_ENABLED=false 즉시 원복 + curl /diagnostics 정상 + signals.matched_tiers NULL 안전`

---

## 실행 플랜

### Phase 1 (순차 — 인프라 / config / 마이그레이션 선행)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | env 10종 + ATR resolver 함수 + `stocks.is_kospi200` Alembic | 백엔드 | — |

### Phase 2 (순차 — Task 2 → Task 3 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | ATR 캘리브레이션 모듈(SMA/EWMA + IQR 트리밍) + 08:35 잡 + 폴백 3단 + 누수 가드 테스트 | 백엔드 | `feature-dev:feature-dev` |
| Task 3 | 병렬 OR tier 분리 + `signals.matched_tiers` 컬럼 + prev_close 거래량 컨펌 + gap_open 시초가 컷 + ATR_CEIL_HARD 적용 | 백엔드 | `feature-dev:feature-dev` |

### Phase 3 (순차 — Task 3 결과 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | tier phi 상관 + 조건부 P(B\|A) + 시뮬-실측 절대차 + R1~R4 격리 + 쿼터 캡 테스트 + ATR shadow 그리드 + drift warn | 백엔드 | — |

### Phase 4 (단일 — UI)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | tier-correlation-card + tier-pass-rate-card UI (ATR 분포 카드 제거) | 프론트엔드 | `frontend-design` |

### Phase 5 (순차 — 통합 검증 + 임시 가드 + 런북)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | 통합 회귀 + 임시 시간가드 env + Kill-switch 런북 + deploy.md env 10종 등록 (Paper 1거래일은 관찰 항목) | 전체 | `verification-before-completion` |

> **팀 실행**: Phase 4의 UI 작업은 단일이며 Phase 1~3 백엔드 작업은 의존성 직렬. Task 4 메트릭과 Task 5 UI는 직렬 의존 (API → UI). 단일 작업자 권장.

---

## Task 상세

### Task 1: env 10종 + ATR resolver 함수 + `stocks.is_kospi200` Alembic

**Files:**
- Modify: `backend/core/config.py` (env 10종 추가)
- Modify: `backend/.env.example` (동일 10종 + 주석)
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (`ATR_FILTER_PCT=0.05` 상수 → `_resolve_atr_ceil(snapshot, tier, redis_client, is_fallback)` 함수로 추출)
- Create: `backend/alembic/versions/{rev}_add_stocks_is_kospi200.py` (`stocks.is_kospi200 BOOLEAN NOT NULL DEFAULT FALSE` + 인덱스)
- Create: `backend/data/kospi200_static_backup.json` (정적 백업 리스트, KRX 분기 리밸런싱 동기화 — 최초 200종목 코드만)
- Test: `backend/tests/strategies/test_atr_resolver.py` (신규)
- Test: `backend/tests/test_stocks_is_kospi200_migration.py` (신규)

**Step 1: 테스트 작성**
- `tests/strategies/test_atr_resolver.py` 검증 케이스:
  - `is_fallback=True` → `ATR_CEIL_FALLBACK=0.05` 반환 (동적 미적용)
  - `tier="gap_open"` + ATR 정상 → 동적 상한이 아닌 **`ATR_CEIL_HARD=0.08` 반환** (우회 X, 절대 한계 적용)
  - `tier IN ("prev_high", "prev_close")` + Redis `metrics:atr:ceil:2026-04-30="0.072"` → `0.072` 반환
  - Redis 키 부재 시 → 직전일 캐시 폴백 → `ATR_CEIL_HARD=0.08` 폴백
  - `ATR_CALIBRATION_ENABLED=false` → 동적 미적용, `ATR_CEIL_HARD` 사용
  - `ATR_FLOOR=0.025` 하한 — 모든 tier(gap_open 포함)에서 ATR < 0.025 시 상한 비교 이전에 `False` 반환
  - 동적 상한이 ATR_CEIL_HARD 초과 값(예: 0.085) 반환 시 → `ATR_CEIL_HARD=0.08`로 캡
- `tests/test_stocks_is_kospi200_migration.py` — alembic upgrade head 후 컬럼 존재 + 인덱스 + 기본값 False 확인
- 검증: `docker compose exec backend pytest tests/strategies/test_atr_resolver.py tests/test_stocks_is_kospi200_migration.py -v`
- 예상: FAIL

**Step 2: config 환경변수 추가**
- `core/config.py` Settings 클래스에 10종 필드 추가 (Phase 8.6 Sprint 2 v2 주석)
- `.env.example`에 동일 키 + 한글 주석 작성
- 검증: `docker compose exec backend python -c "from core.config import settings; print(settings.ATR_FLOOR, settings.ATR_CEIL_HARD, settings.ATR_CALIBRATION_METHOD, settings.TEMP_TIME_GUARD_SPRINT2)"`
- 예상: `0.025 0.08 sma True`

**Step 3: ATR resolver 함수 추출**
- `modules/trading/strategies/momentum_breakout.py`에 `async def _resolve_atr_ceil(snapshot, tier, redis_client, is_fallback) -> float | None` 추가
- 반환값: `float` = 상한값, `None` = 하한 미달 등으로 즉시 reject 신호
- **gap_open이라도 ATR_CEIL_HARD=0.08을 절대 한계로 반환** (Sprint v1 우회 X)
- 동적 상한이 HARD 초과 시 HARD로 캡

**Step 4: Alembic 마이그레이션 + 정적 백업**
- `alembic revision --autogenerate -m "add stocks.is_kospi200"` → `is_kospi200 BOOLEAN NOT NULL DEFAULT FALSE` + `ix_stocks_is_kospi200`
- `data/kospi200_static_backup.json` — KRX KOSPI200 200종목 stock_code 배열 (분기별 리밸런싱 시 수동 갱신, 주석 포함)
- 검증: `docker compose exec backend alembic upgrade head && pytest tests/strategies/test_atr_resolver.py tests/test_stocks_is_kospi200_migration.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/core/config.py backend/.env.example backend/modules/trading/strategies/momentum_breakout.py backend/alembic/versions/*.py backend/data/kospi200_static_backup.json backend/tests/strategies/test_atr_resolver.py backend/tests/test_stocks_is_kospi200_migration.py
git commit -m "feat(phase8.6-sprint2): task1 — env 10종 + ATR resolver(HARD 절대상한) + is_kospi200 컬럼 + 정적 백업"
```

**완료 기준:**
- ✅ pytest `test_atr_resolver.py` 7+ 케이스 PASS
- ✅ Alembic 마이그레이션 적용 후 `stocks.is_kospi200` 컬럼 + 인덱스 존재
- ✅ 정적 백업 JSON 파일 200종목 포함
- ✅ 기존 `test_momentum_breakout.py` 회귀 0건 (PARALLEL_OR_TIER_ENABLED=true 기본값에서도 직렬 동작 유지 — Task 3 전까지)
- ✅ `.env.example` 10종 추가 확인

---

### Task 2: ATR 캘리브레이션 모듈 + 08:35 잡 + 폴백 3단 + EWMA + IQR + 누수 가드

**skill:** `feature-dev:feature-dev`

**Files:**
- Create: `backend/modules/screening/atr_calibration.py`
- Modify: `backend/modules/collector/scheduler.py` (08:35 잡 등록 + 안전모드 셋업)
- Modify: `backend/modules/notification/manager.py` (안전모드 텔레그램 메시지 헬퍼 추가)
- Test: `backend/tests/screening/test_atr_calibration.py`
- Test: `backend/tests/screening/test_atr_calibration_no_leakage.py` (신규 — `trade_date < CURRENT_DATE` 단위 테스트)

**Step 1: 테스트 작성**
- `tests/screening/test_atr_calibration.py` 검증 케이스:
  - `compute_kospi200_atr_p80(session, lookback_days=20, method="sma")` — 모의 KOSPI200 50종목 일봉 데이터로 종목별 20일 평균 ATR 계산 후 단면 P80
  - **IQR ×1.5 트리밍** 적용 — outlier 제거 후 분포에서 P80 산출
  - `method="ewma"` 분기 — λ=0.94 EWMA 가중치 적용
  - `np.percentile(trimmed, 80) * ATR_CEIL_MULT(=1.2)` 결과가 `min(ATR_CEIL_HARD=0.08, ...)`로 캡
  - **데이터 부족 폴백 3단**:
    - 1단: `market_data` 결측 ≥30종목 OR KOSPI200 마스터 ≥10종목 미만 → 직전일 Redis 캐시 (TTL 3거래일) 재사용
    - 2단: 직전일 캐시 부재 → `ATR_CEIL_HARD=0.08` 정적 사용
    - 3단: 2단 폴백 `metrics:atr:ceil:fallback_count` 카운터 ≥3회 누적 → **안전모드** (signals 발행 일시 중단 `SAFE_MODE_TIMEOUT_MIN=120`분 + 텔레그램 알림)
  - Redis `metrics:atr:ceil:{date}` 저장 (TTL 3거래일 = 약 5일)
  - Redis `metrics:atr:dist:{date}` 저장 (P10/P20/P50/P80/P95 + sample_n)
  - Redis `metrics:atr:ceil_grid:{date}` 저장 (mult `{1.0, 1.1, 1.2, 1.3}` × P80 결과 4종)
  - 단면 P80 vs 시계열 P80(직전 5일 캐시 평균) 차 ≥0.015 시 `quant_dist_drift_warn:{date}` 카운터 INCR
  - `ATR_CALIBRATION_ENABLED=false` → 잡 자체 no-op
- `tests/screening/test_atr_calibration_no_leakage.py`:
  - 캘리브레이션 쿼리에 `trade_date < CURRENT_DATE` (당일 행 미포함) 단위 검증
- 검증: `pytest tests/screening/ -v -k atr_calibration`
- 예상: FAIL

**Step 2: ATR 캘리브레이션 구현**
- `atr_calibration.py`:
  - `_load_kospi200_codes(session)` — `stocks.is_kospi200=True` 조회, 결과 ≥10 미만 시 `data/kospi200_static_backup.json` 폴백
  - `_compute_atr_ratio(daily_rows, window=14)` — ATR ÷ close (재사용: `screening/factors.py`의 `calc_volatility_factor`)
  - `_apply_iqr_trim(values, k=1.5)` — Q1 - k×IQR ~ Q3 + k×IQR 범위만 유지
  - `_apply_ewma(series, lambda_=0.94)` — EWMA 가중 평균
  - `compute_kospi200_atr_p80(session, lookback_days=20, method="sma")` — 단면 분포 → P80
  - `_record_grid_and_dist(redis, p80, sample_n, dist_pcts)` — Redis 메트릭 3종 저장
  - `_check_drift(redis, today_p80)` — 시계열 P80(직전 5일 평균) 비교
  - `run_atr_calibration(session_factory, redis_client, notifier)` — 메인 진입점, 폴백 3단 + 안전모드 트리거

**Step 3: scheduler 잡 등록 + 안전모드 게이트**
- `modules/collector/scheduler.py`:
  - `start()` 메서드에 `CronTrigger(hour=8, minute=35, second=0, timezone=tz)` 잡 추가
  - 잡 함수 `_atr_calibration_job(self)`: `if not settings.ATR_CALIBRATION_ENABLED: return` 가드
- 신호 발행 측(`modules/trading/engine.py`)에 안전모드 가드: Redis `safe_mode:active` 키 존재 시 신호 발행 skip + 로그
- 안전모드 텔레그램 알림 (`notification/manager.py`): `send_safe_mode_alert(reason, until)` 헬퍼

**Step 4: 누수 방지 + 테스트**
- 검증: `pytest tests/screening/ tests/test_scheduler.py tests/trading/test_engine_safe_mode.py -v`
- 예상: PASS (job_count +1, 누수 가드 PASS, 안전모드 가드 PASS)

**Step 5: 커밋**
```
git add backend/modules/screening/atr_calibration.py backend/modules/collector/scheduler.py backend/modules/notification/manager.py backend/modules/trading/engine.py backend/tests/screening/test_atr_calibration.py backend/tests/screening/test_atr_calibration_no_leakage.py backend/tests/test_scheduler.py
git commit -m "feat(phase8.6-sprint2): task2 — ATR 캘리브레이션 SMA/EWMA + IQR 트리밍 + 폴백 3단 + 안전모드 + 08:35 잡"
```

**완료 기준:**
- ✅ `test_atr_calibration.py` 8+ 케이스 PASS (SMA + EWMA + IQR + drift + grid + dist + 폴백 3단)
- ✅ `test_atr_calibration_no_leakage.py` PASS (`trade_date < CURRENT_DATE`)
- ✅ scheduler `_atr_calibration_job` 등록 확인 (job_count +1)
- ✅ Redis 키 4종 저장 확인 (수동 trigger): `metrics:atr:ceil:{date}` / `metrics:atr:dist:{date}` / `metrics:atr:ceil_grid:{date}` / `metrics:atr:ceil:fallback_count`
- ✅ 안전모드 진입 시 신호 발행 차단 + 텔레그램 알림 발송 확인

---

### Task 3: 병렬 OR tier 분리 + `signals.matched_tiers` + prev_close 거래량 컨펌 + gap_open 시초가 컷

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/trading/strategies/momentum_breakout.py`
  - 신규: `_evaluate_gap_open(snapshot, ctx) -> tuple[bool, dict]`
  - 신규: `_evaluate_prev_high(snapshot, ctx) -> tuple[bool, dict]`
  - 신규: `_evaluate_prev_close(snapshot, ctx) -> tuple[bool, dict]` (5분봉 거래량 컨펌 포함)
  - 수정: `generate_signal()` — `PARALLEL_OR_TIER_ENABLED` 분기, OR 결합 + matched_tiers 메타
  - 수정: `_shadow_evaluate()` — tier별 독립 pass/fail 카운터 (`shadow:tier:{name}:{passed|failed}:{date}`)
- Create: `backend/alembic/versions/{rev}_add_signals_matched_tiers.py` (`signals.matched_tiers JSON NULL` 컬럼)
- Modify: `backend/db/models/signals.py` (`matched_tiers: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)`)
- Modify: `backend/modules/trading/engine.py` (signals 저장 시 matched_tiers 영속화)
- Test: `backend/tests/strategies/test_parallel_or_tier.py` (신규)
- Test: `backend/tests/strategies/test_prev_close_volume_confirm.py` (신규)
- Test: `backend/tests/test_momentum_breakout.py` (회귀)

**tier별 sub-게이트 (v2 확정):**

| Tier | sub-게이트 | 진입 시간 |
|------|-----------|----------|
| `gap_open` | `gap_rate ≥ 0.03` AND `ATR ∈ [0.025, ATR_CEIL_HARD=0.08]` (절대 한계 적용) AND `current_price > open_price` (매물 흡수 컷 — 시초가 ≥ 현재가 시 거름) | 09:05 까지 우선 (TEMP_TIME_GUARD_SPRINT2: 09:00~09:10 차단 적용 후 09:10~ 진입) |
| `prev_high` | `current_price > prev_high × 1.001` (breakout) AND `ATR ∈ [ATR_FLOOR, ATR_CEIL_DYNAMIC]` | 09:10 ~ 13:00 |
| `prev_close` | 시간가드 + `current_price > prev_close × 1.001` AND **거래량 컨펌**(5분봉 양봉 2연속 OR vol_5m ≥ 직전 4봉 평균 ×2) | 09:10 ~ 13:00 |

**병렬 OR 결합:**
- 3개 tier 평가 → 통과 tier 수 ≥ 1이면 신호 발행
- `matched_tiers: list[str]` 기록 (사용자 확정 #4 채택)
- `confidence`는 통과 tier들의 **평균** 사용 (사용자 확정 #4 — 최댓값 X, 최리스크 보수 채택)
- 폴백 종목(`is_fallback=true`)은 `ATR_CEIL_FALLBACK=0.05` 고정 (동적 미적용)
- TEMP_TIME_GUARD_SPRINT2=true 시: 09:00~09:10 / 14:30+ 모든 tier 차단

**Step 1: 테스트 작성 — 병렬 OR + prev_close 거래량 컨펌 + gap_open 컷**
- `tests/strategies/test_parallel_or_tier.py` (10 케이스):
  - C1: `gap_open` 단독 (gap=4%, ATR=0.03, current>open) → 신호, `matched_tiers=["gap_open"]`
  - C2: `prev_high` 단독 (gap=1%, breakout, ATR=0.04) → 신호, `["prev_high"]`
  - C3: `prev_close` 단독 (오전 11시, gap=0.5%, current > prev_close+0.1%, **vol_5m=2.5×평균**) → 신호, `["prev_close"]`
  - C4: 모두 실패 → reject
  - C5: gap_open + prev_high 동시 → `["gap_open","prev_high"]`, confidence = 평균
  - C6: ATR=0.09(HARD 초과) — gap_open도 fail (절대 한계 적용) → reject
  - C7: ATR=0.020(하한 미달) — 모든 tier fail → reject
  - C8: 폴백 종목 + ATR=0.06(`ATR_CEIL_FALLBACK=0.05` 초과) → 모든 tier fail
  - C9: gap_open + 시초가 ≥ 현재가 (매물 흡수 실패) → gap_open fail
  - C10: TEMP_TIME_GUARD_SPRINT2=true + 09:05 → 모든 tier 차단(reject)
- `tests/strategies/test_prev_close_volume_confirm.py` (5 케이스):
  - V1: prev_close 시간가드 통과 + vol_5m=2.5× → 통과
  - V2: prev_close 시간가드 통과 + 5분봉 양봉 2연속 → 통과
  - V3: prev_close 시간가드 통과 + 거래량 컨펌 미달(vol=1.5× + 양봉 1개) → fail
  - V4: 5분봉 데이터 부재 → fail-safe(거름)
  - V5: 양봉 2연속 OR 조건이 OR 결합인지 확인 (둘 중 하나만 만족해도 통과)
- 검증: `pytest tests/strategies/ -v -k parallel_or or prev_close`
- 예상: FAIL

**Step 2: tier sub-게이트 함수 분리**
- `momentum_breakout.py`에 3개 함수 추가, 각각 `(passed: bool, detail: dict)` 반환
- prev_close 거래량 컨펌: 5분봉 vol_5m Redis 캐시 (Phase 6.1 패턴 재사용)
- `generate_signal()` 분기:
  ```
  if settings.TEMP_TIME_GUARD_SPRINT2 and (now < 09:10 or now >= 14:30):
      return reject(reason="temp_time_guard")
  if settings.PARALLEL_OR_TIER_ENABLED:
      results = [
          ("gap_open", *await self._evaluate_gap_open(...)),
          ("prev_high", *await self._evaluate_prev_high(...)),
          ("prev_close", *await self._evaluate_prev_close(...)),
      ]
      matched = [name for name, passed, _ in results if passed]
      if not matched:
          return reject(...)
      confidence = mean([detail["confidence"] for name, passed, detail in results if passed])
      return signal(matched_tiers=matched, confidence=confidence, ...)
  else:
      # 기존 직렬 로직
  ```
- 공통 게이트(`min_volume_floor`, `volume_threshold`, `trade_strength`, `confidence ≥ MIN_CONFIDENCE`)는 OR 결합 후 한 번만 적용

**Step 3: Alembic + signals.matched_tiers 영속화**
- `alembic revision --autogenerate -m "add signals.matched_tiers"` → `signals.matched_tiers JSON NULL`
- `engine.py`에서 신호 저장 시 `matched_tiers` 컬럼에 list[str] 저장 (NULL 안전 — 토글 OFF 시 NULL)

**Step 4: shadow 평가 tier별 카운터**
- `_shadow_evaluate()` 내 각 tier 독립 평가 결과를 `shadow:tier:{name}:{passed|failed}:{date}` Redis 카운터에 기록
- 검증: `pytest tests/strategies/ tests/test_momentum_breakout.py -v`
- 예상: PASS (회귀 + 신규)

**Step 5: 커밋**
```
git add backend/modules/trading/strategies/momentum_breakout.py backend/db/models/signals.py backend/alembic/versions/*.py backend/modules/trading/engine.py backend/tests/strategies/test_parallel_or_tier.py backend/tests/strategies/test_prev_close_volume_confirm.py backend/tests/test_momentum_breakout.py
git commit -m "feat(phase8.6-sprint2): task3 — 병렬 OR tier(독립 sub-게이트) + matched_tiers + prev_close vol 컨펌 + gap_open 시초가 컷 + ATR HARD 절대상한"
```

**완료 기준:**
- ✅ `test_parallel_or_tier.py` 10 케이스 PASS
- ✅ `test_prev_close_volume_confirm.py` 5 케이스 PASS
- ✅ `test_momentum_breakout.py` 회귀 0건 (`PARALLEL_OR_TIER_ENABLED=false` 토글 시 Sprint 1 동작 100% 복원)
- ✅ Alembic `signals.matched_tiers` 컬럼 추가 + NULL 안전성 확인
- ✅ tier별 shadow 카운터 Redis 기록 확인
- ✅ confidence = 평균 산식 검증

---

### Task 4: tier phi 상관 + 조건부 통과율 + 시뮬-실측 절대차 + R1~R4 격리 + 쿼터 캡 + ATR shadow 그리드 + drift warn

**Files:**
- Create: `backend/modules/screening/tier_correlation.py`
- Create: `backend/modules/screening/sim_vs_real_diff.py`
- Modify: `backend/api/routes/metrics.py` (신규 엔드포인트 3종)
- Modify: `backend/modules/notification/manager.py` (시뮬-실측 절대차 ≥0.15 알림 + drift warn 알림)
- Test: `backend/tests/screening/test_tier_correlation.py`
- Test: `backend/tests/screening/test_sim_vs_real_diff.py` (신규)
- Test: `backend/tests/strategies/test_parallel_or_quota_cap.py` (신규 — 일일 10건 + 동시보유 2 회로)
- Test: `backend/tests/strategies/test_parallel_or_r1_r4_isolation.py` (신규 — R1~R4 격리 회귀)

**Step 1: 테스트 작성**
- `test_tier_correlation.py`:
  - `compute_pairwise_phi(daily_tier_signals, window_days=7)` — tier 발생일 0/1 시퀀스 → **phi coefficient** 매트릭스 (Pearson 대신, 박퀀트 ★)
  - `compute_conditional_pass_rate(...)` — P(B|A) 조건부 통과율 (gap_open 통과 시 prev_high도 통과 빈도)
  - tier별 일별 신호 수 0건 시 skip (분모 0 회피)
  - 7일 누적 phi ≤ 0.3 + P(B|A) ≤ 0.5 목표선 PASS/FAIL
- `test_sim_vs_real_diff.py`:
  - `compute_sim_vs_real_diff(date, redis)` — shadow 통과율(예상) vs 실제 신호 통과율 절대차
  - 차이 ≥0.15 시 텔레그램 알림 트리거
  - `metrics:quant:sim_vs_real_diff:{date}` 저장
- `test_parallel_or_quota_cap.py` (최리스크 ★):
  - 일일 신호 한도 10건 — 11번째 신호 reject (matched_tiers 무관)
  - 동시 보유 2 포지션 — 3번째 진입 reject
  - 한도 도달 시 `quota_cap_blocked` 카운터 INCR
- `test_parallel_or_r1_r4_isolation.py` (최리스크 ★):
  - matched_tiers 추가가 R1(폴백 비중 ≥70% 자동 롤백)·R2·R3·R4 산식 분모/분자에 영향 없음
  - matched_tiers=["fallback_only"] 가상 케이스에서도 폴백 비중 계산 정확
- 검증: `pytest tests/ -v -k tier_correlation or sim_vs_real or quota_cap or r1_r4`
- 예상: FAIL

**Step 2: 메트릭 모듈 + 일별 집계 + ATR shadow 그리드**
- `tier_correlation.py`:
  - phi coefficient (binary correlation) 계산
  - 조건부 P(B|A) 계산
  - `signals.matched_tiers` JSON 컬럼에서 추출
- `sim_vs_real_diff.py`:
  - shadow:tier 카운터 vs signals 실제 카운터 비교
  - Redis 저장 + 알림
- daily_screening_metrics 패턴 재사용 (Sprint 1)
- ATR shadow 그리드는 Task 2에서 이미 저장 — Task 4는 API 노출만 추가

**Step 3: API 엔드포인트 + drift warn 알림**
- `GET /api/v1/metrics/tier-pass-rate` — tier별 일별 pass 7일 추이
- `GET /api/v1/metrics/tier-correlation` — phi + P(B|A) 매트릭스 7일 이동
- `GET /api/v1/metrics/sim-vs-real-diff` — 절대차 7일 추이 + 임계 0.15
- 응답 예: `{"window_days":7, "phi":{"gap_open-prev_high":0.12, ...}, "cond_prob":{"gap_open|prev_high":0.42, ...}, "max_phi":0.18, "threshold":0.3, "ok":true}`
- drift warn (`quant_dist_drift_warn` ≥1) 시 텔레그램 일별 1회 알림

**Step 4: G3 회로차단기 보정**
- 기존 G3 통과율 임계 → "체결 손실 누적" 임계로 일시 전환 (병렬 OR 직후 통과율 N배 시 G3 오발동 방지)
- OR 모드 전용 보정 계수 `G3_OR_MODE_MULT=N`(통과 tier 수 평균) 도입
- `modules/screening/g3_circuit_breaker.py` 또는 기존 가드 모듈에 분기 추가

**Step 5: 커밋**
```
git add backend/modules/screening/tier_correlation.py backend/modules/screening/sim_vs_real_diff.py backend/api/routes/metrics.py backend/modules/notification/manager.py backend/modules/screening/g3_circuit_breaker.py backend/tests/screening/test_tier_correlation.py backend/tests/screening/test_sim_vs_real_diff.py backend/tests/strategies/test_parallel_or_quota_cap.py backend/tests/strategies/test_parallel_or_r1_r4_isolation.py
git commit -m "feat(phase8.6-sprint2): task4 — phi 상관 + 조건부 P(B|A) + 시뮬-실측 절대차 + R1~R4 격리 + 쿼터 캡 + drift warn + G3 OR 보정"
```

**완료 기준:**
- ✅ `test_tier_correlation.py` 4+ 케이스 PASS (phi + cond_prob)
- ✅ `test_sim_vs_real_diff.py` 3+ 케이스 PASS
- ✅ `test_parallel_or_quota_cap.py` 3+ 케이스 PASS (일일 10건 + 동시 2 + 차단 카운터)
- ✅ `test_parallel_or_r1_r4_isolation.py` 4 케이스 PASS (R1~R4 각각 격리 검증)
- ✅ API 3종 응답 정상
- ✅ drift warn 알림 트리거 검증
- ✅ G3 회로차단기 OR 모드 보정 동작

---

### Task 5: tier-correlation-card + tier-pass-rate-card UI (ATR 분포 카드 제거)

**skill:** `frontend-design`

**Files:**
- Create: `frontend/components/diagnostics/tier-correlation-card.tsx`
- Create: `frontend/components/diagnostics/tier-pass-rate-card.tsx`
- Modify: `frontend/app/(dashboard)/diagnostics/page.tsx` (카드 2종 등록, ATR 분포 카드는 Sprint 4)

**Step 1: 카드 구현**
- `tier-correlation-card.tsx`:
  - `useSWR("/api/v1/metrics/tier-correlation", fetcher, { refreshInterval: 60000 })`
  - phi 3×3 히트맵 (recharts 또는 grid)
  - 조건부 P(B|A) 별도 표시
  - 목표선 phi ≤0.3 / P(B|A) ≤0.5 색상 인디케이터
  - 7일 이동 라인차트
- `tier-pass-rate-card.tsx`:
  - tier별 일별 pass 막대그래프 (gap_open/prev_high/prev_close)
  - "tier 다양성 ≥ 3종 활성" 5일 누적 인디케이터(G-C 게이트)
  - 시뮬-실측 절대차 추세 (별도 미니 차트, ≥0.15 시 빨강)

**Step 2: 통합 + 검증**
- diagnostics/page.tsx 카드 추가 (기존 fallback-signal-rate-card 옆)
- 검증: `cd frontend && npx tsc --noEmit && npm run dev` → `/diagnostics` 확인

**Step 3: 커밋**
```
git add frontend/components/diagnostics/tier-correlation-card.tsx frontend/components/diagnostics/tier-pass-rate-card.tsx frontend/app/(dashboard)/diagnostics/page.tsx
git commit -m "feat(phase8.6-sprint2): task5 — tier 상관(phi+조건부) + tier pass rate + 시뮬-실측 절대차 카드"
```

**완료 기준:**
- ✅ `npx tsc --noEmit` 에러 0건
- ✅ `/diagnostics` 카드 2종 정상 렌더
- ✅ phi + P(B|A) + 시뮬-실측 절대차 시각화 동작

---

### Task 6: 통합 회귀 + 임시 시간가드 + Kill-switch 런북 + deploy.md env 10종 등록

**skill:** `verification-before-completion`

**Step 1: 전체 회귀**
- `docker compose exec backend pytest -v` (전체 PASS)
- `cd frontend && npx tsc --noEmit`
- `PARALLEL_OR_TIER_ENABLED=false` 토글 회귀 — Sprint 1 동작 100% 복원
- `TEMP_TIME_GUARD_SPRINT2=true` 동작 확인 (09:00~09:10 / 14:30+ 차단 로그)
- `ATR_CALIBRATION_ENABLED=false` 토글 — `ATR_CEIL_HARD` 정적 사용 회귀

**Step 2: L5 사전 시뮬레이션 (박퀀트/최리스크 ★)**
- Sprint 1 shadow 데이터로 ATR_FLOOR=0.025 적용 시 fail율 산출
- fail율 ≥60%면 `ATR_FLOOR=0.020`으로 시작값 변경 후 deploy.md 변경 사유 기록
- 산출 결과: `docs/phase/phase8.6/sprint2/atr_floor_simulation.md`에 기록

**Step 3: Kill-switch 런북 작성 (deploy.md)**
- `deploy.md`에 다음 섹션 추가:
  ```
  ## Phase 8.6 Sprint 2 Kill-switch 런북

  ### 즉시 원복 (1줄)
  Railway 환경변수 `PARALLEL_OR_TIER_ENABLED=false` 설정 후 backend 재배포.

  ### 검증 (3단)
  1. curl https://api.{DOMAIN}/api/v1/diagnostics | jq .parallel_or_enabled  → false 확인
  2. PostgreSQL: SELECT COUNT(*) FROM signals WHERE matched_tiers IS NULL;  → 신규 신호 NULL 안전 확인
  3. 텔레그램 신호 발행 확인 (Sprint 1 직렬 동작 복원)

  ### 안전모드 해제 (수동)
  Redis: DEL safe_mode:active
  ```

**Step 4: deploy.md 업데이트**
- "Railway 환경변수 추가 확인: PARALLEL_OR_TIER_ENABLED, ATR_CALIBRATION_ENABLED, ATR_CALIBRATION_METHOD, ATR_FLOOR, ATR_CEIL_HARD, ATR_CEIL_FALLBACK, ATR_CEIL_MULT, ATR_CALIBRATION_WINDOW_DAYS, TEMP_TIME_GUARD_SPRINT2, SAFE_MODE_TIMEOUT_MIN" 항목 추가
- "Alembic 마이그레이션 적용: stocks.is_kospi200, signals.matched_tiers" 항목 추가
- "[관찰 항목] Paper 1거래일 ATR 캘리브레이션 잡 + 병렬 OR tier 신호 + matched_tiers 메타데이터 + 시뮬-실측 절대차 — Sprint 3 착수 게이트" 항목 추가 (종료 게이트 X, 관찰만)

**Step 5: 커밋 + 회고**
```
git add deploy.md docs/phase/phase8.6/sprint2/
git commit -m "chore(phase8.6-sprint2): task6 — 통합 회귀 + Kill-switch 런북 + deploy.md env 10종 + L5 시뮬"
```

**완료 기준:**
- ✅ pytest 전체 PASS (신규 43 + Sprint 1 회귀 50 = 총 93 PASS)
- ✅ npx tsc --noEmit 에러 0건
- ✅ env 토글 OFF 시 회귀 0건 (3종 토글 모두 검증, 39 PASS)
- ✅ Kill-switch 런북 deploy.md 등록
- ✅ L5 사전 시뮬 결과 문서화 (`docs/phase/phase8.6/sprint2/atr_floor_simulation.md`)
- ✅ deploy.md 환경변수 10종 + Alembic 2종 + 관찰 항목 등록
- ⚠️ Paper 1거래일은 **종료 조건 X** — 관찰 항목으로만 기록, Sprint 3 착수 게이트로 사용

---

## 최종 검증 계획 (Sprint 2 종료 시점)

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | All PASS (신규 ~40개 + 기존 회귀) |
| 프론트 타입체크 | `cd frontend && npx tsc --noEmit` | 에러 없음 |
| ATR 캘리브레이션 잡 | 수동 trigger | Redis 4종 키(`metrics:atr:ceil`, `dist`, `ceil_grid`, `fallback_count`) 저장 |
| 병렬 OR 단위 | `pytest tests/strategies/test_parallel_or_tier.py -v` | 10 PASS |
| prev_close 거래량 컨펌 | `pytest tests/strategies/test_prev_close_volume_confirm.py -v` | 5 PASS |
| 쿼터 캡 회로 | `pytest tests/strategies/test_parallel_or_quota_cap.py -v` | 3 PASS |
| R1~R4 격리 | `pytest tests/strategies/test_parallel_or_r1_r4_isolation.py -v` | 4 PASS |
| 시뮬-실측 절대차 | `pytest tests/screening/test_sim_vs_real_diff.py -v` | 3 PASS |
| 캘리브레이션 누수 | `pytest tests/screening/test_atr_calibration_no_leakage.py -v` | PASS |
| 토글 OFF 회귀 | `PARALLEL_OR_TIER_ENABLED=false pytest tests/test_momentum_breakout.py -v` | Sprint 1 동작 동일 |
| tier 상관 API | `curl /api/v1/metrics/tier-correlation \| jq .` | phi + cond_prob 매트릭스 |
| 시뮬-실측 절대차 API | `curl /api/v1/metrics/sim-vs-real-diff \| jq .` | 7일 추이, ok=true |
| Diagnostics UI 카드 2종 | 브라우저 `/diagnostics` | tier-correlation / tier-pass-rate 정상 |
| Kill-switch 런북 | deploy.md 수동 검증 | 1줄 원복 + 3단 검증 + 안전모드 해제 절차 |
| [관찰] Paper 1거래일 | 다음 영업일 16:00 | 본 신호 ≥1건, matched_tiers 정상 (Sprint 3 게이트, 종료 조건 X) |

---

## 재사용 자산

- Phase 4.7 (3팩터 분리) — tier sub-게이트 분리 구조 패턴
- Phase 4.8 Sprint 1 (KIS 일봉 보조 수집) — KOSPI200 일봉 데이터 소스로 `market_data` 재사용
- Phase 6.1 (5분봉 vol5m Redis) — prev_close 거래량 컨펌 5분봉 캐시 재사용
- Phase 8.5 Sprint 2.5 (`OverrideBanner`) — env 토글 시각화 패턴
- Phase 8.6 Sprint 1 (`shadow_evaluate` 카운터, `_resolve_min_volume_floor`) — tier별 shadow 카운터 동일 패턴
- Phase 8.6 Sprint 1 (daily_screening_metrics 일별 집계) — tier 상관/시뮬-실측 일별 집계 동일 패턴
- Phase 8.6 Sprint 1 (R1~R4 자동 롤백) — 격리 회귀 테스트 대상

---

## 알려진 리스크 (Sprint 2 한정)

| # | 리스크 | 완화 |
|---|--------|------|
| L1 | 병렬 OR로 일일 신호가 10건 한도(Phase 7.2)를 자주 초과 | Task 4 쿼터 캡 단위 테스트로 강제 적용 보장. Sprint 3에서 우선순위 큐 도입 |
| L2 | KOSPI200 ATR 캘리브레이션 데이터 부족 | Task 2 폴백 3단 (직전일 캐시 → HARD 정적 → 안전모드). 정적 백업 200종목 리스트 이중화 |
| L3 | gap_open ATR 우회 X(HARD 0.08 적용)로 시뮬-실측 괴리 재발 | Task 4 시뮬-실측 절대차 메트릭으로 1주 내 감지. drift warn 알림 |
| L4 | Alembic 2종(`is_kospi200`, `matched_tiers`) 프로덕션 적용 누락 | deploy.md "alembic upgrade head" + Railway 자동 배포 후 확인 |
| L5 | `ATR_FLOOR=0.025`가 박스권 종목 다수 거름 | Task 6 Step 2 사전 시뮬레이션으로 검증, fail율 ≥60%면 0.020으로 시작 |
| L6 | 병렬 OR 통과율 N배 → G3 회로차단기 오발동 또는 무력화 | Task 4 G3 OR 모드 보정 계수 + 임계 일시 전환(체결 손실 누적) |
| L7 | TEMP_TIME_GUARD_SPRINT2 누락 시 09:00~09:10 노이즈 데이터로 Paper 1거래일 평가 | env 기본값 true + deploy.md 수동 검증 항목 |
| L8 | 안전모드 진입 후 해제 누락으로 신호 발행 영구 차단 | SAFE_MODE_TIMEOUT_MIN=120 자동 해제 + Kill-switch 런북에 수동 해제 절차(`DEL safe_mode:active`) |

---

## 회귀 가드 (Phase 7.0 LIVE 파라미터 코드 잠금 — Sprint 1 G9 계승)

본 Sprint 어떤 변경에서도 다음은 수정 금지:

- `MAX_POSITION = 2`
- `POSITION_SIZE_PCT = 0.05` (5%)
- `DAILY_MAX_LOSS_PCT = -0.02` (-2%)
- `EMERGENCY_STOP_PCT = -0.03` (-3%)

위 4개 변경 시도 시 빌드 실패 (Sprint 1 5개 회귀 테스트로 보장).

---

## 완료 후 다음 단계

Sprint 2 완료 → 사용자 안내:

1. **Paper 1거래일 관찰** (Sprint 3 착수 게이트, 종료 조건 X)
2. **Sprint 3 착수 (`volume_surge` tier 신설 + 시간 필터 본 가드)** — Paper 1일 통과 시 권장
3. **파라미터 튜닝** — `ATR_FLOOR=0.020`, `ATR_CEIL_MULT` shadow 그리드 분석 결과 검토
4. **Sprint 4 사전 준비** — walk-forward 60일 + KS 검정 + ATR 분포 카드 (이관)

> v2 본 문서는 사용자 확정 5종 + 4명 리뷰 합의를 모두 반영한 최종안. Step 1(테스트 작성)부터 즉시 진행 가능.

---

## Sprint 마무리

**완료일:** 2026-04-29
**PR:** (sprint-close 완료 후 기록 예정)
