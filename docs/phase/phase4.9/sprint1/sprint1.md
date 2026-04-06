# Sprint 1: DB 기반 스크리닝 의존성 + 재시도 후 재실행 (Phase 4.9)

**Goal:** 이중 실패(포털+KIS) 시에도 DB에 유효 데이터가 있으면 스크리닝을 진행하고, 08:30 재시도 성공 시 스크리닝 + 후속 단계를 자동 재실행한다.

**Architecture:** validator.py에 `validate_screening_readiness()` 추가하여 DB 데이터 충분성 검증. scheduler.py의 `_primary_screen()`에서 pipeline_status 실패 시 DB 폴백 오버라이드. `_premarket_retry()` 성공 후 "skipped" 상태인 후속 단계 재실행.

**Tech Stack:** SQLAlchemy (async), Redis, APScheduler, pytest

**Sprint 기간:** 2026-04-06 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 4.8 Sprint 3 (pytest passed, PR #80)
**브랜치명:** `phase4.9-sprint1`

---

## 제외 범위

- pipeline_healthy=true 전환: DB 폴백 스크리닝이 성공해도 pipeline_healthy=false 유지 (자동 매매 차단). 기존 `_are_core_steps_healthy()`가 premarket "success"를 요구하므로 자연 차단됨
- DEPENDENCY_MAP 변경: primary_screen만 DB 폴백 오버라이드, 다른 단계의 의존성은 그대로 유지
- 프론트엔드 변경: 이 Sprint에서 프론트엔드 수정 없음
- 소스 상수 공유 리팩토링: validate_screening_readiness와 screener의 소스 필터를 상수로 공유하는 작업은 별도 이슈 (미해결 사항 #2)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | validate_screening_readiness() 구현 + 단위 테스트 | 백엔드 | -- |

### Phase 2 (순차 — Task 1 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | _primary_screen() DB 폴백 + _send_stale_data_alert() + 재시도 후 재실행 | 백엔드 | -- |

### Phase 3 (순차 — Task 2 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | DB 폴백 스크리닝 + 재시도 후 재실행 통합 테스트 | 백엔드 | -- |

---

### Task 1: validate_screening_readiness() 구현 + 단위 테스트

**Files:**
- Modify: `backend/modules/collector/validator.py` (CollectionValidator에 메서드 추가)
- Create: `backend/tests/test_screening_readiness.py`

**Step 1: 테스트 작성**
- `backend/tests/test_screening_readiness.py` 생성
- FakeRedis 패턴 사용 (conftest.py 참조)
- 테스트 케이스:
  1. `test_screening_readiness_pass_t1`: T-1 데이터 1500건 이상, null_ratio < 5% -> passed=True, severity="info"
  2. `test_screening_readiness_pass_t2_stale`: T-2 데이터만 있음 (latest_date < prev_trading_day) -> passed=True, severity="warning", is_stale=True
  3. `test_screening_readiness_fail_insufficient`: 데이터 1000건 -> passed=False, failure_type="data_insufficient"
  4. `test_screening_readiness_fail_null_ratio`: null_ratio >= 5% -> passed=False, failure_type="data_quality"
  5. `test_screening_readiness_empty_db`: 데이터 0건 -> passed=False
- DB 세션 모킹: AsyncMock으로 session.execute 결과를 제어
  - total_stmt 결과: `(total_count, latest_date)` 튜플 반환하는 mock
  - null_stmt 결과: `null_count` 스칼라 반환하는 mock
  - source_stmt 결과: `[(source, count)]` 리스트 반환하는 mock
- 검증: `docker compose exec backend pytest tests/test_screening_readiness.py -v`
- 예상: FAIL (validate_screening_readiness 미존재)

**Step 2: validate_screening_readiness() 구현**
- `backend/modules/collector/validator.py`의 CollectionValidator 클래스에 async 메서드 추가
- 시그니처: `async def validate_screening_readiness(self, session: AsyncSession) -> ValidationResult`
- 구현 로직 (phase4.9.md 구현 상세 #1 참조):
  - `today = datetime.now(KST).date()`
  - `boundary = get_prev_trading_day(today, n=2)` (기존 `_is_within_t2`와 동일 경계)
  - 소스 필터: `["data_go_kr", "kis_daily"]` (screener의 `_fetch_today_and_prev` date_subq와 일치 -- screener.py 라인 137 참조)
  - 쿼리 1: `select(func.count(), func.max(MarketData.data_date)).where(data_date >= boundary, source.in_(sources))` -> total_count, latest_date
  - total_count < 1500 -> `ValidationResult(passed=False, failure_type="data_insufficient", ...)`
  - 쿼리 2: `select(func.count()).where(data_date >= boundary, source.in_(sources), close_price.is_(None))` -> null_count
  - null_ratio = null_count / total_count, >= 0.05 -> `ValidationResult(passed=False, failure_type="data_quality", ...)`
  - 쿼리 3: `select(MarketData.source, func.count()).where(...).group_by(MarketData.source)` -> source_counts (디버깅용)
  - T-2 경고 판정: `prev_trading_day = get_prev_trading_day(today, n=1)`, `is_stale = latest_date < prev_trading_day`
  - severity: "warning" if is_stale else "info"
  - 반환: `ValidationResult(passed=True, severity=severity, details={total_count, null_ratio, latest_date, source_counts, is_stale})`
- 검증: `docker compose exec backend pytest tests/test_screening_readiness.py -v`
- 예상: PASS (5개 테스트)

**Step 3: 커밋**
```
git add backend/modules/collector/validator.py backend/tests/test_screening_readiness.py
git commit -m "feat(phase4.9-sprint1): task1 -- validate_screening_readiness 구현 + 단위 테스트"
```

**완료 기준:**
- ⬜ pytest tests/test_screening_readiness.py 5개 PASS
- ⬜ 기존 테스트 회귀 없음

---

### Task 2: _primary_screen() DB 폴백 + 텔레그램 알림 + 재시도 후 재실행

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (`_primary_screen`, `_premarket_retry`, `_send_stale_data_alert` 수정/추가)

**Step 1: _send_stale_data_alert() 추가**
- `backend/modules/collector/scheduler.py`에 async 메서드 추가
- 위치: `_send_double_failure_alert` 아래 (라인 241 부근)
- 시그니처: `async def _send_stale_data_alert(self, details: dict) -> None`
- 구현:
  - `if self._telegram_bot is None: return`
  - 메시지 HTML 포맷:
    ```
    <b>[경고]</b> DB 폴백 스크리닝 -- T-2 데이터 사용
    최신 데이터: {details.get('latest_date')}
    건수: {details.get('total_count')}건
    소스: {details.get('source_counts')}
    ```
  - `await self._telegram_bot.send_notification(msg)`
- 검증: 코드 리뷰 (Step 3에서 통합 검증)

**Step 2: _primary_screen() DB 폴백 오버라이드**
- `backend/modules/collector/scheduler.py`의 `_primary_screen()` (라인 729) 수정
- 현재 로직: `_check_dependency("primary_screen")` 실패 시 즉시 "skipped" 반환
- 변경 로직 (phase4.9.md 구현 상세 #2 참조):
  1. 기존 `_check_dependency("primary_screen")` 호출 -> dep_ok
  2. dep_ok=True -> 기존 스크리닝 로직 그대로 실행 (변경 없음)
  3. dep_ok=False -> DB 폴백 시도:
     - `async with self._session_factory() as db_session:` -> `readiness = await self._validator.validate_screening_readiness(db_session)`
     - readiness.passed=True:
       - `logger.warning("premarket 실패지만 DB 데이터 충분 -- 스크리닝 진행 (DB 폴백): %s", readiness.details)`
       - readiness.severity == "warning" -> `await self._send_stale_data_alert(readiness.details)`
       - 이하 기존 스크리닝 로직 실행 (screener.screen -> save_results -> WS 구독 등)
     - readiness.passed=False:
       - `logger.warning("스크리닝 스킵: premarket 실패 + DB 데이터 부족 (%s)", readiness.failure_reason)`
       - `await self._update_step_status("primary_screen", "skipped", error=readiness.failure_reason)`
       - `return {"skipped": True, "candidates": 0, "passed": 0}`
     - except Exception as e:
       - `logger.warning("DB 충분성 검증 실패 -- 기존 의존성 체크 따름: %s", e)`
       - 기존 skipped 로직 실행
  - 핵심: pipeline_healthy는 절대 건드리지 않음. `_update_step_status("primary_screen", "success", ...)`로 기록하되, `_are_core_steps_healthy`는 premarket "success"를 요구하므로 pipeline_healthy=false가 유지됨
- 검증: `docker compose exec backend pytest tests/test_scheduler_dependency.py -v`
- 예상: 기존 테스트 PASS (premarket failed -> skipped 동작은 DB 데이터 없는 mock 환경에서 여전히 동일)

**Step 3: _premarket_retry() 후속 재실행 추가**
- `backend/modules/collector/scheduler.py`의 `_premarket_retry()` (라인 573) 수정
- 현재 로직: validation.passed 후 상태 업데이트 + 알림 발송으로 종료
- 추가 로직 (validation.passed 블록 내, cross-check 이후):
  1. `pipeline_status = await self._get_pipeline_status()`
  2. `screen_status = pipeline_status.get("primary_screen", {}).get("status")`
  3. `if screen_status == "skipped":` (또는 "failed")
     - `existing = await self._redis.get(PIPELINE_RUNNING_KEY)`
     - `if existing:` -> `logger.warning("파이프라인 실행 중 -- 재시도 후 재실행 스킵")` -> return
     - `logger.info("포털 재시도 성공 -> 스크리닝 + 후속 단계 재실행")`
     - `try:` -> `await self._primary_screen()`, `await self._dart_collect()`, `await self._sentiment_collect()`
     - `except Exception as e:` -> `logger.exception("재시도 후 재실행 실패: %s", e)`
- 검증: `docker compose exec backend pytest tests/test_scheduler_retry.py -v`
- 예상: 기존 재시도 테스트 PASS

**Step 4: 커밋**
```
git add backend/modules/collector/scheduler.py
git commit -m "feat(phase4.9-sprint1): task2 -- _primary_screen DB 폴백 + 텔레그램 알림 + 재시도 후 재실행"
```

**완료 기준:**
- ⬜ 기존 scheduler 테스트 전체 PASS (test_scheduler*.py)
- ⬜ _primary_screen DB 폴백 로직 구현
- ⬜ _premarket_retry 후속 재실행 로직 구현
- ⬜ _send_stale_data_alert 구현

---

### Task 3: DB 폴백 스크리닝 + 재시도 후 재실행 통합 테스트

**Files:**
- Create: `backend/tests/test_pipeline_db_fallback.py`

**Step 1: 테스트 작성**
- `backend/tests/test_pipeline_db_fallback.py` 생성
- `_make_scheduler()` 패턴 재사용 (test_scheduler_dependency.py 참조)
- 테스트 케이스:
  1. `test_primary_screen_db_fallback_success`: premarket "failed" + DB 데이터 충분 (T-1) -> 스크리닝 진행, primary_screen "success"
     - validator.validate_screening_readiness를 mock해서 passed=True, severity="info" 반환
     - screener.screen을 mock해서 결과 반환
     - 결과: primary_screen status="success", candidates > 0
  2. `test_primary_screen_db_fallback_stale_alert`: premarket "failed" + DB 데이터 T-2 -> 스크리닝 진행 + 텔레그램 경고
     - validator.validate_screening_readiness를 mock해서 passed=True, severity="warning" 반환
     - telegram_bot.send_notification이 호출되었는지 assert
     - 메시지에 "[경고]" + "T-2" 포함 확인
  3. `test_primary_screen_db_fallback_insufficient`: premarket "failed" + DB 데이터 부족 -> 스크리닝 스킵
     - validator.validate_screening_readiness를 mock해서 passed=False 반환
     - 결과: primary_screen "skipped"
  4. `test_primary_screen_db_fallback_exception`: DB 검증 자체 예외 -> 안전한 스킵
     - validator.validate_screening_readiness가 Exception raise
     - 결과: primary_screen "skipped"
  5. `test_premarket_retry_triggers_rerun`: 포털 재시도 성공 + primary_screen "skipped" -> 스크리닝 + dart + sentiment 재실행
     - premarket "failed", primary_screen "skipped" 상태 설정
     - DataGoKrCollector.collect_all mock (성공)
     - validator.validate_premarket mock (passed=True)
     - _primary_screen, _dart_collect, _sentiment_collect가 호출되었는지 확인
  6. `test_premarket_retry_no_rerun_when_screen_success`: 포털 재시도 성공 + primary_screen "success" -> 재실행 안 함
     - primary_screen 이미 "success" 상태
     - _primary_screen이 호출되지 않았는지 확인
  7. `test_premarket_retry_rerun_blocked_by_running_lock`: 재실행 시 PIPELINE_RUNNING_KEY 존재 -> 스킵
     - PIPELINE_RUNNING_KEY를 미리 설정
     - _primary_screen이 호출되지 않았는지 확인
  8. `test_pipeline_healthy_stays_false_on_db_fallback`: DB 폴백 스크리닝 성공해도 pipeline_healthy=false 유지
     - premarket "failed" + DB 폴백으로 primary_screen "success"
     - pipeline_healthy 키 값이 "false"인지 확인
- 검증: `docker compose exec backend pytest tests/test_pipeline_db_fallback.py -v`
- 예상: PASS (8개 테스트)

**Step 2: 전체 회귀 테스트**
- `docker compose exec backend pytest -v`
- 기존 테스트 회귀 없음 확인

**Step 3: 커밋**
```
git add backend/tests/test_pipeline_db_fallback.py
git commit -m "feat(phase4.9-sprint1): task3 -- DB 폴백 스크리닝 + 재시도 후 재실행 통합 테스트"
```

**완료 기준:**
- ⬜ pytest tests/test_pipeline_db_fallback.py 8개 PASS
- ⬜ pytest -v 전체 회귀 없음

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| 단위 테스트 | `docker compose exec backend pytest tests/test_screening_readiness.py -v` | 5 passed |
| 통합 테스트 | `docker compose exec backend pytest tests/test_pipeline_db_fallback.py -v` | 8 passed |
| 스케줄러 기존 테스트 | `docker compose exec backend pytest tests/test_scheduler_dependency.py tests/test_scheduler_retry.py -v` | 전체 passed |
| pytest 전체 | `docker compose exec backend pytest -v` | 회귀 없음 |
