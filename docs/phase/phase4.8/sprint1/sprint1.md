# Sprint 1: KIS 일봉 보조 수집기 + 스케줄러 폴백 (Phase 4.8)

**Goal:** 공공데이터포털 장전 수집 실패 시 KIS REST 일봉 API로 자동 폴백하여 1차 스크리닝 0건 장애를 방지한다.

**Architecture:** KISRestClient에 `get_daily_price()` 메서드를 추가하고, 이를 활용하는 KISDailyCollector를 신규 생성한다. scheduler의 `_premarket_collect()`에서 포털 수집 실패 시 KIS 보조 수집을 자동 호출하는 폴백 로직을 추가한다. screener의 `_fetch_today_and_prev()` date_subq에서 `kis_daily` 소스도 인식하도록 확장하고, market_cap 부재 시 stocks.listed_shares 기반 추정 로직을 추가한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, PostgreSQL, Redis, APScheduler, httpx, pytest-asyncio

**상태:** ✅ 완료 (2026-04-03)

**Sprint 기간:** 2026-04-02 ~ 2026-04-03
**이전 스프린트:** Phase 4.7 Sprint 1 (pytest 통과, PR #72)
**브랜치명:** `phase4.8-sprint1`

---

## 제외 범위

- 08:30 포털 재시도 스케줄 (Sprint 2)
- 텔레그램 보조 수집 전환 알림 / 이중 실패 긴급 알림 (Sprint 2)
- 데이터 cross-check (포털 vs KIS 종가 1% 괴리 warning) (Sprint 2)
- 포털 재시도 성공 시 데이터 우선순위 로직 (Sprint 2)
- 프론트엔드 변경 없음

## 실행 플랜

의존성 그래프: Task 1(KIS REST 메서드) -> Task 2(수집기) -> Task 3(스케줄러 폴백) -> Task 4(스크리닝 소스 필터). Task 5(통합 테스트)는 Task 4 이후.

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | KIS REST 일봉 조회 메서드 추가 | 백엔드 | -- |
| Task 2 | KIS 일봉 보조 수집기 신규 생성 | 백엔드 | -- |

### Phase 2 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | 스케줄러 폴백 로직 + validator 확장 | 백엔드 | `feature-dev:feature-dev` |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 스크리닝 소스 필터 확장 + market_cap 추정 | 백엔드 | -- |

### Phase 4 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | 통합 테스트 (폴백 시나리오) | 백엔드 | -- |

---

### Task 1: KIS REST 일봉 조회 메서드

**Files:**
- Modify: `backend/core/clients/kis_rest.py` (get_daily_price 메서드 추가)
- Test: `backend/tests/test_kis_rest.py` (기존 파일에 테스트 추가)

**Step 1: 테스트 작성**
- `backend/tests/test_kis_rest.py`에 `test_get_daily_price` 테스트 추가
- KISRestClient._request를 AsyncMock으로 패치하여 FHKST03010100 응답 시뮬레이션
- 반환값: DailyPrice(stock_code, data_date, open_price, high_price, low_price, close_price, volume, change_rate)
- 검증: `docker compose exec backend pytest tests/test_kis_rest.py::test_get_daily_price -v`
- 예상: FAIL (DailyPrice 미정의, get_daily_price 미존재)

**Step 2: DailyPrice 스키마 + get_daily_price 구현**
- `backend/core/clients/kis_rest.py` 수정
- Pydantic 스키마 추가:
  ```
  class DailyPrice(BaseModel):
      stock_code: str
      data_date: str          # YYYYMMDD
      open_price: int
      high_price: int
      low_price: int
      close_price: int
      volume: int
      change_rate: float
  ```
- `get_daily_price(stock_code: str, start_date: str, end_date: str) -> list[DailyPrice]` 메서드 추가
  - API: `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice`
  - tr_id: `FHKST03010100`
  - params:
    - FID_COND_MRKT_DIV_CODE: "J"
    - FID_INPUT_ISCD: stock_code
    - FID_INPUT_DATE_1: start_date
    - FID_INPUT_DATE_2: end_date
    - FID_PERIOD_DIV_CODE: "D"
    - FID_ORG_ADJ_PRC: "0" (수정주가 미반영 — 확정 파라미터 #3)
  - output2 배열에서 DailyPrice 리스트로 변환
  - output2[n]의 stck_bsop_date, stck_oprc, stck_hgpr, stck_lwpr, stck_clpr, acml_vol, prdy_ctrt 매핑
- 검증: `docker compose exec backend pytest tests/test_kis_rest.py::test_get_daily_price -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/clients/kis_rest.py backend/tests/test_kis_rest.py
git commit -m "feat(phase4.8-sprint1): task1 -- KIS REST 일봉 조회 메서드 추가"
```

**완료 기준:**
- ✅ get_daily_price 테스트 통과
- ✅ DailyPrice 스키마 정의 완료

---

### Task 2: KIS 일봉 보조 수집기

**Files:**
- Create: `backend/modules/collector/sources/kis_daily_collector.py`
- Test: `backend/tests/test_kis_daily_collector.py`

**Step 1: 테스트 작성**
- `backend/tests/test_kis_daily_collector.py` 생성
- 테스트 케이스:
  1. `test_collect_all_stocks_success` — 활성 주식 3종목 조회, 2종목 성공, 1종목 실패 → CollectionResult(collected=2, failed=1, total_target=3)
  2. `test_batch_commit` — 50종목 배치 단위로 DB commit이 호출되는지 검증 (확정 파라미터 #4)
  3. `test_source_tag_kis_daily` — 저장된 MarketData.source가 "kis_daily"인지 확인 (확정 파라미터 #5)
  4. `test_collect_result_data_date` — CollectionResult.data_date가 전일(T-1) 날짜인지 확인
  5. `test_minimum_success_rate` — 80% 미만 수집 시 실패 판정 (확정 파라미터 #7)
- KISRestClient.get_daily_price를 AsyncMock으로 패치
- DB 세션은 AsyncMock 사용 (기존 test_kis_collector.py 패턴 참조)
- 검증: `docker compose exec backend pytest tests/test_kis_daily_collector.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: KISDailyCollector 구현**
- `backend/modules/collector/sources/kis_daily_collector.py` 생성
- 클래스 구조:
  ```
  class KISDailyCollector:
      def __init__(self, rest_client: KISRestClient, db_session: AsyncSession)
      async def collect_all(self, target_date: str | None = None) -> CollectionResult
      async def _get_active_stock_codes(self) -> list[str]
      async def _save_daily_price(self, stock_code: str, price: DailyPrice) -> None
  ```
- `collect_all`:
  1. target_date가 None이면 전일(T-1) 날짜 계산 (trading_calendar.get_prev_trading_day 사용)
  2. stocks 테이블에서 is_active=True, stock_type="STOCK" 전체 조회
  3. 50종목씩 배치 순회 (확정 파라미터 #4)
  4. 각 종목에 get_daily_price(stock_code, target_date, target_date) 호출
  5. 배치 완료 시 db_session.commit() (중간 commit으로 부분 실패 복구)
  6. source="kis_daily"로 market_data 테이블에 upsert (확정 파라미터 #5)
  7. 실패 종목은 카운트만, 배치 진행 차단 안 함
  8. 최종 CollectionResult 반환 (data_date=target_date)
- `_save_daily_price`: KISCollector._save_etf_price 패턴 재사용
  - pg_insert + on_conflict_do_update (index_elements: stock_code, data_date, source)
  - market_cap은 None (KIS 일봉에 시총 미포함 — 미해결 사항 #3)
- 검증: `docker compose exec backend pytest tests/test_kis_daily_collector.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/kis_daily_collector.py backend/tests/test_kis_daily_collector.py
git commit -m "feat(phase4.8-sprint1): task2 -- KIS 일봉 보조 수집기 구현"
```

**완료 기준:**
- ✅ KISDailyCollector 5개 테스트 통과
- ✅ source="kis_daily" 태그 저장 확인
- ✅ 배치 50종목 단위 commit 동작 확인

---

### Task 3: 스케줄러 폴백 로직 + validator 확장

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (_premarket_collect 폴백 로직 추가)
- Modify: `backend/modules/collector/validator.py` (validate_kis_daily 메서드 추가)
- Modify: `backend/tests/test_scheduler.py` (폴백 시나리오 테스트 추가)
- Modify: `backend/tests/test_collection_validator.py` (validate_kis_daily 테스트 추가)

**Step 1: validator에 validate_kis_daily 테스트 + 구현**
- `backend/tests/test_collection_validator.py`에 테스트 추가:
  1. `test_validate_kis_daily_pass` — collected >= total_target * 0.8 → passed=True
  2. `test_validate_kis_daily_fail_low_rate` — collected < total_target * 0.8 → passed=False
  3. `test_validate_kis_daily_pass_exact_threshold` — 정확히 80% → passed=True
- `backend/modules/collector/validator.py`에 `validate_kis_daily` 메서드 추가:
  - 파라미터: CollectionResult
  - 검증 로직: collected / total_target >= 0.8 (확정 파라미터 #7)
  - 실패 시: failure_type="permanent", failure_reason="KIS 보조 수집률 부족: {ratio} < 80%"
- 검증: `docker compose exec backend pytest tests/test_collection_validator.py -v`
- 예상: PASS

**Step 2: scheduler 폴백 테스트 작성**
- `backend/tests/test_scheduler.py`에 폴백 시나리오 테스트 추가:
  1. `test_premarket_fallback_to_kis_daily` — 포털 수집 후 validation 실패 시 KIS 보조 수집 자동 호출
  2. `test_premarket_fallback_kis_success` — KIS 보조 수집 성공 시 pipeline_status에 "premarket" status="success" (폴백 경유)
  3. `test_premarket_fallback_kis_fail` — KIS 보조 수집도 실패 시 pipeline_healthy=false 유지
  4. `test_premarket_no_fallback_on_success` — 포털 수집 성공 시 KIS 보조 수집 호출 안 함
- _make_scheduler() 패턴 재사용, DataGoKrCollector와 KISDailyCollector를 AsyncMock으로 패치
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v -k "fallback"`
- 예상: FAIL (폴백 로직 미구현)

**Step 3: scheduler._premarket_collect() 폴백 구현**
- `backend/modules/collector/scheduler.py` 수정
- 상단 import 추가: `from modules.collector.sources.kis_daily_collector import KISDailyCollector`
- `_premarket_collect()` 수정 로직:
  1. 기존: 포털 수집 → validation → 결과 반환
  2. 변경: 포털 수집 → validation → **실패 시 KIS 폴백 분기**
  3. 폴백 분기:
     ```
     if not validation.passed:
         logger.warning("포털 수집 실패, KIS 보조 수집 전환: reason=%s", validation.failure_reason)
         # KIS 보조 수집 실행
         client = self._inquiry_client or self._rest_client
         async with self._session_factory() as db_session:
             daily_collector = KISDailyCollector(client, db_session)
             kis_result = await daily_collector.collect_all()
         kis_validation = self._validator.validate_kis_daily(kis_result)
         if kis_validation.passed:
             # 보조 수집 성공 — premarket step을 success로 갱신
             await self._update_step_status("premarket", "success",
                 collected_count=kis_result.collected, validation=kis_validation)
             logger.info("KIS 보조 수집 성공: collected=%d", kis_result.collected)
             return kis_result.collected
         else:
             # 이중 실패 — pipeline_healthy=false 유지
             await self._update_step_status("premarket", "failed",
                 error=f"이중 실패: 포털({validation.failure_reason}), KIS({kis_validation.failure_reason})",
                 collected_count=kis_result.collected, validation=kis_validation)
             await self._send_failure_alert("premarket",
                 f"이중 실패 — 포털: {validation.failure_reason}, KIS: {kis_validation.failure_reason}")
             return 0
     ```
  4. 기존 exception 핸들러 내에서도 KIS 폴백 시도 (포털 자체가 예외 발생한 경우)
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v -k "fallback"`
- 예상: PASS

**Step 4: 기존 테스트 회귀 확인**
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v`
- 예상: 전체 PASS (기존 테스트에 영향 없음)

**Step 5: 커밋**
```
git add backend/modules/collector/scheduler.py backend/modules/collector/validator.py backend/tests/test_scheduler.py backend/tests/test_collection_validator.py
git commit -m "feat(phase4.8-sprint1): task3 -- 스케줄러 폴백 로직 + validator 확장"
```

**완료 기준:**
- ✅ validate_kis_daily 3개 테스트 통과
- ✅ 폴백 시나리오 4개 테스트 통과
- ✅ 기존 scheduler 테스트 회귀 없음

---

### Task 4: 스크리닝 소스 필터 확장 + market_cap 추정

**Files:**
- Modify: `backend/modules/screening/screener.py` (_fetch_today_and_prev source 필터 확장, market_cap 추정)
- Modify: `backend/tests/test_screener.py` (소스 필터 + market_cap 추정 테스트 추가)

**Step 1: 테스트 작성**
- `backend/tests/test_screener.py`에 테스트 추가:
  1. `test_fetch_includes_kis_daily_source` — date_subq가 source IN ("data_go_kr", "kis_daily")로 필터링하는지 확인
  2. `test_market_cap_estimation_from_listed_shares` — market_cap이 None이고 stocks.listed_shares와 close_price가 있을 때 listed_shares * close_price로 추정
  3. `test_market_cap_zero_when_no_listed_shares` — listed_shares가 None이면 market_cap=0 유지
  4. `test_mixed_source_latest_date_priority` — data_go_kr과 kis_daily 날짜가 다를 때 최신 날짜 우선 (확정 파라미터 #14)
- DB 세션 AsyncMock + market_data/stocks 테이블 모킹
- 검증: `docker compose exec backend pytest tests/test_screener.py -v -k "kis_daily or market_cap_estimation or mixed_source"`
- 예상: FAIL

**Step 2: _fetch_today_and_prev 소스 필터 확장**
- `backend/modules/screening/screener.py` 수정
- 기존 date_subq:
  ```python
  .where(MarketData.source == "data_go_kr")
  ```
- 변경:
  ```python
  .where(MarketData.source.in_(["data_go_kr", "kis_daily"]))
  ```
- 같은 종목에 두 소스가 있으면 data_go_kr 우선 (확정 파라미터 #5, #11):
  - stock_dates 매핑 후, 동일 종목/날짜에 두 소스가 있으면 data_go_kr 행을 선택
  - 구현: 쿼리 결과를 (stock_code, data_date) 그룹핑 후 source 우선순위 적용

**Step 3: market_cap 추정 로직 추가**
- `_fetch_today_and_prev` 내 mapped 생성 시:
  ```python
  market_cap = int(today_row["market_cap"] or 0)
  if market_cap == 0 and today_row.get("listed_shares") and today_row["close_price"]:
      market_cap = int(today_row["listed_shares"]) * int(today_row["close_price"])
  ```
- Stock.listed_shares를 join에 추가 (기존 쿼리에 Stock 칼럼 추가):
  ```python
  Stock.listed_shares,
  ```
- 검증: `docker compose exec backend pytest tests/test_screener.py -v -k "kis_daily or market_cap_estimation or mixed_source"`
- 예상: PASS

**Step 4: 기존 테스트 회귀 확인**
- 검증: `docker compose exec backend pytest tests/test_screener.py -v`
- 예상: 전체 PASS

**Step 5: 커밋**
```
git add backend/modules/screening/screener.py backend/tests/test_screener.py
git commit -m "feat(phase4.8-sprint1): task4 -- 스크리닝 소스 필터 확장 + market_cap 추정"
```

**완료 기준:**
- ✅ 소스 필터 확장 테스트 통과
- ✅ market_cap 추정 테스트 통과
- ✅ 기존 screener 테스트 회귀 없음

---

### Task 5: 통합 테스트 (폴백 시나리오)

**Files:**
- Create: `backend/tests/test_phase4_8_integration.py`

**Step 1: 통합 테스트 작성**
- `backend/tests/test_phase4_8_integration.py` 생성
- 테스트 시나리오:
  1. `test_portal_fail_kis_fallback_screening` — 포털 실패 -> KIS 보조 수집 -> 스크리닝 정상 동작
     - DataGoKrCollector.collect_all을 실패로 모킹
     - KISDailyCollector.collect_all을 성공으로 모킹 (source="kis_daily")
     - PrimaryScreener.screen()이 kis_daily 데이터로 후보 반환하는지 확인
  2. `test_portal_success_no_fallback` — 포털 정상 -> KIS 보조 수집 미호출
     - DataGoKrCollector.collect_all을 성공으로 모킹
     - KISDailyCollector가 호출되지 않음을 assert_not_called()로 확인
  3. `test_dual_failure_pipeline_unhealthy` — 포털 + KIS 모두 실패 -> pipeline_healthy=false
     - 양쪽 모두 실패 모킹
     - Redis에서 pipeline_healthy 값이 "false"인지 확인
  4. `test_kis_daily_market_cap_estimation` — KIS 보조 데이터에 market_cap=None일 때 listed_shares 기반 추정이 스크리닝에 적용되는지 확인
- 검증: `docker compose exec backend pytest tests/test_phase4_8_integration.py -v`
- 예상: PASS

**Step 2: 커밋**
```
git add backend/tests/test_phase4_8_integration.py
git commit -m "feat(phase4.8-sprint1): task5 -- 폴백 시나리오 통합 테스트"
```

**완료 기준:**
- ✅ 통합 테스트 4개 시나리오 전체 통과

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 기존 + 신규 전체 passed |
| KIS REST 테스트 | `docker compose exec backend pytest tests/test_kis_rest.py -v` | get_daily_price 포함 passed |
| 보조 수집기 테스트 | `docker compose exec backend pytest tests/test_kis_daily_collector.py -v` | 5 passed |
| validator 테스트 | `docker compose exec backend pytest tests/test_collection_validator.py -v` | validate_kis_daily 포함 passed |
| 스케줄러 폴백 테스트 | `docker compose exec backend pytest tests/test_scheduler.py -v -k "fallback"` | 4 passed |
| 스크리너 소스 필터 | `docker compose exec backend pytest tests/test_screener.py -v` | 전체 passed |
| 통합 테스트 | `docker compose exec backend pytest tests/test_phase4_8_integration.py -v` | 4 passed |
