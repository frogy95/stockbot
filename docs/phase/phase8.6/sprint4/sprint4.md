# Sprint 4: Walk-forward 백테스트 + 시뮬↔실측 자동 감지 + 임계 재조정 진단 (Phase 8.6)

**Goal:** 60거래일+ KIS 분봉/일봉 데이터로 walk-forward 백테스트(TimeSeriesSplit 40/20)를 실행하여 (1) 현 임계가 시장에 부적합한지 진단, (2) Bootstrap 95% CI 하한과 KS/카이제곱 검정으로 시뮬-실측 분포 괴리를 자동 감지, (3) LIVE 토글 게이트 G-Bt1·G-Bt2·G-Bt3 자동 평가 잡 코드를 구현한다.

**Architecture:** `backend/modules/backtest/` 패키지 신규 생성 — `historical_loader.py`(KIS 분봉/일봉 백필), `walkforward.py`(TimeSeriesSplit 슬라이딩 + 시뮬 신호 발생률 산출), `distribution_check.py`(KS 2-sample + 카이제곱), `bootstrap_ci.py`(1000회 리샘플링), `live_gate.py`(G-Bt1/2/3 직렬 AND 평가). 매주 월요일 00:00 KST 자동 잡으로 KS 검정 트리거, 결과를 Redis + DB에 기록하고 텔레그램 알림. 진단 리포트는 시뮬 신호 발생률 vs 5/7+5/8 실측(0건)을 비교하여 **임계 재조정 후보**(volume_threshold·체결강도·호가비율·prev_close tier 등)를 산출한다. 임계 재조정 자체는 Sprint 4 후속 hotfix 또는 Sprint 5에서 적용.

**Tech Stack:** Python 3.12 / scipy.stats(KS·카이제곱) / numpy(percentile·bootstrap) / SQLAlchemy async / APScheduler / Next.js 16 admin 페이지

