# Sprint 2: 복원력 강화 + 불필요 실행 방지 (Phase 6)

**Goal:** KIS REST 500 에러 재시도/백오프, recovery 단계적 재시도(09:05/09:10/09:15), premarket 예외 경로 KIS 폴백, 나머지 핸들러 is_trading_day 가드 추가.

**Sprint 기간:** 2026-04-12 ~ 2026-04-12
**상태:** ✅ 완료
**브랜치명:** `phase6-sprint1` (Sprint 1과 동일 브랜치에서 연속 구현)

---

## 완료된 작업

### Task 1: KIS REST 재시도/백오프
- `kis_daily_collector.py`: `_fetch_with_retry()` 메서드 추가
- HTTP 500/502/503/429 시 지수 백오프 재시도 (최대 3회, 2-4-8초)
- HTTP 400/401/403 등은 즉시 실패 (재시도 무의미)
- 테스트 3건: `test_kis_daily_collector_retries_on_500`, `test_kis_daily_collector_retries_on_429`, `test_kis_daily_collector_no_retry_on_400`

### Task 2: recovery 단계적 재시도
- `scheduler.py`: `_market_open_recovery()` 09:05/09:10/09:15 단계적 재시도 (5분 간격, 최대 3회)
- 3회 모두 실패 시 `[긴급]` 텔레그램 알림
- `is_trading_day()` 가드 추가
- 테스트 4건: `test_recovery_three_stage_retry`, `test_recovery_skips_if_connected`, `test_recovery_succeeds_on_second_attempt`, `test_recovery_final_failure_alert`

### Task 3: premarket 예외 경로 KIS 폴백
- `scheduler.py`: `_premarket_collect()` except 블록에서 `_run_kis_daily_fallback()` 시도
- KIS 폴백 성공 시 `[정보]` 알림, KIS 폴백도 실패 시 `[긴급]` 이중 실패 알림
- 테스트 1건: `test_premarket_exception_triggers_kis_fallback`

### Task 4: 나머지 핸들러 is_trading_day 가드
- `_market_close()`, `_premarket_retry()` 에 `is_trading_day()` 가드 추가
- 테스트 2건: `test_market_close_skips_non_trading_day`, `test_premarket_retry_skips_non_trading_day`

## 검증 결과

- 신규 테스트 10건 PASS
- 기존 테스트 회귀 수정 7건 (is_trading_day 패치 추가)
- 전체 771 passed, 0 failed
