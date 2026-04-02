# Sprint 2: 데이터 품질 + KODEX 필터 + 통합 검증 (Phase 4.6)

**Goal:** 한국거래소 휴장일 대응, ETF 시세 수집 대상을 KODEX만으로 축소, DB 후검증 체계 구축, 수집 결과 상세 로깅, 전체 통합 검증까지 완료하여 Phase 4.6을 마무리한다.

**Architecture:** Sprint 1에서 구축한 CollectionValidator + CollectionResult 체계 위에, trading_calendar 유틸로 공휴일을 처리하고, kis_collector의 `_get_etf_codes()`에 KODEX 필터를 추가하여 시세 수집 대상을 ~280종목으로 축소한다. DB 후검증 쿼리로 적재 결과를 재확인하고, scheduler에 구조화된 로깅을 추가한다.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (async), pytest, APScheduler

**Sprint 기간:** 2026-04-02 ~ (사용자 검토 후 구현)
**이전 스프린트:** Sprint 1 (pytest 603 passed, PR #58 + 핫픽스 PR #60/#61)
**브랜치명:** `phase4.6-sprint2`

---

## 제외 범위

- ETN 시세 수집 (Phase 5 범위)
- 유효성 검증 임계값 운영 보정 (1주일 운영 데이터 수집 후)
- 공공데이터포털 ETF API 탐색 (Phase 5 범위)
- 프론트엔드 변경 없음
- DB 스키마 / Alembic 마이그레이션 없음
- KODEX 외 ETF 운용사 필터링 설정 UI (Phase 5에서 검토)

---

## 실행 플랜

### Phase 1 (순차 -- 기반 유틸)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 한국거래소 휴장일 캘린더 유틸 | 백엔드 | -- |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | KODEX ETF 필터링 | 백엔드 | -- |
| Task 3 | data_go_kr 휴장일 통합 | 백엔드 | -- |
| Task 4 | CollectionValidator DB 후검증 | 백엔드 | -- |

### Phase 3 (순차 -- Task 1~4 완료 후)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | scheduler 상세 로깅 + 신선도 검증 | 백엔드 | -- |

### Phase 4 (순차 -- 최종)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | 통합 테스트 | 백엔드 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 Task 2/3/4를 병렬 구현합니다. 파일 소유권이 겹치지 않습니다.

---

### Task 1: trading_calendar -- 한국거래소 휴장일 캘린더

**Files:**
- Create: `backend/core/trading_calendar.py`
- Test: `backend/tests/test_trading_calendar.py`

**Step 1: 테스트 작성**
- `backend/tests/test_trading_calendar.py` 생성
- 테스트 시나리오:
  - `is_trading_day("2026-01-01")` -> False (신정)
  - `is_trading_day("2026-04-06")` -> False (일요일)
  - `is_trading_day("2026-04-03")` -> True (평일, 공휴일 아님)
  - `is_trading_day("2026-09-28")` -> False (추석)
  - `get_latest_trading_day(date(2026, 1, 1))` -> 2025-12-31 (전일 영업일)
  - `get_prev_trading_day(date(2026, 4, 6), n=2)` -> T-2 거래일 계산
- 검증: `docker compose exec backend pytest tests/test_trading_calendar.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 모듈 구현**
- `backend/core/trading_calendar.py` 생성
- `KR_HOLIDAYS_2026`: 2026년 한국 공휴일 set (date 객체)
  - 1/1(신정), 1/28~1/30(설날), 3/1(삼일절), 5/5(어린이날), 5/24(석가탄신), 6/6(현충일), 8/15(광복절), 9/14~9/16(추석), 10/3(개천절), 10/9(한글날), 12/25(성탄절)
  - 대체공휴일: 3/2(삼일절 대체), 10/5(추석 대체) -- 확인 필요, 주석으로 "2026년 확정 대체공휴일 확인 필요" 표기
- `is_trading_day(d: date) -> bool`: 주말(토/일) 또는 공휴일이면 False
- `get_latest_trading_day(d: date) -> date`: d 이전의 가장 최근 거래일 반환 (d가 거래일이면 d 반환)
- `get_prev_trading_day(d: date, n: int = 1) -> date`: d 기준 n번째 이전 거래일 반환
- 검증: `docker compose exec backend pytest tests/test_trading_calendar.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/trading_calendar.py backend/tests/test_trading_calendar.py
git commit -m "feat(phase4.6-sprint2): task1 -- 한국거래소 2026년 휴장일 캘린더 유틸"
```

**완료 기준:**
- ⬜ pytest 테스트 통과
- ⬜ is_trading_day, get_latest_trading_day, get_prev_trading_day 정상 동작

---

### Task 2: KODEX ETF 필터링 -- 시세 수집 대상 축소

**Files:**
- Modify: `backend/modules/collector/sources/kis_collector.py` (`_get_etf_codes` 메서드에 KODEX 필터 추가)
- Modify: `backend/tests/test_kis_collector.py` (KODEX 필터 테스트 추가)

**Step 1: 테스트 추가**
- `backend/tests/test_kis_collector.py`에 테스트 추가
- 테스트 시나리오:
  - `_get_etf_codes()`가 stock_name이 'KODEX'로 시작하는 ETF만 반환하는지 확인
  - DB에 KODEX 2종, 비KODEX 2종 mock -> 결과 2종만 반환
  - `collect_etf_prices()`에서 KODEX 필터 적용 시 total_target 검증
- `_get_etf_codes()`는 private 메서드이므로, mock DB에 stock_name 포함 데이터 세팅 후 `collect_etf_prices(etf_codes=None)` 호출로 간접 테스트
- 검증: `docker compose exec backend pytest tests/test_kis_collector.py -v`
- 예상: FAIL (필터 미구현)

**Step 2: KODEX 필터 구현**
- `backend/modules/collector/sources/kis_collector.py`의 `_get_etf_codes()` 수정
- 현재:
  ```python
  select(Stock.stock_code).where(
      Stock.stock_type == "ETF",
      Stock.is_active.is_(True),
  )
  ```
- 변경:
  ```python
  select(Stock.stock_code).where(
      Stock.stock_type == "ETF",
      Stock.is_active.is_(True),
      Stock.stock_name.startswith("KODEX"),
  )
  ```
- `startswith`는 SQLAlchemy의 `ColumnOperators.startswith()` 사용 (LIKE 'KODEX%' 생성)
- 로그 추가: `logger.info("KODEX ETF 수집 대상: %d종목", len(codes))`
- 주의: ETF 마스터(stocks 테이블) 전체 데이터는 유지. 시세 수집 대상만 KODEX로 제한
- 검증: `docker compose exec backend pytest tests/test_kis_collector.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/kis_collector.py backend/tests/test_kis_collector.py
git commit -m "feat(phase4.6-sprint2): task2 -- ETF 시세 수집 대상을 KODEX만으로 제한"
```

**완료 기준:**
- ⬜ `_get_etf_codes()`가 KODEX ETF만 반환
- ⬜ 마스터 데이터(stocks 테이블)는 전체 ETF 유지
- ⬜ pytest 테스트 통과

---

### Task 3: data_go_kr 휴장일 통합 -- trading_calendar 활용

**Files:**
- Modify: `backend/modules/collector/sources/data_go_kr.py` (`_latest_trading_date` 메서드에서 trading_calendar 사용)
- Modify: `backend/modules/collector/validator.py` (`_is_within_t2` 메서드에서 trading_calendar 사용)
- Modify: `backend/tests/test_data_go_kr.py` (필요 시 날짜 폴백 관련 테스트 보강)

**Step 1: data_go_kr.py 수정**
- `_latest_trading_date()` 메서드에서 기존 "주말만 건너뜀" 로직을 `trading_calendar.get_latest_trading_day()` 호출로 교체
- import 추가: `from core.trading_calendar import get_latest_trading_day`
- 기존 while 루프(weekday 체크)를 `get_latest_trading_day(target_date)` 한 줄로 대체
- 검증: `docker compose exec backend pytest tests/test_data_go_kr.py -v`
- 예상: PASS

**Step 2: validator.py 수정**
- `_is_within_t2()` 메서드에서 기존 "주말만 건너뜀" 로직을 `trading_calendar.get_prev_trading_day()` 호출로 교체
- import 추가: `from core.trading_calendar import get_prev_trading_day`
- 기존 while 루프 -> `boundary = get_prev_trading_day(today, n=2)`, `return target >= boundary`
- 검증: `docker compose exec backend pytest tests/test_collection_validator.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/data_go_kr.py backend/modules/collector/validator.py backend/tests/test_data_go_kr.py
git commit -m "feat(phase4.6-sprint2): task3 -- data_go_kr + validator에 trading_calendar 공휴일 통합"
```

**완료 기준:**
- ⬜ `_latest_trading_date()`가 공휴일을 건너뜀
- ⬜ `_is_within_t2()`가 공휴일을 건너뜀
- ⬜ pytest 테스트 통과

---

### Task 4: CollectionValidator DB 후검증 -- 적재 결과 재확인

**Files:**
- Modify: `backend/modules/collector/validator.py` (DB 후검증 메서드 추가)
- Create: `backend/tests/test_validator_db.py`

**Step 1: 테스트 작성**
- `backend/tests/test_validator_db.py` 생성
- mock AsyncSession을 사용하여:
  - `validate_premarket_db(session)` -> COUNT(market_data) >= 1500 확인, null 비율 < 5% 확인
  - `validate_etf_db(session)` -> COUNT(market_data where source='kis_rest' AND data_date=today) 확인
  - DB에 데이터 0건 -> failed 반환
  - DB에 데이터 충분 + null 비율 초과 -> failed 반환
  - DB에 데이터 충분 + null 비율 정상 -> passed 반환
- 검증: `docker compose exec backend pytest tests/test_validator_db.py -v`
- 예상: FAIL (메서드 미존재)

**Step 2: DB 후검증 메서드 구현**
- `backend/modules/collector/validator.py`에 메서드 추가:
  - `async def validate_premarket_db(self, session: AsyncSession) -> ValidationResult`:
    - `SELECT COUNT(*) FROM market_data WHERE data_date >= {T-2 거래일} AND source = 'data_go_kr'`
    - `SELECT COUNT(*) FROM market_data WHERE close_price IS NULL AND data_date >= {T-2 거래일}` -> null 비율 계산
    - 건수 >= 1500 AND null 비율 < 5% -> passed
  - `async def validate_etf_db(self, session: AsyncSession) -> ValidationResult`:
    - `SELECT COUNT(*) FROM market_data WHERE data_date = {today} AND source = 'kis_rest'`
    - KODEX 대상 약 280종목의 50% = 140건 이상 -> passed
- import 추가: `from sqlalchemy.ext.asyncio import AsyncSession`, `from sqlalchemy import func, select`, `from core.models.market_data import MarketData`
- `_is_within_t2`에서 사용하던 trading_calendar 활용 (Task 3 선행)
- 검증: `docker compose exec backend pytest tests/test_validator_db.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/validator.py backend/tests/test_validator_db.py
git commit -m "feat(phase4.6-sprint2): task4 -- CollectionValidator DB 후검증 (premarket + ETF)"
```

**완료 기준:**
- ⬜ `validate_premarket_db()` 정상 동작
- ⬜ `validate_etf_db()` 정상 동작
- ⬜ pytest 테스트 통과

---

### Task 5: scheduler 상세 로깅 + 신선도 검증

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (수집 결과 상세 로깅 + market_data 신선도 검증)
- Modify: `backend/tests/test_scheduler.py` (로깅/신선도 관련 테스트 추가)

**Step 1: 상세 로깅 추가**
- `scheduler.py`의 각 수집 메서드(`_premarket_collect`, `_etf_collect`, `_dart_collect`, `_sentiment_collect`)에 구조화된 로깅 추가:
  - 수집 시작: `logger.info("수집 시작: step=%s", step_name)`
  - 수집 완료: `logger.info("수집 완료: step=%s collected=%d failed=%d total=%d validation=%s", step_name, result.collected, result.failed, result.total_target, "PASS" if validation.passed else "FAIL")`
  - 실패 시: `logger.error("수집 실패: step=%s reason=%s", step_name, validation.failure_reason)`
- `_etf_collect` 메서드에 KODEX 필터 적용 관련 로그 추가: `logger.info("ETF 수집 대상: KODEX %d종목 (전체 ETF 대비)", result.total_target)`

**Step 2: market_data 신선도 검증 추가**
- `_premarket_collect()` 성공 후, DB 후검증 호출:
  ```python
  async with self._session_factory() as db_session:
      db_validation = await self._validator.validate_premarket_db(db_session)
  ```
- DB 후검증 실패 시: `logger.warning("DB 후검증 실패: %s", db_validation.failure_reason)`
  - pipeline_status에 `db_validation` 필드 추가 (참고 정보, pipeline_healthy에는 영향 없음 -- 수집 자체 검증이 우선)
- `_etf_collect()` 성공 후에도 동일하게 `validate_etf_db()` 호출

**Step 3: 테스트 보강**
- `backend/tests/test_scheduler.py`에 로깅/신선도 관련 테스트 추가:
  - premarket 수집 성공 후 DB 후검증 호출 확인 (mock validator)
  - etf 수집 성공 후 DB 후검증 호출 확인
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat(phase4.6-sprint2): task5 -- scheduler 상세 로깅 + market_data 신선도 DB 후검증"
```

**완료 기준:**
- ⬜ 수집 결과가 step/collected/failed/total/validation 포함하여 로깅
- ⬜ DB 후검증이 premarket/etf 수집 후 실행
- ⬜ pytest 테스트 통과

---

### Task 6: 통합 테스트

**Files:**
- Create: `backend/tests/test_phase4_6_sprint2_integration.py`
- (기존 테스트 전체 실행으로 regression 확인)

**Step 1: 통합 테스트 작성**
- `backend/tests/test_phase4_6_sprint2_integration.py` 생성
- 테스트 시나리오:
  1. **trading_calendar 통합**: `_is_within_t2`가 공휴일을 올바르게 처리 (2026-01-01 전후 데이터)
  2. **KODEX 필터 통합**: `KISCollector._get_etf_codes()` mock DB에 KODEX 5종 + 비KODEX 3종 -> 5종만 반환
  3. **ETF 수집 + 검증 통합**: KODEX ~280종목 기준으로 validate_etf_collect가 50% 임계값 적용
  4. **DB 후검증 통합**: validate_premarket_db/validate_etf_db가 정상 DB 상태에서 passed 반환
  5. **scheduler 파이프라인 통합**: premarket -> primary_screen -> etf -> dart -> sentiment 순서 실행, pipeline_healthy 판정
  6. **날짜 폴백 + 공휴일**: 공휴일(1/1)에 data_go_kr 수집 시 전일(12/31)로 폴백
- 검증: `docker compose exec backend pytest tests/test_phase4_6_sprint2_integration.py -v`
- 예상: PASS

**Step 2: 전체 테스트 regression 확인**
- 검증: `docker compose exec backend pytest -v`
- 예상: 603+ passed, 0 failed

**Step 3: 커밋**
```
git add backend/tests/test_phase4_6_sprint2_integration.py
git commit -m "feat(phase4.6-sprint2): task6 -- Phase 4.6 Sprint 2 통합 테스트"
```

**완료 기준:**
- ⬜ 통합 테스트 6개 시나리오 전체 PASS
- ⬜ 기존 테스트 전체 regression PASS (603+ passed)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 603+ passed, 0 failed |
| trading_calendar 단위 | `docker compose exec backend pytest tests/test_trading_calendar.py -v` | 6+ passed |
| KODEX 필터 | `docker compose exec backend pytest tests/test_kis_collector.py -v` | 5+ passed |
| DB 후검증 | `docker compose exec backend pytest tests/test_validator_db.py -v` | 5+ passed |
| 통합 테스트 | `docker compose exec backend pytest tests/test_phase4_6_sprint2_integration.py -v` | 6 passed |
| KODEX 종목 수 확인 | `docker compose exec backend python -c "..."` (DB 쿼리로 KODEX ETF 수 확인) | ~280종목 |
| ETF 시세 수집 속도 | 프로덕션 배포 후 다음 거래일 08:15 로그 확인 | ~30초 이내 완료 |
