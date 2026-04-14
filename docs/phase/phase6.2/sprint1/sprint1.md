# Sprint 1: 장전 수집 단순화 + 포털 장후 보조 (Phase 6.2)

**Goal:** 08:00 수집을 KIS 일봉 직접 호출로 전환하고, 포털은 16:00 장후 보조 수집으로 market_cap/listed_shares만 갱신하며, 불필요한 포털 관련 코드를 제거한다.

**Architecture:** scheduler.py의 `_premarket_collect`를 KIS 직접 호출로 단순화하고, `_premarket_retry`를 KIS 재시도로 전환하며, 16:00 `_portal_supplement_collect` cron을 신규 추가한다. validator.py의 `validate_premarket_db` 소스 조건을 확장한다.

**Tech Stack:** Python 3.12, FastAPI, APScheduler, SQLAlchemy 2.0 (async), Redis 7

**Sprint 기간:** 2026-04-14 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 6.1 Sprint 1 (798 passed, PR #125)
**브랜치명:** `phase6.2-sprint1`

---

## 제외 범위

- 프론트엔드 변경 없음
- DB 스키마 변경 없음 (Alembic 마이그레이션 불필요)
- 새 의존성 추가 없음
- 백필 실행은 배포 후 수동으로 수행 (기존 `trigger_premarket_date` API 활용, 이 Sprint에서 코드 변경 없음)
- `_send_fallback_info_alert`, `_send_double_failure_alert` 메서드 삭제는 이 Sprint에서 수행하되, 외부에서 참조하는 곳이 없으면 제거 (데드코드 정리)
- pipeline_healthy 조건 변경 없음 (기존 유지)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | validator.py — validate_premarket_db 소스 조건 확장 | 백엔드 | — |
| Task 2 | scheduler.py — _premarket_collect 단순화 + _premarket_retry KIS 전환 + 16:00 cron 추가 + 데드코드 제거 | 백엔드 | — |

### Phase 2 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | 기존 테스트 수정 + 신규 테스트 + 통합 검증 | 백엔드 | — |

> Task 1과 Task 2는 파일이 다르지만 Task 2가 validator 변경에 의존하므로 순차 실행한다.

---

### Task 1: validate_premarket_db 소스 조건 확장

**Files:**
- Modify: `backend/modules/collector/validator.py` (L218-270 validate_premarket_db 메서드 내 소스 필터)
- Test: `backend/tests/test_scheduler_integration.py` (기존 테스트 — 변경 시 확인)

**Step 1: validator.py 수정**
- `backend/modules/collector/validator.py`의 `validate_premarket_db` 메서드에서 소스 필터를 변경:
  - **현재**: `MarketData.source == "data_go_kr"` (L226, L242 — 2곳)
  - **변경**: `MarketData.source.in_(["data_go_kr", "kis_daily"])` (2곳 모두)
- 이 수정이 없으면 08:00 KIS 수집 후 DB 검증이 항상 실패한다 ("건수 부족: 0 < 1500")
- 검증: `docker compose exec backend pytest tests/ -k "validate_premarket" -v`
- 예상: 관련 테스트 PASS (기존 테스트는 mock 기반이므로 소스 조건 변경에 직접 영향 없음)

**Step 2: 커밋**
```
git add backend/modules/collector/validator.py
git commit -m "feat(phase6.2-sprint1): task1 -- validate_premarket_db 소스 조건 확장 (data_go_kr + kis_daily)"
```

**완료 기준:**
- ⬜ validate_premarket_db의 2개 쿼리에서 `source.in_(["data_go_kr", "kis_daily"])` 조건 적용
- ⬜ 기존 테스트 회귀 없음

---

### Task 2: scheduler.py 단순화 (핵심 변경)

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/collector/scheduler.py`
  - `_premarket_collect` (L563-645): 포털 호출 제거 -> KIS 직접 호출 단순화
  - `_premarket_retry` (L668-726): 포털 재시도 -> KIS 재시도로 전환
  - `_portal_supplement_collect`: 16:00 cron 신규 메서드 추가
  - `start()` (L338): 16:00 cron job 등록
  - 08:30 cron 주석 갱신 ("포털 재시도" -> "KIS 재시도")
  - `_run_kis_daily_fallback` -> `_run_kis_daily_collect` 이름 변경 (폴백 -> 주 경로)
  - `_send_fallback_info_alert`, `_send_double_failure_alert` 메서드 제거 (호출부 제거로 데드코드)
  - `_send_recovery_info_alert` 메서드 수정: "포털 재시도 성공" -> "KIS 재시도 성공"으로 메시지 변경

**Step 1: `_premarket_collect` 단순화**
- 현재: 포털(DataGoKrCollector) 시도 -> 실패 시 KIS 폴백 -> 예외 경로에서도 KIS 폴백 (3중 분기, ~80줄)
- 변경: KIS 일봉 직접 호출 (단일 경로, ~20줄)
- 핵심 로직:
  1. 파이프라인 상태 초기화 (기존 유지: pipeline_healthy=false, pipeline_status 전체 pending)
  2. `_run_kis_daily_collect()` 호출 (기존 `_run_kis_daily_fallback`을 이름만 변경)
  3. `validate_kis_daily(kis_result)` 검증
  4. 성공 시 `_update_step_status("premarket", "success", ...)`
  5. 실패 시 `_update_step_status("premarket", "failed", ...)`
  6. `_run_db_validation("premarket", "validate_premarket_db")` 호출
  7. `return kis_result.collected`
- 제거 대상:
  - `DataGoKrCollector` 인스턴스 생성 및 `collect_all()` 호출
  - `validate_premarket(result)` 호출 (포털 전용 검증)
  - cross-check 로직 (`cross_check_prices` 호출) — 포털 데이터가 08:00에 없으므로 비교 불가
  - KIS 폴백 분기 (이미 주 경로이므로 "폴백" 없음)
  - 이중 실패 분기 및 `_send_double_failure_alert` 호출
  - 예외 경로 KIS 폴백 시도 블록
  - `_send_fallback_info_alert` 호출

**Step 2: `_run_kis_daily_fallback` -> `_run_kis_daily_collect` 이름 변경**
- 메서드명만 변경, 내부 로직 동일:
  - `client = self._inquiry_client or self._rest_client`
  - `KISDailyCollector(client, db_session).collect_all()` 반환
- docstring 갱신: "폴백" 제거 -> "08:00 KIS 일봉 수집 실행"

**Step 3: `_premarket_retry` KIS 재시도로 전환**
- 현재: 포털(DataGoKrCollector) 재수집 시도
- 변경: KIS(`_run_kis_daily_collect()`) 재시도
- 핵심 로직:
  1. 비거래일 스킵 (기존 유지)
  2. `premarket_status == "success"` 시 스킵 (기존 유지)
  3. `_run_kis_daily_collect()` 호출 (DataGoKrCollector 대신)
  4. `validate_kis_daily(kis_result)` 검증 (validate_premarket 대신)
  5. 성공 시: `_update_step_status("premarket", "success", ...)` + `_send_recovery_info_alert(kis_result.collected)` + `_run_db_validation` + 스크리닝 재실행 (기존 로직 유지)
  6. 실패 시: 경고 로그만 (KIS 재시도 실패 — 다음 수동 트리거 필요)
- 제거 대상:
  - `DataGoKrCollector` 인스턴스 생성 및 `collect_all()` 호출
  - `validate_premarket(result)` 호출
  - cross-check 로직

**Step 4: `_portal_supplement_collect` 신규 메서드 추가**
- 위치: `_premarket_retry` 메서드 다음 (scheduler.py 내 스케줄 job 영역)
- 핵심 로직:
  1. `datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()`로 오늘 날짜 확인
  2. `is_trading_day(today)` 비거래일 스킵
  3. `async with self._session_factory() as db_session:` DB 세션 생성
  4. `DataGoKrCollector(db_session).collect_all()` 호출 (전 종목 수집)
  5. 성공: `logger.info("16:00 포털 보조 수집 완료: collected=%d", result.collected)`
  6. 0건: `logger.warning("16:00 포털 보조 수집 0건")`
  7. 예외: `logger.warning("16:00 포털 보조 수집 실패: %s", e)` (장애가 아님 — KIS 데이터로 운영 중)
- pipeline_status 업데이트 없음 (장전 파이프라인과 독립)

**Step 5: `start()` cron 등록 갱신**
- 16:00 포털 보조 수집 cron 추가:
  ```python
  self._scheduler.add_job(
      self._portal_supplement_collect,
      CronTrigger(hour=16, minute=0, timezone=tz),
      id="portal_supplement",
      misfire_grace_time=MISFIRE_GRACE_TIME,
  )
  ```
- 08:30 `premarket_retry` cron의 주석 갱신: "포털 재시도" -> "KIS 재시도"

**Step 6: 데드코드 제거**
- `_send_fallback_info_alert` 메서드 제거 (호출부가 모두 _premarket_collect에서 제거됨)
- `_send_double_failure_alert` 메서드 제거 (호출부가 모두 _premarket_collect에서 제거됨)
- `_send_recovery_info_alert` docstring 갱신: "포털 재시도" -> "KIS 재시도"
- `DataGoKrCollector` import는 유지 (`_portal_supplement_collect`에서 사용)

**Step 7: 검증**
- 검증: `docker compose exec backend python -c "from modules.collector.scheduler import CollectorScheduler; print('import OK')"`
- 예상: import OK (구문 오류 없음)

**Step 8: 커밋**
```
git add backend/modules/collector/scheduler.py
git commit -m "feat(phase6.2-sprint1): task2 -- _premarket_collect KIS 직접 호출 전환 + 16:00 포털 cron + 데드코드 제거"
```

**완료 기준:**
- ⬜ `_premarket_collect`가 KIS 직접 호출 단일 경로
- ⬜ `_premarket_retry`가 KIS 재시도
- ⬜ `_portal_supplement_collect` 16:00 cron 동작
- ⬜ `_run_kis_daily_fallback` -> `_run_kis_daily_collect` 이름 변경
- ⬜ `_send_fallback_info_alert`, `_send_double_failure_alert` 제거
- ⬜ import 오류 없음

---

### Task 3: 기존 테스트 수정 + 신규 테스트 + 통합 검증

**Files:**
- Modify: `backend/tests/test_scheduler.py` (job_count 변경: 5 -> 6, portal_supplement job 확인)
- Modify: `backend/tests/test_scheduler_retry.py` (DataGoKrCollector -> KISDailyCollector mock 전환)
- Create: `backend/tests/test_scheduler_phase62.py` (신규 — 단순화 검증 테스트)
- Verify: `backend/tests/test_scheduler_phase6.py` (기존 — 회귀 확인)
- Verify: `backend/tests/test_scheduler_integration.py` (기존 — 회귀 확인)

**Step 1: test_scheduler.py 수정**
- `test_scheduler_registers_jobs`: job_count 5 -> 6 (portal_supplement 추가)
- job_ids에 `"portal_supplement"` 포함 확인 추가
- 검증: `docker compose exec backend pytest tests/test_scheduler.py::test_scheduler_registers_jobs -v`
- 예상: PASS

**Step 2: test_scheduler_retry.py 수정**
- 기존 테스트들이 `DataGoKrCollector`를 mock하고 `validate_premarket`으로 검증하는 구조
- 변경: `_run_kis_daily_collect`를 mock하고 `validate_kis_daily`로 검증하는 구조로 전환
- 수정 대상 테스트:
  - `test_retry_skipped_when_premarket_success`: DataGoKrCollector mock 제거 -> `_run_kis_daily_collect` mock으로 변경
  - `test_retry_executes_when_premarket_failed`: DataGoKrCollector -> `_run_kis_daily_collect` mock, validate_premarket -> validate_kis_daily 검증으로 변경
  - `test_retry_portal_success_overrides_kis`: 이름 변경 (portal -> kis), DataGoKrCollector -> `_run_kis_daily_collect` mock으로 전환
- import 변경: `DataGoKrCollector` import 제거
- 검증: `docker compose exec backend pytest tests/test_scheduler_retry.py -v`
- 예상: 3 passed

**Step 3: test_scheduler_phase62.py 신규 생성**
- 테스트 1: `test_premarket_collect_calls_kis_directly` — `_premarket_collect()`가 `_run_kis_daily_collect()`를 호출하고 DataGoKrCollector를 호출하지 않는지 검증
- 테스트 2: `test_premarket_collect_success_updates_status` — KIS 수집 성공 시 premarket status="success" 확인
- 테스트 3: `test_premarket_collect_failure_updates_status` — KIS 수집 예외 시 premarket status="failed" + 알림 발송 확인
- 테스트 4: `test_portal_supplement_collect_calls_data_go_kr` — `_portal_supplement_collect()`가 DataGoKrCollector.collect_all()을 호출하는지 검증
- 테스트 5: `test_portal_supplement_collect_skips_non_trading_day` — 비거래일 스킵 확인
- 테스트 6: `test_portal_supplement_collect_failure_logs_warning` — 포털 예외 시 경고 로그만 (장애 아님)
- 테스트 7: `test_start_registers_portal_supplement_job` — start() 호출 후 portal_supplement job 등록 확인
- `_make_scheduler` 패턴은 `test_scheduler_phase6.py`에서 재사용 (ws_client.connected, set_on_ws_failure 등 포함)
- 검증: `docker compose exec backend pytest tests/test_scheduler_phase62.py -v`
- 예상: 7 passed

**Step 4: 전체 테스트 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (기존 ~798 + 신규 7 = ~805 passed)

**Step 5: 커밋**
```
git add backend/tests/test_scheduler.py backend/tests/test_scheduler_retry.py backend/tests/test_scheduler_phase62.py
git commit -m "feat(phase6.2-sprint1): task3 -- 테스트 수정 + Phase 6.2 단순화 검증 테스트 7건 추가"
```

**완료 기준:**
- ⬜ test_scheduler.py job_count=6, portal_supplement 포함
- ⬜ test_scheduler_retry.py KIS 기반으로 전환
- ⬜ test_scheduler_phase62.py 7개 테스트 PASS
- ⬜ 전체 pytest PASS

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | ~805 passed |
| import 검증 | `docker compose exec backend python -c "from modules.collector.scheduler import CollectorScheduler"` | 오류 없음 |
| 포털 코드 제거 확인 | `grep -n "DataGoKrCollector" backend/modules/collector/scheduler.py` | `_portal_supplement_collect`에서만 참조 (1곳 + import 1곳) |
| 폴백 알림 제거 확인 | `grep -n "_send_fallback_info_alert\|_send_double_failure_alert" backend/modules/collector/scheduler.py` | 0건 |
| KIS 이름 변경 확인 | `grep -n "_run_kis_daily_fallback" backend/modules/collector/scheduler.py` | 0건 |
| 16:00 cron 등록 확인 | `grep -n "portal_supplement" backend/modules/collector/scheduler.py` | add_job + 메서드 정의 (2곳+) |
