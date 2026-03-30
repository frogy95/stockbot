# Sprint 3: 보조 데이터 + 통합 테스트 (Phase 2)

**Goal:** DART 재무 기초 데이터와 네이버 뉴스 센티멘트를 보조 데이터로 수집하고, Phase 2 전체 파이프라인 통합 테스트를 완성한다.

**Architecture:** DART API에서 corp_code XML을 다운로드하여 DB에 종목코드-법인코드 매핑 테이블을 구축한 뒤, 1차 스크리닝 통과 종목(최대 30건)의 재무 기초 데이터(매출/영업이익/순이익)를 조회한다. 네이버 검색 API로 후보 종목의 뉴스를 수집하고 키워드 기반 간이 센티멘트 점수를 산출한다. 두 보조 데이터 모두 스케줄러에 장전 배치 job으로 등록한다.

**Tech Stack:** httpx (DART REST + 네이버 REST), lxml (corp_code XML 파싱), SQLAlchemy async, Alembic, APScheduler, pytest

**Sprint 기간:** 2026-03-30 ~ 2026-03-30
**상태:** ✅ 완료 (2026-03-30)
**이전 스프린트:** Sprint 2 (227 passed, PR #6)
**브랜치명:** `phase2-sprint3`
**PR:** https://github.com/frogy95/stockbot/pull/7

---

## 제외 범위

- 센티멘트 분석에 ML/NLP 모델 사용하지 않음 -- 키워드 사전 기반 간이 점수만 구현
- 보조 데이터를 기존 팩터 스코어링에 통합하지 않음 -- 별도 조회 API만 제공 (Phase 5에서 가중치 조정 시 통합 예정)
- DART 공시 모니터링 (실시간 공시 알림)은 Phase 6 범위
- corp_code XML 자동 분기 갱신 스케줄은 이번 Sprint에서 구현하지 않음 -- 수동 스크립트 + 스케줄러 job 등록만
- 프론트엔드 UI 변경 없음

## 실행 플랜

의존성: Task 1(테이블) -> Task 2, Task 3 (병렬 가능) -> Task 4(스케줄러 연동) -> Task 5(통합 테스트)

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 보조 데이터 테이블 3종 + Alembic 마이그레이션 | 백엔드 | -- |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | DART 재무 수집기 (corp_code 매핑 + 재무 조회) | 백엔드 | -- |
| Task 3 | 네이버 뉴스 센티멘트 수집기 | 백엔드 | -- |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 스케줄러 연동 + 보조 데이터 API | 백엔드 | `feature-dev:feature-dev` |
| Task 5 | Phase 2 전체 파이프라인 통합 테스트 | 백엔드 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 Task 2와 Task 3을 병렬 구현합니다.

---

### Task 1: 보조 데이터 테이블 + Alembic 마이그레이션

**Files:**
- Create: `backend/core/models/corp_code.py`
- Create: `backend/core/models/financial_data.py`
- Create: `backend/core/models/news_sentiment.py`
- Modify: `backend/core/models/__init__.py` (새 모델 3종 import 추가)
- Create: `backend/alembic/versions/xxx_보조_데이터_테이블_추가.py` (autogenerate)
- Test: `backend/tests/test_auxiliary_models.py`

**Step 1: 테스트 작성**
- `backend/tests/test_auxiliary_models.py` 생성
- CorpCode, FinancialData, NewsSentiment 모델의 테이블명, 컬럼명, 타입, 유니크 제약조건을 검증하는 테스트 작성
- 기존 `test_models.py`, `test_screening_result_model.py` 패턴 참고 (모델 클래스의 `__tablename__`, `__table__` 컬럼 확인)
- 검증: `docker compose exec backend pytest tests/test_auxiliary_models.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: corp_code 모델 구현**
- `backend/core/models/corp_code.py` 생성
- 클래스: `CorpCode(Base)`
- 테이블명: `corp_codes`
- 컬럼: `id` (SERIAL PK), `corp_code` (VARCHAR(8) UNIQUE NOT NULL), `corp_name` (VARCHAR(100) NOT NULL), `stock_code` (VARCHAR(10) nullable -- 상장사만), `modify_date` (DATE nullable), `updated_at` (TIMESTAMPTZ, onupdate=func.now())
- 인덱스: `stock_code` 인덱스

**Step 3: financial_data 모델 구현**
- `backend/core/models/financial_data.py` 생성
- 클래스: `FinancialData(Base)`
- 테이블명: `financial_data`
- 컬럼: `id` (SERIAL PK), `stock_code` (VARCHAR(10) FK -> stocks.stock_code NOT NULL), `fiscal_year` (INTEGER NOT NULL), `fiscal_quarter` (INTEGER NOT NULL), `revenue` (BIGINT nullable), `operating_profit` (BIGINT nullable), `net_income` (BIGINT nullable), `extra_data` (JSONB DEFAULT '{}'), `source` (VARCHAR(20) DEFAULT 'dart'), `collected_at` (TIMESTAMPTZ DEFAULT NOW())
- 제약조건: `UNIQUE(stock_code, fiscal_year, fiscal_quarter)`
- 인덱스: `(stock_code)`, `(fiscal_year, fiscal_quarter)`

**Step 4: news_sentiment 모델 구현**
- `backend/core/models/news_sentiment.py` 생성
- 클래스: `NewsSentiment(Base)`
- 테이블명: `news_sentiments`
- 컬럼: `id` (SERIAL PK), `stock_code` (VARCHAR(10) FK -> stocks.stock_code NOT NULL), `title` (TEXT NOT NULL), `source_url` (TEXT nullable), `published_at` (TIMESTAMPTZ nullable), `sentiment_score` (NUMERIC(4,3) nullable -- -1.0 ~ +1.0), `keyword` (VARCHAR(100) nullable), `collected_at` (TIMESTAMPTZ DEFAULT NOW())
- 인덱스: `(stock_code, published_at)`

**Step 5: __init__.py 업데이트 + Alembic 마이그레이션**
- `backend/core/models/__init__.py`에 3개 모델 import 추가 (기존 패턴: `from core.models.xxx import Xxx`)
- `docker compose exec backend alembic revision --autogenerate -m "보조 데이터 테이블 추가 (corp_codes, financial_data, news_sentiments)"`
- `docker compose exec backend alembic upgrade head`
- 검증: `docker compose exec backend pytest tests/test_auxiliary_models.py -v`
- 예상: PASS

**Step 6: 커밋**
```
git add backend/core/models/corp_code.py backend/core/models/financial_data.py backend/core/models/news_sentiment.py backend/core/models/__init__.py backend/alembic/versions/*보조* backend/tests/test_auxiliary_models.py
git commit -m "feat(phase2-sprint3): task1 -- 보조 데이터 테이블 3종 (corp_codes, financial_data, news_sentiments)"
```

**완료 기준:**
- ✅ 3개 테이블 모델 pytest 통과
- ✅ Alembic 마이그레이션 정상 적용
- ✅ `\dt` 명령으로 테이블 3개 확인

---

### Task 2: DART 재무 수집기

**Files:**
- Create: `backend/modules/collector/sources/dart.py`
- Create: `backend/scripts/load_corp_codes.py`
- Test: `backend/tests/test_dart.py`

**Step 1: 테스트 작성**
- `backend/tests/test_dart.py` 생성
- 테스트 대상:
  - `DartCollector.parse_corp_code_xml(xml_bytes)`: corp_code XML 바이트를 파싱하여 `[{corp_code, corp_name, stock_code, modify_date}, ...]` 리스트 반환. 상장사만 `stock_code`가 있고, 비상장사는 None/빈값
  - `DartCollector.fetch_financial(corp_code, year, quarter)`: DART API 호출하여 매출/영업이익/순이익 딕셔너리 반환. httpx 응답을 모킹하여 테스트
  - `DartCollector.collect_financials(stock_codes)`: 종목코드 리스트를 받아 corp_code 매핑 후 재무 데이터 수집 + DB 저장. 최대 30건 한도 검증
  - corp_code 매핑 실패 시(비상장, ETF) 스킵 동작 검증
- 검증: `docker compose exec backend pytest tests/test_dart.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: DART 수집기 구현**
- `backend/modules/collector/sources/dart.py` 생성
- 클래스: `DartCollector`
- 생성자: `__init__(self, db_session: AsyncSession)` -- 기존 DataGoKrCollector 패턴 따름
- 상수: `CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"`, `FINANCIAL_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"`, `MAX_FINANCIAL_QUERIES = 30`
- 메서드:
  - `async fetch_corp_code_zip() -> bytes`: DART API에서 corp_code ZIP 다운로드 (안에 CORPCODE.xml 포함)
  - `parse_corp_code_xml(xml_bytes: bytes) -> list[dict]`: lxml로 XML 파싱. `<list>` 태그 하위의 `corp_code`, `corp_name`, `stock_code`, `modify_date` 추출. `stock_code`가 빈 문자열이면 None 처리 (비상장)
  - `async save_corp_codes(records: list[dict]) -> int`: DB upsert (corp_code 기준). 저장 건수 반환
  - `async fetch_financial(corp_code: str, year: str, reprt_code: str) -> dict | None`: DART 재무 API 호출. `status == "000"`이면 매출/영업이익/순이익 추출, 아니면 None
  - `async collect_financials(stock_codes: list[str]) -> int`: stock_code 리스트 → corp_code 매핑 (DB 조회) → 재무 조회 → financial_data upsert. 수집 건수 반환. ETF/비상장은 매핑 실패로 자동 스킵
- 재무 데이터 추출 시 `account_nm`에서 "매출액", "영업이익", "당기순이익" 키워드 매칭. `thstrm_amount` 필드에서 금액 추출 (콤마 제거 후 정수 변환)
- reprt_code 매핑: `{1: "11013", 2: "11012", 3: "11014", 4: "11011"}` (분기별 보고서 코드)
- API 키: `settings.DART_API_KEY` 사용
- 에러 처리: API 호출 실패 시 로깅 후 스킵 (전체 수집 중단하지 않음)
- 검증: `docker compose exec backend pytest tests/test_dart.py -v`
- 예상: PASS

**Step 3: corp_code 로드 스크립트 구현**
- `backend/scripts/load_corp_codes.py` 생성
- 독립 실행 가능한 async 스크립트
- DartCollector를 사용하여 corp_code ZIP 다운로드 → 파싱 → DB 저장
- 실행: `docker compose exec backend python scripts/load_corp_codes.py`
- 저장 건수 출력
- 검증: 스크립트 실행 후 `corp_codes` 테이블에 레코드 확인 (stock_code IS NOT NULL 건수 = 상장사 수)

**Step 4: 커밋**
```
git add backend/modules/collector/sources/dart.py backend/scripts/load_corp_codes.py backend/tests/test_dart.py
git commit -m "feat(phase2-sprint3): task2 -- DART 재무 수집기 (corp_code 매핑 + 재무 기초 데이터)"
```

**완료 기준:**
- ✅ pytest 테스트 통과 (XML 파싱, 재무 조회, DB 저장)
- ✅ corp_code 로드 스크립트 정상 실행
- ✅ ETF/비상장 종목 스킵 동작 확인

---

### Task 3: 네이버 뉴스 센티멘트 수집기

**Files:**
- Create: `backend/modules/collector/sources/naver.py`
- Test: `backend/tests/test_naver.py`

**Step 1: 테스트 작성**
- `backend/tests/test_naver.py` 생성
- 테스트 대상:
  - `NaverCollector.search_news(query, display)`: 네이버 검색 API 호출. httpx 응답 모킹. `items` 리스트에서 `title`, `link`, `pubDate` 추출
  - `NaverCollector.calc_sentiment(title) -> float`: 키워드 사전 기반 센티멘트 점수 계산. 긍정 키워드(상승, 호재, 급등, 신고가, 흑자 등) = +, 부정 키워드(하락, 악재, 급락, 적자, 손실 등) = -. 중립 = 0.0
  - `NaverCollector.collect_sentiments(stock_codes_names)`: 종목코드+이름 리스트 → 뉴스 검색 → 센티멘트 계산 → DB 저장. 수집 건수 반환
  - Rate Limit 준수 검증: 일 25,000건 한도 감안, 종목당 10건 조회. display=10 고정
- 검증: `docker compose exec backend pytest tests/test_naver.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 네이버 수집기 구현**
- `backend/modules/collector/sources/naver.py` 생성
- 클래스: `NaverCollector`
- 생성자: `__init__(self, db_session: AsyncSession)`
- 상수: `SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"`, `DEFAULT_DISPLAY = 10`, `POSITIVE_KEYWORDS`, `NEGATIVE_KEYWORDS`
- 센티멘트 키워드 사전:
  - 긍정: 상승, 호재, 급등, 신고가, 흑자, 성장, 호실적, 매수, 상한가, 돌파, 회복, 증가
  - 부정: 하락, 악재, 급락, 적자, 손실, 감소, 매도, 하한가, 폭락, 위기, 부진, 실적악화
- 메서드:
  - `async search_news(query: str, display: int = 10) -> list[dict]`: 네이버 뉴스 검색 API 호출. 헤더에 `X-Naver-Client-Id`, `X-Naver-Client-Secret` 설정. items 리스트 반환
  - `calc_sentiment(title: str) -> float`: HTML 태그 제거 (`<b>`, `</b>`). 긍정/부정 키워드 카운트. 점수 = (긍정 - 부정) / max(긍정 + 부정, 1). -1.0 ~ +1.0 범위 클램프
  - `async collect_sentiments(stock_info: list[dict]) -> int`: `[{"stock_code": "005930", "stock_name": "삼성전자"}, ...]` 형태 입력. 종목명으로 뉴스 검색 → 센티멘트 계산 → news_sentiments 테이블 저장. 수집 건수 반환. 종목 간 0.1초 딜레이 (Rate Limit 대응)
  - `_parse_pub_date(pub_date_str: str) -> datetime | None`: RFC 2822 형식 pubDate 파싱
- API 키: `settings.NAVER_CLIENT_ID`, `settings.NAVER_CLIENT_SECRET` 사용
- 에러 처리: 검색 실패 시 로깅 후 해당 종목 스킵
- 검증: `docker compose exec backend pytest tests/test_naver.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/naver.py backend/tests/test_naver.py
git commit -m "feat(phase2-sprint3): task3 -- 네이버 뉴스 센티멘트 수집기 (키워드 기반 간이 점수)"
```

**완료 기준:**
- ✅ pytest 테스트 통과 (뉴스 검색, 센티멘트 계산, DB 저장)
- ✅ 센티멘트 점수 범위 -1.0 ~ +1.0 검증
- ✅ HTML 태그 정리 동작 확인

---

### Task 4: 스케줄러 연동 + 보조 데이터 API

**skill:** `feature-dev:feature-dev`

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (DART/네이버 배치 job 추가)
- Modify: `backend/main.py` (DartCollector, NaverCollector import 안 함 -- 스케줄러 내부에서 생성)
- Modify: `backend/api/routes/screening.py` (보조 데이터 조회 API 3개 추가)
- Test: `backend/tests/test_auxiliary_api.py`

**Step 1: 테스트 작성**
- `backend/tests/test_auxiliary_api.py` 생성
- 테스트 대상:
  - `GET /api/v1/auxiliary/financial/{stock_code}`: 특정 종목의 최신 재무 데이터 반환
  - `GET /api/v1/auxiliary/sentiment/{stock_code}`: 특정 종목의 최근 뉴스 센티멘트 반환 (최신 10건)
  - `GET /api/v1/auxiliary/status`: 보조 데이터 수집 상태 (마지막 실행 시간, 수집 건수)
- 검증: `docker compose exec backend pytest tests/test_auxiliary_api.py -v`
- 예상: FAIL

**Step 2: 보조 데이터 API 구현**
- `backend/api/routes/screening.py` 수정 (기존 screening 라우터에 추가)
- 엔드포인트 3개:
  - `GET /screening/auxiliary/financial/{stock_code}`: financial_data 테이블에서 해당 종목의 최신 분기 데이터 조회. `{stock_code, fiscal_year, fiscal_quarter, revenue, operating_profit, net_income, source, collected_at}` 반환
  - `GET /screening/auxiliary/sentiment/{stock_code}`: news_sentiments 테이블에서 해당 종목의 최근 뉴스 10건. `{title, sentiment_score, published_at, source_url}` 반환
  - `GET /screening/auxiliary/status`: 보조 데이터 수집 상태. 스케줄러에서 마지막 실행 시간 조회
- 검증: `docker compose exec backend pytest tests/test_auxiliary_api.py -v`
- 예상: PASS (API만, 스케줄러 미연동)

**Step 3: 스케줄러에 보조 데이터 job 추가**
- `backend/modules/collector/scheduler.py` 수정
- `__init__`에 `_last_dart`, `_last_sentiment` 상태 추가
- 새 job 2개 등록:
  - `_dart_collect`: CronTrigger(hour=8, minute=15) -- 장전 08:15 (1차 스크리닝 후). 1차 스크리닝 통과 종목의 corp_code 매핑 → 재무 데이터 수집
  - `_sentiment_collect`: CronTrigger(hour=8, minute=20) -- 장전 08:20. 1차 스크리닝 통과 종목의 뉴스 센티멘트 수집
- `get_status()` 딕셔너리에 `last_dart`, `last_sentiment` 추가
- 트리거 메서드: `trigger_dart()`, `trigger_sentiment()` 추가 (수동 실행용)
- 검증: 스케줄러 테스트에서 job 등록 확인
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/collector/scheduler.py backend/api/routes/screening.py backend/tests/test_auxiliary_api.py
git commit -m "feat(phase2-sprint3): task4 -- 스케줄러 보조 데이터 job + 조회 API 3종"
```

**완료 기준:**
- ✅ API 3개 엔드포인트 정상 응답
- ✅ 스케줄러에 dart_collect, sentiment_collect job 등록 확인
- ✅ 수동 트리거 동작 확인

---

### Task 5: Phase 2 전체 파이프라인 통합 테스트

**Files:**
- Create: `backend/tests/test_phase2_integration.py`
- Modify: 없음 (테스트만)

**Step 1: 통합 테스트 작성**
- `backend/tests/test_phase2_integration.py` 생성 (기존 `test_phase2_sprint1_integration.py`, `test_phase2_sprint2_integration.py` 패턴 참고)
- 테스트 시나리오:
  1. **데이터 수집 → 1차 스크리닝 파이프라인**: 테스트 데이터 DB 삽입 → PrimaryScreener.screen() → screening_results 저장 확인
  2. **1차 스크리닝 → DART 재무 수집 파이프라인**: 스크리닝 통과 종목 → DartCollector.collect_financials() → financial_data 저장 확인 (DART API 모킹)
  3. **1차 스크리닝 → 네이버 센티멘트 수집 파이프라인**: 스크리닝 통과 종목 → NaverCollector.collect_sentiments() → news_sentiments 저장 확인 (네이버 API 모킹)
  4. **보조 데이터 API 조회**: 저장된 재무/센티멘트 데이터를 API로 조회하여 정합성 검증
  5. **기존 회귀 테스트**: Sprint 1 수집기, Sprint 2 스크리닝 모듈이 변경 없이 정상 동작 확인
- 모든 외부 API는 모킹 (httpx 응답 패치)
- DB 세션은 독립 생성 (의존성 주입 대신 직접 세션 팩토리 사용 -- Sprint 1 패턴)
- 검증: `docker compose exec backend pytest tests/test_phase2_integration.py -v`
- 예상: PASS

**Step 2: 전체 회귀 테스트**
- `docker compose exec backend pytest -v` 실행
- 기존 테스트 전체(~227건) + 신규 테스트 모두 통과 확인
- 예상: ~250+ passed

**Step 3: 커밋**
```
git add backend/tests/test_phase2_integration.py
git commit -m "feat(phase2-sprint3): task5 -- Phase 2 전체 파이프라인 통합 테스트"
```

**완료 기준:**
- ✅ 통합 테스트 5개 시나리오 모두 PASS
- ✅ 전체 pytest 회귀 테스트 통과 (기존 + 신규)
- ✅ 외부 API 모킹 정상 동작

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | ~250+ passed |
| 모델 테스트 | `docker compose exec backend pytest tests/test_auxiliary_models.py -v` | 3 passed |
| DART 수집기 | `docker compose exec backend pytest tests/test_dart.py -v` | 4+ passed |
| 네이버 수집기 | `docker compose exec backend pytest tests/test_naver.py -v` | 4+ passed |
| 보조 API | `docker compose exec backend pytest tests/test_auxiliary_api.py -v` | 3+ passed |
| 통합 테스트 | `docker compose exec backend pytest tests/test_phase2_integration.py -v` | 5+ passed |
| DB 마이그레이션 | `docker compose exec backend alembic upgrade head` | OK |
| 재무 API | `curl -s http://localhost:8000/api/v1/screening/auxiliary/financial/005930 \| jq .` | `{stock_code, fiscal_year, ...}` |
| 센티멘트 API | `curl -s http://localhost:8000/api/v1/screening/auxiliary/sentiment/005930 \| jq .` | `{sentiments: [...]}` |
| 수집 상태 API | `curl -s http://localhost:8000/api/v1/screening/auxiliary/status \| jq .` | `{last_dart, last_sentiment}` |
