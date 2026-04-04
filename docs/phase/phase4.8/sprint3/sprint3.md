# Sprint 3: 장전 파이프라인 체인 구조 전환 (Phase 4.8)

**Goal:** 고정 시각 독립 CronTrigger 6개를 08:00 단일 체인 파이프라인으로 전환하여 KIS 폴백 수집 시 primary_screen 스킵 문제를 근본적으로 해소한다.

**Architecture:** 기존 `run_premarket_pipeline()` 체인 메서드를 그대로 활용하되, 08:00 CronTrigger에 락 선점 래퍼(`_run_scheduled_pipeline`)를 등록하고 개별 장전 job 6개를 제거한다. 수동 트리거 API와 08:30 재시도 job은 유지한다.

**Tech Stack:** APScheduler CronTrigger, Redis 락

**Sprint 기간:** 2026-04-05 ~ (사용자 검토 후 구현)
**이전 스프린트:** Sprint 2 (674 passed, PR #78)
**브랜치명:** `phase4.8-sprint3`

---

## 제외 범위

- 개별 수동 트리거 API 변경 (`trigger_premarket`, `trigger_etf` 등 유지)
- `run_premarket_pipeline()` 메서드 로직 변경 (기존 체인 순서 그대로)
- `_premarket_retry` job 구조 변경 (08:30 독립 실행 유지)
- `secondary_screen` IntervalTrigger 변경 (30초 주기 유지)
- 프론트엔드 변경 (없음)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | `_run_scheduled_pipeline()` 래퍼 + `start()` 리팩토링 | 백엔드 | -- |
| Task 2 | 기존 테스트 수정 + 체인 파이프라인 테스트 신규 | 백엔드 | -- |
| Task 3 | 통합 검증 + 회귀 테스트 | 백엔드 | -- |

> 단일 파일(scheduler.py) 중심 변경이므로 순차 실행만 가능.

---

### Task 1: `_run_scheduled_pipeline()` 래퍼 + `start()` 리팩토링

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (`_run_scheduled_pipeline()` 메서드 추가, `start()` 장전 job 6개 제거 + 단일 체인 job 등록)

**Step 1: `_run_scheduled_pipeline()` 래퍼 메서드 추가**

`run_premarket_pipeline()` 바로 위에 새 메서드를 추가한다:
- 메서드명: `_run_scheduled_pipeline(self) -> None`
- 동작:
  1. `PIPELINE_RUNNING_KEY` Redis 키 조회 (`await self._redis.get(PIPELINE_RUNNING_KEY)`)
  2. 이미 존재하면 `logger.warning("파이프라인 이미 실행 중 -- 자동 스케줄 스킵")` 후 return
  3. 락 선점: `await self._redis.set(PIPELINE_RUNNING_KEY, "auto", ttl=STATE_TTL)`
  4. 파이프라인 시작 시각 로깅: `logger.info("장전 파이프라인 시작 (자동 스케줄)")`
  5. `await self.run_premarket_pipeline()` 호출
  6. 파이프라인 종료 시각 + 소요 시간 로깅 (try/finally로 시작/종료 시각 차이 계산)
- 주의: `run_premarket_pipeline()` 내부의 `finally` 블록이 이미 `PIPELINE_RUNNING_KEY` 삭제를 담당하므로 래퍼에서 중복 삭제하지 않는다.

**Step 2: `start()` 메서드 리팩토링**

현재 `start()` (L295~375)에서 다음 6개 job 등록을 **제거**한다:
- `premarket_collect` (08:00) -- L299~304
- `etf_master_collect` (08:10) -- L305~309
- `etf_collect` (08:15) -- L311~315
- `primary_screen` (08:10, `if self._primary_screener:` 블록) -- L336~342
- `dart_collect` (08:15) -- L344~348
- `sentiment_collect` (08:20) -- L350~354

다음 1개 job을 **추가**한다:
```python
self._scheduler.add_job(
    self._run_scheduled_pipeline,
    CronTrigger(hour=8, minute=0, timezone=tz),
    id="premarket_pipeline",
    misfire_grace_time=MISFIRE_GRACE_TIME,
)
```

다음 5개 job은 **유지**한다 (변경 없음):
- `market_open` (09:00)
- `market_close` (15:30)
- `market_open_recovery` (09:05)
- `premarket_retry` (08:30)
- `secondary_screen` (30초 주기, `if self._realtime_screener:` 블록)

**Step 3: 검증**

```bash
docker compose exec backend python -c "from modules.collector.scheduler import CollectorScheduler; print('import OK')"
```
- 예상: `import OK` (문법 오류 없음)

**Step 4: 커밋**

```
git add backend/modules/collector/scheduler.py
git commit -m "feat(phase4.8-sprint3): task1 -- 장전 파이프라인 체인 구조 전환 (래퍼 추가 + start 리팩토링)"
```

**완료 기준:**
- ⬜ `_run_scheduled_pipeline()` 래퍼 메서드가 락 선점 + 체인 호출 + 시간 로깅을 수행
- ⬜ `start()`에서 장전 CronTrigger 6개 제거, `premarket_pipeline` 1개 등록
- ⬜ 유지 대상 job 5개 (`market_open`, `market_close`, `market_open_recovery`, `premarket_retry`, `secondary_screen`) 영향 없음

---

### Task 2: 기존 테스트 수정 + 체인 파이프라인 테스트 신규

**Files:**
- Modify: `backend/tests/test_scheduler.py` (job 등록 검증 테스트 수정)
- Create: `backend/tests/test_pipeline_chain.py` (체인 파이프라인 동작 검증)

**Step 1: `test_scheduler.py` job 등록 테스트 수정**

`test_scheduler_registers_jobs()` (L44~63) 수정:
- 기존: `job_count == 9`, `"premarket_collect" in job_ids` 등 6개 개별 job 검증
- 변경 후: 
  - job_count 값을 새 구조에 맞게 조정 (기존 9개에서 개별 장전 6개 제거 + 체인 1개 추가 = 4개. screener 미설정 상태이므로 premarket_pipeline, market_open, market_close, market_open_recovery, premarket_retry = 5개. 단, secondary_screen은 `if self._realtime_screener:` 가드로 미등록)
  - `assert "premarket_pipeline" in job_ids`
  - 제거된 job ID가 없는지 확인: `assert "premarket_collect" not in job_ids`, `assert "etf_master_collect" not in job_ids`, `assert "primary_screen" not in job_ids`, `assert "etf_collect" not in job_ids`, `assert "dart_collect" not in job_ids`, `assert "sentiment_collect" not in job_ids`
  - `assert "premarket_retry" in job_ids` (유지 확인)
  - `assert "market_open" in job_ids` (유지 확인)

**Step 2: `test_pipeline_chain.py` 신규 테스트 작성**

`backend/tests/test_pipeline_chain.py` 생성. 기존 `test_scheduler.py`의 `_make_scheduler()` 패턴과 `test_scheduler_integration.py`의 FakeRedis 패턴을 참고한다.

테스트 케이스 4건:
1. **`test_chain_pipeline_registered_at_0800`**: `start()` 호출 후 `premarket_pipeline` job이 등록되고, 개별 장전 job(premarket_collect, etf_master_collect 등)이 없는지 확인
2. **`test_run_scheduled_pipeline_acquires_lock`**: `_run_scheduled_pipeline()` 호출 시 `PIPELINE_RUNNING_KEY`에 "auto" 값이 설정되고, `run_premarket_pipeline()`이 호출되는지 확인. FakeRedis 사용.
3. **`test_run_scheduled_pipeline_skips_when_locked`**: `PIPELINE_RUNNING_KEY`가 이미 존재할 때 `_run_scheduled_pipeline()` 호출 시 `run_premarket_pipeline()`이 호출되지 않는지 확인
4. **`test_chain_pipeline_logs_duration`**: `_run_scheduled_pipeline()` 호출 후 소요 시간 로깅이 출력되는지 확인 (caplog 사용)

**Step 3: 검증**

```bash
docker compose exec backend pytest tests/test_scheduler.py tests/test_pipeline_chain.py -v
```
- 예상: 기존 test_scheduler 테스트 + 신규 4건 모두 PASS

**Step 4: 커밋**

```
git add backend/tests/test_scheduler.py backend/tests/test_pipeline_chain.py
git commit -m "feat(phase4.8-sprint3): task2 -- job 등록 테스트 수정 + 체인 파이프라인 테스트 추가"
```

**완료 기준:**
- ⬜ `test_scheduler_registers_jobs()` 새 job 구조 반영
- ⬜ `test_pipeline_chain.py` 4건 PASS (등록/락 선점/락 충돌/시간 로깅)

---

### Task 3: 통합 검증 + 회귀 테스트

**Files:**
- 변경 없음 (전체 테스트 실행으로 회귀 확인)

**Step 1: 전체 pytest 실행**

```bash
docker compose exec backend pytest -v
```
- 예상: 674+ tests passed (Sprint 2 기준 674개 + Task 2 신규 4건)
- 주의: `test_scheduler_integration.py`의 기존 테스트는 개별 메서드(`_premarket_collect`, `_primary_screen` 등)를 직접 호출하므로 체인 구조와 무관하게 정상 동작해야 한다. 만약 실패하면 원인 분석 후 수정.

**Step 2: 기존 통합 테스트 확인**

```bash
docker compose exec backend pytest tests/test_scheduler_integration.py tests/test_pipeline_api.py tests/test_pipeline_health.py -v
```
- 예상: 모두 PASS (개별 메서드 호출 테스트는 CronTrigger 변경에 영향 없음)

**Step 3: 커밋 (필요 시)**

테스트 실패로 수정한 파일이 있으면 커밋:
```
git add [수정된 파일들]
git commit -m "fix(phase4.8-sprint3): task3 -- 테스트 회귀 수정"
```

회귀 없이 전체 통과하면 커밋 불필요.

**완료 기준:**
- ⬜ 전체 pytest 통과 (회귀 없음)
- ⬜ 스케줄러 관련 통합 테스트 전체 통과

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 678+ passed (674 + 4 신규) |
| 체인 파이프라인 테스트 | `docker compose exec backend pytest tests/test_pipeline_chain.py -v` | 4 passed |
| 스케줄러 기본 테스트 | `docker compose exec backend pytest tests/test_scheduler.py -v` | 기존 건수 passed |
| 통합 테스트 | `docker compose exec backend pytest tests/test_scheduler_integration.py -v` | 기존 건수 passed |
| 재시도 테스트 유지 | `docker compose exec backend pytest tests/test_scheduler_retry.py -v` | 기존 건수 passed |
| 알림 테스트 유지 | `docker compose exec backend pytest tests/test_scheduler_telegram_alert.py -v` | 기존 건수 passed |
