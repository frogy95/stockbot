# Sprint 1: ETF 마스터 수집 + 스케줄러 통합 (Phase 2.5)

**Goal:** KIS 종목 마스터파일(.mst)에서 ETF/ETN 종목을 파싱하여 stocks 테이블에 적재하고, 스케줄러와 통합하여 기존 ETF 시세 수집 파이프라인이 정상 동작하게 한다.

**Architecture:** KIS가 제공하는 KOSPI/KOSDAQ 종목 마스터파일(.mst.zip)을 HTTP로 다운로드하여 CP949 고정길이 파싱 후 ETP 필드로 ETF/ETN을 필터링한다. 종목명 패턴 매칭으로 leverage_ratio/etf_type/underlying_index를 추출하고, 3단계 계층형 폴백(mst -> 기존 DB 유지 -> 시드 50종목)으로 안정성을 확보한다.

**Tech Stack:** Python 3.12, httpx (HTTP 다운로드), zipfile (압축 해제), struct-like 고정길이 파싱, SQLAlchemy async (DB upsert)

**Sprint 기간:** 2026-03-30 ~ 2026-03-30
**상태:** ✅ 완료
**이전 스프린트:** Phase 2 Sprint 3 (pytest 전체 통과, PR #7)
**브랜치명:** `phase2.5-sprint1`
**PR:** https://github.com/frogy95/stockbot/pull/26

---

## 제외 범위

- 프론트엔드 작업 없음 (백엔드 전용 Phase)
- ETF 시세 수집 로직 수정 없음 (기존 `KISCollector.collect_etf_prices()` 그대로 사용)
- 1차/2차 스크리닝 로직 수정 없음 (ETF가 stocks에 들어가면 자동으로 스크리닝 대상 포함)
- ETF 데이터를 팩터 스코어링에 통합하지 않음 (Phase 5 범위)
- Alembic 마이그레이션 없음 (Stock 모델의 기존 stock_type/extra_data 필드 활용)

## 실행 플랜

의존성: Task 1(환경변수) -> Task 2(핵심 모듈) -> Task 3(시드 데이터) -> Task 4(스케줄러+API) -> Task 5(통합 테스트)

모든 Task가 백엔드 전용이고, 핵심 모듈(`kis_master.py`)에 집중되므로 순차 실행이 적합하다.

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | KIS_MST_BASE_URL 환경변수 추가 | 백엔드 | -- |
| Task 2 | KIS 마스터 수집기 (mst 파싱 + ETF 필터링 + DB upsert + sanity check + 폴백) | 백엔드 | -- |

### Phase 2 (순차 -- Task 2 완료 후)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | 시드 ETF 50종목 스크립트 | 백엔드 | -- |
| Task 4 | 스케줄러 통합 + 수동 트리거 API | 백엔드 | -- |

### Phase 3 (순차 -- Phase 2 완료 후)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | 통합 테스트 + 회귀 검증 | 백엔드 | -- |

---

### Task 1: KIS_MST_BASE_URL 환경변수 추가

**Files:**
- Modify: `backend/core/config.py` (Settings 클래스에 KIS_MST_BASE_URL 필드 추가)
- Modify: `.env.example` (KIS_MST_BASE_URL 항목 추가)

**Step 1: Settings에 환경변수 추가**
- `backend/core/config.py`의 Settings 클래스에 `KIS_MST_BASE_URL: str = "https://new.real.download.dws.co.kr/common/master"` 필드 추가
- 한투 API 관련 설정 블록(KIS_MOCK_APP_KEY 근처)에 배치
- 검증: `docker compose exec backend python -c "from core.config import settings; print(settings.KIS_MST_BASE_URL)"`
- 예상: `https://new.real.download.dws.co.kr/common/master`

**Step 2: .env.example 업데이트**
- `.env.example`의 한투 API 섹션에 `KIS_MST_BASE_URL=https://new.real.download.dws.co.kr/common/master` 추가
- 주석으로 용도 설명: `# KIS 종목 마스터파일 다운로드 베이스 URL (URL 변경 시 코드 수정 없이 대응)`
- 검증: `.env.example` 파일에 해당 라인 존재 확인

**Step 3: 커밋**
```
git add backend/core/config.py .env.example
git commit -m "feat(phase2.5-sprint1): task1 -- KIS_MST_BASE_URL 환경변수 추가"
```

**완료 기준:**
- ✅ Settings.KIS_MST_BASE_URL 기본값 출력 확인
- ✅ .env.example에 항목 추가 확인

---

### Task 2: KIS 마스터 수집기

**Files:**
- Create: `backend/modules/collector/sources/kis_master.py`
- Create: `backend/tests/test_kis_master.py`

**Step 1: 테스트 작성**
- `backend/tests/test_kis_master.py` 생성
- 테스트 대상:
  1. `parse_kospi_mst()`: KOSPI mst 바이너리 → 종목 리스트 파싱 (CP949 고정길이). 테스트 fixture로 최소 파싱 가능한 바이트열 구성
  2. `parse_kosdaq_mst()`: KOSDAQ mst 바이너리 → 종목 리스트 파싱 (KOSPI와 필드 구조 다름)
  3. `filter_etf()`: ETP 구분값으로 ETF/ETN 필터링. ETF -> stock_type='ETF', ETN -> stock_type='ETN', 일반주식 -> 제외
  4. `enrich_etf_metadata()`: 종목명 패턴 매칭 → etf_type/leverage_ratio/underlying_index 추출
     - "KODEX 레버리지" → etf_type='leverage', leverage_ratio=2
     - "KODEX 인버스" → etf_type='inverse', leverage_ratio=-1
     - "KODEX 200선물인버스2X" → etf_type='inverse', leverage_ratio=-2
     - "KODEX 200" → etf_type='normal', leverage_ratio=1
     - "TIGER 200" → etf_type='normal', leverage_ratio=1
  5. `sanity_check()`: 최소 200종목 미만 → False, 200 이상 → True. spot-check 5종목(069500, 122630, 114800, 252670, 102110) 존재 확인. 전일 대비 +-10% 초과 → False
  6. `sync_to_db()`: stocks 테이블 upsert (mock DB 세션). stock_type='ETF'/'ETN' scope 제한 확인 (일반 주식 레코드 삭제하지 않음)
  7. `download_mst()`: httpx mock으로 다운로드 성공/실패 시나리오. 재시도 3회 로직 확인
  8. `collect()` 통합: 다운로드 → 파싱 → 필터링 → 메타데이터 → sanity → DB. 정상 흐름 + mst 실패 시 기존 DB 유지 폴백
- 검증: `docker compose exec backend pytest tests/test_kis_master.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: KISMasterCollector 구현**
- `backend/modules/collector/sources/kis_master.py` 생성
- 클래스: `KISMasterCollector`
- 생성자: `__init__(self, db_session: AsyncSession)` — DB 세션 의존성 주입
- MST_URLS: `{"kospi": "{base_url}/kospi_code.mst.zip", "kosdaq": "{base_url}/kosdaq_code.mst.zip"}` — settings.KIS_MST_BASE_URL 사용

- **`async def download_mst(self, market: str) -> bytes`**:
  - httpx.AsyncClient로 mst.zip 다운로드. timeout=60초 (확정 파라미터)
  - 실패 시 재시도 3회, 10초 간격 (확정 파라미터)
  - zipfile로 압축 해제하여 mst 바이트 반환
  - 실패 시 예외 발생 (상위에서 폴백 처리)

- **`def parse_kospi_mst(self, data: bytes) -> list[dict]`**:
  - CP949 인코딩 고정길이 파싱
  - KIS 공식 GitHub `kis_kospi_code_mst.py` 참조하여 필드 offset 결정
  - 반환: `[{"stock_code": str, "stock_name": str, "market_type": "KOSPI", "etp_prod_type": str, ...}]`

- **`def parse_kosdaq_mst(self, data: bytes) -> list[dict]`**:
  - KOSDAQ용 필드 구조 (KOSPI와 offset 다름)
  - KIS 공식 GitHub `kis_kosdaq_code_mst.py` 참조

- **`def filter_etf(self, records: list[dict]) -> list[dict]`**:
  - etp_prod_type 필드로 ETF/ETN 구분
  - ETF -> stock_type='ETF', ETN -> stock_type='ETN'
  - 일반 주식/기타 -> 제외

- **`def enrich_etf_metadata(self, records: list[dict]) -> list[dict]`**:
  - 종목명 패턴 매칭으로 etf_type, leverage_ratio, underlying_index 추출
  - 패턴 (Phase 문서 확정):
    - "인버스2X" 또는 "곱버스" -> etf_type='inverse', leverage_ratio=-2
    - "인버스" (2X 아닌) -> etf_type='inverse', leverage_ratio=-1
    - "레버리지" 또는 "2X" 또는 "2배" -> etf_type='leverage', leverage_ratio=2
    - "3X" 또는 "3배" -> etf_type='leverage', leverage_ratio=3
    - 그 외 -> etf_type='normal', leverage_ratio=1
  - underlying_index: 종목명에서 추출 가능한 경우 (예: "KODEX 200" -> "KOSPI200"), 아닌 경우 ""

- **`def sanity_check(self, etf_list: list[dict], prev_count: int | None = None) -> bool`**:
  - 최소 200종목 이상 (확정 파라미터)
  - spot-check 5종목 존재 확인: 069500, 122630, 114800, 252670, 102110
  - prev_count가 있으면 전일 대비 +-10% 초과 시 False
  - 실패 사유 로깅

- **`async def sync_to_db(self, etf_list: list[dict]) -> int`**:
  - stocks 테이블에 upsert (stock_code 기준)
  - stock_type='ETF' 또는 'ETN' scope만 처리 — 기존 일반 주식 레코드에 영향 주지 않음
  - extra_data에 etf_type, leverage_ratio, underlying_index, source='kis_mst', mst_updated_at 저장
  - upsert된 종목 수 반환

- **`async def collect(self) -> dict`**:
  - 메인 오케스트레이션 메서드
  - 1순위: KOSPI + KOSDAQ mst 다운로드 → 파싱 → ETF 필터링 → 메타데이터 → sanity check → DB upsert
  - 2순위: mst 실패 또는 sanity check 실패 → 기존 stocks 테이블 ETF 유지 + 경고 로깅 (알림은 Phase 3)
  - 반환: `{"etf_count": int, "etn_count": int, "source": "mst"|"existing_db"|"seed", "sanity_passed": bool}`

- 검증: `docker compose exec backend pytest tests/test_kis_master.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/kis_master.py backend/tests/test_kis_master.py
git commit -m "feat(phase2.5-sprint1): task2 -- KIS 마스터 수집기 (mst 파싱 + ETF 필터링 + DB upsert + sanity check)"
```

**완료 기준:**
- ✅ pytest test_kis_master.py 전체 통과
- ✅ KOSPI/KOSDAQ mst 파싱 로직 분리 구현
- ✅ sanity check 5종목 spot-check 통과
- ✅ 폴백 계층 (mst 실패 -> 기존 DB 유지) 테스트 통과

---

### Task 3: 시드 ETF 50종목 스크립트

**Files:**
- Create: `backend/scripts/seed_etf.py`
- Create: `backend/tests/test_seed_etf.py`

**Step 1: 테스트 작성**
- `backend/tests/test_seed_etf.py` 생성
- 테스트 대상:
  1. `SEED_ETFS` 리스트가 50종목 이상인지 확인
  2. spot-check 5종목(069500, 122630, 114800, 252670, 102110) 포함 확인
  3. 각 시드에 stock_code, stock_name, stock_type, market_type, etf_type, leverage_ratio 필수 필드 존재
  4. `seed_etfs()` 함수: mock DB 세션으로 upsert 실행 확인
  5. KODEX/TIGER/KBSTAR/ARIRANG/HANARO 계열 종목 존재 확인 (확정 파라미터)
- 검증: `docker compose exec backend pytest tests/test_seed_etf.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: seed_etf.py 구현**
- `backend/scripts/seed_etf.py` 생성
- `SEED_ETFS`: 50종목 리스트 (종목코드, 종목명, stock_type, market_type, etf_type, leverage_ratio, underlying_index 포함)
  - KODEX 계열 ~15종목 (200, 레버리지, 인버스, 200선물인버스2X, 코스닥150, 코스닥150레버리지, 삼성그룹, 반도체 등)
  - TIGER 계열 ~15종목 (200, 미국S&P500, 미국나스닥100, 차이나전기차SOLACTIVE, 2차전지테마 등)
  - KBSTAR 계열 ~8종목 (200, ESG사회책임투자 등)
  - ARIRANG 계열 ~6종목 (200, 고배당주 등)
  - HANARO 계열 ~6종목 (200, 코스피 등)
- `async def seed_etfs(db_session: AsyncSession) -> int`: stocks 테이블에 upsert, 시드된 종목 수 반환
- 시드 역할: 최초 설치 전용 (운영 폴백이 아님, 확정 파라미터)
- 검증: `docker compose exec backend pytest tests/test_seed_etf.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/scripts/seed_etf.py backend/tests/test_seed_etf.py
git commit -m "feat(phase2.5-sprint1): task3 -- 시드 ETF 50종목 (최초 설치용)"
```

**완료 기준:**
- ✅ 50종목 이상 시드 데이터 정의
- ✅ KODEX/TIGER/KBSTAR/ARIRANG/HANARO 계열 커버
- ✅ pytest test_seed_etf.py 전체 통과

---

### Task 4: 스케줄러 통합 + 수동 트리거 API

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (08:10 ETF 마스터 갱신 job 추가, 08:05 -> 08:15 ETF 시세 수집 시간 조정)
- Modify: `backend/api/routes/collector.py` (etf-master 수동 트리거 엔드포인트 추가)
- Modify: `backend/main.py` (KISMasterCollector 관련 변경이 필요한 경우)
- Create: `backend/tests/test_etf_master_api.py`

**Step 1: 테스트 작성**
- `backend/tests/test_etf_master_api.py` 생성
- 테스트 대상:
  1. 스케줄러에 etf_master_collect job이 08:10 KST로 등록되는지 확인
  2. etf_collect job이 08:15 KST로 변경되었는지 확인 (기존 08:05 -> 08:15)
  3. `POST /api/v1/collector/trigger/etf-master` 엔드포인트 존재 확인 (스케줄러 mock)
  4. `GET /api/v1/collector/status`에 last_etf_master 필드 포함 확인
  5. `trigger_etf_master()` 호출 시 KISMasterCollector.collect() 실행 확인
- 검증: `docker compose exec backend pytest tests/test_etf_master_api.py -v`
- 예상: FAIL

**Step 2: 스케줄러 수정**
- `backend/modules/collector/scheduler.py` 수정:
  - `__init__`에 `self._last_etf_master: datetime | None = None` 추가
  - `start()`에 새 job 추가:
    ```
    etf_master_collect job: CronTrigger(hour=8, minute=10, timezone=tz)
    ```
  - 기존 `etf_collect` job 시간 변경: `minute=5` -> `minute=15` (확정 파라미터)
  - `_etf_master_collect()` 메서드 추가: KISMasterCollector 인스턴스 생성 + collect() 호출
  - 3순위 폴백 연결: DB에 ETF 없음(최초 설치) -> seed_etfs() 호출
  - `get_status()`에 `last_etf_master` 필드 추가
  - `trigger_etf_master()` 메서드 추가

**Step 3: API 엔드포인트 추가**
- `backend/api/routes/collector.py` 수정:
  - `POST /collector/trigger/etf-master` 엔드포인트 추가
  - 기존 패턴 참조: BackgroundTasks로 비동기 실행, scheduler.trigger_etf_master() 호출
  - 응답: `{"triggered": True, "message": "ETF 마스터 갱신 시작됨. /api/v1/collector/status 에서 last_etf_master 확인"}`

**Step 4: 검증**
- 검증: `docker compose exec backend pytest tests/test_etf_master_api.py -v`
- 예상: PASS
- 추가 검증: `docker compose exec backend pytest tests/test_scheduler.py tests/test_collector_api.py -v` (기존 테스트 회귀 확인)

**Step 5: 커밋**
```
git add backend/modules/collector/scheduler.py backend/api/routes/collector.py backend/tests/test_etf_master_api.py
git commit -m "feat(phase2.5-sprint1): task4 -- 스케줄러 ETF 마스터 08:10 job + 시세 08:15 조정 + 트리거 API"
```

**완료 기준:**
- ✅ etf_master_collect job 08:10 KST 등록 확인
- ✅ etf_collect job 08:15 KST로 변경 확인
- ✅ POST /collector/trigger/etf-master 동작 확인
- ✅ 기존 스케줄러/API 테스트 회귀 없음

---

### Task 5: 통합 테스트 + 회귀 검증

**Files:**
- Create: `backend/tests/test_phase2_5_integration.py`

**Step 1: 통합 테스트 작성**
- `backend/tests/test_phase2_5_integration.py` 생성
- 테스트 시나리오:
  1. **ETF 마스터 수집 전체 흐름**: mock mst 데이터 -> 파싱 -> 필터링 -> 메타데이터 -> sanity -> DB upsert -> stocks 테이블에 ETF 존재 확인
  2. **기존 ETF 시세 파이프라인 연결**: stocks에 ETF 적재 후 `KISCollector._get_etf_codes()`가 ETF 코드 반환하는지 확인
  3. **폴백 시나리오**: mst 다운로드 실패 시 기존 DB 유지 확인 (기존 ETF 레코드 손실 없음)
  4. **시드 폴백 시나리오**: DB에 ETF 없음 + mst 실패 -> seed_etfs() 호출 확인
  5. **일반 주식 안전성**: ETF upsert가 기존 stock_type='STOCK' 레코드에 영향 주지 않음
  6. **스케줄러 job 순서**: etf_master_collect(08:10) -> etf_collect(08:15) 시간 순서 확인
- 검증: `docker compose exec backend pytest tests/test_phase2_5_integration.py -v`
- 예상: PASS

**Step 2: 전체 회귀 테스트**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 통과 (기존 Phase 2 테스트 포함)

**Step 3: 커밋**
```
git add backend/tests/test_phase2_5_integration.py
git commit -m "feat(phase2.5-sprint1): task5 -- Phase 2.5 통합 테스트 + 전체 회귀 검증"
```

**완료 기준:**
- ✅ Phase 2.5 통합 테스트 전체 통과
- ✅ pytest -v 전체 통과 (340 passed, 1 failed — test_stock_crud DB 데이터 충돌, 기존 이슈)
- ✅ 기존 ETF 시세 파이프라인(KISCollector) 정상 연결 확인

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 통과 (기존 + 신규) |
| KIS 마스터 테스트 | `docker compose exec backend pytest tests/test_kis_master.py -v` | 전체 통과 |
| 시드 테스트 | `docker compose exec backend pytest tests/test_seed_etf.py -v` | 전체 통과 |
| API 테스트 | `docker compose exec backend pytest tests/test_etf_master_api.py -v` | 전체 통과 |
| 통합 테스트 | `docker compose exec backend pytest tests/test_phase2_5_integration.py -v` | 전체 통과 |
| 수동 트리거 API | `curl -X POST http://localhost:8000/api/v1/collector/trigger/etf-master` | `{"triggered": true, ...}` |
| 수집 상태 API | `curl -s http://localhost:8000/api/v1/collector/status \| jq .` | last_etf_master 필드 포함 |
