# Sprint 1: 근본 수리 + KIS 도메인 분리 + 유효성 검증 (Phase 4.6)

**Goal:** 데이터 수집 파이프라인의 근본 원인 7건을 해결하고, CollectionResult/CollectionValidator 체계를 구축하여 0건 수집이 success로 기록되는 거짓 양성을 제거한다.

**Architecture:** Dockerfile --reload 제거로 프로덕션 안정화, KIS inquiry_client(LIVE)/trading_client(TRADING_ENV) 이중 구조로 도메인 분리, CollectionResult dataclass + CollectionValidator 클래스로 수집 유효성 검증을 수집기와 분리. 각 수집기가 CollectionResult를 반환하면 scheduler가 CollectionValidator로 검증 후 pipeline_status에 validation dict를 포함시킨다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Redis 7, APScheduler, httpx, pytest

**Sprint 기간:** 2026-04-02 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 4.5 Sprint 1 (pytest passed, PR #57 develop merge 완료)
**브랜치명:** `phase4.6-sprint1`

---

## 제외 범위

- 한국거래소 휴장일 캘린더 (Sprint 2)
- DB 후검증 쿼리 (Sprint 2)
- market_data 신선도 검증 (Sprint 2)
- 수집 결과 상세 로깅 강화 (Sprint 2)
- 통합 검증 자동화 (Sprint 2)
- ETN 시세 수집 (Phase 5)
- 프론트엔드 변경 없음

## 실행 플랜

### Phase 1 (순차 — 인프라 + 기반)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | Dockerfile --reload 제거 + docker-compose 개발 override | 인프라 | -- |
| Task 2 | KIS 조회/매매 도메인 분리 (kis_config + main.py) | 백엔드 | `feature-dev:feature-dev` |
| Task 3 | CollectionResult + ValidationResult + CollectionValidator 도입 | 백엔드 | -- |

### Phase 2 (병렬 가능 — 수집기별 독립 작업)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | data_go_kr 수집기 개선 (CollectionResult + 날짜 폴백 + updated_at + null 카운팅) | 백엔드 | -- |
| Task 5 | kis_collector 수집기 개선 (CollectionResult + inquiry_client + 실패 추적) | 백엔드 | -- |
| Task 6 | dart + naver 수집기 개선 (CollectionResult + MAX_FINANCIAL_QUERIES 제거) | 백엔드 | -- |

### Phase 3 (순차 — 통합)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 7 | scheduler.py 통합 (CollectionValidator 호출 + pipeline_healthy 강화 + 실패 구조화) | 백엔드 | `feature-dev:feature-dev` |
| Task 8 | 통합 테스트 + 기존 테스트 수정 | 백엔드 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 Task 4/5/6을 병렬 구현합니다. 각 Task가 수정하는 파일이 겹치지 않습니다.

---

### Task 1: Dockerfile --reload 제거 + docker-compose 개발 override

**Files:**
- Modify: `backend/Dockerfile` (CMD에서 --reload 제거)
- Modify: `docker-compose.yml` (backend 서비스에 command override 추가)

**Step 1: Dockerfile CMD 수정**
- `backend/Dockerfile` 수정
- 기존: `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]`
- 변경: `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]`
- WatchFiles 무한 재시작 루프의 근본 원인 제거
- 검증: `grep -q "reload" backend/Dockerfile && echo "FAIL: --reload 잔존" || echo "PASS"`
- 예상: PASS

**Step 2: docker-compose.yml 개발 override 추가**
- `docker-compose.yml`의 backend 서비스에 command 필드 추가
- `command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]`
- 로컬 개발에서는 docker-compose.yml의 command가 Dockerfile CMD를 오버라이드하여 --reload 유지
- Railway 프로덕션에서는 Dockerfile CMD만 사용 (command 오버라이드 없음)
- 검증: `docker compose config | grep -A5 "backend:" | grep "command"`
- 예상: command에 --reload 포함 확인

**Step 3: 커밋**
```
git add backend/Dockerfile docker-compose.yml
git commit -m "feat(phase4.6-sprint1): task1 -- Dockerfile --reload 제거 + 개발 override"
```

**완료 기준:**
- ⬜ Dockerfile CMD에 --reload 없음
- ⬜ docker-compose.yml에서 개발용 --reload override 존재
- ⬜ `docker compose config`로 override 동작 확인

---

### Task 2: KIS 조회/매매 도메인 분리

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/core/clients/kis_config.py` (`get_inquiry_environment()` 헬퍼 추가)
- Modify: `backend/main.py` (inquiry_env/inquiry_client 이중 초기화 + KIS_APP_KEY 존재 검증)
- Modify: `backend/core/config.py` (KIS_APP_KEY 빈 문자열 기본값은 유지 — 검증은 main.py에서)
- Test: `backend/tests/test_kis_config.py` (get_inquiry_environment 테스트 추가)

**Step 1: kis_config.py에 inquiry 헬퍼 추가**
- `backend/core/clients/kis_config.py` 수정
- `get_inquiry_environment() -> KISEnvironment` 함수 추가: 항상 `LIVE` 인스턴스를 반환
- 기존 `get_current_environment()`, `get_environment()` 변경 없음
- 검증: `docker compose exec backend python -c "from core.clients.kis_config import get_inquiry_environment; e = get_inquiry_environment(); print(e.name)"`
- 예상: `live`

**Step 2: main.py lifespan 이중 초기화**
- `backend/main.py` lifespan 수정
- 기존 단일 env/token_manager/throttler/rest_client 초기화 직후에 inquiry용 인스턴스 추가:
  - `inquiry_env = get_inquiry_environment()` (항상 LIVE)
  - `inquiry_token_manager = KISTokenManager(env=inquiry_env, redis=redis_client)` (Redis 키 자동 분리: `kis:live:access_token`)
  - `inquiry_throttler = TokenBucketThrottler(interval=inquiry_env.rate_limit_interval)` (LIVE 기준 0.07초)
  - `inquiry_client = KISRestClient(env=inquiry_env, token_manager=inquiry_token_manager, throttler=inquiry_throttler)`
- `app.state.kis_inquiry` = inquiry_client 저장
- 기존 rest_client는 trading_client 역할 (이름 변경 없음 — 기존 코드 호환)
- CollectorScheduler 생성자에 `inquiry_client` 파라미터 전달 (Step 3에서 처리하므로 여기선 전달만)
- KIS_APP_KEY 존재 검증: lifespan 초입에 `if not app_settings.KIS_APP_KEY:` -> `logger.warning("KIS_APP_KEY 미설정: 시세 조회 불가")` (서버 시작은 차단하지 않음 — CI/테스트 환경 대응)
- import 추가: `from core.clients.kis_config import get_inquiry_environment`
- shutdown에 `await inquiry_client.close()`, `await inquiry_token_manager.close()` 추가
- 검증: `docker compose exec backend python -c "import main; print('OK')"` (임포트 성공 확인)
- 예상: OK

**Step 3: 테스트 추가**
- `backend/tests/test_kis_config.py` 수정
- `test_get_inquiry_environment_always_live` 추가: TRADING_ENV와 무관하게 항상 LIVE 환경 반환 확인
- 검증: `docker compose exec backend pytest tests/test_kis_config.py -v`
- 예상: 기존 테스트 + 신규 테스트 모두 PASS

**Step 4: 커밋**
```
git add backend/core/clients/kis_config.py backend/main.py backend/tests/test_kis_config.py
git commit -m "feat(phase4.6-sprint1): task2 -- KIS 조회/매매 도메인 분리 (inquiry_client 항상 LIVE)"
```

**완료 기준:**
- ⬜ `get_inquiry_environment()` 항상 LIVE 반환
- ⬜ main.py에서 inquiry_client 별도 초기화
- ⬜ app.state.kis_inquiry 존재
- ⬜ KIS_APP_KEY 미설정 시 warning 로그 (서버 시작은 정상)
- ⬜ test_kis_config.py 전체 PASS

---

### Task 3: CollectionResult + ValidationResult + CollectionValidator 도입

**Files:**
- Create: `backend/modules/collector/models.py` (CollectionResult, ValidationResult dataclass)
- Create: `backend/modules/collector/validator.py` (CollectionValidator 클래스)
- Create: `backend/tests/test_collection_validator.py` (단독 unit test)

**Step 1: models.py 작성**
- `backend/modules/collector/models.py` 생성
- `CollectionResult` dataclass:
  - `collected: int` -- 수집 성공 건수
  - `failed: int = 0` -- 수집 실패 건수
  - `skipped: int = 0` -- 스킵 건수
  - `total_target: int = 0` -- 수집 대상 총 건수
  - `data_date: str | None = None` -- 수집 기준일 (YYYYMMDD)
  - `null_counts: dict[str, int] | None = None` -- 필드별 null 건수 (예: {"close_price": 3, "volume": 1})
- `ValidationResult` dataclass:
  - `passed: bool`
  - `failure_type: str | None = None` -- "retryable" | "permanent"
  - `failure_reason: str | None = None` -- 구체적 실패 사유
  - `details: dict` = field(default_factory=dict)
  - `severity: str = "error"` -- "error" | "warning" | "info"
- 검증: `docker compose exec backend python -c "from modules.collector.models import CollectionResult, ValidationResult; print('OK')"`
- 예상: OK

**Step 2: validator.py 작성**
- `backend/modules/collector/validator.py` 생성
- `CollectionValidator` 클래스, 메서드:
  - `validate_premarket(result: CollectionResult) -> ValidationResult`
    - collected >= 1500, null_ratio(close_price) < 5%, null_ratio(volume) < 5%, data_date within T-2
    - 실패 시 failure_type="permanent", severity="error"
  - `validate_etf_master(result: CollectionResult, sanity_passed: bool) -> ValidationResult`
    - 기존 sanity_check 결과 위임 (sanity_passed 파라미터)
    - 실패 시 failure_type="permanent"
  - `validate_etf_collect(result: CollectionResult) -> ValidationResult`
    - collected >= total_target * 50%
    - 실패 시 failure_type="permanent"
  - `validate_primary_screen(result: CollectionResult) -> ValidationResult`
    - 0건 허용: severity="warning" (passed=True)
  - `validate_dart(result: CollectionResult) -> ValidationResult`
    - corp_code 매핑률 >= 50% (result.collected / result.total_target)
    - 0건: severity="warning" (passed=True)
  - `validate_sentiment(result: CollectionResult) -> ValidationResult`
    - 수집 성공률 >= 70% (result.collected / result.total_target)
    - 0건: severity="warning" (passed=True)
- null_ratio 계산 헬퍼: `_null_ratio(result, field_name) -> float` -- null_counts[field_name] / collected, collected==0이면 1.0
- T-2 거래일 판정: data_date가 오늘(KST) 기준 2 영업일 이내인지 (주말 건너뜀, 공휴일은 Sprint 2에서 추가)
- 검증: `docker compose exec backend python -c "from modules.collector.validator import CollectionValidator; print('OK')"`
- 예상: OK

**Step 3: 테스트 작성**
- `backend/tests/test_collection_validator.py` 생성
- 시나리오:
  - premarket: 1500건 이상 + null < 5% -> passed=True
  - premarket: 1499건 -> passed=False, failure_type="permanent"
  - premarket: null_ratio(close_price) >= 5% -> passed=False
  - premarket: data_date가 T-3 -> passed=False
  - etf_collect: 50% 이상 -> passed=True
  - etf_collect: 49% -> passed=False
  - primary_screen: 0건 -> passed=True, severity="warning"
  - dart: 매핑률 49% -> passed=False
  - dart: 0건(total_target=0) -> passed=True, severity="warning"
  - sentiment: 성공률 69% -> passed=False
  - sentiment: 0건 -> passed=True, severity="warning"
- 검증: `docker compose exec backend pytest tests/test_collection_validator.py -v`
- 예상: 전체 PASS

**Step 4: 커밋**
```
git add backend/modules/collector/models.py backend/modules/collector/validator.py backend/tests/test_collection_validator.py
git commit -m "feat(phase4.6-sprint1): task3 -- CollectionResult + CollectionValidator 유효성 검증 체계"
```

**완료 기준:**
- ⬜ CollectionResult, ValidationResult dataclass 정의 완료
- ⬜ CollectionValidator 6개 검증 메서드 구현
- ⬜ test_collection_validator.py 11개+ 시나리오 전체 PASS

---

### Task 4: data_go_kr 수집기 개선

**Files:**
- Modify: `backend/modules/collector/sources/data_go_kr.py` (CollectionResult 반환 + 날짜 폴백 + updated_at + null 카운팅)
- Modify: `backend/tests/test_data_go_kr.py` (CollectionResult 반환 테스트 + 폴백 테스트)

**Step 1: collect_all 반환값 변경**
- `backend/modules/collector/sources/data_go_kr.py` 수정
- `collect_all` 반환 타입: `int` -> `CollectionResult`
- import 추가: `from modules.collector.models import CollectionResult`
- 수집 루프 중 null_counts 딕셔너리 누적: close_price가 None이면 +1, volume이 None이면 +1
- 반환: `CollectionResult(collected=total_collected, data_date=bas_dt, null_counts=null_counts)`

**Step 2: 날짜 폴백 로직**
- `_latest_trading_date` -> `_get_trading_dates(max_days: int = 7) -> list[str]` 변경 (또는 별도 메서드 추가)
- 현재 `_latest_trading_date()`는 직전 평일 1개만 반환
- 변경: 최대 7일 전까지의 거래일 목록을 반환 (주말 건너뜀)
- `collect_all`에서 첫 번째 날짜로 수집 -> 0건이면 다음 날짜 시도 -> 최대 7일
- 폴백 시도 사이에 로그: `logger.warning("기준일 %s 수집 0건, 폴백 시도: %s", tried_date, next_date)`

**Step 3: _upsert_stock에 updated_at 명시적 설정**
- `_upsert_stock` 메서드의 `on_conflict_do_update` set_에 `"updated_at": func.now()` 추가
- import 추가: `from sqlalchemy import func` (select는 이미 import됨)
- 기존 ORM의 `onupdate=func.now()`는 pg_insert upsert 시 미작동 (phase4.6.md 근본 원인 #5)

**Step 4: 테스트 수정**
- `backend/tests/test_data_go_kr.py` 수정
- `collect_all` 반환값이 CollectionResult인지 확인
- null_counts 딕셔너리에 close_price, volume 키 존재 확인
- 날짜 폴백 시나리오: 첫 번째 날짜에서 0건 -> 두 번째 날짜 시도 mock
- 검증: `docker compose exec backend pytest tests/test_data_go_kr.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/modules/collector/sources/data_go_kr.py backend/tests/test_data_go_kr.py
git commit -m "feat(phase4.6-sprint1): task4 -- data_go_kr CollectionResult + 날짜 폴백 + updated_at"
```

**완료 기준:**
- ⬜ collect_all이 CollectionResult 반환
- ⬜ 0건 수집 시 최대 7일 날짜 폴백 시도
- ⬜ _upsert_stock에 updated_at 명시적 설정
- ⬜ null_counts에 close_price, volume 카운팅
- ⬜ test_data_go_kr.py 전체 PASS

---

### Task 5: kis_collector 수집기 개선

**Files:**
- Modify: `backend/modules/collector/sources/kis_collector.py` (CollectionResult 반환 + 실패 추적 + close_price 0 체크)
- Modify: `backend/tests/test_kis_collector.py` (CollectionResult 반환 테스트)

**Step 1: collect_etf_prices 반환값 변경**
- `backend/modules/collector/sources/kis_collector.py` 수정
- `collect_etf_prices` 반환 타입: `int` -> `CollectionResult`
- import 추가: `from modules.collector.models import CollectionResult`
- etf_codes 전체 수를 `total_target`으로 설정
- 수집 루프에서 실패 건수 `failed` 카운팅 (기존 except 블록)
- close_price == 0 체크: price.price가 0이면 수집 성공에서 제외, null_counts에 기록
- 반환: `CollectionResult(collected=collected, failed=failed, total_target=len(etf_codes), null_counts=null_counts)`

**Step 2: _save_etf_price에 updated_at 명시적 설정**
- `on_conflict_do_update` set_에 `"updated_at": func.now()` 추가
- import 추가: `from sqlalchemy import func`

**Step 3: 테스트 수정**
- `backend/tests/test_kis_collector.py` 수정
- 반환값이 CollectionResult인지 확인
- total_target, collected, failed 필드 검증
- 검증: `docker compose exec backend pytest tests/test_kis_collector.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/collector/sources/kis_collector.py backend/tests/test_kis_collector.py
git commit -m "feat(phase4.6-sprint1): task5 -- kis_collector CollectionResult + 실패 추적 + updated_at"
```

**완료 기준:**
- ⬜ collect_etf_prices가 CollectionResult 반환
- ⬜ 실패 건수, total_target 추적
- ⬜ close_price 0 체크
- ⬜ updated_at 명시적 설정
- ⬜ test_kis_collector.py 전체 PASS

---

### Task 6: dart + naver 수집기 개선

**Files:**
- Modify: `backend/modules/collector/sources/dart.py` (CollectionResult 반환 + MAX_FINANCIAL_QUERIES 제거 + 매핑 건수 추적)
- Modify: `backend/modules/collector/sources/naver.py` (CollectionResult 반환 + 성공/실패 추적)
- Modify: `backend/tests/test_dart.py` (CollectionResult 반환 테스트)
- Modify: `backend/tests/test_naver.py` (CollectionResult 반환 테스트)

**Step 1: dart.py collect_financials 개선**
- `backend/modules/collector/sources/dart.py` 수정
- import 추가: `from modules.collector.models import CollectionResult`
- `collect_financials` 반환 타입: `int` -> `CollectionResult`
- `MAX_FINANCIAL_QUERIES = 30` 상한 제거: `target_codes = [sc for sc in stock_codes if sc in mapping]` ([:MAX_FINANCIAL_QUERIES] 슬라이스 제거)
- total_target = len(stock_codes) (전체 종목 수)
- 매핑 성공 건수 = len(target_codes) -> CollectionResult.skipped = total_target - len(target_codes) (매핑 실패 = 스킵)
- 수집 실패 건수 추적 (fetch_financial이 None 또는 except 시)
- 반환: `CollectionResult(collected=collected, failed=failed, skipped=skipped, total_target=total_target)`

**Step 2: naver.py collect_sentiments 개선**
- `backend/modules/collector/sources/naver.py` 수정
- import 추가: `from modules.collector.models import CollectionResult`
- `collect_sentiments` 반환 타입: `int` -> `CollectionResult`
- total_target = len(stock_info) (종목 수)
- 종목별 뉴스 검색 실패 시 failed += 1 (search_news가 빈 리스트 반환이 아닌 Exception 시)
- 뉴스 0건인 종목은 skipped += 1
- 반환: `CollectionResult(collected=success_count, failed=failed, skipped=skipped, total_target=total_target)`
  - success_count = 뉴스가 1건 이상 수집된 종목 수 (뉴스 건수가 아닌 종목 수 기준)

**Step 3: 테스트 수정**
- `backend/tests/test_dart.py` 수정: collect_financials 반환값이 CollectionResult인지 확인, MAX_FINANCIAL_QUERIES 슬라이스가 없어졌는지 확인
- `backend/tests/test_naver.py` 수정: collect_sentiments 반환값이 CollectionResult인지 확인
- 검증: `docker compose exec backend pytest tests/test_dart.py tests/test_naver.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/collector/sources/dart.py backend/modules/collector/sources/naver.py backend/tests/test_dart.py backend/tests/test_naver.py
git commit -m "feat(phase4.6-sprint1): task6 -- dart/naver CollectionResult + MAX_FINANCIAL_QUERIES 상한 제거"
```

**완료 기준:**
- ⬜ dart collect_financials가 CollectionResult 반환, MAX_FINANCIAL_QUERIES 제거
- ⬜ naver collect_sentiments가 CollectionResult 반환, 종목별 성공/실패 추적
- ⬜ test_dart.py, test_naver.py 전체 PASS

---

### Task 7: scheduler.py 통합

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (inquiry_client 파라미터 + CollectionValidator 호출 + _update_step_status 확장 + _are_core_steps_healthy 강화 + 실패 구조화)

**Step 1: __init__ 파라미터 확장**
- `CollectorScheduler.__init__`에 `inquiry_client: KISRestClient | None = None` 파라미터 추가
- `self._inquiry_client = inquiry_client` 저장
- import 추가: `from modules.collector.models import CollectionResult, ValidationResult`, `from modules.collector.validator import CollectionValidator`
- `self._validator = CollectionValidator()` 인스턴스 생성

**Step 2: _update_step_status 시그니처 확장**
- 기존: `(self, step, status, error=None)`
- 변경: `(self, step, status, error=None, collected_count=None, validation=None)`
- `collected_count`와 `validation` (ValidationResult)을 pipeline_status entry에 포함:
  ```python
  if collected_count is not None:
      entry["collected_count"] = collected_count
  if validation is not None:
      entry["validation"] = {
          "passed": validation.passed,
          "failure_type": validation.failure_type,
          "failure_reason": validation.failure_reason,
          "details": validation.details,
          "severity": validation.severity,
      }
  ```
- pipeline_healthy 판정: 기존 status=="success" 외에 validation.passed도 확인
  - `_are_core_steps_healthy` 수정: `status == "success"` AND (`validation`이 없거나 `validation.passed == True`)

**Step 3: _premarket_collect 수정**
- `collector.collect_all()` 반환값: int -> CollectionResult
- `result = await collector.collect_all()`
- `validation = self._validator.validate_premarket(result)`
- validation.passed가 False이면: status를 "failed"로, error에 validation.failure_reason
- validation.passed가 True이면: status를 "success"로
- `_update_step_status`에 collected_count=result.collected, validation=validation 전달
- 기존 `count` 반환 -> `result.collected` 반환 (API 호환)

**Step 4: _etf_collect 수정**
- `KISCollector(self._inquiry_client or self._rest_client, db_session)` -- inquiry_client 우선 사용
- 반환값 CollectionResult 처리 + validate_etf_collect 호출
- validation 실패 시 "failed" + 알림

**Step 5: _etf_master_collect 수정**
- 기존 result dict의 sanity_passed 활용
- `CollectionResult(collected=result["etf_count"] + result["etn_count"], ...)` 래핑
- `validate_etf_master(collection_result, sanity_passed=result.get("sanity_passed", False))` 호출

**Step 6: _dart_collect, _sentiment_collect 수정**
- dart: collect_financials 반환값 CollectionResult 처리 + validate_dart 호출
- sentiment: collect_sentiments 반환값 CollectionResult 처리 + validate_sentiment 호출
- 0건이어도 warning만 (passed=True) -> status는 "success" + severity 기록

**Step 7: _primary_screen 수정**
- 기존 results 리스트에서 CollectionResult 래핑
- `CollectionResult(collected=len(passed))` -> validate_primary_screen 호출
- 0건: warning 알림 (기존 동작 유지 + severity 추가)

**Step 8: 커밋**
```
git add backend/modules/collector/scheduler.py
git commit -m "feat(phase4.6-sprint1): task7 -- scheduler CollectionValidator 통합 + pipeline_healthy 강화"
```

**완료 기준:**
- ⬜ scheduler.__init__에 inquiry_client 파라미터 추가
- ⬜ _update_step_status에 collected_count, validation 포함
- ⬜ 모든 수집 단계에서 CollectionValidator 호출
- ⬜ _are_core_steps_healthy가 validation.passed도 확인
- ⬜ ETF 수집이 inquiry_client 사용

---

### Task 8: 통합 테스트 + 기존 테스트 수정

**Files:**
- Modify: `backend/tests/test_scheduler.py` (collect_all/collect_etf_prices 반환값 Mock 수정)
- Modify: `backend/tests/test_scheduler_dependency.py` (반환값 변경 대응)
- Modify: `backend/tests/test_scheduler_telegram_alert.py` (반환값 변경 대응)
- Modify: `backend/tests/test_scheduler_redis_state.py` (반환값 변경 대응)
- Modify: `backend/tests/test_pipeline_health.py` (validation dict 포함 확인)
- Modify: `backend/tests/test_pipeline_api.py` (pipeline_status 스키마 변경 대응)
- Create: `backend/tests/test_phase4_6_integration.py` (도메인 분리 + 유효성 검증 통합 시나리오)

**Step 1: 기존 scheduler 테스트 Mock 수정**
- `collect_all` Mock 반환값: `int` -> `CollectionResult(collected=N, ...)`
- `collect_etf_prices` Mock 반환값: `int` -> `CollectionResult(collected=N, total_target=N, ...)`
- `collect_financials`, `collect_sentiments` Mock 반환값도 동일하게 CollectionResult로 변경
- `_make_scheduler()`에 inquiry_client 파라미터 추가 (MagicMock)
- 검증: `docker compose exec backend pytest tests/test_scheduler.py tests/test_scheduler_dependency.py tests/test_scheduler_telegram_alert.py tests/test_scheduler_redis_state.py -v`
- 예상: 전체 PASS

**Step 2: pipeline_health 테스트 수정**
- `test_pipeline_health.py`에서 pipeline_status에 `collected_count`, `validation` dict 포함 확인
- `_are_core_steps_healthy`가 validation.passed=False일 때 healthy=False 반환 확인
- 검증: `docker compose exec backend pytest tests/test_pipeline_health.py -v`
- 예상: PASS

**Step 3: 통합 테스트 작성**
- `backend/tests/test_phase4_6_integration.py` 생성
- 시나리오:
  1. **도메인 분리 확인**: inquiry_client가 LIVE 환경, rest_client가 TRADING_ENV 환경
  2. **premarket 유효성 검증 통합**: collect_all이 1500건+ 반환 -> pipeline_healthy="true"
  3. **premarket 유효성 검증 실패**: collect_all이 100건 반환 -> pipeline_healthy="false" + validation.passed=false
  4. **ETF 수집에 inquiry_client 사용 확인**: _etf_collect 내부에서 inquiry_client가 KISCollector에 전달
  5. **0건 수집 시 pipeline_healthy=false**: collect_all이 0건 -> "failed" + pipeline_healthy 미설정
  6. **pipeline_status JSON 확장 확인**: collected_count, validation dict 존재
- 검증: `docker compose exec backend pytest tests/test_phase4_6_integration.py -v`
- 예상: 전체 PASS

**Step 4: 전체 테스트 실행**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (기존 테스트 회귀 없음)

**Step 5: 커밋**
```
git add backend/tests/
git commit -m "feat(phase4.6-sprint1): task8 -- 통합 테스트 + 기존 테스트 CollectionResult 대응"
```

**완료 기준:**
- ⬜ 기존 scheduler 관련 테스트 전체 PASS (Mock 반환값 수정)
- ⬜ pipeline_health 테스트에 validation 검증 추가
- ⬜ test_phase4_6_integration.py 6개 시나리오 PASS
- ⬜ pytest 전체 테스트 회귀 없음

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| Dockerfile --reload 제거 | `grep "reload" backend/Dockerfile` | 결과 없음 |
| docker-compose override | `docker compose config \| grep -A2 command` | --reload 포함 |
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS |
| inquiry_client LIVE | `docker compose exec backend python -c "from core.clients.kis_config import get_inquiry_environment; print(get_inquiry_environment().name)"` | `live` |
| CollectionResult import | `docker compose exec backend python -c "from modules.collector.models import CollectionResult; print('OK')"` | OK |
| CollectionValidator import | `docker compose exec backend python -c "from modules.collector.validator import CollectionValidator; print('OK')"` | OK |
| pipeline_status 스키마 | Redis `GET scheduler:pipeline_status` JSON에 `collected_count`, `validation` 키 포함 | 수동 트리거 후 확인 |