**Sprint 기간:** 2026-05-08 ~ (사용자 검토 후 구현, 예상 5~8일)
**이전 스프린트:** Sprint 3 (1116 PASS, PR #200 develop 머지 대기, 2026-05-08 hotfix `time-filter-block-counter` 포함)
**브랜치명:** `phase8.6-sprint4`

---

## 사전 컨텍스트 (필독)

### Sprint 4 즉시 착수 사유 (phase8.6.md §4 예외 조항, 2026-05-08)

Sprint 3 v2.9.0 배포 후 Paper 2거래일(5/7+5/8) 관찰:
- **G2 신호 0건 누적** (R1 발동까지 5/11 1거래일 남음)
- **근본 원인이 Sprint 3 변경분 외**: 2차 스크리닝 통과 종목 단일(950160 ETF) + `volume_threshold` 2.0 vs 측정 1.26 (1.6배 갭)
- 5거래일 관찰 강제 조건은 G-Bt3 입력값을 만들어내지 못함이 자명 → Sprint 4 즉시 착수

→ Sprint 4 walk-forward 결과로 **임계 재조정 후보** 산출 → hotfix 적용 → 의미 있는 시점에 Paper 관찰 재시작.

판정 리포트: `.claude/agent-memory/phase8-6-sprint2-observation-check/observation_2026-05-08.md`

### 의존성 체크

- ✅ Sprint 2 완료 (병렬 OR + ATR 캘리브레이션)
- ✅ Sprint 3 완료 (volume_surge + 시간 필터)
- ✅ KIS REST 일봉 인프라: `backend/modules/collector/sources/kis_daily_collector.py` 재사용 가능 (배치 50건, 지수 백오프 2-4-8, source="kis_daily")
- ⚠️ KIS 분봉 백필: 본격 인프라는 Phase 9 Sprint 0 — 본 Sprint에서는 **일봉 60거래일** 우선 사용 + 5분봉은 가용 데이터(Sprint 3에서 vol5m Redis 축적 중)만 활용
- ✅ scipy 미설치 → requirements.txt에 추가 필요
- ✅ 기존 `atr_calibration.py`·`tier_correlation.py`·`sim_vs_real_diff.py` 모듈 패턴 재사용

---

## 제외 범위

- **임계 재조정 자체 적용**: Sprint 4는 **진단 + 후보 산출까지**. 실제 `volume_threshold`·체결강도·호가비율 변경은 후속 hotfix 또는 Sprint 5
- **5분봉 60거래일 백필**: Phase 9 Sprint 0에서 본격 진행. Sprint 4는 일봉 60일 + 가용 5분봉만 사용
- **자동 LIVE 토글**: G-Bt1·G-Bt2·G-Bt3 충족 평가만 자동, 실제 LIVE 활성화는 사용자 수동 (텔레그램 2단계 확인)
- **백테스트 PnL 시뮬레이션**: 본 Sprint는 **신호 발생률 산출**까지. 손익 시뮬레이션은 Phase 9·10 후속
- **Paper 관찰 재시작**: Sprint 4 결과 기반 hotfix 적용 후 별도 일정 (Sprint 4 자체 산출물 아님)

---

## 실행 플랜

### Phase 1 (순차 — 인프라 전제)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | scipy 의존성 추가 + backtest 패키지 스캐폴드 + Alembic 마이그레이션 (backtest_runs / backtest_signal_metrics 테이블) | 백엔드 | — |

### Phase 2 (순차 — 데이터 → 백테스트 → 검정)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | historical_loader — 60거래일 일봉 데이터 로드 + 박스권/추세장 분류기 + 데이터셋 충분성 검증 | 백엔드 | `feature-dev:feature-dev` |
| Task 3 | walkforward — TimeSeriesSplit 40/20 슬라이딩 + tier별 시뮬 신호 발생률 산출 + 시뮬-실측 격차 진단 리포트 | 백엔드 | `feature-dev:feature-dev` |
| Task 4 | distribution_check (KS 2-sample + 카이제곱) + bootstrap_ci (95% CI 1000회) | 백엔드 | — |
| Task 5 | live_gate — G-Bt1/G-Bt2/G-Bt3 직렬 AND 자동 평가 잡 + 매주 월요일 00:00 KST 트리거 + 텔레그램 알림 | 백엔드 | — |

### Phase 3 (병렬 가능 — API + UI)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | API 라우터 (`/api/v1/backtest/run`, `/distribution-check`, `/live-gate-status`) + admin 토큰 가드 | 백엔드 | — |
| Task 7 | admin 백테스트 페이지 (실행 버튼 + 결과 테이블 + KS 7주 이동 + LIVE 토글 게이트 카드) | 프론트엔드 | `frontend-design` |

### Phase 4 (순차 — 통합 검증)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 8 | 60일 백테스트 1회 실행 + KS 인위 데이터 트리거 + 임계 재조정 후보 리포트 작성 | 전체 | `verification-before-completion` |

> **팀 실행**: Phase 3을 팀으로 실행하면 Task 6(백엔드)/Task 7(프론트엔드)가 병렬 가능 (파일 소유권 분리됨).

---

## Task 1: 인프라 스캐폴드 + scipy + Alembic

**Files:**
- Modify: `backend/requirements.txt` (scipy 추가)
- Create: `backend/modules/backtest/__init__.py`
- Create: `backend/modules/backtest/models.py` (TypedDict / dataclass for run/signal/gate result)
- Create: `backend/core/models/backtest.py` (SQLAlchemy: BacktestRun, BacktestSignalMetric, LiveGateStatus)
- Create: `backend/alembic/versions/{hash}_add_backtest_tables.py`
- Test: `backend/tests/backtest/__init__.py`

**Step 1: scipy 추가**
- `backend/requirements.txt`에 `scipy>=1.14,<2.0` 추가 (KS 2-sample / 카이제곱 / bootstrap에 사용)
- 검증: `docker compose exec backend python -c "from scipy import stats; print(stats.ks_2samp([1,2,3],[1,2,4]))"`
- 예상: `KstestResult(statistic=...)` 출력

**Step 2: SQLAlchemy 모델 정의**
- `backend/core/models/backtest.py` 생성
- `BacktestRun`: id, run_id (UUID str), period_start (date), period_end (date), n_trading_days (int), regime_box_days (int), regime_trend_days (int), status ("running"|"completed"|"failed"), error (str|null), started_at, completed_at
- `BacktestSignalMetric`: id, run_id (FK), tier (str: gap_open/prev_high/prev_close/volume_surge), pass_rate_simulated (float), pass_rate_actual (float|null), ks_statistic (float|null), ks_pvalue (float|null), bootstrap_ci_lower (float|null), bootstrap_ci_upper (float|null), recorded_at
- `LiveGateStatus`: id, evaluated_at, g_bt1_passed (bool), g_bt2_passed (bool), g_bt3_passed (bool), all_passed (bool), details (JSONB)
- 인덱스: `BacktestRun(period_end DESC)`, `BacktestSignalMetric(run_id, tier)`

**Step 3: Alembic 마이그레이션 생성**
- `docker compose exec backend alembic revision --autogenerate -m "add backtest tables for phase8.6 sprint4"`
- 생성된 파일을 검토하여 3개 테이블 + 인덱스 모두 포함 확인
- 검증: `docker compose exec backend alembic upgrade head`
- 예상: head 적용 + 에러 없음

**Step 4: backtest 패키지 스캐폴드**
- `backend/modules/backtest/__init__.py` (빈 파일)
- `backend/modules/backtest/models.py`: `@dataclass`로 `BacktestConfig`, `BacktestResult`, `GateEvalResult` 정의 (in-memory 결과 객체용; DB 모델과는 별개)

**Step 5: 커밋**
```
git checkout -b phase8.6-sprint4
git add backend/requirements.txt backend/core/models/backtest.py backend/alembic/versions/ backend/modules/backtest/__init__.py backend/modules/backtest/models.py backend/tests/backtest/__init__.py
git commit -m "feat(phase8.6-sprint4): task1 — scipy 의존성 + backtest 모델/마이그레이션 스캐폴드"
```

**완료 기준:**
- ⬜ scipy import 성공
- ⬜ alembic upgrade head 통과
- ⬜ 3개 테이블 생성 확인 (`\d backtest_runs` 등)

---

## Task 2: historical_loader + 박스권/추세장 분류

**Files:**
- Create: `backend/modules/backtest/historical_loader.py`
- Test: `backend/tests/backtest/test_historical_loader.py`

**Step 1: 테스트 작성 (TDD)**
- `tests/backtest/test_historical_loader.py` 생성
- 시나리오:
  - `load_kospi_daily(period_end, n_days=60)` — `MarketData` source∈("data_go_kr","kis_daily") 필터로 KOSPI 일봉 60거래일 로드, 결과는 pandas DataFrame 또는 list[dict] (날짜 오름차순)
  - `classify_regime(df)` — KOSPI 60일 표준편차 σ 산출 후 `σ ≤ 1.5σ_long_term` → 박스권 / 그 외 → 추세장으로 일별 라벨링. 반환 dict: `{"box_days": int, "trend_days": int, "labels": list[str]}`
  - `is_dataset_sufficient(regime_summary)` — 박스권 ≥20일 AND 추세장 ≥20일 AND 총 ≥60일 충족 시 True
  - 거래일 부족 시 `DatasetInsufficientError` 발생
- 검증: `docker compose exec backend pytest tests/backtest/test_historical_loader.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: historical_loader 구현**
- `backend/modules/backtest/historical_loader.py` 생성
- `async def load_kospi_daily(session: AsyncSession, period_end: date, n_days: int = 60) -> list[dict]`:
  - `MarketData`에서 `source.in_(["data_go_kr", "kis_daily"])`, `Stock.is_kospi200=True` 종목들의 일봉 로드
  - 거래일이 부족하면 `kis_daily_collector.collect_all(target_date)`로 보강(선택)은 생략 — 부족 시 `DatasetInsufficientError`
  - 반환: 날짜별 KOSPI 평균 종가/등락률/표준편차 시계열 (간단한 시장 레짐 산출용)
- `def classify_regime(daily_series: list[dict]) -> dict`:
  - `numpy.std`로 60일 σ_long_term 산출
  - 각 일별 20일 rolling σ가 σ_long_term × 1.5 이하면 "box", 그 외 "trend" 라벨
  - 라벨 카운트 반환
- `def is_dataset_sufficient(summary: dict) -> bool`:
  - 박스권 ≥20일 AND 추세장 ≥20일 AND 총 일수 ≥60일

**Step 3: KIS 일봉 백필 메커니즘 차용 (선택적 보강)**
- DB에 60일분 KOSPI 200 종목 일봉이 부족할 경우 운영자가 수동으로 호출 가능한 helper:
  - `async def backfill_missing_daily(session, start_date, end_date) -> int`:
    - `KISDailyCollector.collect_all(target_date=str)`을 거래일별로 순차 호출 (Phase 9 Sprint 0 인프라 일부 차용)
    - rate limit 보호: 거래일 간 1초 sleep
- 본 함수는 admin API에서만 호출 (Task 6에서 라우팅)

**Step 4: 검증 + 커밋**
- 검증: `docker compose exec backend pytest tests/backtest/test_historical_loader.py -v`
- 예상: 6 PASS
- `git add backend/modules/backtest/historical_loader.py backend/tests/backtest/test_historical_loader.py`
- `git commit -m "feat(phase8.6-sprint4): task2 — historical_loader 60일 일봉 + 박스권/추세장 분류"`

**완료 기준:**
- ⬜ pytest 6 PASS
- ⬜ DB에 KOSPI200 60일 일봉 존재 확인 (없으면 backfill_missing_daily 호출 안내)

---

## Task 3: walkforward 엔진 + 시뮬-실측 격차 진단

**Files:**
- Create: `backend/modules/backtest/walkforward.py`
- Test: `backend/tests/backtest/test_walkforward.py`

**Step 1: 테스트 작성 (TDD)**
- 시나리오:
  - `TimeSeriesSplit` 기반 슬라이딩: 60일 데이터 → 1 슬라이드 (학습 40 / 검증 20). 80일 → 2 슬라이드. 100일 → 3 슬라이드
  - `simulate_tier_pass_rate(daily_series, tier_config)` — tier별 진입 조건을 일별로 평가하여 `pass율 = 통과일수 / 총일수` 산출. tier_config는 `{"prev_high": {"volume_threshold": 2.0, "atr_floor": 0.025, ...}}` 형태
  - `compute_actual_pass_rate(session, period_start, period_end)` — `signals` 테이블에서 실측 tier별 발행 비율 산출
  - `diagnose_threshold_gap(simulated, actual, threshold=5.0)` — 시뮬 vs 실측 격차 ≥ 5%p 시 "임계 재조정 후보" 플래그 + 어느 임계 변경 시 격차가 줄어드는지 grid search (volume_threshold ∈ [1.5, 1.6, 1.8, 2.0], 호가비율 ∈ [1.0, 1.5, 2.0])
- 검증: pytest FAIL 예상

**Step 2: walkforward 구현**
- `class WalkForwardRunner`:
  - `async def run(self, period_end: date, n_days: int = 60) -> BacktestResult`:
    1. historical_loader로 데이터 로드
    2. 박스권 ≥20 + 추세장 ≥20 검증, 미충족 시 즉시 실패
    3. TimeSeriesSplit 슬라이드 (학습 40 / 검증 20)
    4. 슬라이드별 tier 4종(`gap_open`/`prev_high`/`prev_close`/`volume_surge`) 시뮬 pass율 산출
    5. 학습-검증 R² 격차 ≤ 10%p 검증 (G-Bt1)
    6. 결과를 `BacktestRun` + `BacktestSignalMetric`에 INSERT
- `simulate_tier_pass_rate()`: 현재 운영 중인 임계(`settings.VOLUME_SURGE_VOL_RATIO`, `momentum_breakout`의 `volume_threshold` 등)를 그대로 사용한 시뮬레이션
- `diagnose_threshold_gap()`:
  - 시뮬 pass율 vs 실측 pass율 격차 산출
  - 격차 ≥ 5%p이고 실측 < 시뮬 → "임계가 시장 부적합" 플래그
  - grid search: volume_threshold·체결강도·호가비율 후보 변경 시 시뮬 pass율 vs 실측 격차 최소화 조합 산출
  - 반환: `{"flag": "threshold_too_strict", "candidates": {"volume_threshold": 1.6, ...}}`

**Step 3: 진단 리포트 로깅**
- 결과 JSON을 `logger.info("backtest_diagnose ...", extra={...})` 구조화 로깅
- Task 8에서 이 로그를 사람이 읽을 수 있는 마크다운 리포트로 추출

**Step 4: 검증 + 커밋**
- `docker compose exec backend pytest tests/backtest/test_walkforward.py -v`
- 예상: 8 PASS
- 커밋: `feat(phase8.6-sprint4): task3 — walkforward 엔진 + 임계 재조정 진단`

**완료 기준:**
- ⬜ pytest 8 PASS
- ⬜ 60일 더미 데이터로 1 슬라이드 실행 성공
- ⬜ diagnose_threshold_gap이 시뮬>실측 격차 인식

---

## Task 4: KS 검정 + 카이제곱 + Bootstrap CI

**Files:**
- Create: `backend/modules/backtest/distribution_check.py`
- Create: `backend/modules/backtest/bootstrap_ci.py`
- Test: `backend/tests/backtest/test_distribution_check.py`
- Test: `backend/tests/backtest/test_bootstrap_ci.py`

**Step 1: 테스트 작성**
- distribution_check 시나리오:
  - 동일 분포 두 표본 → KS p ≥ 0.05 (귀무가설 기각 안 함)
  - 명백히 다른 두 표본(평균 5σ 차이) → KS p < 0.05
  - 카이제곱 적합도 검정도 동일 패턴 검증
  - p < 0.05 시 `BACKTEST_REBUILD_REQUIRED` env 플래그 True 전환 + 텔레그램 알림 트리거 함수 호출
- bootstrap_ci 시나리오:
  - 일평균 신호 수 [0, 0, 1, 0, 2] → 95% CI 하한 < 1 (FAIL)
  - 일평균 신호 수 [2, 2, 3, 2, 3] → 95% CI 하한 ≥ 1 (PASS)
  - n_resamples=1000 default

**Step 2: distribution_check 구현**
- `def ks_test(simulated: list[float], actual: list[float]) -> dict`:
  - `scipy.stats.ks_2samp(simulated, actual)` 호출
  - 반환: `{"statistic": float, "pvalue": float, "rebuild_required": pvalue < 0.05}`
- `def chi_square_test(observed: list[int], expected: list[float]) -> dict`:
  - `scipy.stats.chisquare(observed, expected)` 호출
- `async def trigger_rebuild_alert(notifier, ks_result, chi_result) -> None`:
  - p < 0.05 시 텔레그램 메시지 발송 + Redis `metrics:backtest:rebuild_required = "true"` 설정

**Step 3: bootstrap_ci 구현**
- `def bootstrap_ci_lower(daily_signal_counts: list[int], n_resamples: int = 1000, ci: float = 0.95) -> tuple[float, float]`:
  - `numpy.random.choice`로 1000회 리샘플링 → 평균 분포 → 2.5/97.5 퍼센타일
  - 반환: (lower, upper)
- `def evaluate_g_bt2(daily_signal_counts: list[int]) -> bool`:
  - CI 하한 ≥ 1 시 PASS

**Step 4: 검증 + 커밋**
- `docker compose exec backend pytest tests/backtest/test_distribution_check.py tests/backtest/test_bootstrap_ci.py -v`
- 예상: 7 PASS
- 커밋: `feat(phase8.6-sprint4): task4 — KS 검정 + 카이제곱 + Bootstrap CI`

**완료 기준:**
- ⬜ pytest 7 PASS
- ⬜ KS 인위 데이터(평균 5σ 차이) p < 0.05 확인

---

## Task 5: LIVE 토글 게이트 G-Bt1·G-Bt2·G-Bt3 자동 평가 잡

**Files:**
- Create: `backend/modules/backtest/live_gate.py`
- Modify: `backend/modules/scheduler/scheduler.py` (월요일 00:00 KST 잡 추가)
- Test: `backend/tests/backtest/test_live_gate.py`
- Test: `backend/tests/scheduler/test_scheduler_backtest_job.py` (또는 기존 test_scheduler.py 확장)

**Step 1: live_gate 테스트 작성**
- 시나리오:
  - G-Bt1: walk-forward 검증 R² 학습 대비 -10%p 이내 → PASS
  - G-Bt2: Bootstrap CI 하한 ≥ 1 → PASS
  - G-Bt3: Paper 5거래일 G-A(일평균 ≥1.5) + G-B(0건 일수 ≤30%) → PASS (입력값은 `signals` 테이블에서 조회)
  - 3개 모두 PASS 시에만 `all_passed=True`
  - 1개라도 FAIL → `all_passed=False` + dry_run 강제 유지

**Step 2: live_gate 구현**
- `class LiveGateEvaluator`:
  - `async def assess(self, session) -> GateEvalResult`:
    - 최신 `BacktestRun` 조회
    - G-Bt1: `BacktestSignalMetric` 학습/검증 격차 산출
    - G-Bt2: bootstrap_ci_lower 호출
    - G-Bt3: 직전 5거래일 `signals` 테이블에서 일별 신호 수 산출
    - 결과를 `LiveGateStatus`에 INSERT
    - `all_passed=False` 시 텔레그램 알림 + `metrics:live_gate:dry_run_forced = "true"` Redis set
  - 모든 게이트 평가는 env 토글 (`LIVE_GATE_AUTO_EVAL_ENABLED=True`)

**Step 3: 스케줄러 등록**
- `backend/modules/scheduler/scheduler.py`에 매주 월요일 00:00 KST 잡 추가:
  - `CronTrigger(day_of_week="mon", hour=0, minute=0, timezone="Asia/Seoul")`
  - 잡 함수: `run_weekly_backtest_and_gate_assess()` — walk-forward 실행 + KS 검정 + LIVE 게이트 평가 통합 실행
- 잡 키 적재: `scheduler:last_backtest_assess` (Sprint 3 Task 4에서 정립한 `_save_last_timestamp` 패턴 재사용)

**Step 4: 검증 + 커밋**
- `docker compose exec backend pytest tests/backtest/test_live_gate.py tests/scheduler/test_scheduler_backtest_job.py -v`
- 예상: 6 PASS
- 커밋: `feat(phase8.6-sprint4): task5 — LIVE 토글 게이트 G-Bt1/G-Bt2/G-Bt3 자동 평가 잡`

**완료 기준:**
- ⬜ pytest 6 PASS
- ⬜ 스케줄러 잡 등록 확인 (월요일 00:00 KST)
- ⬜ env 토글 동작 (`LIVE_GATE_AUTO_EVAL_ENABLED=False` 시 스킵)

---

## Task 6: API 라우터

**Files:**
- Create: `backend/api/routes/backtest.py`
- Modify: `backend/main.py` (라우터 등록)

**Step 1: 엔드포인트 정의**
- `POST /api/v1/backtest/run` — admin 토큰 필수 (`Depends(get_current_user)` + role 체크 또는 별도 admin guard). body: `{"period_end": "2026-05-08", "n_days": 60}`. 비동기 실행 (BackgroundTasks 사용 또는 즉시 응답 + 상태 폴링)
- `GET /api/v1/backtest/runs?limit=10` — 최근 실행 목록
- `GET /api/v1/backtest/runs/{run_id}` — 단일 실행 상세 (signal metrics 포함)
- `GET /api/v1/backtest/distribution-check` — 최근 KS 검정 결과 7주
- `GET /api/v1/backtest/live-gate-status` — 최신 G-Bt1/2/3 평가 결과
- `POST /api/v1/backtest/backfill-daily` — admin 전용, `historical_loader.backfill_missing_daily` 트리거

**Step 2: 권한 가드**
- 기존 `api/deps.py::get_current_user` 활용 + 사용자 role 검증
- role 시스템이 없으면 환경변수 `BACKTEST_ADMIN_USER_ID` 단일 사용자 ID 매칭으로 단순화 (**2026-05-08 사용자 결정: A안 채택** — 임시 해법, Phase 8.7 role 시스템에서 정립)

**Step 3: 검증**
- `curl -s -X POST http://localhost:8000/api/v1/backtest/run -H "Authorization: Bearer $TOKEN" -d '{"period_end":"2026-05-08","n_days":60}' | jq .`
- 예상: `{"run_id": "...", "status": "running"}`
- `curl -s http://localhost:8000/api/v1/backtest/live-gate-status -H "Authorization: Bearer $TOKEN" | jq .`
- 예상: `{"g_bt1_passed": false, "g_bt2_passed": false, "g_bt3_passed": false, "all_passed": false}` (초기값)

**Step 4: 커밋**
- 커밋: `feat(phase8.6-sprint4): task6 — backtest API 라우터 (admin 가드)`

**완료 기준:**
- ⬜ 5개 엔드포인트 응답 확인
- ⬜ 비인증 요청 401 반환

---

## Task 7: admin 백테스트 페이지

**Files:**
- Create: `frontend/app/(dashboard)/admin/backtest/page.tsx`
- Create: `frontend/components/diagnostics/backtest-result-table.tsx`
- Create: `frontend/components/diagnostics/ks-trend-card.tsx`
- Create: `frontend/components/diagnostics/live-gate-card.tsx`

**Step 1: 페이지 구조**
- `/admin/backtest` 경로 — 기존 `(dashboard)/diagnostics` 레이아웃 재사용
- 섹션:
  1. **Walk-forward 실행** — period_end / n_days 입력 + 실행 버튼 → POST `/api/v1/backtest/run`
  2. **최근 실행 결과 테이블** — tier별 학습/검증 pass율 + Bootstrap CI
  3. **시뮬-실측 KS 검정 7주 이동** — line chart (recharts) + p<0.05 임계선
  4. **LIVE 토글 게이트 카드** — G-Bt1/G-Bt2/G-Bt3 ✅/❌ + all_passed 상태
  5. **임계 재조정 후보 카드** — Task 3 diagnose_threshold_gap 결과 (volume_threshold·체결강도 등 권고값)

**Step 2: 컴포넌트 분리**
- `backtest-result-table.tsx`: tier 4종 행 + 학습/검증 pass율/CI/격차 컬럼
- `ks-trend-card.tsx`: 7주 KS p-value 추이 + 0.05 임계선 표시
- `live-gate-card.tsx`: 3개 게이트 상태 + dry_run_forced 배너 (Sprint 2.5 OverrideBanner 패턴)

**Step 3: API 클라이언트**
- `frontend/lib/api.ts`에 `runBacktest()`, `getBacktestRuns()`, `getLiveGateStatus()` 추가 (기존 `apiPost`/`apiGet` 패턴 사용)

**Step 4: 검증 + 커밋**
- `cd frontend && npx tsc --noEmit`
- 예상: 0 errors
- 브라우저 렌더 확인 (Playwright 또는 수동)
- 커밋: `feat(phase8.6-sprint4): task7 — admin 백테스트 페이지 + 4종 카드`

**완료 기준:**
- ⬜ tsc 0 errors
- ⬜ 페이지 렌더 + 실행 버튼 동작
- ⬜ live-gate-card 3개 게이트 상태 시각화

---

## Task 8: 60일 백테스트 1회 실행 + 임계 재조정 후보 리포트

**Files:**
- Create: `docs/phase/phase8.6/sprint4/backtest_diagnostic_report.md`
- Create: `docs/phase/phase8.6/sprint4/threshold_recalibration_candidates.md`

**Step 1: 60일 백테스트 실제 실행**
- DB에 KOSPI 200 60일 일봉이 충분한지 확인:
  - `docker compose exec db psql -U postgres -d stockbot -c "SELECT COUNT(DISTINCT data_date) FROM market_data WHERE source IN ('data_go_kr','kis_daily') AND data_date >= CURRENT_DATE - INTERVAL '90 days';"`
  - 60 미만이면 `POST /api/v1/backtest/backfill-daily` 호출하여 보강
- `POST /api/v1/backtest/run` 호출 → run_id 획득
- 완료 대기 후 `GET /api/v1/backtest/runs/{run_id}`로 결과 조회

**Step 2: 진단 리포트 작성**
- `backtest_diagnostic_report.md`:
  - 60일 데이터 분포 (박스권/추세장 일수)
  - tier별 시뮬 pass율 vs 5/7+5/8 실측 (0건)
  - Bootstrap CI 하한
  - KS 검정 결과
  - LIVE 토글 게이트 G-Bt1/2/3 판정

**Step 3: 임계 재조정 후보 리포트**
- `threshold_recalibration_candidates.md`:
  - **현 임계가 시장 부적합인지 판정**: 시뮬 pass율 ≥ 5% AND 실측 ≈ 0% → "현 임계 부적합" 결론
  - **재조정 후보**:
    - `volume_threshold`: 현 2.0 → 권고 1.5~1.6 (5/8 측정 1.26 + 시뮬 grid search 결과)
    - 2차 스크리닝 체결강도 임계: 현 값 → 권고
    - 호가비율 임계: 현 값 → 권고
    - prev_close tier 임계: 현 값 → 권고
  - **적용 방식 안내**: hotfix 또는 Sprint 5에서 env 변경

**Step 4: KS 인위 트리거 검증**
- 인위적으로 시뮬 pass율 38.9% vs 실측 3% 데이터 주입 (test fixture) → KS p < 0.05 확인 + 텔레그램 알림 발송 확인 (mock)

**Step 5: pytest 전체 + 커밋**
- `docker compose exec backend pytest -v` (전체 회귀)
- `cd frontend && npx tsc --noEmit`
- 커밋: `docs(phase8.6-sprint4): task8 — 60일 백테스트 진단 리포트 + 임계 재조정 후보`

**완료 기준:**
- ⬜ 60일 백테스트 1회 실행 완료
- ⬜ 진단 리포트 2개 작성
- ⬜ KS 인위 데이터 트리거 검증
- ⬜ pytest 전체 통과
- ⬜ tsc 0 errors

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 1116+ passed (Sprint 3 회귀 0) |
| backtest 단위 테스트 | `docker compose exec backend pytest tests/backtest/ -v` | 27+ passed |
| Alembic 적용 | `docker compose exec backend alembic upgrade head` | head 적용 |
| scipy import | `docker compose exec backend python -c "from scipy import stats"` | 에러 없음 |
| API run | `curl -X POST .../backtest/run -H "Authorization: ..." -d '...'` | run_id 반환 |
| API live-gate | `curl .../backtest/live-gate-status -H "Authorization: ..."` | g_bt1/2/3 반환 |
| 프론트 타입체크 | `cd frontend && npx tsc --noEmit` | 0 errors |
| admin 페이지 렌더 | 브라우저 `/admin/backtest` | 4종 카드 표시 |
| 진단 리포트 | `docs/phase/phase8.6/sprint4/backtest_diagnostic_report.md` | 작성 완료 |
| 임계 재조정 후보 | `docs/phase/phase8.6/sprint4/threshold_recalibration_candidates.md` | 작성 완료 |

---

## 신규/변경 환경변수 (Railway 수동 설정 대상)

| Env | 기본값 | 용도 |
|-----|--------|------|
| `BACKTEST_ENABLED` | `True` | walk-forward 잡 마스터 토글 |
| `LIVE_GATE_AUTO_EVAL_ENABLED` | `True` | 매주 월요일 자동 평가 잡 토글 |
| `BACKTEST_REBUILD_REQUIRED` | `False` | KS 검정 p<0.05 시 자동 True 전환 |
| `BACKTEST_ADMIN_USER_ID` | `1` | API 접근 허용 사용자 ID (또는 role 시스템) |
| `BACKTEST_DEFAULT_N_DAYS` | `60` | walk-forward 기본 데이터셋 크기 |

deploy.md 수동 검증 항목에 위 5개 추가 필수.

---

## 리스크 / 미해결 사항

1. **scipy 패키지 크기**: ~50MB 추가 → Railway 빌드 시간/이미지 크기 영향. **2026-05-08 사용자 결정: scipy 채택 (A안)** — KS/카이제곱 정확성이 LIVE 토글 게이트 통과 판정에 직결되므로 표준 구현 사용
2. **KOSPI 200 60일 일봉 데이터 충분성**: 운영 시작 시점 + 휴일에 따라 60일 미충족 가능. backfill-daily API로 보강 가능하나 KIS rate limit 주의
3. **임계 재조정 적용 시점**: Sprint 4 진단 → hotfix 사이에 R1 자동 롤백 발동 가능 (5/11 1거래일 더 0건 시). **2026-05-08 사용자 결정: A안 채택** — Sprint 4는 후보 산출까지, 적용은 별도 hotfix. R1 발동은 가드레일 정상 작동으로 수용 (phase8.6.md §4 예외 조항)
4. **BACKTEST_ADMIN_USER_ID 단일 ID 방식의 한계**: role 시스템 부재 시 임시 해법. Phase 8.7 인증 강화에서 제대로 해결
5. **LIVE 토글 게이트가 자동 평가 후 자동 LIVE 활성화는 하지 않음** (사용자 수동 확인 + 텔레그램 2단계). 본 Sprint는 평가까지만

---

## 사용자 다음 단계 안내

```
📋 다음 단계를 선택해주세요:
1. sprint-dev로 구현 시작 (/sprint-dev 8.6-4)
2. 검토 후 수동 진행

docs/phase/phase8.6/sprint4/sprint4.md를 먼저 검토하세요 (실행 플랜, Task 8개, 임계 재조정 후보 산출 범위).
수정이 필요하면 진행 전에 알려주세요.

특히 검토 권장:
- Task 1: scipy 의존성 추가 (이미지 크기 ~50MB ↑) — numpy 직접 구현 대안 가능
- Task 6: BACKTEST_ADMIN_USER_ID 단일 ID 방식 (role 시스템 부재 임시 해법)
- 제외 범위: 임계 재조정 자체 적용은 Sprint 4 후속 hotfix 또는 Sprint 5

반드시 사용자 응답을 기다린 후 진행합니다. sprint-dev를 자동으로 호출하지 않습니다.
```
