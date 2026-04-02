# Sprint 2: 데이터 품질 + 통합 검증 (Phase 4.6)

**Goal:** 한국거래소 휴장일 캘린더를 도입하여 T-2 거래일 판정을 정확하게 만들고, DB 후검증 + market_data 신선도 검증 + 수집 결과 상세 로깅을 추가하여 데이터 품질을 보장한다.

**Architecture:** `core/trading_calendar.py` 모듈에 2026년 한국거래소 휴장일을 하드코딩하고 `is_trading_day(date)` / `prev_trading_day(date, n)` 유틸을 제공한다. CollectionValidator에 DB 후검증 메서드(`validate_premarket_db`)를 추가하여 실제 DB 레코드의 건수와 null 비율을 확인한다. scheduler.py에서는 premarket 수집 후 DB 후검증과 market_data 신선도 검증을 연쇄 실행하며, 모든 수집 단계에 구조화된 상세 로깅을 추가한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Redis 7, pytest

**Sprint 기간:** 2026-04-02 ~ (사용자 검토 후 구현)
**이전 스프린트:** Sprint 1 (pytest 602 passed, PR #58)
**브랜치명:** `phase4.6-sprint2`

---

## 제외 범위

- ETN 시세 수집 (Phase 5)
- 유효성 검증 임계값 운영 보정 (1주일 운영 후)
- 공공데이터포털 ETF/ETN 별도 API 탐색 (Phase 5)
- 프론트엔드 변경 없음
- Alembic 마이그레이션 없음 (DB 스키마 변경 없음)
- 2027년 이후 휴장일 (2026년만 하드코딩, 향후 API 전환 검토)

## 실행 플랜

의존성 분석: Task 1(trading_calendar)이 Task 2, 3, 4의 전제. Task 2/3/4는 수정 파일이 겹치지 않아 병렬 가능. Task 5는 전체 통합 테스트.

### Phase 1 (순차 -- 기반)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 한국거래소 휴장일 캘린더 모듈 | 백엔드 | -- |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | data_go_kr 날짜 계산에 trading_calendar 통합 | 백엔드 | -- |
| Task 3 | CollectionValidator DB 후검증 + market_data 신선도 검증 | 백엔드 | -- |
| Task 4 | scheduler 상세 로깅 + 신선도/DB 후검증 호출 | 백엔드 | -- |

### Phase 3 (순차 -- 통합)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | 통합 테스트 + 기존 테스트 수정 + 전체 회귀 검증 | 백엔드 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 Task 2/3/4를 병렬 구현합니다. 각 Task가 수정하는 파일이 겹치지 않습니다.

---

### Task 1: 한국거래소 휴장일 캘린더 모듈

**Files:**
- Create: `backend/core/trading_calendar.py`
- Create: `backend/tests/test_trading_calendar.py`

**Step 1: 테스트 작성**
- `backend/tests/test_trading_calendar.py` 생성
- 시나리오:
  - `is_trading_day(date(2026, 1, 1))` -> False (신정)
  - `is_trading_day(date(2026, 3, 2))` -> False (삼일절 대체)
  - `is_trading_day(date(2026, 5, 5))` -> False (어린이날)
  - `is_trading_day(date(2026, 4, 6))` -> True (월요일 평일)
  - `is_trading_day(date(2026, 4, 4))` -> False (토요일)
  - `is_trading_day(date(2026, 4, 5))` -> False (일요일)
  - `prev_trading_day(date(2026, 1, 2), n=1)` -> date(2025, 12, 31) (신정 건너뜀)
  - `prev_trading_day(date(2026, 5, 6), n=2)` -> date(2026, 5, 1) (5/5 어린이날 + 주말 건너뜀)
  - `get_trading_dates_from(date, max_days=7)` -> 주말+공휴일 건너뛴 거래일 리스트
- 검증: `docker compose exec backend pytest tests/test_trading_calendar.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: trading_calendar.py 구현**
- `backend/core/trading_calendar.py` 생성
- 2026년 한국거래소 휴장일 frozenset (date 객체):
  - 1/1(신정), 1/28~1/30(설날연휴), 3/1(삼일절), 3/2(대체공휴일), 5/1(근로자의날), 5/5(어린이날), 5/24(부처님오신날), 6/6(현충일), 8/15(광복절), 8/17(대체공휴일), 9/16~9/18(추석연휴), 10/3(개천절), 10/5(대체공휴일), 10/9(한글날), 12/25(성탄절)
  - 6/3(대통령선거일) -- 2026년 특수 휴장일
- 함수:
  - `is_trading_day(d: date) -> bool`: 평일이고 휴장일이 아니면 True
  - `prev_trading_day(d: date, n: int = 1) -> date`: d 이전 n번째 거래일 반환
  - `get_trading_dates_from(d: date, max_days: int = 7) -> list[date]`: d-1부터 역순 거래일 max_days개 반환 (공공데이터포털 폴백용)
- 검증: `docker compose exec backend pytest tests/test_trading_calendar.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/trading_calendar.py backend/tests/test_trading_calendar.py
git commit -m "feat(phase4.6-sprint2): task1 -- 한국거래소 2026년 휴장일 캘린더 모듈"
```

**완료 기준:**
- ⬜ `is_trading_day` 공휴일/주말 정확 판정
- ⬜ `prev_trading_day` 공휴일 건너뛰기 정상
- ⬜ `get_trading_dates_from` 거래일 리스트 반환
- ⬜ test_trading_calendar.py 전체 PASS

---

### Task 2: data_go_kr 날짜 계산에 trading_calendar 통합

**Files:**
- Modify: `backend/modules/collector/sources/data_go_kr.py` (`_get_trading_dates` 메서드를 trading_calendar 활용으로 변경)
- Modify: `backend/tests/test_data_go_kr.py` (공휴일 폴백 테스트 추가)

**Step 1: _get_trading_dates 수정**
- `backend/modules/collector/sources/data_go_kr.py` 수정
- 기존 `_get_trading_dates()`: 자체 주말 건너뛰기 로직 (공휴일 미처리)
- 변경: `from core.trading_calendar import get_trading_dates_from` import 후 위임
  ```
  @staticmethod
  def _get_trading_dates(max_days: int = 7) -> list[str]:
      from core.trading_calendar import get_trading_dates_from
      from core.config import settings
      today_kst = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
      dates = get_trading_dates_from(today_kst, max_days)
      return [d.strftime("%Y%m%d") for d in dates]
  ```
- `_latest_trading_date()` 는 `_get_trading_dates(1)[0]` 호출이므로 자동 적용
- 검증: `docker compose exec backend pytest tests/test_data_go_kr.py -v`
- 예상: 기존 테스트 PASS (폴백 로직 동일)

**Step 2: 공휴일 폴백 테스트 추가**
- `backend/tests/test_data_go_kr.py`에 테스트 추가
- `test_get_trading_dates_skips_holidays`: trading_calendar를 mock하여 특정 날짜가 공휴일일 때 건너뛰는지 확인
- 검증: `docker compose exec backend pytest tests/test_data_go_kr.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/data_go_kr.py backend/tests/test_data_go_kr.py
git commit -m "feat(phase4.6-sprint2): task2 -- data_go_kr 날짜 계산에 trading_calendar 통합"
```

**완료 기준:**
- ⬜ `_get_trading_dates()`가 공휴일을 건너뜀
- ⬜ `_latest_trading_date()`가 공휴일 다음 거래일 반환
- ⬜ test_data_go_kr.py 전체 PASS

---

### Task 3: CollectionValidator DB 후검증 + validator에 trading_calendar 통합

**Files:**
- Modify: `backend/modules/collector/validator.py` (DB 후검증 메서드 추가 + `_is_within_t2`에 trading_calendar 통합)
- Modify: `backend/tests/test_collection_validator.py` (DB 후검증 + 휴장일 T-2 테스트 추가)

**Step 1: _is_within_t2에 trading_calendar 통합**
- `backend/modules/collector/validator.py` 수정
- 기존 `_is_within_t2`: 주말만 건너뜀 (공휴일 무시)
- 변경: `from core.trading_calendar import prev_trading_day` import
- `_is_within_t2` 내부에서 `prev_trading_day(today, n=2)` 호출하여 T-2 거래일 계산
  - 기존 while 루프 제거, `prev_trading_day`로 대체
  - `target >= prev_trading_day(today, 2)` 이면 True

**Step 2: validate_premarket_db 메서드 추가**
- `validate_premarket_db(session: AsyncSession) -> ValidationResult` 비동기 메서드 추가
- 검증 내용:
  1. `SELECT COUNT(*) FROM market_data WHERE data_date = (SELECT MAX(data_date) FROM market_data)` -- 최신 날짜 레코드 수
  2. 최신 data_date가 T-2 거래일 이내인지 (신선도 검증)
  3. `SELECT COUNT(*) FROM market_data WHERE data_date = :latest AND close_price IS NULL` -- null 비율
- 반환:
  - 레코드 수 < 1500: failed, failure_reason="DB 후검증: 레코드 부족"
  - data_date가 T-2 초과: failed, failure_reason="DB 후검증: 데이터 신선도 부족"
  - close_price null >= 5%: failed, failure_reason="DB 후검증: close_price null 비율 초과"
  - 모두 통과: passed=True
- import 추가: `from sqlalchemy import func, select`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from core.models.market_data import MarketData`

**Step 3: validate_market_data_freshness 메서드 추가**
- `validate_market_data_freshness(session: AsyncSession) -> ValidationResult` 비동기 메서드
- `SELECT MAX(data_date) FROM market_data` 조회
- 최신 data_date가 T-2 거래일 이내인지만 확인 (간단한 신선도 체크)
- scheduler에서 장중 진입 전 호출 용도

**Step 4: 테스트 추가**
- `backend/tests/test_collection_validator.py`에 테스트 추가:
  - `test_is_within_t2_skips_holidays`: 공휴일이 끼면 T-2 범위가 자동 확장
  - `test_validate_premarket_db_pass`: mock session에서 1500건+, null < 5%, T-2 이내 -> passed=True
  - `test_validate_premarket_db_fail_count`: 1000건 -> passed=False
  - `test_validate_premarket_db_fail_freshness`: T-3 거래일 -> passed=False
  - `test_validate_premarket_db_fail_null_ratio`: close_price null >= 5% -> passed=False
  - `test_validate_market_data_freshness_pass`: T-1 -> passed=True
  - `test_validate_market_data_freshness_fail`: T-3 -> passed=False
- 검증: `docker compose exec backend pytest tests/test_collection_validator.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/modules/collector/validator.py backend/tests/test_collection_validator.py
git commit -m "feat(phase4.6-sprint2): task3 -- DB 후검증 + market_data 신선도 + trading_calendar 통합"
```

**완료 기준:**
- ⬜ `_is_within_t2`가 공휴일 포함 정확한 T-2 판정
- ⬜ `validate_premarket_db` DB 레코드 건수/null/신선도 검증
- ⬜ `validate_market_data_freshness` 신선도 전용 검증
- ⬜ test_collection_validator.py 기존 + 신규 전체 PASS

---

### Task 4: scheduler 상세 로깅 + 신선도/DB 후검증 호출

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (_premarket_collect에 DB 후검증 호출, 장중 진입 시 신선도 검증, 모든 수집 단계에 상세 로깅)

**Step 1: _premarket_collect에 DB 후검증 추가**
- `backend/modules/collector/scheduler.py` 수정
- `_premarket_collect` 메서드에서 CollectionValidator.validate_premarket(result) 통과 후:
  - 추가: `db_validation = await self._validator.validate_premarket_db(db_session)` 호출
  - DB 후검증 실패 시: 기존 premarket status를 "warning"으로 업데이트 (failed까지는 아님 -- 수집 자체는 성공)
  - pipeline_status entry에 `db_validation` dict 추가
  - 주의: db_session은 `async with self._session_factory() as db_session:` 블록 안에서 호출해야 함
    -> collect_all 완료 후 같은 블록 내에서 validate_premarket_db 호출
- 로깅: `logger.info("DB 후검증: %s", "통과" if db_validation.passed else db_validation.failure_reason)`

**Step 2: _market_open에 신선도 검증 추가**
- `_market_open` 메서드 시작부에:
  - `async with self._session_factory() as db_session:`
  - `freshness = await self._validator.validate_market_data_freshness(db_session)`
  - 실패 시: `logger.warning("market_data 신선도 부족: %s", freshness.failure_reason)` + 텔레그램 알림
  - 성공 시: `logger.info("market_data 신선도 확인: 최신 data_date 정상")`
  - 신선도 실패해도 WS 연결은 차단하지 않음 (warning만) -- 시장 데이터가 오래됐어도 실시간 수신은 필요

**Step 3: 수집 단계별 상세 로깅 추가**
- 모든 수집 단계(`_premarket_collect`, `_etf_collect`, `_etf_master_collect`, `_dart_collect`, `_sentiment_collect`, `_primary_screen`)에 구조화된 로깅 추가:
  - 시작: `logger.info("[%s] 수집 시작 — 의존성: %s", step, deps_status)`
  - 완료: `logger.info("[%s] 수집 완료 — collected=%d, failed=%d, validation=%s, 소요시간=%.1fs", step, result.collected, result.failed, "통과"/"실패", elapsed)`
  - 실패: `logger.error("[%s] 수집 실패 — error=%s, 소요시간=%.1fs", step, str(e), elapsed)`
- 소요시간 측정: 각 메서드 시작에 `start_time = datetime.now()`, 완료에 `elapsed = (datetime.now() - start_time).total_seconds()`
- pipeline_status entry에 `"elapsed_sec"` 필드 추가 (float)

**Step 4: 커밋**
```
git add backend/modules/collector/scheduler.py
git commit -m "feat(phase4.6-sprint2): task4 -- scheduler DB 후검증 + 신선도 검증 + 상세 로깅"
```

**완료 기준:**
- ⬜ premarket 수집 후 DB 후검증 자동 실행
- ⬜ 장중 진입 시 market_data 신선도 검증
- ⬜ 모든 수집 단계에 소요시간 + 구조화된 로깅
- ⬜ pipeline_status에 elapsed_sec 필드 포함

---

### Task 5: 통합 테스트 + 기존 테스트 수정 + 전체 회귀 검증

**Files:**
- Modify: `backend/tests/test_scheduler.py` (_make_scheduler에 inquiry_client 전달 확인, 상세 로깅 관련 변경 대응)
- Modify: `backend/tests/test_phase4_6_integration.py` (DB 후검증 + 신선도 검증 통합 시나리오 추가)
- Modify: `backend/tests/test_scheduler_dependency.py` (로깅 변경으로 인한 호환성 확인)
- Modify: `backend/tests/test_scheduler_telegram_alert.py` (신선도 실패 시 알림 시나리오 추가)
- Create: `backend/tests/test_scheduler_pipeline.py` (파이프라인 전체 흐름 + DB 후검증 연쇄 테스트)

**Step 1: test_scheduler_pipeline.py 작성**
- `backend/tests/test_scheduler_pipeline.py` 생성
- 시나리오:
  1. **premarket 수집 + DB 후검증 연쇄**: collect_all 성공 -> validate_premarket 통과 -> validate_premarket_db 통과 -> pipeline_status에 db_validation 포함
  2. **premarket 수집 성공 + DB 후검증 실패**: collect_all 성공 -> validate_premarket 통과 -> validate_premarket_db 실패 -> pipeline_status에 warning
  3. **market_open 신선도 검증 통과**: validate_market_data_freshness 통과 -> WS 연결 정상
  4. **market_open 신선도 실패 + WS 연결 유지**: validate_market_data_freshness 실패 -> warning 로그 + 텔레그램 알림 + WS 연결은 정상 진행
  5. **elapsed_sec 기록 확인**: premarket 완료 후 pipeline_status에 elapsed_sec 존재
- 검증: `docker compose exec backend pytest tests/test_scheduler_pipeline.py -v`
- 예상: PASS

**Step 2: test_phase4_6_integration.py 확장**
- 기존 시나리오에 추가:
  - **trading_calendar 통합 확인**: validator._is_within_t2가 공휴일 고려하여 T-2 판정
  - **data_go_kr 공휴일 폴백**: _get_trading_dates가 공휴일 건너뜀
- 검증: `docker compose exec backend pytest tests/test_phase4_6_integration.py -v`
- 예상: PASS

**Step 3: 기존 테스트 호환성 확인 및 수정**
- `test_scheduler.py`: _premarket_collect 내부에서 db_session 블록이 변경되었으므로 Mock 패치 경로 확인
- `test_scheduler_dependency.py`: 로깅 포맷 변경에 따른 테스트 호환성
- `test_scheduler_telegram_alert.py`: 신선도 실패 시 텔레그램 알림 Mock 추가
- 검증: `docker compose exec backend pytest tests/test_scheduler.py tests/test_scheduler_dependency.py tests/test_scheduler_telegram_alert.py -v`
- 예상: PASS

**Step 4: 전체 회귀 검증**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (기존 602개 + 신규 테스트)

**Step 5: 커밋**
```
git add backend/tests/
git commit -m "feat(phase4.6-sprint2): task5 -- 통합 테스트 + 기존 테스트 수정 + 전체 회귀 검증"
```

**완료 기준:**
- ⬜ test_scheduler_pipeline.py 5개 시나리오 PASS
- ⬜ test_phase4_6_integration.py 기존 + 신규 시나리오 PASS
- ⬜ 기존 scheduler 테스트 전체 호환성 유지
- ⬜ pytest 전체 테스트 PASS (0 failed)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| trading_calendar import | `docker compose exec backend python -c "from core.trading_calendar import is_trading_day; print(is_trading_day(__import__('datetime').date(2026,1,1)))"` | False |
| trading_calendar 평일 | `docker compose exec backend python -c "from core.trading_calendar import is_trading_day; print(is_trading_day(__import__('datetime').date(2026,4,6)))"` | True |
| data_go_kr 공휴일 처리 | `docker compose exec backend python -c "from modules.collector.sources.data_go_kr import DataGoKrCollector; dates = DataGoKrCollector._get_trading_dates(3); print(dates)"` | 공휴일 제외된 거래일 3개 |
| validator import | `docker compose exec backend python -c "from modules.collector.validator import CollectionValidator; v=CollectionValidator(); print('OK')"` | OK |
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS |
