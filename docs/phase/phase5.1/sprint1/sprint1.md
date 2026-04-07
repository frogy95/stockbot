# Sprint 1: change_rate 필터 수정 + 적응형 확장 (Phase 5.1)

**Goal:** change_rate_min 완화(-2.0) + 적응형 필터 change_rate 확장 + 하락 종목 안전장치 + 필터별 탈락 통계 로깅으로 1차 스크리닝 0건 재발 방지

**Architecture:** PrimaryFilters.change_rate_min을 1.0에서 -2.0으로 완화하고, _apply_filters_with_adaptive에 change_rate 단계적 완화([-2.0, -3.0])를 추가한다. 하락 종목(change_rate < 0)에는 auto_trade_blocked + position_size_ratio 안전장치를 적용한다. 필터별 탈락 카운트를 WARNING 로그로 출력하여 향후 파라미터 튜닝 데이터를 확보한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), pytest

**Sprint 기간:** 2026-04-08 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 5 Sprint 2 (완료, PR #102)
**브랜치명:** `phase5.1-sprint1`

---

## 제외 범위

- change_rate 절대값 필터 (|change_rate| >= 0.3%) -- Phase 6 이관 합의
- 코스피/코스닥 지수 기반 동적 임계값 -- Phase 6 이관 합의
- 하락 종목 익일 수익률 백테스팅 -- Phase 6
- 프론트엔드 변경 없음 (백엔드 필터 조건 수정만)
- DB 스키마 변경 없음 (Alembic 마이그레이션 불필요)
- 성과 분석 대시보드 (Phase 5 Sprint 3)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | change_rate_min 완화 + 적응형 change_rate 확장 | 백엔드 | — |

### Phase 2 (순차, Task 1에 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | 하락 종목 안전장치 + 필터별 탈락 통계 로깅 | 백엔드 | — |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | 테스트 업데이트 + 통합 검증 | 백엔드 | — |

---

### Task 1: change_rate_min 완화 + 적응형 change_rate 확장

**Files:**
- Modify: `backend/modules/screening/filters.py` (PrimaryFilters.change_rate_min 기본값 변경)
- Modify: `backend/modules/screening/screener.py` (PrimaryScreener.__init__에 change_rate_adaptive_steps 추가, _apply_filters_with_adaptive 확장)

**Step 1: filters.py -- change_rate_min 기본값 변경**
- `PrimaryFilters.change_rate_min` 기본값: `1.0` -> `-2.0`
- change_rate_max는 7.0 유지 (확정 파라미터 #2)
- 검증: `docker compose exec backend python -c "from modules.screening.filters import PrimaryFilters; f=PrimaryFilters(); assert f.change_rate_min == -2.0; assert f.change_rate_max == 7.0; print('OK')"`
- 예상: OK

**Step 2: screener.py -- PrimaryScreener.__init__에 change_rate_adaptive_steps 파라미터 추가**
- 새 파라미터: `change_rate_adaptive_steps: list[float] | None = None`
- 기본값: `[-2.0, -3.0]` (확정 파라미터 #3)
- `self.change_rate_adaptive_steps`에 저장
- 검증: `docker compose exec backend python -c "from modules.screening.screener import PrimaryScreener; ps=PrimaryScreener(); assert ps.change_rate_adaptive_steps == [-2.0, -3.0]; print('OK')"`
- 예상: OK

**Step 3: screener.py -- _apply_filters_with_adaptive 확장**
- 기존 로직: volume_ratio만 단계적 완화
- 변경 로직:
  1. 기본 필터로 시도 (volume_ratio=1.5, change_rate_min=-2.0)
  2. 부족하면 volume_ratio 단계적 완화 (기존: [1.5, 1.2])
  3. 여전히 부족하면 change_rate_min 단계적 완화 (신규: [-2.0, -3.0])
  4. 최저 하한: change_rate_min >= -5.0 (확정 파라미터 #7)
- 완화 순서: volume_ratio 먼저, change_rate 후순위 (확정 파라미터 #4)
- change_rate 완화 시에는 volume_ratio도 마지막 적용 단계를 유지 (volume_ratio는 이미 완화된 상태에서 change_rate 추가 완화)
- WARNING 로그: `"적응형 필터 적용: change_rate_min %.1f, 후보 %d개"`
- 검증: `docker compose exec backend pytest tests/test_screener.py::TestAdaptiveFilter -v` (Step 3만 실행하면 기존 테스트는 통과해야 함, change_rate는 기존 테스트에서 3.0이므로 -2.0 기본에 이미 통과)
- 예상: PASS (기존 테스트는 change_rate=3.0 사용)

**Step 4: 커밋**
```
git add backend/modules/screening/filters.py backend/modules/screening/screener.py
git commit -m "feat(phase5.1-sprint1): task1 -- change_rate_min -2.0 완화 + 적응형 change_rate 확장"
```

**완료 기준:**
- ⬜ PrimaryFilters().change_rate_min == -2.0
- ⬜ PrimaryScreener().change_rate_adaptive_steps == [-2.0, -3.0]
- ⬜ _apply_filters_with_adaptive가 volume_ratio -> change_rate 순서로 완화
- ⬜ 기존 pytest 회귀 없음

---

### Task 2: 하락 종목 안전장치 + 필터별 탈락 통계 로깅

**Files:**
- Modify: `backend/modules/screening/screener.py` (screen()에 하락 종목 플래그 추가, _apply_filters에 탈락 통계 로깅 추가)
- Modify: `backend/modules/screening/filters.py` (passes_primary_filter에서 탈락 사유 반환 지원)

**Step 1: screener.py -- 하락 종목 안전장치**
- screen() 메서드에서 scorer.score_candidates() 이후, _truncate_and_rank() 이후:
  - 각 결과 항목에 대해:
    - `change_rate < 0`: `auto_trade_blocked = True` 설정 (확정 파라미터 #5)
    - `change_rate <= -2.0`: `position_size_ratio = 0.5` 추가 설정 (확정 파라미터 #6)
  - 이 플래그들은 기존 기본 후보(is_fallback)와 동일한 필드 재활용
- 적용 위치: `_mark_hot_stocks(result)` 호출 직후, `is_relaxed` 플래그 설정 직전
- 검증: `docker compose exec backend python -c "print('코드 구조 확인만')"`
- 예상: OK (테스트는 Task 3에서 수행)

**Step 2: filters.py + screener.py -- 필터별 탈락 통계 로깅**
- `_apply_filters` 메서드에 탈락 사유별 카운트 수집 로직 추가:
  - prev_volume=0 탈락 수
  - volume_ratio 탈락 수
  - volume_min 탈락 수
  - market_cap 탈락 수
  - change_rate 탈락 수 (하한/상한 구분)
  - 통과 수
- 로직: `_apply_filters` 내부에서 `passes_primary_filter` 대신 직접 각 조건을 검사하면서 카운트를 누적하거나, passes_primary_filter는 유지하되 별도 카운트 루프 추가
- 선택: passes_primary_filter는 그대로 유지하고, `_apply_filters`에서 별도로 탈락 사유를 카운팅하는 `_log_filter_stats(rows, filters)` 헬퍼 메서드를 추가
  - 이유: passes_primary_filter 시그니처 변경 없음 (외부 의존 있을 수 있음)
- `_log_filter_stats`는 `_apply_filters` 호출 후 WARNING 로그 출력:
  ```
  "1차 필터 통계: 입력 %d, prev_volume=0 탈락 %d, volume_ratio 탈락 %d, volume_min 탈락 %d, market_cap 탈락 %d, change_rate 탈락 %d (하한 %d/상한 %d), 통과 %d"
  ```
- 호출 위치: `_apply_filters_with_adaptive` 내부의 첫 `_apply_filters` 호출 직후 1회만 (적응형 완화 루프에서는 호출하지 않음 -- 로그 폭발 방지)
- 검증: 테스트는 Task 3에서 수행 (로그 캡처 테스트)

**Step 3: 커밋**
```
git add backend/modules/screening/screener.py backend/modules/screening/filters.py
git commit -m "feat(phase5.1-sprint1): task2 -- 하락 종목 안전장치 + 필터별 탈락 통계 로깅"
```

**완료 기준:**
- ⬜ change_rate < 0 종목에 auto_trade_blocked=True
- ⬜ change_rate <= -2.0 종목에 position_size_ratio=0.5
- ⬜ 필터별 탈락 통계 WARNING 로그 출력
- ⬜ passes_primary_filter 시그니처 변경 없음

---

### Task 3: 테스트 업데이트 + 통합 검증

**Files:**
- Modify: `backend/tests/test_filters.py` (change_rate_min=-2.0 기본값 테스트, 음수 change_rate 통과 테스트)
- Modify: `backend/tests/test_screener.py` (적응형 change_rate 테스트, 하락 종목 안전장치 테스트, 필터 통계 로깅 테스트)

**Step 1: test_filters.py 수정**
- `TestPrimaryFilters.test_default_values`: `assert f.change_rate_min == -2.0` (기존 1.0 -> -2.0)
- `TestPassesPrimaryFilter` 추가 테스트:
  - `test_pass_negative_change_rate`: change_rate=-1.5로 통과 (>= -2.0이므로)
    - data: volume=200_000, prev_volume=100_000, market_cap=100e9, change_rate=-1.5, stock_type="STOCK"
    - assert passes_primary_filter(data, PrimaryFilters()) is True
  - `test_fail_change_rate_too_low_negative`: change_rate=-3.0으로 탈락 (< -2.0이므로)
    - assert passes_primary_filter(data, PrimaryFilters()) is False
  - `test_pass_zero_change_rate`: change_rate=0.0으로 통과 (>= -2.0이므로)
    - assert passes_primary_filter(data, PrimaryFilters()) is True
- 기존 `test_fail_change_rate_too_low` 수정: change_rate=0.5는 이제 통과하므로 change_rate를 -3.0으로 변경하거나, 테스트 의도를 수정
  - 기존: change_rate=0.5, assert False -> 이제 0.5 >= -2.0이므로 True
  - 변경: change_rate=-3.0 (< -2.0이므로 False)
- 검증: `docker compose exec backend pytest tests/test_filters.py -v`
- 예상: PASS

**Step 2: test_screener.py -- 적응형 change_rate 테스트 추가**
- `TestAdaptiveFilter` 클래스에 추가:
  - `test_adaptive_change_rate_relaxation`: volume_ratio 완화로도 부족하면 change_rate 완화 동작 확인
    - rows: volume_ratio=2.0(기본 통과), change_rate=-2.5(기본 탈락, -3.0 완화 시 통과) x 15개
    - screener = PrimaryScreener(change_rate_adaptive_steps=[-2.0, -3.0])
    - passed, is_relaxed = screener._apply_filters_with_adaptive(rows)
    - assert len(passed) >= 10 and is_relaxed is True
  - `test_adaptive_volume_first_then_change_rate`: volume_ratio 완화만으로 충분하면 change_rate 완화 안 함
    - rows: volume_ratio=1.3(기본 1.5 탈락, 1.2 완화 통과), change_rate=3.0 x 15개
    - passed, is_relaxed = screener._apply_filters_with_adaptive(rows)
    - assert len(passed) >= 10 and is_relaxed is True
    - 모든 항목의 change_rate가 원래 값 유지 확인 (change_rate 완화는 미적용)
  - `test_adaptive_change_rate_floor`: change_rate_min이 -5.0 아래로 내려가지 않음
    - screener = PrimaryScreener(change_rate_adaptive_steps=[-2.0, -3.0, -6.0])
    - 내부적으로 -6.0이 -5.0으로 클램핑되는지 확인
- 검증: `docker compose exec backend pytest tests/test_screener.py::TestAdaptiveFilter -v`
- 예상: PASS

**Step 3: test_screener.py -- 하락 종목 안전장치 테스트 추가**
- 새 클래스 `TestNegativeChangeRateSafety`:
  - `test_negative_change_rate_auto_trade_blocked`:
    - rows: change_rate=-1.0 (< 0) x 12개, volume_ratio=3.0
    - screen() 실행 후 모든 항목에 auto_trade_blocked=True 확인
  - `test_deep_negative_position_size_ratio`:
    - rows: change_rate=-2.5 (<= -2.0) x 12개, volume_ratio=3.0
    - screen() 실행 후 모든 항목에 position_size_ratio=0.5 확인
  - `test_positive_change_rate_no_safety`:
    - rows: change_rate=3.0 (> 0) x 12개, volume_ratio=3.0
    - screen() 실행 후 auto_trade_blocked/position_size_ratio 미설정 확인
- _fetch_today_and_prev와 _get_recent_market_data를 모킹하여 순수 로직만 검증
- 검증: `docker compose exec backend pytest tests/test_screener.py::TestNegativeChangeRateSafety -v`
- 예상: PASS

**Step 4: test_screener.py -- 필터 통계 로깅 테스트 추가**
- 새 클래스 `TestFilterStatsLogging`:
  - `test_filter_stats_logged`:
    - rows: 다양한 탈락 사유 혼합 (prev_volume=0 2개, volume_ratio 미달 3개, market_cap 미달 1개, change_rate 탈락 2개, 통과 5개)
    - caplog (pytest fixture) 사용하여 WARNING 로그에 "1차 필터 통계" 문자열 포함 확인
    - 입력 수, 통과 수가 로그에 정확히 기재되었는지 확인
- 검증: `docker compose exec backend pytest tests/test_screener.py::TestFilterStatsLogging -v`
- 예상: PASS

**Step 5: 전체 테스트 실행 + 커밋**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (회귀 없음)
```
git add backend/tests/test_filters.py backend/tests/test_screener.py
git commit -m "feat(phase5.1-sprint1): task3 -- 테스트 업데이트 (change_rate 완화 + 적응형 + 안전장치 + 로깅)"
```

**완료 기준:**
- ⬜ test_filters.py: change_rate_min=-2.0 기본값 + 음수 change_rate 통과/탈락 테스트
- ⬜ test_screener.py: 적응형 change_rate 완화 테스트 3종
- ⬜ test_screener.py: 하락 종목 안전장치 테스트 3종
- ⬜ test_screener.py: 필터별 탈락 통계 로깅 테스트
- ⬜ pytest 전체 통과

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 passed, 0 failed |
| change_rate_min 기본값 | `docker compose exec backend python -c "from modules.screening.filters import PrimaryFilters; assert PrimaryFilters().change_rate_min == -2.0; print('OK')"` | OK |
| 적응형 change_rate 파라미터 | `docker compose exec backend python -c "from modules.screening.screener import PrimaryScreener; assert PrimaryScreener().change_rate_adaptive_steps == [-2.0, -3.0]; print('OK')"` | OK |
| 적응형 필터 메서드 | `docker compose exec backend python -c "from modules.screening.screener import PrimaryScreener; assert hasattr(PrimaryScreener(), '_log_filter_stats'); print('OK')"` | OK |
| change_rate 필터 동작 | `docker compose exec backend python -c "from modules.screening.filters import PrimaryFilters, passes_primary_filter; d={'volume':200000,'prev_volume':100000,'market_cap':100000000000,'change_rate':-1.5,'stock_type':'STOCK'}; assert passes_primary_filter(d, PrimaryFilters()); print('OK')"` | OK |
