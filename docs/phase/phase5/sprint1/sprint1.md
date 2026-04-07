# Sprint 1: 1차 스크리닝 안정화 (Phase 5)

**Goal:** volume_ratio 필터 완화, 적응형 필터, prev_volume 폴백, 기본 후보 선정, date.today() KST 전환으로 1차 스크리닝 0건 문제 해결

**Architecture:** PrimaryScreener.screen()에 적응형 필터 로직과 폴백 경로를 추가하여 필터 통과 0건 시 단계적 완화 -> 기본 후보 순으로 최소 후보를 보장한다. date.today()는 프로덕션 코드 5개 파일에서 KST datetime으로 교체한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), pytest

**Sprint 기간:** 2026-04-07 ~ 2026-04-07
**상태:** ✅ 완료 (2026-04-07)
**PR:** https://github.com/frogy95/stockbot/pull/101
**이전 스프린트:** Phase 4.9 Sprint 1 (완료, PR #90)
**브랜치명:** `phase5-sprint1`

---

## 제외 범위

- 완전 자동 모드 구현 (Sprint 2)
- 텔레그램 고도화 / 일일 리포트 (Sprint 2)
- 성과 분석 대시보드 (Sprint 3)
- 장세 판별 모듈 / rolling z-score (Phase 6 이관)
- 프론트엔드 변경 없음 (백엔드 전용 Sprint)
- DB 스키마 변경 없음 (Alembic 마이그레이션 불필요)
- ETF 시세 수집기 타임존 버그 (핫픽스 완료, PR #93)
- 수동 수집 API (핫픽스 완료, PR #95)
- 필터별 탈락 통계 WARNING 로깅 (핫픽스 완료, PR #99)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | date.today() KST 전환 (risk_manager 최우선) | 백엔드 | `feature-dev:feature-dev` |

### Phase 2 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | volume_ratio 완화 + 적응형 필터 + prev_volume 폴백 | 백엔드 | `feature-dev:feature-dev` |

### Phase 3 (순차, Task 2에 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | 기본 후보 선정 (0건 시 거래량 상위 15개) | 백엔드 | — |

### Phase 4 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 통합 검증 | 전체 | — |

---

### Task 1: date.today() KST 전환

**skill:** `feature-dev:feature-dev`

**배경:** Railway 서버는 UTC로 동작하므로 `date.today()`가 KST 기준 날짜와 불일치한다. 프로덕션 코드 5개 파일 + `datetime.now()` 2개소를 수정한다.

**Files:**
- Modify: `backend/modules/trading/risk_manager.py` (line 180, 311: `date.today()` -> KST, line 268, 377: `datetime.now()` -> KST)
- Modify: `backend/modules/notifier/manager.py` (line 105: `date.today()`)
- Modify: `backend/modules/notifier/commands.py` (line 47: `date.today()`)
- Modify: `backend/api/routes/dashboard.py` (line 33: `date.today()`)
- Modify: `backend/api/routes/trading.py` (line 57: `date.today()`)
- Create: `backend/tests/test_kst_date.py`

**수정 대상 상세:**

1. `risk_manager.py` line 180 — `check_daily_loss()`:
   - `datetime.combine(date.today(), time.min)` -> `datetime.combine(datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date(), time.min)`
   - `from zoneinfo import ZoneInfo` 추가, `from core.config import settings` 추가

2. `risk_manager.py` line 268 — `check_time_restriction()`:
   - `datetime.now().time()` -> `datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).time()`

3. `risk_manager.py` line 311 — `record_loss()`:
   - `datetime.combine(date.today(), time.min)` -> 동일 KST 패턴

4. `risk_manager.py` line 377 — `assert_settings_unlocked()`:
   - `datetime.now().time()` -> KST 패턴

5. `manager.py` line 105 — `send_daily_report()`:
   - `datetime.combine(date.today(), ...)` -> KST 패턴

6. `commands.py` line 47 — `handle_today()`:
   - `today = date.today()` -> `today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()`

7. `dashboard.py` line 33 — `get_summary()`:
   - `today = date.today()` -> KST 패턴

8. `trading.py` line 57 — `get_history()`:
   - `target_date = date.today()` -> KST 패턴

**KST 헬퍼 패턴:** 각 파일에서 직접 `datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()` 호출 (유틸 함수 추출은 필요 시 simplify 단계에서 판단).

**Step 1: 테스트 작성**
- `backend/tests/test_kst_date.py` 생성
- `risk_manager.check_daily_loss()`가 KST 날짜 기준으로 오늘 거래만 조회하는지 검증
- `risk_manager.check_time_restriction()`이 KST 시간으로 판단하는지 검증
- 검증: `docker compose exec backend pytest tests/test_kst_date.py -v`
- 예상: FAIL (아직 수정 전)

**Step 2: risk_manager.py 수정 (최우선)**
- `from zoneinfo import ZoneInfo` 및 `from core.config import settings` import 추가
- 4개소 수정 (line 180, 268, 311, 377)
- 검증: `docker compose exec backend pytest tests/test_kst_date.py -v`
- 예상: PASS

**Step 3: 나머지 4개 파일 수정**
- `manager.py`, `commands.py`, `dashboard.py`, `trading.py`에 동일 패턴 적용
- 각 파일에 `from zoneinfo import ZoneInfo` 및 `from core.config import settings` import 추가 (이미 있으면 skip)
- 검증: `docker compose exec backend pytest -v`
- 예상: 기존 테스트 전체 PASS (회귀 없음)

**Step 4: 커밋**
```
git add backend/modules/trading/risk_manager.py backend/modules/notifier/manager.py backend/modules/notifier/commands.py backend/api/routes/dashboard.py backend/api/routes/trading.py backend/tests/test_kst_date.py
git commit -m "feat(phase5-sprint1): task1 -- date.today()/datetime.now() KST 전환 (5개 프로덕션 파일)"
```

**완료 기준:**
- ✅ test_kst_date.py 테스트 통과
- ✅ 기존 pytest 전체 회귀 없음
- ✅ `grep -r "date.today()" backend/ --include="*.py"` 결과에 프로덕션 코드 없음 (테스트 코드는 허용)

---

### Task 2: volume_ratio 완화 + 적응형 필터 + prev_volume 폴백

**skill:** `feature-dev:feature-dev`

**배경:** `volume_ratio >= 2.0`에서 88% 탈락, `prev_volume=0`으로 319건 탈락. 기본 임계값을 1.5로 완화하고, 적응형 필터(단계적 완화)와 prev_volume 폴백(5일 평균)을 추가한다.

**Files:**
- Modify: `backend/modules/screening/filters.py` (volume_ratio 기본값 변경)
- Modify: `backend/modules/screening/screener.py` (적응형 필터 + prev_volume 폴백)
- Modify: `backend/tests/test_filters.py` (volume_ratio 1.5 기준 테스트 업데이트)
- Modify: `backend/tests/test_screener.py` (적응형 필터 + 폴백 테스트 추가)

**수정 상세:**

1. **`filters.py`** — `PrimaryFilters.volume_ratio` 기본값 2.0 -> 1.5

2. **`screener.py`** — `PrimaryScreener` 클래스에 다음 메서드 추가/수정:

   a. `__init__`에 적응형 필터 파라미터 추가:
      - `adaptive_steps: list[float] = [1.5, 1.2]` (확정 파라미터 #2)
      - `adaptive_min_candidates: int = 10` (확정 파라미터 #3)

   b. `screen()` 메서드 수정:
      - 기존: `filtered = self._apply_filters(rows)` -> `if not filtered: return []`
      - 변경: `filtered = self._apply_filters_with_adaptive(rows)` 호출
      - `_apply_filters_with_adaptive`는 필터 통과 후보가 `adaptive_min_candidates` 미만이면 단계적 완화 실행

   c. **`_apply_filters_with_adaptive(rows)`** 신규 메서드:
      ```
      1) self._apply_filters(rows)로 기본 필터 적용 (volume_ratio=1.5)
      2) len(passed) >= adaptive_min_candidates → passed 반환, is_relaxed=False
      3) 미달 시 adaptive_steps 순회:
         - 임시 PrimaryFilters(volume_ratio=step)로 재필터
         - len(passed) >= adaptive_min_candidates → passed 반환, is_relaxed=True
      4) 모든 step 소진 시 마지막 결과 반환 (0건 포함), is_relaxed=True
      ```
      - 반환값: `tuple[list[dict], bool]` (filtered_rows, is_relaxed)
      - `is_relaxed=True`이면 결과에 `"is_relaxed": True` 플래그 설정 (확정 파라미터 #9)
      - WARNING 로그: "적응형 필터 적용: volume_ratio {step}, 후보 {count}개"

   d. **`_get_fallback_prev_volume(session, stock_code)`** 신규 메서드:
      - `_fetch_today_and_prev` 내부에서 `prev_volume=0`인 종목에 대해 호출
      - 최근 5일 market_data에서 volume 조회 (source IN ["data_go_kr", "kis_daily"])
      - 유효 데이터 3일+ 조건 충족 시 평균값 반환 (확정 파라미터 #4)
      - 3일 미만이면 0 반환 (폴백 실패 → 기존 동작과 동일하게 탈락)

   e. **`_fetch_today_and_prev()` 수정:**
      - `prev_volume = date_rows[1]["volume"] if len(date_rows) > 1 else 0` 부분에서
      - `prev_volume == 0`이면 `_get_fallback_prev_volume()` 호출
      - 이를 위해 session 파라미터 활용 (이미 전달받고 있음)

**Step 1: 테스트 작성**
- `test_filters.py` 수정: `test_default_values`에서 `volume_ratio == 1.5`로 변경
- `test_screener.py`에 다음 테스트 추가:
  - `TestAdaptiveFilter.test_adaptive_relaxes_when_below_min` — 후보 10개 미만 시 완화
  - `TestAdaptiveFilter.test_no_relaxation_when_enough` — 10개+ 시 완화 안 함
  - `TestAdaptiveFilter.test_adaptive_stops_at_1_2` — 1.0 이하로 떨어지지 않음
  - `TestAdaptiveFilter.test_is_relaxed_flag` — 완화 시 플래그 설정
  - `TestPrevVolumeFallback.test_fallback_5day_avg` — 5일 평균 폴백
  - `TestPrevVolumeFallback.test_fallback_insufficient_data` — 유효 2일 이하 → 0
- 검증: `docker compose exec backend pytest tests/test_screener.py tests/test_filters.py -v`
- 예상: FAIL (구현 전)

**Step 2: filters.py 수정**
- `PrimaryFilters.volume_ratio` 기본값 2.0 -> 1.5
- 검증: `docker compose exec backend pytest tests/test_filters.py::TestPrimaryFilters -v`
- 예상: PASS

**Step 3: screener.py — prev_volume 폴백 구현**
- `_get_fallback_prev_volume()` 메서드 추가
- `_fetch_today_and_prev()`에서 `prev_volume==0` 시 폴백 호출
- 검증: `docker compose exec backend pytest tests/test_screener.py::TestPrevVolumeFallback -v`
- 예상: PASS

**Step 4: screener.py — 적응형 필터 구현**
- `_apply_filters_with_adaptive()` 메서드 추가
- `screen()` 메서드에서 `_apply_filters` 대신 `_apply_filters_with_adaptive` 호출
- `is_relaxed` 플래그를 결과 각 항목에 설정
- 검증: `docker compose exec backend pytest tests/test_screener.py::TestAdaptiveFilter -v`
- 예상: PASS

**Step 5: 전체 검증 + 커밋**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS
```
git add backend/modules/screening/filters.py backend/modules/screening/screener.py backend/tests/test_filters.py backend/tests/test_screener.py
git commit -m "feat(phase5-sprint1): task2 -- volume_ratio 1.5 완화 + 적응형 필터 + prev_volume 폴백"
```

**완료 기준:**
- ✅ volume_ratio 기본값 1.5
- ✅ 적응형 필터 [1.5, 1.2] 단계 동작
- ✅ prev_volume=0 시 5일 평균 폴백 (유효 3일+ 조건)
- ✅ is_relaxed 플래그 정상 설정
- ✅ pytest 전체 통과

---

### Task 3: 기본 후보 선정 (0건 시 거래량 상위 15개)

**배경:** 적응형 필터까지 적용해도 후보가 0건이면, 거래량 상위 15개 (시총 500억+)를 기본 후보로 선정하여 2차 스크리닝에 직접 투입한다. 기본 후보는 스코어링 skip, 반자동만 허용, 포지션 사이징 50%.

**Files:**
- Modify: `backend/modules/screening/screener.py` (`_get_fallback_candidates`, screen() 수정)
- Modify: `backend/modules/screening/scorer.py` (기본 후보 스코어링 skip 처리 — 불필요할 수 있음, 아래 설계 참조)
- Modify: `backend/tests/test_screener.py` (기본 후보 테스트 추가)

**수정 상세:**

1. **`screener.py`** — `_get_fallback_candidates()` 신규 메서드:
   - `_fetch_today_and_prev()`에서 반환된 전체 종목 데이터(rows) 중에서:
     - `market_cap >= 50_000_000_000` (시총 500억+)
     - `volume` 내림차순 정렬
     - 상위 15개 선택
   - 각 항목에 다음 플래그 설정:
     - `"is_fallback": True` — 기본 후보 표시
     - `"is_relaxed": True` — 완화됨 표시 (확정 파라미터 #9)
     - `"auto_trade_blocked": True` — 완전 자동 매매 금지 (확정 파라미터 #7)
     - `"position_size_ratio": 0.5` — 포지션 사이징 50% (확정 파라미터 #8)
   - 스코어링 skip: `score=0`, `rank` 거래량 순, `is_passed=True`, `factors={}` (확정 파라미터 #6)

2. **`screen()` 메서드 수정:**
   - 적응형 필터 후에도 `len(filtered) == 0`이면 `_get_fallback_candidates(rows)` 호출
   - 기본 후보는 `scorer.score_candidates()` 호출하지 않고 바로 반환
   - WARNING 로그: "1차 스크리닝 0건 — 기본 후보 {count}개 투입 (거래량 상위, 시총 500억+)"

3. **기본 후보 안전장치 (Phase 5 Sprint 2에서 소비):**
   - `is_fallback`, `auto_trade_blocked`, `position_size_ratio` 플래그는 screening_results에 factors JSON에 저장
   - 2차 스크리닝과 TradingEngine에서 이 플래그를 읽어 반자동/50% 사이징 적용은 Sprint 2에서 구현
   - 이번 Sprint에서는 플래그만 설정하고, 기존 engine.process_screening_results의 동작은 변경하지 않음

**Step 1: 테스트 작성**
- `test_screener.py`에 다음 테스트 추가:
  - `TestFallbackCandidates.test_fallback_returns_top_15` — 0건 시 거래량 상위 15개
  - `TestFallbackCandidates.test_fallback_market_cap_filter` — 시총 500억 미만 제외
  - `TestFallbackCandidates.test_fallback_flags` — is_fallback, auto_trade_blocked, position_size_ratio 플래그
  - `TestFallbackCandidates.test_fallback_skips_scoring` — score=0, factors={}
  - `TestFallbackCandidates.test_no_fallback_when_candidates_exist` — 후보 있으면 기본 후보 미생성
- 검증: `docker compose exec backend pytest tests/test_screener.py::TestFallbackCandidates -v`
- 예상: FAIL (구현 전)

**Step 2: _get_fallback_candidates 구현**
- `screener.py`에 메서드 추가
- `screen()` 메서드에서 적응형 필터 0건 시 호출 경로 추가
- 검증: `docker compose exec backend pytest tests/test_screener.py::TestFallbackCandidates -v`
- 예상: PASS

**Step 3: 전체 검증 + 커밋**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS
```
git add backend/modules/screening/screener.py backend/tests/test_screener.py
git commit -m "feat(phase5-sprint1): task3 -- 기본 후보 선정 (0건 시 거래량 상위 15개, 시총 500억+)"
```

**완료 기준:**
- ✅ 0건 시 기본 후보 15개 반환
- ✅ 시총 500억+ 필터 적용
- ✅ is_fallback, auto_trade_blocked, position_size_ratio 플래그 설정
- ✅ 스코어링 skip (score=0, factors={})
- ✅ pytest 전체 통과

---

### Task 4: 통합 검증

**Files:**
- (기존 파일 — 추가 수정 없음)

**Step 1: pytest 전체 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (회귀 없음)

**Step 2: date.today() 잔존 확인**
- 검증: `grep -rn "date.today()" backend/ --include="*.py" | grep -v test | grep -v __pycache__`
- 예상: 프로덕션 코드에 0건

**Step 3: datetime.now() 잔존 확인**
- 검증: `grep -rn "datetime.now()" backend/modules/ --include="*.py" | grep -v __pycache__`
- 예상: KST 미포함 호출 0건 (dart.py의 `datetime.now().year`는 연도만 사용하므로 UTC/KST 무관 — 허용)

**Step 4: 적응형 필터 시나리오 수동 검증**
- Docker 환경에서 screener를 직접 호출하여 적응형 동작 확인
- 검증:
```bash
docker compose exec backend python -c "
import asyncio
from modules.screening.screener import PrimaryScreener
from modules.screening.filters import PrimaryFilters
print('PrimaryFilters volume_ratio:', PrimaryFilters().volume_ratio)
assert PrimaryFilters().volume_ratio == 1.5
ps = PrimaryScreener()
assert hasattr(ps, '_apply_filters_with_adaptive')
print('OK: 적응형 필터 메서드 존재 확인')
"
```
- 예상: `PrimaryFilters volume_ratio: 1.5`, `OK: 적응형 필터 메서드 존재 확인`

**완료 기준:**
- ✅ pytest 전체 통과 (709 passed, 0 failed)
- ✅ date.today() 프로덕션 잔존 0건
- ✅ datetime.now() 미보호 호출 0건
- ✅ PrimaryFilters().volume_ratio == 1.5 확인

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 passed, 0 failed |
| date.today() 잔존 | `grep -rn "date.today()" backend/ --include="*.py" \| grep -v test \| grep -v __pycache__` | 0건 |
| datetime.now() 미보호 | `grep -rn "datetime.now()" backend/modules/ --include="*.py" \| grep -v __pycache__` | KST 포함 또는 연도만 사용 |
| volume_ratio 기본값 | Python import 확인 | 1.5 |
| 적응형 필터 메서드 | Python hasattr 확인 | True |
| 기본 후보 메서드 | Python hasattr 확인 | True |
