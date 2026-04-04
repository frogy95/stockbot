# Sprint 2: 재시도 스케줄 + 알림 + 모니터링 (Phase 4.8)

**Goal:** 포털 08:30 재시도, KIS 폴백 전환/이중 실패 텔레그램 알림, 데이터 cross-check 경고 로깅을 구현하여 EOD 수집 내결함성을 완성한다.

**Architecture:** 스케줄러에 08:30 재시도 CronTrigger job을 추가하고, 기존 `_send_failure_alert` 패턴을 확장하여 정보성/긴급 알림을 분리한다. validator에 cross-check 메서드를 추가하여 포털+KIS 종가 괴리를 감지한다.

**Tech Stack:** APScheduler CronTrigger, TelegramBot.send_notification, SQLAlchemy async

**Sprint 기간:** 2026-04-03 ~ 2026-04-05
**이전 스프린트:** Sprint 1 (661 passed, PR #77)
**브랜치명:** `phase4.8-sprint2`
**상태:** ✅ 완료 (2026-04-05)
**PR:** https://github.com/frogy95/stockbot/pull/78

---

## 제외 범위

- 프론트엔드 변경 없음
- DB 스키마 변경 없음 (Alembic 마이그레이션 불필요)
- 새 의존성(pip) 추가 없음
- cross-check 결과의 자동 데이터 보정 (warning 로깅만)
- 대시보드 파이프라인 상태 UI 개선 (Phase 5 이후)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | KIS 폴백 반환값 수정 + 알림 메서드 추가 | 백엔드 | -- |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | 08:30 포털 재시도 job + 재시도 성공 시 포털 우선 로직 | 백엔드 | -- |
| Task 3 | 데이터 cross-check (포털 vs KIS 종가 1% 괴리) | 백엔드 | -- |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 통합 테스트 (재시도 + 알림 + cross-check 시나리오) | 백엔드 | -- |

> **병렬 실행**: Phase 2의 Task 2, 3은 수정 파일이 겹치지 않으므로 병렬 실행 가능.

---

### Task 1: KIS 폴백 반환값 수정 + 알림 메서드 추가

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (폴백 반환값 수정, 정보성/긴급 알림 메서드 추가)
- Modify: `backend/tests/test_scheduler_telegram_alert.py` (새 알림 테스트 추가)

**Step 1: 테스트 작성**
- `backend/tests/test_scheduler_telegram_alert.py`에 다음 테스트 추가:
  - `test_kis_fallback_sends_info_alert`: 포털 실패 -> KIS 폴백 성공 시 `[정보]` 키워드 포함 텔레그램 알림 발송 확인
  - `test_double_failure_sends_critical_alert`: 포털 + KIS 모두 실패 시 `[긴급]` 키워드 포함 알림 발송 + `pipeline_healthy=false` 유지 확인
- 검증: `docker compose exec backend pytest tests/test_scheduler_telegram_alert.py -v`
- 예상: FAIL (알림 메서드 미구현)

**Step 2: 알림 메서드 구현 + 폴백 반환값 수정**
- `backend/modules/collector/scheduler.py` 수정:
  1. `_send_fallback_info_alert(step: str, portal_reason: str, kis_collected: int)` 메서드 추가 — `[정보]` 태그로 "포털 수집 실패, KIS 보조 수집 전환" 알림 (확정 파라미터 #16)
  2. `_send_double_failure_alert(step: str, portal_reason: str, kis_reason: str)` 메서드 추가 — `[긴급]` 태그로 이중 실패 알림 (확정 파라미터 #15)
  3. `_premarket_collect()` 메서드 수정:
     - KIS 폴백 성공 경로에서 `_send_fallback_info_alert()` 호출 추가
     - 이중 실패 경로에서 기존 `_send_failure_alert()` 대신 `_send_double_failure_alert()` 호출
     - (Sprint 1 이슈 #6) 폴백 성공 시 `return kis_result.collected`는 이미 정상 — 포털 실패 후 `return result.collected`에 도달하지 않도록 early return 확인
- 검증: `docker compose exec backend pytest tests/test_scheduler_telegram_alert.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler_telegram_alert.py
git commit -m "feat(phase4.8-sprint2): task1 -- KIS 폴백 알림 메서드 + 반환값 정리"
```

**완료 기준:**
- ✅ KIS 폴백 성공 시 `[정보]` 알림 발송 테스트 통과
- ✅ 이중 실패 시 `[긴급]` 알림 발송 테스트 통과
- ✅ 기존 telegram alert 테스트 3개 회귀 없음

---

### Task 2: 08:30 포털 재시도 job + 재시도 성공 시 포털 우선 로직

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (재시도 job 등록, `_premarket_retry` 메서드 추가)
- Create: `backend/tests/test_scheduler_retry.py` (재시도 로직 테스트)

**Step 1: 테스트 작성**
- `backend/tests/test_scheduler_retry.py` 생성:
  - `test_retry_job_registered`: `start()` 호출 후 `premarket_retry` job이 08:30 CronTrigger로 등록되었는지 확인
  - `test_retry_skipped_when_premarket_success`: 포털 08:00 수집 성공 (pipeline_status.premarket.status == "success") 시 재시도 스킵 확인
  - `test_retry_executes_when_premarket_failed`: 포털 08:00 실패 상태일 때 재시도 실행 -> 포털 재수집 -> 성공 시 `_update_step_status("premarket", "success")` 호출 확인
  - `test_retry_portal_success_overrides_kis`: 재시도 성공 시 포털 데이터가 우선으로 step status 업데이트 (확정 파라미터 #11)
- 검증: `docker compose exec backend pytest tests/test_scheduler_retry.py -v`
- 예상: FAIL (메서드 미구현)

**Step 2: 재시도 로직 구현**
- `backend/modules/collector/scheduler.py` 수정:
  1. `start()` 메서드에 08:30 CronTrigger job 추가:
     ```
     self._scheduler.add_job(
         self._premarket_retry,
         CronTrigger(hour=8, minute=30, timezone=tz),
         id="premarket_retry",
         misfire_grace_time=MISFIRE_GRACE_TIME,
     )
     ```
  2. `_premarket_retry()` 메서드 추가:
     - 현재 pipeline_status 조회하여 premarket.status == "success" 이면 조기 반환 (재시도 불필요)
     - 포털 재수집 실행 (`DataGoKrCollector.collect_all()`)
     - `validate_premarket()` 통과 시:
       - `_update_step_status("premarket", "success", ...)` 호출 (포털 데이터 우선, 확정 파라미터 #11)
       - 텔레그램 정보성 알림: `[복구]` 태그로 "08:30 포털 재시도 성공" 메시지
     - 실패 시: 로그만 기록 (KIS 보조 데이터가 이미 있으므로 추가 조치 불필요)
     - `_run_db_validation("premarket", "validate_premarket_db")` 실행
- 검증: `docker compose exec backend pytest tests/test_scheduler_retry.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler_retry.py
git commit -m "feat(phase4.8-sprint2): task2 -- 08:30 포털 재시도 job + 포털 우선 로직"
```

**완료 기준:**
- ✅ premarket_retry job이 08:30에 등록됨
- ✅ 포털 성공 시 재시도 스킵
- ✅ 재시도 성공 시 포털 데이터 우선으로 status 업데이트
- ✅ 재시도 실패 시 기존 KIS 보조 데이터 유지

---

### Task 3: 데이터 cross-check (포털 vs KIS 종가 1% 괴리)

**Files:**
- Modify: `backend/modules/collector/validator.py` (`cross_check_prices` 메서드 추가)
- Create: `backend/tests/test_validator_crosscheck.py` (cross-check 테스트)

**Step 1: 테스트 작성**
- `backend/tests/test_validator_crosscheck.py` 생성:
  - `test_crosscheck_no_divergence`: 포털/KIS 종가 동일 -> 빈 리스트 반환
  - `test_crosscheck_within_1pct`: 종가 차이 0.5% -> 빈 리스트 반환
  - `test_crosscheck_exceeds_1pct`: 종가 차이 2% -> 해당 종목코드 리스트 반환
  - `test_crosscheck_no_overlap`: 포털에만 있는 종목, KIS에만 있는 종목 -> 빈 리스트 (양쪽 모두 있는 종목만 비교)
- 검증: `docker compose exec backend pytest tests/test_validator_crosscheck.py -v`
- 예상: FAIL (메서드 미구현)

**Step 2: cross-check 구현**
- `backend/modules/collector/validator.py` 수정:
  - `async cross_check_prices(session: AsyncSession, data_date: date) -> list[dict]` 메서드 추가:
    - 같은 data_date에서 source="data_go_kr"인 close_price와 source="kis_daily"인 close_price를 종목코드(stock_code) 기준으로 JOIN
    - 양쪽 모두 있는 종목에서 `abs(portal_close - kis_close) / portal_close > 0.01` 인 종목 리스트 반환
    - 반환 형태: `[{"stock_code": str, "portal_close": Decimal, "kis_close": Decimal, "divergence_pct": float}]`
    - 확정 파라미터 #17: 1% 이상 괴리 시 warning 로깅
- 검증: `docker compose exec backend pytest tests/test_validator_crosscheck.py -v`
- 예상: PASS

**Step 3: 스케줄러에 cross-check 호출 연결**
- `backend/modules/collector/scheduler.py`의 `_premarket_collect()` 메서드 끝부분에 cross-check 호출 추가:
  - 포털 수집 성공 후 `cross_check_prices()` 실행
  - 재시도(`_premarket_retry`) 성공 후에도 동일하게 실행
  - 괴리 종목이 있으면 `logger.warning("데이터 cross-check 괴리 발견: %s", divergent_stocks)` 로깅
  - KIS 보조 수집만 있는 경우(포털 데이터 없음)에는 cross-check 스킵
- 검증: `docker compose exec backend pytest tests/test_validator_crosscheck.py tests/test_scheduler_retry.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/collector/validator.py backend/tests/test_validator_crosscheck.py backend/modules/collector/scheduler.py
git commit -m "feat(phase4.8-sprint2): task3 -- 데이터 cross-check 종가 1% 괴리 warning"
```

**완료 기준:**
- ✅ cross_check_prices 메서드 동작 확인
- ✅ 1% 이상 괴리 시 warning 로그 출력
- ✅ 양쪽 모두 있는 종목만 비교 (한쪽만 있으면 스킵)

---

### Task 4: 통합 테스트 (재시도 + 알림 + cross-check 시나리오)

**Files:**
- Modify: `backend/tests/test_phase4_8_integration.py` (통합 시나리오 추가)

**Step 1: 통합 테스트 추가**
- `backend/tests/test_phase4_8_integration.py`에 다음 시나리오 추가:
  - `test_portal_fail_kis_success_retry_success`: 08:00 포털 실패 -> KIS 폴백 성공([정보] 알림) -> 08:30 재시도 성공([복구] 알림) -> cross-check 실행 -> pipeline_healthy=true
  - `test_portal_fail_kis_fail_double_failure`: 08:00 포털 실패 -> KIS 폴백 실패 -> [긴급] 알림 -> pipeline_healthy=false -> 08:30 재시도도 실패 -> 상태 유지
  - `test_portal_success_no_retry_no_fallback`: 08:00 포털 정상 -> 재시도 스킵 -> cross-check 실행 -> 알림 없음 (정상 흐름)
- 검증: `docker compose exec backend pytest tests/test_phase4_8_integration.py -v`
- 예상: PASS

**Step 2: 전체 테스트 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (기존 테스트 회귀 없음)

**Step 3: 커밋**
```
git add backend/tests/test_phase4_8_integration.py
git commit -m "feat(phase4.8-sprint2): task4 -- 재시도+알림+cross-check 통합 테스트"
```

**완료 기준:**
- ✅ 3개 통합 시나리오 테스트 통과 (674 passed 전체)
- ✅ 전체 pytest 회귀 없음

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | {N+10}+ passed (기존 661 + 신규 ~10) |
| 새 테스트 파일 | `docker compose exec backend pytest tests/test_scheduler_retry.py tests/test_validator_crosscheck.py -v` | 8+ passed |
| 기존 알림 테스트 | `docker compose exec backend pytest tests/test_scheduler_telegram_alert.py -v` | 5+ passed |
| 기존 통합 테스트 | `docker compose exec backend pytest tests/test_phase4_8_integration.py -v` | 6+ passed |
| 스케줄러 job 목록 | `curl -s http://localhost:8000/api/v1/collector/status \| jq .scheduler.next_jobs` | premarket_retry job 포함 |
