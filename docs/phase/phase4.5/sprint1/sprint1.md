# Sprint 1: 백엔드 안정화 (Phase 4.5)

**Goal:** 스케줄 의존성 체인, Redis 상태 영속화, pipeline_healthy 매매 차단, 수동 파이프라인 API, 텔레그램 장애 알림으로 장전 장애 복구 체계를 확립한다.

**Architecture:** scheduler.py에 Redis 기반 파이프라인 상태 관리 레이어를 추가한다. 각 스케줄 job 시작 시 선행 단계의 Redis 상태를 확인하여 실패 시 후속을 스킵하고, 핵심 단계(premarket + primary_screen) 성공 시 pipeline_healthy 플래그를 true로 전환한다. TradingEngine은 process_screening_results 진입 시 이 플래그를 확인하여 불완전 데이터 기반 매매를 차단한다. 수동 파이프라인 API는 BackgroundTasks + 폴링 패턴으로 Railway 타임아웃을 우회한다.

**Tech Stack:** Python 3.12, FastAPI, APScheduler, Redis (redis.asyncio), pytest + pytest-asyncio

**Sprint 기간:** 2026-04-01 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 4 Sprint 2 (pytest 통과, PR #44)
**브랜치명:** `phase4.5-sprint1`

---

## 제외 범위

- ETF 시세 수집 부분 실패(11종목 KISDataError) 개선 -- 로깅만 추가, 재시도 로직은 Phase 5
- 프론트엔드 시스템 페이지 -- Sprint 2
- Alembic 마이그레이션 -- DB 스키마 변경 없음
- 스케줄러 cron 시간 변경 -- 기존 시간표 유지

## 실행 플랜

의존성 그래프: Task 1(Redis 영속화) -> Task 2(스케줄 의존성 + pipeline_healthy) -> Task 3(매매 엔진 차단) / Task 4(ETF sanity 완화) 병렬 가능 -> Task 5(health/readiness + 수동 파이프라인 API) -> Task 6(텔레그램 장애 알림) -> Task 7(통합 테스트)

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | Redis 상태 영속화 (scheduler _last_* -> Redis) | 백엔드 | -- |
| Task 2 | 스케줄 의존성 체인 + pipeline_healthy 플래그 | 백엔드 | -- |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | 매매 엔진 pipeline_healthy 차단 | 백엔드 | -- |
| Task 4 | ETF sanity check 조건부 완화 | 백엔드 | -- |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | health/readiness + 수동 파이프라인 API | 백엔드 | -- |
| Task 6 | 텔레그램 장애 알림 | 백엔드 | -- |

### Phase 4 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 7 | 통합 테스트 | 백엔드 | -- |

> **팀 실행**: Phase 2는 Task 3(engine.py)과 Task 4(kis_master.py) 파일 소유권이 겹치지 않아 병렬 실행 가능.

---

### Task 1: Redis 상태 영속화

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (CollectorScheduler.__init__, 각 _last_* 업데이트 지점, get_status)
- Test: `backend/tests/test_scheduler_redis_state.py`

**Step 1: 테스트 작성**
- `backend/tests/test_scheduler_redis_state.py` 생성
- 테스트 1: `test_init_loads_state_from_redis` -- 생성자에서 Redis에 저장된 `scheduler:last_premarket` 등의 값을 로드하는지 확인. AsyncMock redis.get()이 ISO 문자열 반환하면 _last_premarket에 datetime 설정됨
- 테스트 2: `test_premarket_saves_to_redis` -- _premarket_collect 성공 후 redis.set("scheduler:last_premarket", ..., ttl=86400)이 호출되는지 확인
- 테스트 3: `test_get_status_includes_pipeline_status` -- get_status() 반환값에 pipeline_status 키가 포함되는지 확인
- 기존 `test_scheduler.py`의 `_make_scheduler` 패턴 재사용 (AsyncMock session_factory, redis 등)
- 검증: `docker compose exec backend pytest tests/test_scheduler_redis_state.py -v`
- 예상: FAIL (메서드 미구현)

**Step 2: Redis 상태 로드/저장 구현**
- `backend/modules/collector/scheduler.py` 수정
- `__init__`에서 별도 로드 메서드를 준비하되, 실제 로드는 async이므로 `start()` 시점에서 호출
- 새 async 메서드 `_load_state_from_redis()`: Redis에서 `scheduler:last_premarket`, `scheduler:last_etf`, `scheduler:last_primary_screen`, `scheduler:last_etf_master`, `scheduler:last_dart`, `scheduler:last_sentiment` 키를 읽어 _last_* 필드에 datetime.fromisoformat()으로 복원. 키 없으면 None 유지
- 새 async 메서드 `_save_last_timestamp(job_name: str, dt: datetime)`: Redis에 `scheduler:last_{job_name}` 키로 dt.isoformat() 저장, TTL 86400
- `_premarket_collect`, `_etf_collect`, `_etf_master_collect`, `_primary_screen`, `_dart_collect`, `_sentiment_collect` 각각의 성공 경로에서 `_save_last_timestamp` 호출 추가
- `start()`의 self._scheduler.start() 직전에 `await self._load_state_from_redis()` 호출
- 검증: `docker compose exec backend pytest tests/test_scheduler_redis_state.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler_redis_state.py
git commit -m "feat(phase4.5-sprint1): task1 -- Redis 상태 영속화 (scheduler _last_* -> Redis TTL 86400)"
```

**완료 기준:**
- ⬜ _last_* 값이 Redis에 저장/복원됨
- ⬜ TTL 86400 설정됨
- ⬜ 기존 test_scheduler.py 테스트 회귀 없음

---

### Task 2: 스케줄 의존성 체인 + pipeline_healthy 플래그

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (각 스케줄 job에 선행 가드 추가, pipeline_status JSON 관리, pipeline_healthy 플래그)
- Test: `backend/tests/test_scheduler_dependency.py`

**Step 1: 테스트 작성**
- `backend/tests/test_scheduler_dependency.py` 생성
- 테스트 1: `test_primary_screen_skips_when_premarket_failed` -- premarket 상태가 "failed"이면 _primary_screen이 실행되지 않고 "skipped" 반환
- 테스트 2: `test_dart_skips_when_primary_screen_failed` -- primary_screen 상태가 "failed"이면 _dart_collect가 스킵
- 테스트 3: `test_sentiment_skips_when_primary_screen_failed`
- 테스트 4: `test_etf_skips_when_etf_master_failed` -- etf_master 상태가 "failed"이면 _etf_collect가 스킵
- 테스트 5: `test_pipeline_healthy_true_when_core_succeed` -- premarket + primary_screen 모두 "success"이면 pipeline_healthy가 "true"
- 테스트 6: `test_pipeline_healthy_false_on_init` -- 08:00 premarket 시작 시 pipeline_healthy가 "false"로 초기화
- 테스트 7: `test_get_pipeline_status` -- scheduler.get_pipeline_status() 반환 JSON 구조 검증
- Redis mock: AsyncMock의 get/set을 사용하여 pipeline_status JSON과 pipeline_healthy 값 검증
- 검증: `docker compose exec backend pytest tests/test_scheduler_dependency.py -v`
- 예상: FAIL

**Step 2: 파이프라인 상태 관리 구현**
- `backend/modules/collector/scheduler.py` 수정
- 상수 추가: `PIPELINE_STATUS_KEY = "scheduler:pipeline_status"`, `PIPELINE_HEALTHY_KEY = "scheduler:pipeline_healthy"`, `STATE_TTL = 86400`
- 의존성 맵 상수:
  ```
  DEPENDENCY_MAP = {
      "primary_screen": ["premarket"],
      "etf": ["etf_master"],
      "dart": ["primary_screen"],
      "sentiment": ["primary_screen"],
  }
  CORE_STEPS = ["premarket", "primary_screen"]
  ```
- 새 async 메서드 `_get_pipeline_status() -> dict`: Redis에서 PIPELINE_STATUS_KEY를 읽어 dict 반환. 없으면 빈 dict
- 새 async 메서드 `_update_step_status(step: str, status: str, error: str | None = None)`: pipeline_status JSON을 읽고 해당 step을 업데이트, Redis에 저장. status가 "success"이고 모든 CORE_STEPS가 "success"이면 pipeline_healthy를 "true"로 설정
- 새 async 메서드 `_check_dependency(step: str) -> bool`: DEPENDENCY_MAP에서 선행 단계를 확인, 모든 선행이 "success"이면 True
- 새 공개 메서드 `get_pipeline_status() -> dict`: _get_pipeline_status 래퍼 (API 노출용)
- `_premarket_collect` 수정: 시작 시 pipeline_healthy를 "false"로 초기화 + pipeline_status를 전체 초기화 (모든 step을 "pending"으로). 성공 시 `_update_step_status("premarket", "success")`, 실패 시 `_update_step_status("premarket", "failed", error=str(e))`
- `_primary_screen` 수정: 시작 시 `_check_dependency("primary_screen")` 확인, False이면 `_update_step_status("primary_screen", "skipped")` 후 조기 반환. 성공/실패 시 _update_step_status 호출
- `_etf_master_collect`, `_etf_collect`, `_dart_collect`, `_sentiment_collect` 동일 패턴 적용 (etf_master는 선행 없으므로 가드 없이 상태만 기록)
- 검증: `docker compose exec backend pytest tests/test_scheduler_dependency.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler_dependency.py
git commit -m "feat(phase4.5-sprint1): task2 -- 스케줄 의존성 체인 + pipeline_healthy 플래그"
```

**완료 기준:**
- ⬜ 선행 실패 시 후속 job 자동 스킵 + "skipped" 상태 기록
- ⬜ premarket + primary_screen 성공 시 pipeline_healthy = "true"
- ⬜ 매일 08:00 premarket 시작 시 pipeline_healthy = "false"로 초기화
- ⬜ pipeline_status JSON 구조: `{step: {status, timestamp, error}}`
- ⬜ 기존 test_scheduler.py 회귀 없음

---

### Task 3: 매매 엔진 pipeline_healthy 차단

**Files:**
- Modify: `backend/modules/trading/engine.py` (process_screening_results에 가드 추가)
- Test: `backend/tests/test_pipeline_health.py`

**Step 1: 테스트 작성**
- `backend/tests/test_pipeline_health.py` 생성
- 테스트 1: `test_engine_blocks_when_pipeline_unhealthy` -- redis.get("scheduler:pipeline_healthy") 반환값이 None 또는 "false"이면 process_screening_results가 신호 생성 없이 조기 반환
- 테스트 2: `test_engine_proceeds_when_pipeline_healthy` -- redis.get 반환값이 "true"이면 정상 진행 (signal_generator.generate_signals 호출됨)
- TradingEngine 생성에 필요한 mock들: signal_generator(AsyncMock), order_manager(AsyncMock, start/stop/get_queue_size), position_manager(AsyncMock), risk_manager(AsyncMock), position_sizer(AsyncMock), eod_liquidator(MagicMock, is_entry_blocked=False), redis_client(AsyncMock)
- 검증: `docker compose exec backend pytest tests/test_pipeline_health.py -v`
- 예상: FAIL

**Step 2: 가드 구현**
- `backend/modules/trading/engine.py` 수정
- `process_screening_results` 메서드 시작부에 추가 (eod_liquidator 체크 직전):
  - `pipeline_healthy = await self._redis.get("scheduler:pipeline_healthy")`
  - `pipeline_healthy != "true"`이면 `logger.warning("pipeline_healthy=false -- 신호 처리 차단")` 후 return
- 검증: `docker compose exec backend pytest tests/test_pipeline_health.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/trading/engine.py backend/tests/test_pipeline_health.py
git commit -m "feat(phase4.5-sprint1): task3 -- 매매 엔진 pipeline_healthy 차단"
```

**완료 기준:**
- ⬜ pipeline_healthy != "true" 시 신호 처리 스킵
- ⬜ 차단 시 경고 로그 출력

---

### Task 4: ETF sanity check 조건부 완화

**Files:**
- Modify: `backend/modules/collector/sources/kis_master.py` (sanity_check 메서드)
- Test: `backend/tests/test_kis_master.py` (기존 파일에 테스트 추가)

**Step 1: 기존 테스트 확인 + 추가 테스트 작성**
- `backend/tests/test_kis_master.py`에 테스트 추가
- 테스트 1: `test_sanity_check_skips_variation_when_prev_low` -- prev_count=277 (< 200이 아님, 200 이상이므로 +-30% 적용)... 수정: Phase 문서 확인 -- `prev_count < 200`이면 변동률 검증 스킵. prev_count=150이면 변동률 검증 스킵하고 spot-check만 수행
- 테스트 2: `test_sanity_check_allows_30pct_variation` -- prev_count=800, cur_count=600 (25% 감소, +-30% 이내) -> True
- 테스트 3: `test_sanity_check_blocks_over_30pct_variation` -- prev_count=800, cur_count=500 (37.5% 감소, +-30% 초과) -> False
- 테스트 4: `test_sanity_check_prev_277_cur_878` -- 실제 장애 케이스: prev=277, cur=878. prev >= 200이므로 변동률 계산 -> 216% 변동 -> False (이 경우는 seed->mst 전환이므로 별도 대응 필요). 다시 확인: phase4.5.md에서 "prev < 200이면 변동률 검증 스킵". prev=277은 200 이상이므로 변동률 검증 적용, +-30% 초과하여 실패 -> 이 경우 최초 seed 데이터가 277인 것이 문제. 해결: prev_count가 None이거나 < 200이면 스킵. 실제 장애(prev=277)는 seed 데이터라서 정확하지 않을 수 있으므로, Phase 문서의 +-30% 기준이 해결해야 함. phase4.5.md 원문: "prev < 200이면 변동률 검증 스킵". 277은 >= 200이므로 변동률 검증 적용, 하지만 878과의 차이(216%)는 +-30% 초과 -> sanity 실패. 다만 이 상황은 "seed에서 mst로 전환된 최초 1회"에만 발생하고, 이후에는 prev=878에서 시작하므로 문제없음. 즉 최초 1회는 수동 트리거(Task 5)로 해결.
- 검증: `docker compose exec backend pytest tests/test_kis_master.py -v`
- 예상: FAIL (기존 +-10% 기준이라서 test_allows_30pct 실패)

**Step 2: sanity_check 수정**
- `backend/modules/collector/sources/kis_master.py`의 `sanity_check` 메서드 수정
- 기존 코드:
  ```python
  if prev_count and prev_count > 0:
      delta = abs(count - prev_count) / prev_count
      if delta > 0.10:
  ```
- 변경:
  ```python
  if prev_count is not None and prev_count >= 200:
      delta = abs(count - prev_count) / prev_count
      if delta > 0.30:
  ```
- `prev_count`가 None이거나 200 미만이면 변동률 검증 스킵 (spot-check + 최소 200종목 조건만 적용)
- docstring 업데이트: "최소 200종목, spot-check 5종목, prev >= 200일 때 전일 대비 +-30% 이내"
- 검증: `docker compose exec backend pytest tests/test_kis_master.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/kis_master.py backend/tests/test_kis_master.py
git commit -m "feat(phase4.5-sprint1): task4 -- ETF sanity check 조건부 완화 (prev<200 스킵, +-30%)"
```

**완료 기준:**
- ⬜ prev_count < 200이면 변동률 검증 스킵
- ⬜ prev_count >= 200이면 +-30% 허용
- ⬜ 기존 sanity_check 테스트 회귀 없음

---

### Task 5: health/readiness + 수동 파이프라인 API

**Files:**
- Modify: `backend/api/routes/health.py` (GET /health/readiness 추가)
- Modify: `backend/api/routes/collector.py` (POST /collector/trigger/premarket-pipeline, GET /collector/pipeline-status 추가)
- Modify: `backend/modules/collector/scheduler.py` (run_premarket_pipeline 오케스트레이터 메서드 추가)
- Test: `backend/tests/test_health_readiness.py`
- Test: `backend/tests/test_pipeline_api.py`

**Step 1: 테스트 작성**
- `backend/tests/test_health_readiness.py` 생성
  - 테스트 1: `test_readiness_healthy` -- DB+Redis+스케줄러+pipeline_healthy 모두 정상이면 200 + "ready"
  - 테스트 2: `test_readiness_unhealthy_pipeline` -- pipeline_healthy가 "false"이면 503
- `backend/tests/test_pipeline_api.py` 생성
  - 테스트 1: `test_pipeline_status_endpoint` -- GET /api/v1/collector/pipeline-status가 pipeline_status JSON 반환
  - 테스트 2: `test_trigger_premarket_pipeline` -- POST /api/v1/collector/trigger/premarket-pipeline이 BackgroundTasks로 실행
  - 테스트 3: `test_trigger_pipeline_rejects_duplicate` -- 파이프라인 실행 중 중복 요청 시 409 반환
- 검증: `docker compose exec backend pytest tests/test_health_readiness.py tests/test_pipeline_api.py -v`
- 예상: FAIL

**Step 2: health/readiness 엔드포인트 구현**
- `backend/api/routes/health.py` 수정
- 새 엔드포인트 `GET /health/readiness`:
  - 기존 health_check()의 DB+Redis 확인 로직 재활용
  - 추가: `request.app.state.collector_scheduler`의 `_running` 확인
  - 추가: Redis에서 `scheduler:pipeline_healthy` 값 확인
  - 4가지 모두 정상이면 200 `{"status": "ready", ...}`, 하나라도 실패 시 503
- `router`에 Request 의존성 추가 (기존 health에는 없음 -- readiness에만 Request 파라미터 추가)
- 검증: `docker compose exec backend pytest tests/test_health_readiness.py -v`
- 예상: PASS

**Step 3: 수동 파이프라인 오케스트레이터 구현**
- `backend/modules/collector/scheduler.py` 수정
- 새 async 메서드 `run_premarket_pipeline() -> dict`:
  - Redis 락 `scheduler:pipeline_running` 확인, 이미 "true"이면 예외 발생 (중복 방지)
  - 락 설정 (TTL 600초, 10분 타임아웃)
  - pipeline_status 전체 초기화 + pipeline_healthy = "false"
  - 순차 실행: premarket -> etf_master -> primary_screen -> etf -> dart -> sentiment
  - 각 단계 실행 후 _update_step_status 호출, 실패 시 의존 단계 "skipped"로 설정하고 계속 (독립 단계는 실행)
  - 완료 후 락 해제
  - 반환: `{"completed": True, "pipeline_status": {...}}`
- 검증: `docker compose exec backend pytest tests/test_pipeline_api.py -v`
- 예상: PASS (일부)

**Step 4: API 엔드포인트 구현**
- `backend/api/routes/collector.py` 수정
- 새 엔드포인트 `GET /collector/pipeline-status`:
  - scheduler.get_pipeline_status() 호출 + pipeline_healthy 값 함께 반환
- 새 엔드포인트 `POST /collector/trigger/premarket-pipeline`:
  - 파이프라인 실행 중 확인 (Redis `scheduler:pipeline_running`), 실행 중이면 409
  - BackgroundTasks에 scheduler.run_premarket_pipeline 등록
  - 즉시 반환: `{"triggered": True, "message": "파이프라인 시작됨. GET /api/v1/collector/pipeline-status 에서 확인"}`
- 검증: `docker compose exec backend pytest tests/test_pipeline_api.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/api/routes/health.py backend/api/routes/collector.py backend/modules/collector/scheduler.py backend/tests/test_health_readiness.py backend/tests/test_pipeline_api.py
git commit -m "feat(phase4.5-sprint1): task5 -- health/readiness + 수동 파이프라인 API"
```

**완료 기준:**
- ⬜ GET /health/readiness가 DB+Redis+스케줄러+pipeline 상태 포함
- ⬜ POST /collector/trigger/premarket-pipeline이 BackgroundTasks로 비동기 실행
- ⬜ GET /collector/pipeline-status가 단계별 상태 JSON 반환
- ⬜ 중복 실행 방지 (Redis 락)

---

### Task 6: 텔레그램 장애 알림

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (파이프라인 단계 실패/복구 시 텔레그램 알림)
- Test: `backend/tests/test_scheduler_telegram_alert.py`

**Step 1: 테스트 작성**
- `backend/tests/test_scheduler_telegram_alert.py` 생성
- 테스트 1: `test_premarket_failure_sends_telegram` -- _premarket_collect 실패 시 telegram_bot.send_notification 호출됨, 메시지에 "[장애]" + "premarket" + "수동 복구" 문구 포함
- 테스트 2: `test_pipeline_recovery_success_sends_telegram` -- run_premarket_pipeline 성공 완료 시 "[복구 완료]" 메시지 발송
- 테스트 3: `test_no_telegram_when_bot_not_set` -- _telegram_bot이 None이면 에러 없이 스킵
- scheduler._telegram_bot = AsyncMock(send_notification=AsyncMock()) 패턴
- 검증: `docker compose exec backend pytest tests/test_scheduler_telegram_alert.py -v`
- 예상: FAIL

**Step 2: 텔레그램 알림 구현**
- `backend/modules/collector/scheduler.py` 수정
- 새 async 메서드 `_send_failure_alert(step: str, error: str)`:
  - self._telegram_bot이 None이면 return
  - 메시지: `"<b>[장애]</b> {step} 실패\n에러: {error[:200]}\n수동 복구: POST /api/v1/collector/trigger/premarket-pipeline"`
  - `await self._telegram_bot.send_notification(msg)`
- 새 async 메서드 `_send_recovery_alert(success: bool)`:
  - self._telegram_bot이 None이면 return
  - 성공: `"<b>[복구 완료]</b> 장전 파이프라인 정상 복구"`
  - 실패: `"<b>[복구 실패]</b> 장전 파이프라인 일부 실패 -- 수동 확인 필요"`
- `_premarket_collect`, `_primary_screen` 등 핵심 단계의 except 블록에 `_send_failure_alert` 호출 추가
- `run_premarket_pipeline` 완료 시 `_send_recovery_alert` 호출
- 검증: `docker compose exec backend pytest tests/test_scheduler_telegram_alert.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler_telegram_alert.py
git commit -m "feat(phase4.5-sprint1): task6 -- 텔레그램 장애 알림 (실패/복구)"
```

**완료 기준:**
- ⬜ 파이프라인 단계 실패 시 텔레그램 알림 발송
- ⬜ 수동 복구 성공/실패 시 결과 알림 발송
- ⬜ telegram_bot 미설정 시 에러 없이 스킵

---

### Task 7: 통합 테스트 + 기존 테스트 회귀 확인

**Files:**
- Test: `backend/tests/test_scheduler_integration.py`

**Step 1: 통합 테스트 작성**
- `backend/tests/test_scheduler_integration.py` 생성
- 테스트 1: `test_full_pipeline_success_flow` -- premarket 성공 -> etf_master 성공 -> primary_screen 성공 -> etf 성공 -> dart 성공 -> sentiment 성공 -> pipeline_healthy = "true" 확인. 모든 step의 status가 "success"
- 테스트 2: `test_premarket_failure_cascades` -- premarket 실패 -> primary_screen "skipped" -> dart "skipped" -> sentiment "skipped" -> etf_master 독립 실행 가능 -> pipeline_healthy = "false"
- 테스트 3: `test_manual_pipeline_recovers` -- premarket 실패 후 run_premarket_pipeline 호출 -> 모든 단계 성공 -> pipeline_healthy = "true" 복원
- mock 패턴: DataGoKrCollector, KISMasterCollector, KISCollector 등을 patch하여 성공/실패 시나리오 구성
- Redis mock은 dict 기반 FakeRedis 구현 (get/set/delete를 dict로 구현한 간이 mock)
- 검증: `docker compose exec backend pytest tests/test_scheduler_integration.py -v`
- 예상: PASS

**Step 2: 전체 회귀 테스트**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (기존 test_scheduler.py 포함)

**Step 3: 커밋**
```
git add backend/tests/test_scheduler_integration.py
git commit -m "feat(phase4.5-sprint1): task7 -- 통합 테스트 (파이프라인 성공/실패/복구 시나리오)"
```

**완료 기준:**
- ⬜ 전체 파이프라인 성공/실패/복구 3가지 시나리오 테스트 통과
- ⬜ 기존 전체 pytest 회귀 없음

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 passed, 0 failed |
| 새 테스트만 | `docker compose exec backend pytest tests/test_scheduler_redis_state.py tests/test_scheduler_dependency.py tests/test_pipeline_health.py tests/test_health_readiness.py tests/test_pipeline_api.py tests/test_scheduler_telegram_alert.py tests/test_scheduler_integration.py -v` | 전체 passed |
| health/readiness | `curl -s http://localhost:8000/api/v1/health/readiness \| jq .` | `{"status": "ready", ...}` 또는 503 |
| pipeline-status | `curl -s http://localhost:8000/api/v1/collector/pipeline-status \| jq .` | `{"pipeline_status": {...}, "pipeline_healthy": "..."}` |
| 수동 파이프라인 | `curl -s -X POST http://localhost:8000/api/v1/collector/trigger/premarket-pipeline \| jq .` | `{"triggered": true, ...}` |
