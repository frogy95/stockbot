# Sprint 1: 핵심 데이터 수집 (Phase 2)

**Goal:** 공공데이터포털 일괄 수집, 한투 WS 파싱/체결강도, WS 구독 매니저, ETF 수집, 수집 스케줄러를 구현하여 장전/장중 데이터 수집 파이프라인을 완성한다.

**Architecture:** APScheduler 기반 스케줄러가 장전(08:00) 공공데이터포털 일괄 수집, 장중(09:00~15:30) 한투 WS 실시간 체결/호가 수신을 오케스트레이션한다. WS 구독 매니저가 종목 동적 추가/제거를 관리하고, 체결강도 모듈이 5분 윈도우 기반 매수/매도 비율을 계산한다. Phase 1의 KIS REST/WS 클라이언트, 토큰 매니저, 스로틀러를 직접 활용한다.

**Tech Stack:** APScheduler 3.x, httpx (공공데이터포털), websockets (한투 WS), Redis (실시간 캐싱), SQLAlchemy async (DB 저장)

**Sprint 기간:** 2026-03-29 ~ 2026-03-29
**상태:** ✅ 완료 (2026-03-29)
**이전 스프린트:** Phase 1 Sprint 2 (pytest 전체 통과, PR #3)
**브랜치명:** `phase2-sprint1`
**PR:** https://github.com/frogy95/stockbot/pull/5

---

## 제외 범위

- 1차/2차 스크리닝 엔진 (Sprint 2)
- 팩터 스코어링 시스템 (Sprint 2)
- DART 재무 수집, 네이버 뉴스 센티멘트 (Sprint 3)
- 프론트엔드 UI (Phase 4)
- 텔레그램 알림 연동 (Phase 3)
- 수집 실패 시 텔레그램 경고 발송 (Phase 3에서 notifier 모듈 구현 후 연동)
- 수집 실패 폴백의 "전일 데이터 재사용" 로직 (Sprint 2에서 스크리닝과 함께 구현)

## 실행 플랜

### Phase 1 (순차 — DB 스키마 + 의존성)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | screening_results 테이블 + Alembic 마이그레이션 | 백엔드 | -- |

### Phase 2 (병렬 가능 — 독립 수집 모듈)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | 공공데이터포털 수집기 | 백엔드 | -- |
| Task 3 | 한투 WS 데이터 파서 (체결/호가) | 백엔드 | -- |
| Task 4 | 체결강도 계산 모듈 | 백엔드 | -- |

### Phase 3 (순차 — Task 3 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | WS 구독 매니저 | 백엔드 | -- |

### Phase 4 (병렬 가능 — 독립 모듈)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | 한투 REST ETF 수집기 | 백엔드 | -- |

### Phase 5 (순차 — 전체 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 7 | 수집 스케줄러 + API 엔드포인트 | 백엔드 | `feature-dev:feature-dev` |
| Task 8 | 통합 테스트 + main.py 연동 | 백엔드 | -- |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"라고 요청하면 Task 2/3/4를 병렬 구현합니다.

---

### Task 1: screening_results 테이블 + Alembic 마이그레이션

**Files:**
- Create: `backend/core/models/screening_result.py`
- Modify: `backend/core/models/__init__.py` (ScreeningResult import 추가)
- Create: `backend/alembic/versions/xxx_screening_results_테이블_추가.py` (autogenerate)
- Test: `backend/tests/test_screening_result_model.py`

**Step 1: 모델 작성**
- `backend/core/models/screening_result.py` 생성
- ScreeningResult 모델 정의 (Phase 2 문서 스키마 준수):
  - `id`: BIGSERIAL PK
  - `stock_code`: VARCHAR(10) NOT NULL, FK -> stocks.stock_code
  - `screening_type`: VARCHAR(20) NOT NULL (primary/secondary)
  - `score`: DECIMAL(5,2) (0~100)
  - `rank`: INTEGER
  - `factors`: JSONB DEFAULT '{}'
  - `is_hot`: BOOLEAN DEFAULT false (거래량 500%+)
  - `status`: VARCHAR(20) DEFAULT 'active' (active/expired/filtered)
  - `screened_at`: TIMESTAMPTZ DEFAULT NOW()
  - `expires_at`: TIMESTAMPTZ
- `__table_args__`에 UniqueConstraint(stock_code, screening_type, screened_at), Index(screening_type, screened_at), Index(score DESC) 정의
- `backend/core/models/__init__.py`에 `from core.models.screening_result import ScreeningResult` 추가
- 검증: `docker compose exec backend python -c "from core.models.screening_result import ScreeningResult; print(ScreeningResult.__tablename__)"`
- 예상: `screening_results`

**Step 2: Alembic 마이그레이션**
- `docker compose exec backend alembic revision --autogenerate -m "screening_results 테이블 추가"`
- `docker compose exec backend alembic upgrade head`
- 검증: `docker compose exec backend python -c "from core.database import get_engine; import asyncio; asyncio.run(get_engine().dispose())"` + psql로 테이블 확인
- 예상: screening_results 테이블 생성됨

**Step 3: 모델 테스트**
- `backend/tests/test_screening_result_model.py` 생성
- 테스트: ScreeningResult CRUD (생성, 조회, 유니크 제약조건 위반 확인)
- 검증: `docker compose exec backend pytest tests/test_screening_result_model.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/core/models/screening_result.py backend/core/models/__init__.py backend/alembic/versions/ backend/tests/test_screening_result_model.py
git commit -m "feat(phase2-sprint1): task1 -- screening_results 테이블 모델 + 마이그레이션"
```

**완료 기준:**
- ✅ ScreeningResult 모델 정의 완료
- ✅ Alembic 마이그레이션 적용 + 테이블 생성 확인
- ✅ CRUD 테스트 통과

---

### Task 2: 공공데이터포털 수집기

**Files:**
- Create: `backend/modules/collector/sources/__init__.py`
- Create: `backend/modules/collector/sources/data_go_kr.py`
- Test: `backend/tests/test_data_go_kr.py`

**Step 1: 테스트 작성**
- `backend/tests/test_data_go_kr.py` 생성
- httpx 응답을 mock하여 테스트:
  - `test_fetch_market_data_success`: 정상 JSON 응답 파싱 -> MarketData + Stock upsert
  - `test_fetch_market_data_retry`: 첫 호출 실패 후 재시도 성공 (3회 재시도, 30초 간격은 테스트에서 0초로 패치)
  - `test_fetch_market_data_all_fail`: 3회 모두 실패 시 에러 로깅 (예외 발생하지 않음)
  - `test_parse_response_items`: 공공데이터포털 JSON 응답의 items 배열 파싱
- 검증: `docker compose exec backend pytest tests/test_data_go_kr.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 수집기 구현**
- `backend/modules/collector/sources/__init__.py` 생성 (빈 파일)
- `backend/modules/collector/sources/data_go_kr.py` 생성
- `DataGoKrCollector` 클래스:
  - `__init__(self, db_session: AsyncSession, redis: RedisClient)`: DB 세션, Redis 클라이언트 주입
  - `async def collect_all(self) -> int`: 전 종목 일괄 수집 메인 메서드, 수집 종목 수 반환
    - 공공데이터포털 주식시세정보 API 호출 (resultType=json)
    - `settings.DATA_GO_KR_API_KEY` 사용
    - 응답 파싱 후 stocks 테이블 upsert + market_data 테이블 insert
    - source = "data_go_kr"
    - 페이지네이션 처리 (numOfRows=500, 반복 호출)
  - `async def _fetch_page(self, page: int, num_rows: int) -> list[dict]`: 단일 페이지 호출
    - 재시도 로직: 3회, 30초 간격 (설정 가능)
    - httpx.AsyncClient 사용
  - `async def _upsert_stock(self, item: dict) -> None`: stocks 테이블 upsert
  - `async def _save_market_data(self, item: dict) -> None`: market_data 테이블 insert (중복 시 무시)
- API URL: `https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo`
- 주요 파라미터: `serviceKey`, `resultType=json`, `numOfRows=500`, `pageNo`
- 응답 필드 매핑:
  - `srtnCd` -> stock_code
  - `itmsNm` -> stock_name
  - `mrktCtg` -> market_type (KOSPI/KOSDAQ)
  - `clpr` -> close_price
  - `mkp` -> open_price
  - `hipr` -> high_price
  - `lopr` -> low_price
  - `trqu` -> volume
  - `mrktTotAmt` -> market_cap
  - `lstgStCnt` -> listed_shares
  - `fltRt` -> change_rate
  - `basDt` -> data_date
- 검증: `docker compose exec backend pytest tests/test_data_go_kr.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/ backend/tests/test_data_go_kr.py
git commit -m "feat(phase2-sprint1): task2 -- 공공데이터포털 수집기 (전 종목 일괄 OHLCV/시총)"
```

**완료 기준:**
- ✅ 공공데이터포털 JSON 응답 파싱 테스트 통과
- ✅ 재시도 로직 (3회, 30초 간격) 테스트 통과
- ✅ stocks upsert + market_data insert 로직 구현

---

### Task 3: 한투 WS 데이터 파서 (체결/호가)

**Files:**
- Create: `backend/modules/collector/sources/kis_realtime.py`
- Test: `backend/tests/test_kis_realtime.py`

**Step 1: 테스트 작성**
- `backend/tests/test_kis_realtime.py` 생성
- 순수 파싱 함수 테스트 (외부 의존성 없음):
  - `test_parse_execution_data`: H0STCNT0 체결 데이터 파싱 (파이프+캐럿 구분)
  - `test_parse_orderbook_data`: H0STASP0 호가 데이터 파싱
  - `test_parse_invalid_data`: 잘못된 형식 처리 (None 반환)
  - `test_execution_data_fields`: 파싱 결과에 stock_code, price, volume, time, sell_or_buy 등 필수 필드 존재
  - `test_orderbook_data_fields`: 파싱 결과에 ask/bid 가격/수량 필드 존재
- 검증: `docker compose exec backend pytest tests/test_kis_realtime.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 파서 구현**
- `backend/modules/collector/sources/kis_realtime.py` 생성
- 한투 WS 실시간 데이터 형식: `암호화여부|tr_id|건수|데이터본문`
  - 데이터 본문은 `^` (캐럿)으로 필드 구분
- `parse_raw_message(raw: str) -> tuple[str, str, str] | None`: 파이프 구분 파싱 -> (tr_id, encrypted, body)
- `parse_execution(body: str) -> ExecutionData | None`: H0STCNT0 체결 데이터 파싱
  - `ExecutionData` (Pydantic 모델 또는 dataclass):
    - stock_code: str (필드 0)
    - time: str (필드 1, HHMMSS)
    - price: int (필드 2, 현재가)
    - change_sign: str (필드 3, 전일대비부호)
    - change: int (필드 4, 전일대비)
    - change_rate: float (필드 5, 전일대비율)
    - volume: int (필드 12, 체결수량)
    - acml_volume: int (필드 13, 누적거래량)
    - sell_or_buy: str (필드 17, 체결구분 1=매도 2=매수)
  - 필드 인덱스는 설정 딕셔너리로 관리 (하드코딩 회피 — 미해결사항 #5)
- `parse_orderbook(body: str) -> OrderbookData | None`: H0STASP0 호가 데이터 파싱
  - `OrderbookData` (Pydantic 모델 또는 dataclass):
    - stock_code: str (필드 0)
    - time: str (필드 1, HHMMSS)
    - asks: list[tuple[int, int]] (매도호가/수량 10단계)
    - bids: list[tuple[int, int]] (매수호가/수량 10단계)
    - total_ask_volume: int
    - total_bid_volume: int
  - 필드 인덱스 설정 딕셔너리로 관리
- 검증: `docker compose exec backend pytest tests/test_kis_realtime.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/kis_realtime.py backend/tests/test_kis_realtime.py
git commit -m "feat(phase2-sprint1): task3 -- 한투 WS 체결/호가 파서 (H0STCNT0, H0STASP0)"
```

**완료 기준:**
- ✅ H0STCNT0 체결 데이터 파싱 테스트 통과
- ✅ H0STASP0 호가 데이터 파싱 테스트 통과
- ✅ 필드 인덱스 설정 딕셔너리 (하드코딩 방지)

---

### Task 4: 체결강도 계산 모듈

**Files:**
- Create: `backend/modules/collector/trade_strength.py`
- Test: `backend/tests/test_trade_strength.py`

**Step 1: 테스트 작성**
- `backend/tests/test_trade_strength.py` 생성
- 순수 계산 로직 테스트:
  - `test_add_execution_and_calculate`: 매수/매도 체결 추가 후 체결강도 계산
  - `test_window_expiry`: 5분(300초) 윈도우 이후 데이터 만료 확인
  - `test_minimum_accumulation`: 누적 5분 미만 시 중립값(50) 반환
  - `test_all_buy_strength_100`: 전부 매수 시 체결강도 100
  - `test_all_sell_strength_0`: 전부 매도 시 체결강도 0
  - `test_reset_stock`: 종목 데이터 초기화
- 검증: `docker compose exec backend pytest tests/test_trade_strength.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 체결강도 계산기 구현**
- `backend/modules/collector/trade_strength.py` 생성
- `TradeStrengthCalculator` 클래스:
  - `__init__(self, window_seconds: int = 300)`: 5분 윈도우 기본값
  - 내부 구조: `dict[str, deque[tuple[float, int, str]]]` (종목별 타임스탬프/수량/매수매도)
  - `add_execution(self, stock_code: str, timestamp: float, volume: int, sell_or_buy: str) -> None`: 체결 데이터 추가
  - `get_strength(self, stock_code: str) -> float`: 체결강도 계산
    - 공식: (매수 체결량 / (매수 체결량 + 매도 체결량)) * 100
    - 윈도우 내 데이터만 사용 (만료 데이터 자동 정리)
    - 누적 5분 미만 시 중립값 50.0 반환
  - `reset(self, stock_code: str) -> None`: 종목 데이터 초기화
  - `_cleanup(self, stock_code: str, now: float) -> None`: 만료 데이터 정리
- 검증: `docker compose exec backend pytest tests/test_trade_strength.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/trade_strength.py backend/tests/test_trade_strength.py
git commit -m "feat(phase2-sprint1): task4 -- 체결강도 계산 모듈 (5분 윈도우, 매수/매도 누적 비율)"
```

**완료 기준:**
- ✅ 체결강도 계산 공식 정확 (매수/(매수+매도)*100)
- ✅ 5분 윈도우 만료 처리
- ✅ 누적 미달 시 중립값(50) 반환

---

### Task 5: WS 구독 매니저

**Files:**
- Create: `backend/modules/collector/ws_manager.py`
- Test: `backend/tests/test_ws_manager.py`

**Step 1: 테스트 작성**
- `backend/tests/test_ws_manager.py` 생성
- KISWebSocketClient를 mock하여 테스트:
  - `test_subscribe_stock`: 종목 구독 추가 (체결 + 호가 2개 tr_id)
  - `test_unsubscribe_stock`: 종목 구독 해제
  - `test_max_subscription_limit`: 35종목 상한 초과 시 거부 (False 반환)
  - `test_subscribe_duplicate`: 중복 구독 시 무시 (True 반환, 재전송 안함)
  - `test_replace_lowest_priority`: 상한 초과 시 우선순위 기반 로테이션 (가장 낮은 우선순위 종목 교체)
  - `test_concurrent_subscribe`: asyncio.Lock으로 동시 구독 경쟁 조건 방지
  - `test_ws_none_guard`: _ws가 None일 때 subscribe/unsubscribe 호출 시 에러 없이 False 반환 (미해결 #3)
  - `test_get_subscribed_stocks`: 현재 구독 종목 목록 조회
- 검증: `docker compose exec backend pytest tests/test_ws_manager.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: WS 구독 매니저 구현**
- `backend/modules/collector/ws_manager.py` 생성
- `WSSubscriptionManager` 클래스:
  - `__init__(self, ws_client: KISWebSocketClient, max_subscriptions: int = 35)`: WS 클라이언트 주입, 35종목 운영 상한
  - `_lock: asyncio.Lock`: 동시성 제어
  - `_subscriptions: dict[str, float]`: {stock_code: priority_score}
  - `_tr_ids: list[str]`: ["H0STCNT0", "H0STASP0"] 기본 구독 tr_id
  - `async def subscribe(self, stock_code: str, priority: float = 0.0) -> bool`: 종목 구독
    - Lock 획득
    - 이미 구독 중이면 True 반환 (중복 방지)
    - 상한 미만이면 WS 구독 요청 후 True
    - 상한 도달 시: priority가 가장 낮은 종목보다 높으면 교체, 아니면 False
    - _ws is None 시 False 반환 + 경고 로그 (미해결 #3)
  - `async def unsubscribe(self, stock_code: str) -> bool`: 종목 구독 해제
    - Lock 획득
    - _ws is None 시 False 반환 (미해결 #3)
  - `def get_subscribed_stocks(self) -> list[str]`: 현재 구독 종목 목록
  - `@property def count(self) -> int`: 현재 구독 수
  - `async def unsubscribe_all(self) -> None`: 전체 해제
- 검증: `docker compose exec backend pytest tests/test_ws_manager.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/ws_manager.py backend/tests/test_ws_manager.py
git commit -m "feat(phase2-sprint1): task5 -- WS 구독 매니저 (35종목 상한, 우선순위 로테이션, Lock)"
```

**완료 기준:**
- ✅ 35종목 상한 제어
- ✅ 우선순위 기반 로테이션
- ✅ asyncio.Lock 동시성 제어
- ✅ _ws None 가드 (미해결 #3 해결)

---

### Task 6: 한투 REST ETF 수집기

**Files:**
- Create: `backend/modules/collector/sources/kis_collector.py`
- Test: `backend/tests/test_kis_collector.py`

**Step 1: 테스트 작성**
- `backend/tests/test_kis_collector.py` 생성
- KISRestClient를 mock하여 테스트:
  - `test_collect_etf_prices`: ETF 종목 리스트 조회 후 개별 시세 수집
  - `test_collect_etf_save_to_db`: 수집 데이터 market_data 테이블 저장
  - `test_collect_etf_rate_limit`: 스로틀러 통해 호출 속도 제어 확인
  - `test_collect_etf_partial_failure`: 일부 종목 실패 시 나머지 종목은 정상 수집
- 검증: `docker compose exec backend pytest tests/test_kis_collector.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: ETF 수집기 구현**
- `backend/modules/collector/sources/kis_collector.py` 생성
- `KISCollector` 클래스:
  - `__init__(self, rest_client: KISRestClient, db_session: AsyncSession)`: KIS REST 클라이언트, DB 세션 주입
  - `async def collect_etf_prices(self, etf_codes: list[str]) -> int`: ETF 개별 시세 수집
    - `rest_client.get_stock_price(code)` 호출 (기존 메서드 재사용)
    - 결과를 market_data 테이블에 저장 (source = "kis_rest")
    - 실패 시 개별 종목 스킵, 로깅
    - 수집 성공 종목 수 반환
  - `async def _save_etf_price(self, price: StockPrice) -> None`: market_data 저장
- ETF 종목 리스트는 stocks 테이블에서 `stock_type = 'ETF'` 필터로 조회
- 검증: `docker compose exec backend pytest tests/test_kis_collector.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/collector/sources/kis_collector.py backend/tests/test_kis_collector.py
git commit -m "feat(phase2-sprint1): task6 -- 한투 REST ETF 수집기 (개별 시세 조회 + DB 저장)"
```

**완료 기준:**
- ✅ ETF 개별 시세 수집 (KIS REST 재사용)
- ✅ market_data 테이블 저장
- ✅ 부분 실패 처리 (개별 종목 스킵)

---

### Task 7: 수집 스케줄러 + API 엔드포인트

**skill:** `feature-dev:feature-dev`

**Files:**
- Create: `backend/modules/collector/scheduler.py`
- Create: `backend/api/routes/collector.py`
- Modify: `backend/main.py` (스케줄러 lifespan 추가, collector 라우터 등록)
- Test: `backend/tests/test_scheduler.py`
- Test: `backend/tests/test_collector_api.py`

**Step 1: 스케줄러 테스트 작성**
- `backend/tests/test_scheduler.py` 생성
- APScheduler의 job 등록/실행을 mock하여 테스트:
  - `test_scheduler_registers_jobs`: 초기화 시 장전/장중/장후 job 등록 확인
  - `test_scheduler_start_stop`: 시작/종료 정상 동작
  - `test_premarket_job`: 장전 수집 job이 공공데이터포털 + ETF 수집 호출
  - `test_market_open_job`: 장중 시작 시 WS 구독 시작
  - `test_market_close_job`: 장후 WS 구독 해제
  - `test_misfire_grace_time`: misfire_grace_time 60초 설정 확인
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 스케줄러 구현**
- `backend/modules/collector/scheduler.py` 생성
- `CollectorScheduler` 클래스:
  - `__init__(self, data_go_kr: DataGoKrCollector, kis_collector: KISCollector, ws_manager: WSSubscriptionManager, trade_strength: TradeStrengthCalculator, ws_client: KISWebSocketClient, redis: RedisClient)`: 전체 수집 모듈 주입
  - `_scheduler: AsyncIOScheduler` (APScheduler)
  - `async def start(self) -> None`: 스케줄러 시작 + job 등록
    - `add_job(self._premarket_collect, CronTrigger(hour=8, minute=0), misfire_grace_time=60)`
    - `add_job(self._etf_collect, CronTrigger(hour=8, minute=5), misfire_grace_time=60)`
    - `add_job(self._market_open, CronTrigger(hour=9, minute=0), misfire_grace_time=60)`
    - `add_job(self._market_close, CronTrigger(hour=15, minute=30), misfire_grace_time=60)`
  - `async def stop(self) -> None`: 스케줄러 종료
  - `async def _premarket_collect(self) -> None`: 08:00 공공데이터포털 전 종목 수집
  - `async def _etf_collect(self) -> None`: 08:05 ETF 시세 수집
  - `async def _market_open(self) -> None`: 09:00 WS 연결 + 구독 시작
    - WS 클라이언트의 on_data 콜백에 파서 + 체결강도 계산기 + Redis 캐싱 연결
  - `async def _market_close(self) -> None`: 15:30 WS 구독 해제 + 연결 종료
  - `async def _on_realtime_data(self, tr_id: str, raw_data: str) -> None`: WS 수신 콜백
    - tr_id에 따라 parse_execution / parse_orderbook 호출
    - 파싱 결과를 Redis에 TTL 5초로 캐싱 (키: `realtime:{stock_code}:execution`, `realtime:{stock_code}:orderbook`)
    - 체결 데이터면 trade_strength.add_execution() 호출
    - WS 미수신 10초 -> 해당 종목 데이터 무효화 (Redis 키 삭제)
  - `def get_status(self) -> dict`: 스케줄러 상태 조회 (running, next_run_time, job_count)
  - `async def trigger_premarket(self) -> dict`: 수동 트리거 (장전 수집)
  - `async def trigger_etf(self) -> dict`: 수동 트리거 (ETF 수집)

**Step 3: API 엔드포인트 구현**
- `backend/api/routes/collector.py` 생성
- `GET /api/v1/collector/status`: 수집 스케줄러 상태 조회
  - 응답: `{"running": bool, "next_jobs": [...], "ws_subscriptions": int, "last_premarket": str | null}`
- `POST /api/v1/collector/trigger/premarket`: 수동 장전 수집 트리거
  - 응답: `{"triggered": true, "result": {"stocks_collected": int}}`
- `POST /api/v1/collector/trigger/etf`: 수동 ETF 수집 트리거
  - 응답: `{"triggered": true, "result": {"etfs_collected": int}}`
- `GET /api/v1/collector/realtime/{stock_code}`: Redis에서 실시간 시세 조회
  - 응답: `{"execution": {...} | null, "orderbook": {...} | null, "trade_strength": float}`

**Step 4: API 테스트**
- `backend/tests/test_collector_api.py` 생성
  - `test_get_collector_status`: 상태 조회 API
  - `test_trigger_premarket`: 수동 트리거 API
  - `test_get_realtime_data`: 실시간 시세 조회 API
- 검증: `docker compose exec backend pytest tests/test_collector_api.py -v`
- 예상: PASS

**Step 5: 커밋**
```
git add backend/modules/collector/scheduler.py backend/api/routes/collector.py backend/tests/test_scheduler.py backend/tests/test_collector_api.py
git commit -m "feat(phase2-sprint1): task7 -- 수집 스케줄러 (APScheduler) + 수집 상태/트리거 API"
```

**완료 기준:**
- ✅ 장전/장중/장후 스케줄 job 등록
- ✅ WS 수신 콜백 -> 파서 -> Redis 캐싱 파이프라인
- ✅ misfire_grace_time 60초
- ✅ 수집 상태 조회 / 수동 트리거 API 동작

---

### Task 8: 통합 테스트 + main.py 연동

**Files:**
- Modify: `backend/main.py` (스케줄러 초기화/종료 + collector 라우터 등록)
- Test: `backend/tests/test_phase2_sprint1_integration.py`

**Step 1: main.py 연동**
- `backend/main.py` lifespan에 추가:
  - TradeStrengthCalculator 인스턴스 생성
  - WSSubscriptionManager 인스턴스 생성 (ws_client 주입)
  - DataGoKrCollector, KISCollector 인스턴스 생성
  - CollectorScheduler 인스턴스 생성 (모든 수집 모듈 주입)
  - `app.state`에 scheduler, ws_manager, trade_strength 저장
  - startup 시 scheduler.start(), shutdown 시 scheduler.stop()
- collector 라우터 등록: `app.include_router(collector_router, prefix="/api/v1")`
- 검증: `docker compose exec backend python -c "from main import app; print([r.path for r in app.routes])"`
- 예상: collector 라우트 포함

**Step 2: 통합 테스트 작성**
- `backend/tests/test_phase2_sprint1_integration.py` 생성
- 외부 API mock 기반 통합 테스트:
  - `test_premarket_collect_pipeline`: 공공데이터포털 mock -> stocks/market_data DB 저장 확인
  - `test_realtime_data_pipeline`: WS 데이터 mock -> 파싱 -> Redis 캐싱 -> 체결강도 계산
  - `test_collector_api_endpoints`: /collector/status, /collector/trigger/premarket 응답 확인
  - `test_etf_collect_pipeline`: ETF 수집 -> market_data 저장 확인
- 검증: `docker compose exec backend pytest tests/test_phase2_sprint1_integration.py -v`
- 예상: PASS

**Step 3: 전체 pytest**
- `docker compose exec backend pytest -v`
- 예상: 기존 테스트 + 신규 테스트 전부 PASS (회귀 없음)

**Step 4: 커밋**
```
git add backend/main.py backend/tests/test_phase2_sprint1_integration.py
git commit -m "feat(phase2-sprint1): task8 -- 통합 테스트 + main.py 스케줄러 연동"
```

**완료 기준:**
- ✅ main.py lifespan에 수집 모듈 초기화/종료
- ✅ collector 라우터 등록
- ✅ 통합 테스트 통과
- ✅ 전체 pytest 152 passed (회귀 없음)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 기존 + 신규 전부 passed |
| screening_results 테이블 | `docker compose exec postgres psql -U stockbot -c "\d screening_results"` | 테이블 구조 확인 |
| 수집 상태 API | `curl -s http://localhost:8000/api/v1/collector/status \| jq .` | `{"running": true, ...}` |
| 수동 트리거 API | `curl -s -X POST http://localhost:8000/api/v1/collector/trigger/premarket \| jq .` | `{"triggered": true, ...}` |
| 실시간 시세 API | `curl -s http://localhost:8000/api/v1/collector/realtime/005930 \| jq .` | `{"execution": ..., "trade_strength": ...}` |
| Alembic 상태 | `docker compose exec backend alembic current` | head 가리킴 |
