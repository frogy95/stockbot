# Sprint 1: 1차 스크리닝 3팩터 분리 + 임계값 조정 (Phase 4.7)

**Goal:** 1차 스크리닝에서 실시간 데이터 없는 팩터(체결강도, 호가잔량)를 제외하고 3팩터(volume/volatility/momentum)만 사용하여 후보 종목이 실제로 통과되도록 스코어링 구조를 수정한다.

**Architecture:** FactorScorer에 factors 파라미터를 추가하여 1차(3팩터)/2차(5팩터) 재사용 가능하게 확장. PrimaryScreener는 3팩터 + pass_threshold=60.0, RealtimeScreener는 5팩터 + pass_threshold=75.0으로 각각 설정. _build_candidates에서 중립값 팩터 빌드 자체를 제거.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, pytest

**Sprint 기간:** 2026-04-02 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 4.6 Sprint 2 (631 passed, PR #63)
**브랜치명:** `phase4.7-sprint1`

---

## 제외 범위

- 가중치 비대칭 적용 (volume 0.4 등) -- Phase 5에서 IC 기반 조정 예정
- 프론트엔드 변경 -- 이 Sprint에서 UI 변경 없음
- DB 스키마/Alembic 마이그레이션 -- 기존 테이블 구조 유지
- tracking_error_factor 1차 제외에 따른 ETF 별도 처리 -- 1차에서는 ETF도 3팩터만 사용

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | scorer.py 팩터 분리 + FactorScorer 확장 | 백엔드 | -- |
| Task 2 | screener.py 3팩터 빌드 + PrimaryScreener 초기화 수정 | 백엔드 | -- |

### Phase 2 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | RealtimeScreener + main.py 임계값 명시 | 백엔드 | -- |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 테스트 전면 수정 + 회귀 테스트 추가 | 백엔드 | -- |

---

### Task 1: scorer.py 팩터 분리 + FactorScorer 확장

**Files:**
- Modify: `backend/modules/screening/scorer.py` (팩터 상수 추가, FactorScorer.__init__에 factors 파라미터 추가)

**Step 1: PRIMARY 팩터 상수 추가**
- `scorer.py` 상단에 `PRIMARY_STOCK_FACTORS`와 `PRIMARY_ETF_FACTORS` 정의
  - `PRIMARY_STOCK_FACTORS = ["volume_factor", "volatility_factor", "momentum_factor"]`
  - `PRIMARY_ETF_FACTORS = ["volume_factor", "volatility_factor", "momentum_factor"]`
- `PRIMARY_WEIGHTS` 정의: 각 팩터 약 0.333 (1/3 균등)
  - `PRIMARY_WEIGHTS = {"volume_factor": 1/3, "volatility_factor": 1/3, "momentum_factor": 1/3}`
- 검증: `docker compose exec backend python -c "from modules.screening.scorer import PRIMARY_STOCK_FACTORS, PRIMARY_ETF_FACTORS, PRIMARY_WEIGHTS; print(PRIMARY_STOCK_FACTORS, PRIMARY_WEIGHTS)"`
- 예상: 3팩터 리스트와 가중치 출력

**Step 2: FactorScorer.__init__에 factors 파라미터 추가**
- `__init__`에 `factors: dict[str, list[str]] | None = None` 파라미터 추가
  - `factors`는 `{"STOCK": [...], "ETF": [...]}` 형식
  - 기본값: `None` -> 기존 `STOCK_FACTORS`/`ETF_FACTORS` 사용 (하위 호환)
- `self._stock_factors`와 `self._etf_factors`를 인스턴스 변수로 저장
  - `factors`가 None이면: `self._stock_factors = STOCK_FACTORS`, `self._etf_factors = ETF_FACTORS`
  - `factors`가 주어지면: `self._stock_factors = factors.get("STOCK", STOCK_FACTORS)`, `self._etf_factors = factors.get("ETF", ETF_FACTORS)`
- `score_candidates`에서 하드코딩된 `STOCK_FACTORS`/`ETF_FACTORS`를 `self._stock_factors`/`self._etf_factors`로 교체

**Step 3: 커밋**
```
git add backend/modules/screening/scorer.py
git commit -m "feat(phase4.7-sprint1): task1 -- scorer.py 1차/2차 팩터 분리 + FactorScorer factors 파라미터"
```

**완료 기준:**
- ⬜ PRIMARY_STOCK_FACTORS, PRIMARY_ETF_FACTORS, PRIMARY_WEIGHTS 정의 완료
- ⬜ FactorScorer(factors=None)은 기존 5팩터 동작 유지 (하위 호환)
- ⬜ FactorScorer(factors={"STOCK": [...], "ETF": [...]})로 팩터 지정 가능

---

### Task 2: screener.py 3팩터 빌드 + PrimaryScreener 초기화 수정

**Files:**
- Modify: `backend/modules/screening/screener.py` (_build_candidates 수정, PrimaryScreener.__init__ 수정)

**Step 1: PrimaryScreener.__init__ 수정**
- `scorer` 기본값을 `FactorScorer()`에서 명시적 1차 스코어러로 변경:
  ```
  FactorScorer(
      factors={"STOCK": PRIMARY_STOCK_FACTORS, "ETF": PRIMARY_ETF_FACTORS},
      factor_weights=PRIMARY_WEIGHTS,
      pass_threshold=60.0,
  )
  ```
- `from modules.screening.scorer import PRIMARY_STOCK_FACTORS, PRIMARY_ETF_FACTORS, PRIMARY_WEIGHTS` 임포트 추가

**Step 2: _build_candidates에서 중립값 팩터 제거**
- `trade_strength_factor = 50.0` 라인 제거
- `orderbook_ratio_factor = 1.0` 라인 제거
- `tracking_error_factor = 0.0` 라인 제거
- candidates.append의 dict에서 해당 3개 키 제거:
  - `"trade_strength_factor"`, `"orderbook_ratio_factor"`, `"tracking_error_factor"` 키-값 삭제
- 결과적으로 candidates dict에는 `volume_factor`, `momentum_factor`, `volatility_factor`만 팩터로 포함

**Step 3: 최소 후보 경고 로깅 추가**
- `screen()` 메서드에서 `filtered = self._apply_filters(rows)` 직후, `len(filtered) < 5`이면 warning 로깅
  - `logger.warning("1차 스크리닝 필터 통과 종목 %d개 — 소수 후보 시 백분위 왜곡 가능", len(filtered))`
- 파일 상단에 `import logging` + `logger = logging.getLogger(__name__)` 추가

**Step 4: 검증**
- 검증: `docker compose exec backend python -c "from modules.screening.screener import PrimaryScreener; s = PrimaryScreener(); print(s.scorer.pass_threshold, s.scorer._stock_factors)"`
- 예상: `60.0 ['volume_factor', 'volatility_factor', 'momentum_factor']`

**Step 5: 커밋**
```
git add backend/modules/screening/screener.py
git commit -m "feat(phase4.7-sprint1): task2 -- screener.py 3팩터 빌드 + 임계값 60.0 + 최소 후보 경고"
```

**완료 기준:**
- ⬜ _build_candidates가 3팩터만 반환 (trade_strength/orderbook_ratio/tracking_error 미포함)
- ⬜ PrimaryScreener의 FactorScorer가 pass_threshold=60.0 사용
- ⬜ 필터 통과 5개 미만 시 warning 로깅

---

### Task 3: RealtimeScreener + main.py 임계값 명시

**Files:**
- Modify: `backend/modules/screening/realtime_screener.py` (FactorScorer 기본값 변경)
- Modify: `backend/main.py` (RealtimeScreener 생성 시 pass_threshold 명시)

**Step 1: RealtimeScreener 기본 FactorScorer를 pass_threshold=75.0으로 변경**
- `realtime_screener.py`의 `__init__`에서 `self.scorer = scorer or FactorScorer()` -> `self.scorer = scorer or FactorScorer(pass_threshold=75.0)`
- RealtimeScreener는 기존 5팩터(STOCK_FACTORS/ETF_FACTORS) 사용 유지 -- factors 파라미터 변경 불필요

**Step 2: main.py에서 RealtimeScreener 생성 확인**
- `main.py`의 `RealtimeScreener(redis_client=redis_client, trade_strength_calc=trade_strength)` 호출부 확인
- scorer 파라미터를 명시적으로 전달하지 않으므로, Step 1의 기본값 변경으로 자동 적용됨
- 별도 수정 불필요 (main.py 변경 없음)

**Step 3: 검증**
- 검증: `docker compose exec backend python -c "from modules.screening.realtime_screener import RealtimeScreener; s = RealtimeScreener(); print(s.scorer.pass_threshold)"`
- 예상: `75.0`

**Step 4: 커밋**
```
git add backend/modules/screening/realtime_screener.py
git commit -m "feat(phase4.7-sprint1): task3 -- RealtimeScreener pass_threshold 75.0 적용"
```

**완료 기준:**
- ⬜ RealtimeScreener 기본 pass_threshold가 75.0
- ⬜ RealtimeScreener는 기존 5팩터 유지

---

### Task 4: 테스트 전면 수정 + 회귀 테스트 추가

**Files:**
- Modify: `backend/tests/test_scorer.py` (1차/2차 분리 테스트 추가, 기존 테스트 보완)
- Modify: `backend/tests/test_screener.py` (3팩터 빌드 검증, 버그 재현 방지 회귀 테스트)

**Step 1: test_scorer.py 수정**
- 기존 테스트 유지 (5팩터 테스트는 2차 스코어링 검증으로 존속)
- 새 테스트 클래스 `TestPrimaryFactorScorer` 추가:
  - `test_primary_3_factors_only`: PRIMARY_STOCK_FACTORS + PRIMARY_WEIGHTS로 FactorScorer 생성. 3팩터 candidates 입력. factors dict에 3개 키만 포함 확인
  - `test_primary_threshold_60`: pass_threshold=60.0 적용. 3팩터 all 백분위 100인 단일 종목 -> score=100 -> is_passed=True
  - `test_primary_threshold_rejects_low_score`: 2종목 중 하위 종목이 score < 60.0이면 is_passed=False
  - `test_factors_parameter_backward_compatible`: `FactorScorer()`(factors 미지정)는 기존 STOCK_FACTORS/ETF_FACTORS 사용 확인
- 새 테스트 `test_bug_regression_all_tie_factors` 추가:
  - 44개 후보, trade_strength_factor와 orderbook_ratio_factor가 모두 동일값인 시나리오
  - 5팩터 FactorScorer(pass_threshold=80.0)로 스코어링 -> is_passed=True 종목 0건 확인 (버그 재현)
  - 3팩터 FactorScorer(factors=PRIMARY, pass_threshold=60.0)로 스코어링 -> is_passed=True 종목 존재 확인 (수정 검증)

**Step 2: test_screener.py 수정**
- `TestScreenIntegration.test_screen_full_flow` 수정:
  - PrimaryScreener가 3팩터 FactorScorer를 사용하므로, 결과의 factors dict에 3개 키만 포함 확인
  - `trade_strength_factor`, `orderbook_ratio_factor` 키가 factors dict에 없음 확인
  - 3종목 모두 is_passed=True 확인 (3팩터 + pass_threshold=60.0으로 단일 종목/소수 종목은 백분위 높음)
- 새 테스트 `test_build_candidates_no_realtime_factors` 추가:
  - PrimaryScreener._build_candidates 직접 호출
  - 결과 dict에 `trade_strength_factor`, `orderbook_ratio_factor`, `tracking_error_factor` 키가 없음 확인

**Step 3: 전체 테스트 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (기존 + 신규)

**Step 4: 커밋**
```
git add backend/tests/test_scorer.py backend/tests/test_screener.py
git commit -m "feat(phase4.7-sprint1): task4 -- 1차/2차 분리 테스트 + 버그 재현 방지 회귀 테스트"
```

**완료 기준:**
- ⬜ test_scorer.py: 1차(3팩터) 전용 테스트 통과
- ⬜ test_scorer.py: 버그 재현 + 수정 검증 회귀 테스트 통과
- ⬜ test_screener.py: _build_candidates 3팩터만 반환 검증 통과
- ⬜ test_screener.py: 통합 테스트에서 is_passed=True 종목 존재 확인
- ⬜ pytest 전체 PASS

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 passed (기존 + 신규) |
| scorer import | `docker compose exec backend python -c "from modules.screening.scorer import PRIMARY_STOCK_FACTORS, PRIMARY_WEIGHTS; print(len(PRIMARY_STOCK_FACTORS), sum(PRIMARY_WEIGHTS.values()))"` | `3 1.0` (또는 ~0.999) |
| PrimaryScreener 임계값 | `docker compose exec backend python -c "from modules.screening.screener import PrimaryScreener; print(PrimaryScreener().scorer.pass_threshold)"` | `60.0` |
| RealtimeScreener 임계값 | `docker compose exec backend python -c "from modules.screening.realtime_screener import RealtimeScreener; print(RealtimeScreener().scorer.pass_threshold)"` | `75.0` |
| FactorScorer 하위 호환 | `docker compose exec backend python -c "from modules.screening.scorer import FactorScorer, STOCK_FACTORS; s = FactorScorer(); print(s._stock_factors == STOCK_FACTORS)"` | `True` |
