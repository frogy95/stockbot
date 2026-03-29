# Sprint 2: 종목 스크리닝 엔진 (Phase 2)

**Goal:** 1차 스크리닝(장전, DB 정적 필터) + 2차 스크리닝(장중, 실시간 동적 필터) + 팩터 스코어링(순위 백분위, 5팩터) 엔진을 구현하여 후보 종목 선별 파이프라인을 완성한다.

**Architecture:** 1차 스크리닝은 장전 공공데이터포털 수집 데이터(market_data 테이블)에서 거래량/시총/등락률 필터로 후보 30종목을 선별한다. 2차 스크리닝은 장중 Redis 실시간 데이터(체결강도, 호가잔량)로 30초 주기 동적 필터링한다. 팩터 스코어링은 5개 팩터(거래량/변동성/모멘텀/체결강도/호가잔량)를 순위 기반 백분위로 정규화하여 상위 20% 통과 종목을 screening_results 테이블에 기록한다. ETF는 호가잔량 대신 괴리율 팩터를 사용한다.

**Tech Stack:** SQLAlchemy async (DB 쿼리), Redis (실시간 데이터 조회), APScheduler (2차 스크리닝 30초 주기), httpx (REST 시세 조회)

**Sprint 기간:** 2026-03-29 ~
**이전 스프린트:** Phase 2 Sprint 1 (pytest 전체 통과, PR #5)
**브랜치명:** `phase2-sprint2`

---

## 제외 범위

- DART 재무 수집, 네이버 뉴스 센티멘트 (Sprint 3)
- 프론트엔드 UI (Phase 4)
- 텔레그램 알림 연동 (Phase 3)
- 수집 실패 폴백의 "전일 데이터 재사용" 로직 — 1차 스크리닝에서 전일 market_data 자동 활용하므로 별도 폴백 불필요
- 팩터 가중치 조정 (운영 1개월 후 — Phase 5)
- 분봉 데이터 수집/저장 (2차 스크리닝은 Redis 실시간 데이터만 사용)
- 적응형 임계값 (Phase 5 모니터링 후)
- stocks 마스터 seed 스크립트 (`seed_stocks.py`) — Sprint 1 공공데이터포털 수집기가 stocks 테이블 적재 담당, 별도 seed 불필요
- collector API 라우터 추가 수정 — Sprint 1에서 구현 완료, Sprint 2에서는 screening 전용 라우터만 신규 생성

---

## 실행 플랜

### Phase 1 (순차 — 필터/팩터 기초 모듈)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 필터 조건 정의 모듈 | 백엔드 | -- |
| Task 2 | 팩터 계산기 모듈 (주식 5팩터 + ETF 괴리율) | 백엔드 | -- |

### Phase 2 (병렬 가능 — 독립 스크리닝 엔진)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | 팩터 스코어링 엔진 (순위 백분위 + 가중 합산) | 백엔드 | -- |
| Task 4 | 1차 스크리닝 엔진 (장전 DB 정적 필터) | 백엔드 | -- |

### Phase 3 (순차 — Task 3, 4 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | 2차 스크리닝 엔진 (장중 실시간 동적 필터) | 백엔드 | -- |

### Phase 4 (순차 — Task 4, 5 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | 스크리닝 API + 스케줄러 연동 | 백엔드 | `feature-dev:feature-dev` |

### Phase 5 (순차 — 전체 의존)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 7 | 통합 테스트 + 회귀 검증 | 백엔드 | -- |

> **팀 실행**: Phase 2의 Task 3, Task 4는 파일 소유권이 겹치지 않으므로 병렬 실행 가능합니다.

---

### Task 1: 필터 조건 정의 모듈

**Files:**
- Create: `backend/modules/screening/filters.py`
- Test: `backend/tests/test_filters.py`

**Step 1: 테스트 작성**
- `backend/tests/test_filters.py` 생성
- 1차 필터 조건 객체 생성 및 기본값 확인 테스트
  - `PrimaryFilters` 기본값: volume_ratio=2.0, volume_min_stock=50000, volume_min_etf=10000, market_cap_min=50_000_000_000, change_rate_min=1.0, change_rate_max=7.0, max_candidates=30
- 2차 필터 조건 객체 생성 및 기본값 확인 테스트
  - `SecondaryFilters` 기본값: trade_strength_min=70, orderbook_ratio_min=1.2, screening_interval=30, no_signal_before="09:30"
- 필터 적용 헬퍼 함수 테스트
  - `passes_primary_filter(stock_data, filters)` -> bool: 종목 데이터가 1차 필터를 통과하는지 판단
  - 시총 미달, 거래량 미달, 등락률 범위 초과 등 케이스별 False 확인
  - 핫 종목 판정: `is_hot_stock(volume_ratio)` -> bool (500%+ 시 True)
- 검증: `docker compose exec backend pytest tests/test_filters.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 필터 모듈 구현**
- `backend/modules/screening/filters.py` 생성
- `PrimaryFilters` dataclass: Phase 2 확정 파라미터 값을 기본값으로 설정
- `SecondaryFilters` dataclass: Phase 2 확정 파라미터 값을 기본값으로 설정
- `passes_primary_filter(stock_data: dict, filters: PrimaryFilters) -> bool` 함수:
  - stock_data 딕셔너리 키: `volume`, `prev_volume`, `market_cap`, `change_rate`, `stock_type`
  - 거래량 비율 = volume / prev_volume (prev_volume=0이면 False)
  - ETF이면 volume_min_etf 적용, 아니면 volume_min_stock 적용
  - 시총 >= market_cap_min
  - change_rate_min <= change_rate <= change_rate_max
  - 모든 조건 통과 시 True
- `is_hot_stock(volume_ratio: float) -> bool` 함수: volume_ratio >= 5.0 시 True
- 검증: `docker compose exec backend pytest tests/test_filters.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/screening/filters.py backend/tests/test_filters.py
git commit -m "feat(phase2-sprint2): task1 -- 필터 조건 정의 모듈 (1차/2차 필터 + 핫 종목 판정)"
```

**완료 기준:**
- ⬜ pytest 테스트 통과
- ⬜ PrimaryFilters 기본값이 Phase 2 확정 파라미터와 일치

---

### Task 2: 팩터 계산기 모듈

**Files:**
- Create: `backend/modules/screening/factors.py`
- Create: `backend/modules/screening/etf_factors.py`
- Test: `backend/tests/test_factors.py`

**Step 1: 테스트 작성**
- `backend/tests/test_factors.py` 생성
- 주식 팩터 계산 테스트:
  - `calc_volume_factor(volume, prev_volume)` -> float: 전일 대비 거래량 비율. prev_volume=0이면 0.0
  - `calc_volatility_factor(highs: list[int], lows: list[int], closes: list[int])` -> float: ATR 5일. 입력 리스트 5개 요소. ATR = mean(max(H-L, abs(H-prevC), abs(L-prevC)) for each day). 첫날은 H-L만 사용
  - `calc_momentum_factor(closes: list[int])` -> float: 3일 단기 수익률 = (closes[-1] - closes[-4]) / closes[-4] * 100. closes 최소 4개 필요, 부족 시 0.0
  - `calc_trade_strength_factor(trade_strength: float)` -> float: 체결강도 그대로 반환 (0~100)
  - `calc_orderbook_ratio_factor(total_bid_volume: int, total_ask_volume: int)` -> float: 매수/매도 잔량 비율. total_ask_volume=0이면 0.0
- ETF 팩터 테스트:
  - `calc_tracking_error_factor(close_price: int, nav: float)` -> float: 괴리율 = abs((close_price - nav) / nav * 100). nav=0이면 0.0
- 에지 케이스: 입력 데이터 부족 시 중립값(0.0) 반환
- 검증: `docker compose exec backend pytest tests/test_factors.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 주식 팩터 구현**
- `backend/modules/screening/factors.py` 생성
- 5개 함수 구현:
  - `calc_volume_factor(volume: int, prev_volume: int) -> float`
  - `calc_volatility_factor(highs: list[int], lows: list[int], closes: list[int]) -> float` — ATR 5일 계산
  - `calc_momentum_factor(closes: list[int]) -> float` — 3일 수익률
  - `calc_trade_strength_factor(trade_strength: float) -> float` — pass-through
  - `calc_orderbook_ratio_factor(total_bid_volume: int, total_ask_volume: int) -> float` — 비율
- 모든 함수는 순수 함수, 외부 의존성 없음
- 검증: `docker compose exec backend pytest tests/test_factors.py -v -k "not etf"`
- 예상: PASS

**Step 3: ETF 팩터 구현**
- `backend/modules/screening/etf_factors.py` 생성
- `calc_tracking_error_factor(close_price: int, nav: float) -> float` 함수
- 검증: `docker compose exec backend pytest tests/test_factors.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/screening/factors.py backend/modules/screening/etf_factors.py backend/tests/test_factors.py
git commit -m "feat(phase2-sprint2): task2 -- 팩터 계산기 모듈 (주식 5팩터 + ETF 괴리율)"
```

**완료 기준:**
- ⬜ pytest 테스트 통과
- ⬜ ATR 5일, 3일 모멘텀 공식 정확
- ⬜ 데이터 부족 시 안전 기본값 반환

---

### Task 3: 팩터 스코어링 엔진

**Files:**
- Create: `backend/modules/screening/scorer.py`
- Test: `backend/tests/test_scorer.py`

**Step 1: 테스트 작성**
- `backend/tests/test_scorer.py` 생성
- `FactorScorer` 클래스 테스트:
  - `score_candidates(candidates: list[dict]) -> list[dict]`: 후보 종목 리스트를 받아 팩터별 순위 백분위 계산 후 가중 합산 스코어 추가
  - 입력 dict 키: `stock_code`, `stock_type`, `volume_factor`, `volatility_factor`, `momentum_factor`, `trade_strength_factor`, `orderbook_ratio_factor` (ETF는 `tracking_error_factor`)
  - 출력 dict에 `score`, `rank`, `factors` (팩터별 점수 dict), `is_passed` (score >= 80) 추가
- 순위 백분위 테스트:
  - 3개 종목, volume_factor=[100, 200, 300] → 백분위 = [33.3, 66.7, 100.0] (= rank/total * 100)
  - 동률 처리: 같은 값이면 같은 순위
- 가중 합산 테스트:
  - 5팩터 동일 가중(20%) 적용
  - 최종 score = sum(factor_percentile * 0.2)
- 통과 임계 테스트:
  - score >= 80이면 is_passed=True, 아니면 False
- ETF 팩터 분기 테스트:
  - stock_type="ETF"이면 orderbook_ratio_factor 대신 tracking_error_factor 사용 (괴리율은 낮을수록 좋으므로 역순위)
- 빈 리스트 입력 시 빈 리스트 반환
- 단일 종목 시 백분위 100.0
- 검증: `docker compose exec backend pytest tests/test_scorer.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 스코어러 구현**
- `backend/modules/screening/scorer.py` 생성
- `FactorScorer` 클래스:
  - 생성자: `factor_weights` 딕셔너리 (기본 동일 가중 0.2), `pass_threshold` (기본 80.0)
  - `STOCK_FACTORS = ["volume_factor", "volatility_factor", "momentum_factor", "trade_strength_factor", "orderbook_ratio_factor"]`
  - `ETF_FACTORS = ["volume_factor", "volatility_factor", "momentum_factor", "trade_strength_factor", "tracking_error_factor"]`
  - `score_candidates(candidates: list[dict]) -> list[dict]`:
    1. 주식/ETF 분리
    2. 각 그룹에서 팩터별 순위 계산 (값이 높을수록 좋은 팩터: 오름차순 순위, tracking_error는 역순위)
    3. 백분위 = rank / total * 100
    4. 가중 합산 score
    5. 전체 합쳐서 score 내림차순 정렬
    6. rank 부여 (1부터)
    7. is_passed = score >= pass_threshold
    8. factors dict에 팩터별 백분위 기록
- 검증: `docker compose exec backend pytest tests/test_scorer.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/screening/scorer.py backend/tests/test_scorer.py
git commit -m "feat(phase2-sprint2): task3 -- 팩터 스코어링 엔진 (순위 백분위 + 5팩터 가중 합산)"
```

**완료 기준:**
- ⬜ pytest 테스트 통과
- ⬜ 순위 기반 백분위 정규화 동작 확인
- ⬜ ETF 괴리율 역순위 처리 정확

---

### Task 4: 1차 스크리닝 엔진

**Files:**
- Create: `backend/modules/screening/screener.py`
- Test: `backend/tests/test_screener.py`

**Step 1: 테스트 작성**
- `backend/tests/test_screener.py` 생성
- `PrimaryScreener` 클래스 테스트 (DB 모킹 — 순수 로직 검증):
  - `screen(session: AsyncSession) -> list[dict]`: DB에서 market_data + stocks 조인 쿼리 → 필터 적용 → 스코어링 → 상위 30종목 반환
  - 반환 dict: `stock_code`, `stock_name`, `stock_type`, `market_type`, `score`, `rank`, `factors`, `is_hot`, `is_passed`, `volume`, `volume_ratio`, `market_cap`, `change_rate`
- 필터 적용 테스트 (인메모리):
  - `_apply_filters(rows: list[dict]) -> list[dict]`: 필터 통과 종목만 반환
  - 5종목 중 3종목 통과 시나리오
- 후보 상한 테스트:
  - 40종목 통과 시 스코어 상위 30종목만 반환
- 핫 종목 플래그 테스트:
  - 거래량 500%+ 종목에 is_hot=True
- DB 데이터 없음 시 빈 리스트 반환
- 검증: `docker compose exec backend pytest tests/test_screener.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 1차 스크리닝 엔진 구현**
- `backend/modules/screening/screener.py` 생성
- `PrimaryScreener` 클래스:
  - 생성자: `PrimaryFilters` (기본값 사용), `FactorScorer` 인스턴스
  - `async screen(session: AsyncSession) -> list[dict]`:
    1. market_data 테이블에서 당일(또는 최신) + 전일 데이터 조회 (stocks 조인으로 stock_name, stock_type, market_type 포함)
    2. 쿼리: `SELECT md.*, s.stock_name, s.stock_type, s.market_type FROM market_data md JOIN stocks s ON md.stock_code = s.stock_code WHERE md.data_date >= (최근 2일) AND s.is_active = true`
    3. 종목별로 당일/전일 데이터 매핑 → volume_ratio 계산
    4. `passes_primary_filter()` 적용
    5. 팩터 계산: `calc_volume_factor`, `calc_momentum_factor` (market_data에서 최근 4일 close 필요 — 없으면 중립값), `calc_volatility_factor` (최근 5일 H/L/C — 없으면 중립값)
    6. 체결강도/호가잔량은 1차에서 미사용 → 중립값 50.0, 1.0
    7. `FactorScorer.score_candidates()` 호출
    8. 상위 max_candidates(30)개 추출
    9. is_hot 플래그 추가
  - `async _get_recent_market_data(session, days=5) -> dict[str, list[MarketData]]`: 종목별 최근 N일 데이터 조회
  - `async save_results(session: AsyncSession, results: list[dict]) -> int`: screening_results 테이블에 결과 저장 (screening_type="primary")
- 검증: `docker compose exec backend pytest tests/test_screener.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/screening/screener.py backend/tests/test_screener.py
git commit -m "feat(phase2-sprint2): task4 -- 1차 스크리닝 엔진 (DB 정적 필터 + 팩터 스코어링)"
```

**완료 기준:**
- ⬜ pytest 테스트 통과
- ⬜ 필터 조건이 Phase 2 확정 파라미터와 일치
- ⬜ 후보 상한 30종목 제한 동작

---

### Task 5: 2차 스크리닝 엔진

**Files:**
- Create: `backend/modules/screening/realtime_screener.py`
- Test: `backend/tests/test_realtime_screener.py`

**Step 1: 테스트 작성**
- `backend/tests/test_realtime_screener.py` 생성
- `RealtimeScreener` 클래스 테스트:
  - `async screen(candidate_codes: list[str], session: AsyncSession) -> list[dict]`: 1차 후보 종목에 대해 실시간 데이터(Redis) 기반 2차 필터 적용
  - 반환 dict: `stock_code`, `stock_name`, `stock_type`, `score`, `rank`, `factors`, `is_passed`, `trade_strength`, `orderbook_ratio`
- 필터 적용 테스트 (Redis mock):
  - 체결강도 70+ 통과, 미달 제외
  - 호가잔량 비율 1.2+ 통과, 미달 제외
  - 시초가 구간(09:00~09:30) 내에서는 빈 리스트 반환
- 스코어링 통합 테스트:
  - 2차 스크리닝 통과 종목에 팩터 스코어링 적용
  - 실시간 체결강도, 호가잔량이 팩터에 반영되어 스코어 갱신
- Redis 데이터 없는 종목 스킵
- 검증: `docker compose exec backend pytest tests/test_realtime_screener.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 2차 스크리닝 엔진 구현**
- `backend/modules/screening/realtime_screener.py` 생성
- `RealtimeScreener` 클래스:
  - 생성자: `SecondaryFilters`, `FactorScorer`, `RedisClient`, `TradeStrengthCalculator`
  - `async screen(candidate_codes: list[str], session: AsyncSession) -> list[dict]`:
    1. 현재 시각 확인 — no_signal_before("09:30") 이전이면 빈 리스트 반환
    2. 각 candidate_code에 대해:
       a. Redis에서 `realtime:{code}:execution`, `realtime:{code}:orderbook` 조회
       b. 데이터 없으면 스킵
       c. TradeStrengthCalculator에서 체결강도 조회
       d. 호가잔량 비율 = total_bid_volume / total_ask_volume
       e. SecondaryFilters 조건 적용 (trade_strength_min, orderbook_ratio_min)
    3. 통과 종목에 대해 팩터 계산 (DB에서 market_data 최근 데이터 + 실시간 데이터 조합)
    4. `FactorScorer.score_candidates()` 호출
    5. screening_results 테이블에 결과 저장 (screening_type="secondary")
  - `_is_no_signal_period() -> bool`: 시초가 구간 판단 (09:00~09:30)
  - `async _get_realtime_data(code: str) -> dict | None`: Redis에서 실시간 데이터 조회
- 검증: `docker compose exec backend pytest tests/test_realtime_screener.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/modules/screening/realtime_screener.py backend/tests/test_realtime_screener.py
git commit -m "feat(phase2-sprint2): task5 -- 2차 스크리닝 엔진 (실시간 동적 필터 + 시초가 구간 제외)"
```

**완료 기준:**
- ⬜ pytest 테스트 통과
- ⬜ 체결강도 70+, 호가잔량 1.2+ 필터 동작
- ⬜ 시초가 구간(09:00~09:30) 신호 금지 동작

---

### Task 6: 스크리닝 API + 스케줄러 연동

**skill:** `feature-dev:feature-dev`

**Files:**
- Create: `backend/api/routes/screening.py`
- Modify: `backend/main.py` (screening 라우터 등록 + 스크리닝 스케줄러 초기화)
- Modify: `backend/modules/collector/scheduler.py` (1차 스크리닝 스케줄 추가 + 2차 스크리닝 30초 주기 추가 + WS 구독 연동)
- Test: `backend/tests/test_screening_api.py`

**Step 1: 테스트 작성**
- `backend/tests/test_screening_api.py` 생성
- API 엔드포인트 테스트:
  - `GET /api/v1/screening/primary` — 최신 1차 스크리닝 결과 조회
    - 응답: `{"results": [...], "screened_at": "...", "total": N}`
  - `GET /api/v1/screening/secondary` — 최신 2차 스크리닝 결과 조회
    - 응답: `{"results": [...], "screened_at": "...", "total": N}`
  - `POST /api/v1/screening/trigger/primary` — 수동 1차 스크리닝 트리거
    - 응답: `{"triggered": true, "result": {"candidates": N, "passed": M}}`
  - `POST /api/v1/screening/trigger/secondary` — 수동 2차 스크리닝 트리거
    - 응답: `{"triggered": true, "result": {"candidates": N, "passed": M}}`
  - `GET /api/v1/screening/status` — 스크리닝 상태 조회
    - 응답: `{"primary_last_run": "...", "secondary_last_run": "...", "secondary_interval": 30, ...}`
- 검증: `docker compose exec backend pytest tests/test_screening_api.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 스크리닝 API 라우터 구현**
- `backend/api/routes/screening.py` 생성
- `router = APIRouter(tags=["screening"])`
- 5개 엔드포인트 구현:
  - `GET /screening/primary`: screening_results 테이블에서 screening_type="primary", 최신 screened_at 기준 조회
  - `GET /screening/secondary`: screening_results 테이블에서 screening_type="secondary", 최신 screened_at 기준 조회
  - `POST /screening/trigger/primary`: app.state에서 PrimaryScreener 가져와 실행
  - `POST /screening/trigger/secondary`: app.state에서 RealtimeScreener 가져와 실행
  - `GET /screening/status`: 스크리닝 관련 상태 정보
- DB 세션은 `Depends(get_db)` 사용
- 검증: `docker compose exec backend pytest tests/test_screening_api.py -v -k "primary or secondary"`
- 예상: PASS (API 단위)

**Step 3: 스케줄러 연동**
- `backend/modules/collector/scheduler.py` 수정:
  - `CollectorScheduler.__init__`에 `PrimaryScreener`, `RealtimeScreener` 인스턴스 추가
  - 장전 08:10 스케줄: 1차 스크리닝 실행 → 결과로 WS 구독 목록 업데이트 (`ws_manager.subscribe`)
  - 장중 09:30~15:30 30초 주기: 2차 스크리닝 실행 (IntervalTrigger)
  - 장후 15:30에 2차 스크리닝 중지
  - 기존 _premarket_collect 후 1차 스크리닝 호출하는 것이 아니라 별도 job으로 등록 (08:10 — 공공데이터포털 08:00 수집 완료 후)
- `backend/main.py` 수정:
  - `from modules.screening.screener import PrimaryScreener`
  - `from modules.screening.realtime_screener import RealtimeScreener`
  - `from api.routes.screening import router as screening_router`
  - lifespan에서 PrimaryScreener, RealtimeScreener 인스턴스 생성
  - app.state에 저장: `app.state.primary_screener`, `app.state.realtime_screener`
  - CollectorScheduler 생성자에 screener 인스턴스 전달
  - screening_router를 `/api/v1` 프리픽스로 등록
- 검증: `docker compose exec backend pytest tests/test_screening_api.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/api/routes/screening.py backend/tests/test_screening_api.py backend/modules/collector/scheduler.py backend/main.py
git commit -m "feat(phase2-sprint2): task6 -- 스크리닝 API + 스케줄러 연동 (1차 08:10, 2차 30초 주기)"
```

**완료 기준:**
- ⬜ pytest 테스트 통과
- ⬜ API 5개 엔드포인트 정상 응답
- ⬜ 스케줄러에 1차(08:10), 2차(30초 주기) job 등록
- ⬜ 1차 스크리닝 후 WS 구독 목록 자동 업데이트

---

### Task 7: 통합 테스트 + 회귀 검증

**Files:**
- Create: `backend/tests/test_phase2_sprint2_integration.py`
- Modify: `backend/modules/screening/__init__.py` (모듈 export 정리)

**Step 1: 통합 테스트 작성**
- `backend/tests/test_phase2_sprint2_integration.py` 생성
- 전체 파이프라인 테스트:
  - FastAPI 앱 생성 → lifespan 초기화 → screening 라우터 포함 확인
  - `GET /api/v1/screening/primary` 200 응답
  - `GET /api/v1/screening/secondary` 200 응답
  - `GET /api/v1/screening/status` 200 응답
  - OpenAPI 스펙에 screening 엔드포인트 포함 확인
- 회귀 테스트:
  - `GET /api/v1/health` 200 정상
  - `GET /api/v1/collector/status` 200 정상
  - `GET /api/v1/settings` 200 정상
- 검증: `docker compose exec backend pytest tests/test_phase2_sprint2_integration.py -v`
- 예상: PASS

**Step 2: 모듈 __init__.py 정리**
- `backend/modules/screening/__init__.py` 수정
- 주요 클래스 export: `PrimaryScreener`, `RealtimeScreener`, `FactorScorer`
- 검증: `docker compose exec backend python -c "from modules.screening import PrimaryScreener, RealtimeScreener, FactorScorer; print('OK')"`
- 예상: OK

**Step 3: 전체 테스트**
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (기존 테스트 포함)

**Step 4: 커밋**
```
git add backend/tests/test_phase2_sprint2_integration.py backend/modules/screening/__init__.py
git commit -m "feat(phase2-sprint2): task7 -- 통합 테스트 + 회귀 검증"
```

**완료 기준:**
- ⬜ 통합 테스트 통과
- ⬜ 기존 Sprint 1 테스트 회귀 없음
- ⬜ 전체 pytest PASS

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 passed (기존 + 신규) |
| 1차 스크리닝 API | `curl -s http://localhost:8000/api/v1/screening/primary \| jq .` | `{"results": [...], "total": N}` |
| 2차 스크리닝 API | `curl -s http://localhost:8000/api/v1/screening/secondary \| jq .` | `{"results": [...], "total": N}` |
| 수동 1차 트리거 | `curl -s -X POST http://localhost:8000/api/v1/screening/trigger/primary \| jq .` | `{"triggered": true, ...}` |
| 수동 2차 트리거 | `curl -s -X POST http://localhost:8000/api/v1/screening/trigger/secondary \| jq .` | `{"triggered": true, ...}` |
| 스크리닝 상태 | `curl -s http://localhost:8000/api/v1/screening/status \| jq .` | 상태 정보 JSON |
| 스케줄러 상태 | `curl -s http://localhost:8000/api/v1/collector/status \| jq .` | 신규 job 포함 |
| OpenAPI 스펙 | `curl -s http://localhost:8000/openapi.json \| jq '.paths \| keys'` | screening 경로 포함 |
