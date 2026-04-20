# Phase 4.10: ETF 2차 스크리닝 근본 해결 + NAV 파이프라인 구축 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-20)
> **ROADMAP 참조**: `ROADMAP.md` Phase 4.10
> **프로덕션 장애 대응**: 2026-04-20 Railway 로그 기준 2차 스크리닝 31% 실패율 (45회 중 14회 KeyError: 'tracking_error_factor')
> **검토 리포트**:
>
> - `phase4.10-po-review.md` (정프로, PO)
> - `phase4.10-risk-review.md` (최리스크, 리스크관리)
> - `phase4.10-trader-review.md` (김단타, 단타 전문가)
> - `phase4.10-api-review.md` (윤에이피, API 개발자)

---

## 개요

프로덕션 2차 스크리닝(`RealtimeScreener`)이 ETF 후보가 필터를 통과할 때 **확정 크래시**하는 치명적 결함을 근본 해결한다. 크래시는 해당 배치의 **주식 신호까지 동반 소실**시키는 SPOF 전파 구조를 유발하므로, 단순 예외 처리가 아닌 구조적 재설계가 필요하다.

### 장애 파이프라인

```
ETF 후보 1차 스크리닝 통과 (Phase 4.7 PRIMARY_FACTORS 3팩터로 스코어)
  ↓
WS 구독 → 2차 필터 통과 (trade_strength, orderbook_ratio)
  ↓
_build_candidates 블록: factor_candidates dict 생성
  ├─ 주식: orderbook_ratio_factor 포함
  └─ ETF:  tracking_error_factor 누락 ← 원인 1
  ↓
FactorScorer.score_candidates(candidates)
  ↓
etfs = [c for c in candidates if stock_type == "ETF"]
_calc_percentiles(etfs, ETF_FACTORS)  # ETF_FACTORS에 tracking_error_factor 포함
  ↓
values = [c["tracking_error_factor"] for c in etfs]  # KeyError ← 원인 2
  ↓
스코어링 함수 예외 전파 → 2차 스크리닝 배치 전체 실패
  ↓
주식 신호까지 동반 소실 ← 파생 리스크 A (SPOF 전파)
```

### 근본 원인 요약

1. **NAV 데이터 파이프라인 부재**: `calc_tracking_error_factor(close_price, nav)`가 정의만 되어 있고 호출 경로 없음. NAV 데이터가 Redis/DB 어디에도 저장되지 않음
2. **스크리닝 로직 분기 누락**: `realtime_screener.py:165-189` `factor_candidates` 구성 시 주식/ETF 구분 없이 `orderbook_ratio_factor`만 포함
3. **scorer 계약 불일치**: `scorer.py:97-116`의 `ETF_FACTORS` 기본값이 `tracking_error_factor`를 요구하지만 호출측이 제공하지 않음
4. **격리 부재**: ETF 스코어링 실패가 주식 스코어링 결과까지 파괴 (파생 리스크 A)
5. **테스트 공백**: `test_realtime_screener.py`에 ETF 케이스 전무
6. **과거 패턴 재발**: 커밋 `ade1d9d`(2026-03-30)에서 1차 스크리너에 동일 버그를 `tracking_error_factor=0.0` 임시 처리로 미봉책 적용했으나 2차에 전파되지 않음 — **임시 폴백의 영구화/미전파 리스크**

### 아키텍처 방향 (4인 검토 수렴)

```
Sprint 1 (긴급 지혈, 2026-04-21 장 개시 전 배포 목표)
  ├─ realtime_screener._build_candidates에 ETF 분기 추가 (tracking_error_factor=0.0 폴백)
  ├─ scorer.score_candidates에 stock/ETF try/except 격리 (SPOF 전파 차단)
  ├─ 레버리지/인버스 ETF는 NAV 폴백 시 signal_generator에서 완전 제외
  └─ ETF 회귀 테스트 3건 이상

Sprint 2 (NAV 실시간 연동, Sprint 1 24시간 관찰 후 착수)
  ├─ KIS inquire-price 응답의 nav/etf_dspr 필드 Redis 캐시화 (TTL 30초, DB 스키마 변경 없음)
  ├─ RealtimeScreener가 Redis nav → calc_tracking_error_factor 연동 (폴백 경로 유지)
  ├─ etf_pipeline_healthy 플래그 신설 (주식 경로와 독립)
  └─ Sprint 1 폴백 로그 모니터링 (영구화 방지)

Sprint 3 (정식 운영 + 리스크 안전장치)
  ├─ 괴리율 절대 컷오프 (일반 ETF 2%, 레버리지/인버스 1.5%)
  ├─ Stock.etf_leverage_type 필드 추가 (Alembic 1회 마이그레이션)
  ├─ PrimaryFilters.etf_max_tracking_error = 3.0 (1차 조기 필터링)
  ├─ ScreeningResult.factors에 tracking_error_value 원값 저장
  ├─ Sprint 1 폴백 제거 게이트 (일간 폴백 사용률 <1% 확인 후)
  └─ wiki/data-collection-flow.md, wiki/external-apis.md 업데이트
```

### 필요 선행 데이터 및 축적 기간

| 항목 | 상태 | 비고 |
|------|------|------|
| 선행 데이터 축적 | **불필요** | NAV는 장중 실시간 조회(iNAV) 방식. EOD NAV 누적 불필요 |
| 데이터 의존성 | 없음 | KIS API 즉시 호출 가능 |
| 착수 가능 시점 | **즉시** | 프로덕션 장애 대응으로 최우선 |

> ROADMAP.md "Phase 데이터 의존성 관리 원칙" 1~4 검증 완료: 본 Phase는 즉시 착수 가능.

---

## 검토팀 확정 파라미터 (2026-04-20)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 김단타(단타 전문가), 윤에이피(API 개발자) — 4명

### A. Sprint 구성

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| A1 | Sprint 분할 | 단일 또는 통합 Sprint | **3개 Sprint (긴급 폴백 / NAV 연동 / 정식 운영)** | 31% 장애 진행 중, 긴급 지혈과 정식 구축 분리 필수. 전원 합의 | PO |
| A2 | Sprint 1 배포 목표 | 미정 | **2026-04-21 장 개시 전(KST 09:00 이전)** | 매 거래일 31% 실패 누적 차단 | PO |
| A3 | Sprint 2 착수 조건 | 즉시 | **Sprint 1 프로덕션 24시간 PAPER + 72시간 LIVE 관찰 통과** | 폴백 회귀/동작 검증 | 리스크 |
| A4 | Phase 7.0 Sprint 3 LIVE 게이트 | Phase 4.10 미반영 | **"Phase 4.10 Sprint 2 완료"를 LIVE 전환 체크리스트에 추가** | LIVE 31% 소실 차단 | 리스크 |

### B. Sprint 1: 긴급 지혈 (2026-04-21 목표)

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| B1 | ETF 분기 폴백 값 | 미정 | **`tracking_error_factor=0.0`** | 일반 ETF는 매매 유지, 레버리지는 별도 처리(B3) | PO |
| B2 | scorer 격리 | 없음 | **`FactorScorer.score_candidates` 내부에서 stock/ETF 각각 try/except 분리** | SPOF 전파 차단. ETF 실패 시 주식 결과는 정상 반환 | 리스크 |
| B3 | 레버리지/인버스 ETF 처리 | 일반 ETF와 동일 | **NAV 폴백 상태에서는 signal_generator에서 완전 제외** | 레버리지 변동성 2배, 괴리 검증 없이 매수 절대 금지 | 리스크 + 단타 |
| B4 | 레버리지 ETF 임시 분류 방식 | 없음 | **종목명 패턴 매칭 ("레버리지", "2X", "2배", "인버스", "곱버스")** | Sprint 3에서 `etf_leverage_type` 필드로 정식화 | 단타 |
| B5 | 폴백 사용 감시 로깅 | 없음 | **ETF 스코어링마다 `logger.warning("ETF {code} NAV 폴백 사용 중")`** | 영구화 방지 + Sprint 3 제거 시 zero-log 검증 기준 | 리스크 |
| B6 | 코드 주석 의무 | 없음 | **`# FIXME(phase4.10-sprint2): NAV 연동으로 교체` 주석 필수** | Sprint 2 완료 시 grep으로 전량 제거 검증 | PO |
| B7 | scorer `.get()` 방어 | 직접 접근 (KeyError) | **`c.get(factor, 0.0)` 방식으로 변경** | Phase 4.7 미해결 #7 해소. 방어적 프로그래밍 | 리스크 + PO |
| B8 | 회귀 테스트 | 없음 | **`test_realtime_screener.py`에 ETF 시나리오 최소 3건** (KeyError 재현 / 주식+ETF 혼합 / 레버리지 ETF 제외) | 재발 방지 회귀 테스트 | PO |
| B9 | PAPER 사전 검증 | 없음 | **Sprint 1 LIVE 배포 전 PAPER에서 ETF 후보 2차 통과 시나리오 재현 필수** | KIS 모의 동작 차이 방어 | 리스크 + API |

### C. Sprint 2: NAV 실시간 연동

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| C1 | NAV 데이터 소스 | 4개 후보 (KIS / pykrx / KRX / 네이버) | **KIS inquire-price 응답의 `nav`, `etf_dspr`, `etf_ntas_aset_tval` 필드 직접 사용** | 기존 API 재활용, 별도 연동 없음, iNAV 실시간성 확보 | API |
| C2 | NAV 종류 | EOD 또는 iNAV 미지정 | **장중 iNAV만 사용** | 단타 스코어링은 장중 실시간 iNAV 필요. EOD는 백테스트용 (Phase 9로 보류) | 단타 + API |
| C3 | NAV 캐싱 위치 | DB 컬럼 | **Redis `realtime:{code}:etf_nav` (TTL 30초)** | 장중 실시간만 필요, 시계열 DB 불필요 | API |
| C4 | DB 스키마 변경 | `market_data.nav` 컬럼 추가 | **Phase 4.10에서는 변경 없음 (Sprint 3에서 `Stock.etf_leverage_type`만 추가)** | 장중 iNAV는 Redis로 충분. market_data.nav는 Phase 9에서 결정 | API + PO |
| C5 | NAV 갱신 트리거 | 백그라운드 주기 갱신 | **방식 A: 2차 스크리닝 ETF 판정 시점에 동반 호출** | 타임슬라이스 동기화, 호출 빈도 최소화 | API |
| C6 | KIS inquire_client 환경 | 미지정 | **LIVE 고정** (Phase 4.6 원칙) | 시세 조회는 LIVE 도메인 | API |
| C7 | KIS 응답 필드 단위 검증 | 없음 | **Sprint 2 Task 1: 모의거래에서 069500/122630/114800 샘플 조회 → nav 타입/단위 확인 필수** | 문서와 실제 차이 방어. 스케일 오류 방지 | API |
| C8 | 재시도 정책 | 미지정 | **3회 재시도 + 500ms 백오프, Phase 6 Sprint 2 로직 재사용** | 기존 패턴 준수 | API |
| C9 | NAV 수집 최소 성공률 | 미지정 | **활성 ETF의 90% 이상** | 미만 시 `etf_pipeline_healthy=false` | 리스크 |
| C10 | NAV 최대 노후 허용 | 미지정 | **2거래일** (Redis 캐시 만료 전제) | 스크리닝 신선도 기준 | 리스크 |
| C11 | etf_pipeline_healthy 플래그 | 없음 | **신설, 주식 경로와 독립** | ETF 장애가 주식 매매를 막지 않도록 분리 | 리스크 + API |
| C12 | NAV 장애 알림 | 없음 | **텔레그램 즉시 (Phase 4.9 `_send_stale_data_alert` 패턴 재사용)** | 운영 가시성 | 리스크 |
| C13 | WS ETF NAV 스트림 조사 | 없음 | **Sprint 2 Task 1에서 KIS WS에 ETF NAV 실시간 TR 존재 여부 조사** | REST 대신 WS 가능 시 채택 검토 | API |
| C14 | 폴백 경로 유지 | Sprint 2 배포 시 제거 | **Sprint 2에서는 폴백 유지, Sprint 3에서 제거 게이트 통과 후 제거** | 점진 전환 | API + PO |

### D. Sprint 3: 정식 운영 + 리스크 안전장치

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| D1 | 일반 ETF 괴리율 절대 컷오프 | 없음 | **`SecondaryFilters.etf_max_tracking_error = 2.0` (2%)** | 유동성/스프레드 안전선 | 단타 |
| D2 | 레버리지/인버스 괴리율 절대 컷오프 | 없음 | **1.5% (`etf_max_tracking_error_leveraged = 1.5`)** | 변동성 2배 | 단타 + 리스크 |
| D3 | 1차 스크리닝 ETF 조기 필터 | 없음 | **`PrimaryFilters.etf_max_tracking_error = 3.0`** (전일 EOD 기준 — KIS 일봉 수집 시 nav 동반) | 1차에서 과괴리 ETF 조기 차단, WS 슬롯 낭비 방지 | 단타 |
| D4 | 괴리율 경고 임계값 | 없음 | **> 1% 시 warning 로깅** | Sprint 3 배포 후 분포 관찰용 | 단타 |
| D5 | 원값 저장 | 없음 | **`ScreeningResult.factors["tracking_error_value"]`에 괴리율 원값(%) 저장** | 백분위 외 원값 기반 분석 가능 | 단타 |
| D6 | ETF 타입 분류 필드 | 없음 | **`Stock.etf_leverage_type` 컬럼 추가 (`normal` / `leverage_2x` / `inverse` / `inverse_2x`)** | Alembic 1회. Sprint 1 패턴 매칭 → 정식 필드로 승격 | 단타 |
| D7 | Sprint 1 폴백 제거 게이트 | 없음 | **일간 폴백 사용률 < 1%가 3거래일 연속 유지될 때 폴백 제거 PR 생성** | 영구화 방지 + 안정성 검증 | 리스크 + PO |
| D8 | ETF 필터 탈락률 모니터링 | 없음 | **Sprint 3 배포 후 1주일간 ETF 필터 탈락률 로깅 필수. 30% 이상이면 컷오프 상향(2% → 2.5%) 검토** | 과도 차단 방지 | 단타 |
| D9 | Wiki 업데이트 | 없음 | **`wiki/data-collection-flow.md`에 NAV 수집 플로우 추가, `wiki/external-apis.md`에 KIS inquire-price ETF 필드 섹션 추가** | 현재 상태 문서 최신화 | PO |

### E. 임계값 요약표

| 대상 | 1차 스크리닝 (Sprint 3) | 2차 스크리닝 (Sprint 3) | 신호 생성 단계 |
|------|----------------------|----------------------|--------------|
| 일반 ETF | 전일 EOD 괴리율 > 3% 제외 | 장중 iNAV 괴리율 > 2% 제외, > 1% warning | (컷오프 통과 시 진행) |
| 레버리지/인버스 ETF | 전일 EOD 괴리율 > 3% 제외 | 장중 iNAV 괴리율 > 1.5% 제외 | NAV 폴백 상태면 완전 제외 (Sprint 1부터) |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 | 예상 기간 |
|--------|------|----------|--------|---------|
| 1 | 긴급 지혈 — ETF 분기 폴백 + SPOF 격리 | realtime_screener ETF 분기 (폴백 0.0), scorer 격리(try/except), 레버리지 ETF 제외, scorer .get() 방어, ETF 회귀 테스트 3건+ | 없음 | 0.5~1일 (2026-04-21 장 개시 전) |
| 2 | NAV 실시간 연동 — KIS inquire-price 응답 필드 활용 | KIS inquire-price ETF 샘플 검증(Task 1), ETF NAV 조회 래퍼 `get_etf_nav(code)`, Redis `realtime:{code}:etf_nav` 캐시, screener Redis 연동, etf_pipeline_healthy 플래그, 텔레그램 알림 | Sprint 1 배포 후 24h(PAPER) + 72h(LIVE) 관찰 통과 | 1~2일 |
| 3 | 정식 운영 + 리스크 안전장치 | 괴리율 절대 컷오프(2%/1.5%), Stock.etf_leverage_type Alembic 마이그레이션, PrimaryFilters.etf_max_tracking_error=3.0, ScreeningResult 원값 저장, Sprint 1 폴백 제거, wiki 업데이트 | Sprint 2 배포 + 3일 관찰 (폴백 사용률 < 1%) | 1.5~2일 |

---

## Sprint 1 상세 — 긴급 지혈

### 작업 순서

1. **scorer.py 방어 로직** — `_calc_percentiles`에서 `c[factor]` → `c.get(factor, 0.0)` 변경
2. **scorer.py 격리 분리** — `score_candidates` 내부에서 stock/ETF 각각 try/except로 분리. ETF 실패 시 주식 결과는 정상 반환
3. **realtime_screener.py ETF 분기 추가** — `_build_candidates` 블록에서 stock_type=ETF면 `tracking_error_factor=0.0` 주입, 주식은 `orderbook_ratio_factor`만
4. **FIXME 주석 + warning 로깅** — 폴백 사용 시 `logger.warning` + 코드에 `# FIXME(phase4.10-sprint2):` 주석
5. **signal_generator 레버리지 ETF 제외** — 종목명 패턴 매칭으로 NAV 폴백 상태 레버리지/인버스 ETF를 신호 생성에서 제외
6. **ETF 회귀 테스트 3건+** — KeyError 재현 테스트(수정 전 실패 / 수정 후 성공), 주식+ETF 혼합 스코어링 테스트, 레버리지 ETF 제외 테스트
7. **PAPER 재현 검증** — 수동: ETF 후보가 2차 필터 통과하는 시나리오 재현, 크래시 없음 + 주식도 정상 반환 확인
8. **LIVE 배포 (2026-04-21 장 개시 전)**

### 백엔드

| 파일 | 변경 | 설명 |
|------|------|------|
| `backend/modules/screening/scorer.py` | **수정** | `_calc_percentiles` 내부 `c[factor]` → `c.get(factor, 0.0)`. `score_candidates` 내부 stock/ETF try/except 격리 분리 (`try: scored.extend(_calc_percentiles(stocks, self._stock_factors)) except Exception: logger.error(...)` 동일 패턴 ETF에도 적용) |
| `backend/modules/screening/realtime_screener.py` | **수정** | `factor_candidates.append(...)` 블록에서 `stock_type == "ETF"` 분기 추가. ETF인 경우 `"tracking_error_factor": 0.0` 주입 + `logger.warning` + `# FIXME(phase4.10-sprint2):` 주석 |
| `backend/modules/trading/signal_generator.py` | **수정** | ScreeningResult 소비 단계에서 stock_type=ETF이고 종목명에 레버리지/인버스 패턴 포함 시 신호 생성 스킵 (임시 패턴 매칭 — Sprint 3에서 etf_leverage_type 필드로 교체) |
| `backend/tests/test_realtime_screener.py` | **신규/수정** | ETF 시나리오 테스트 3건 추가: (1) ETF 단독 2차 통과 크래시 없음 검증, (2) 주식+ETF 혼합 시 양쪽 모두 스코어 부여 + 배치 생존, (3) 레버리지 ETF는 signal_generator 입력에서 제외됨 |
| `backend/tests/test_scorer.py` | **수정** | `_calc_percentiles` 결측 키 방어 테스트 추가 (tracking_error_factor 없는 ETF 입력 시 0.0 처리 + 크래시 없음) |
| `backend/tests/test_signal_generator.py` | **수정** | 레버리지 ETF(122630 등) 입력 시 신호 생성 스킵 검증 |

### 프론트엔드

Sprint 1 프론트엔드 변경 없음.

### 재사용 자산

| 기존 모듈 | 활용 |
|----------|------|
| `FactorScorer._calc_percentiles` | 기존 함수에 `.get()` 방어만 추가 |
| `FactorScorer.score_candidates` | 기존 로직에 try/except 래핑 추가 |
| `RealtimeScreener._build_candidates` (실질적으로 `screen()` 165-189 블록) | 기존 구조 유지, 분기문만 삽입 |
| 텔레그램 알림(`notifier`) | Sprint 1에서는 warning 로깅으로 충분, 텔레그램 미사용 |
| 종목명 패턴 매칭 | Sprint 2 완료 후 Sprint 3에서 `Stock.etf_leverage_type` 필드로 정식 교체 예정 |

---

## Sprint 2 상세 — NAV 실시간 연동 (개요)

> 상세 작업 계획은 Sprint 2 착수 시 `docs/phase/phase4.10/sprint2/sprint2.md`에서 전개.

### 핵심 Task

1. **Task 1 (선행 조사)**: 모의거래에서 069500(KODEX 200), 122630(KODEX 레버리지), 114800(KODEX 인버스) 3종 샘플로 `inquire-price` 호출 → nav/etf_dspr 필드 타입·단위·스케일 검증 + KIS WS에 ETF NAV 스트림 존재 여부 확인
2. **Task 2**: `kis_collector.py`에 `get_etf_nav(code)` 메서드 추가 (3회 재시도 + 500ms 백오프)
3. **Task 3**: Redis 캐시 `realtime:{code}:etf_nav` 저장 로직 (TTL 30초, JSON: `{"nav": float, "etf_dspr": float, "updated_at": iso}`)
4. **Task 4**: `realtime_screener.py`에서 Redis nav 조회 → `calc_tracking_error_factor` 실제 값 계산 (폴백 경로 유지)
5. **Task 5**: `etf_pipeline_healthy` 플래그 신설 (기존 `pipeline_healthy`와 독립), NAV 수집 실패율 > 10% 시 false
6. **Task 6**: NAV 장애 텔레그램 알림 (`_send_stale_data_alert` 패턴 재사용)
7. **Task 7**: Sprint 2 통합 테스트 + PAPER 검증

### 주요 파일

| 파일 | 변경 |
|------|------|
| `backend/modules/collector/sources/kis_collector.py` | **수정** — `get_etf_nav(code)` 메서드 추가 |
| `backend/modules/screening/realtime_screener.py` | **수정** — Redis nav 조회 → `calc_tracking_error_factor` 호출. 폴백 경로 유지(Sprint 3에서 제거) |
| `backend/modules/collector/scheduler.py` | **수정** — `etf_pipeline_healthy` 플래그 관리. NAV 장애 알림 |
| `backend/core/redis.py` | **검증만** — 기존 `realtime:{code}:*` 패턴 활용 |
| 테스트 | **추가** — `test_kis_etf_nav.py`, `test_realtime_screener_nav.py` |

---

## Sprint 3 상세 — 정식 운영 + 리스크 안전장치 (개요)

> 상세 작업 계획은 Sprint 3 착수 시 `docs/phase/phase4.10/sprint3/sprint3.md`에서 전개.

### 핵심 Task

1. **Task 1**: `SecondaryFilters`에 `etf_max_tracking_error=2.0`, `etf_max_tracking_error_leveraged=1.5` 추가. `realtime_screener.py` 2차 필터 단계에서 절대 컷오프 적용
2. **Task 2**: Alembic 마이그레이션 — `Stock.etf_leverage_type` 컬럼 추가(`normal | leverage_2x | inverse | inverse_2x`). 시드 스크립트로 기존 ETF 종목명 패턴 매칭 일괄 분류
3. **Task 3**: `PrimaryFilters.etf_max_tracking_error=3.0` 추가, `screener.py`에서 전일 EOD NAV 기준 1차 필터링 (market_data에 nav 저장 필요시 Sprint 2에서 확장, 현재 초안은 KIS 일봉 수집 시 동반)
4. **Task 4**: `ScreeningResult.factors["tracking_error_value"]`에 원값(%) 저장
5. **Task 5**: Sprint 1 폴백 제거 — `realtime_screener.py`에서 `tracking_error_factor=0.0` 하드코딩 라인 + FIXME 주석 제거 + signal_generator 패턴 매칭 로직 → `Stock.etf_leverage_type` 필드 기반 체크로 교체
6. **Task 6**: wiki/data-collection-flow.md 업데이트 (NAV 수집 플로우 추가)
7. **Task 7**: wiki/external-apis.md 업데이트 (KIS inquire-price ETF 필드 섹션)
8. **Task 8**: ETF 필터 탈락률 로깅 + 1주일 모니터링 결과 리포트 (Sprint 3 완료 직후 별도 문서)

### 주요 파일

| 파일 | 변경 |
|------|------|
| `backend/modules/screening/filters.py` | **수정** — `SecondaryFilters`, `PrimaryFilters`에 etf_max_tracking_error 필드 추가 |
| `backend/modules/screening/realtime_screener.py` | **수정** — 절대 컷오프 적용. Sprint 1 폴백 제거 |
| `backend/modules/screening/screener.py` | **수정** — 1차 ETF 컷오프 |
| `backend/core/models/stock.py` | **수정** — `etf_leverage_type` 컬럼 추가 |
| `backend/alembic/versions/*.py` | **신규** — etf_leverage_type 추가 마이그레이션 |
| `backend/scripts/seed_etf_leverage_type.py` | **신규** — 기존 ETF 종목명 패턴 매칭 시드 |
| `backend/modules/trading/signal_generator.py` | **수정** — 패턴 매칭 → etf_leverage_type 기반 체크 |
| `backend/modules/screening/scorer.py` | **수정** — factors dict에 원값 저장 |
| `wiki/data-collection-flow.md` | **수정** — NAV 플로우 |
| `wiki/external-apis.md` | **수정** — KIS ETF 필드 |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 상태 | 대응 |
|---|------|--------|------|------|
| 1 | Sprint 1 폴백의 영구화 | High | ⚠️ | B5(warning 로깅), B6(FIXME 주석), D7(제거 게이트) 3중 방어 |
| 2 | KIS inquire-price ETF 필드 문서/실제 불일치 | High | ⚠️ | Sprint 2 Task 1(C7) 모의거래 샘플 검증으로 선제 확인 |
| 3 | NAV 파이프라인 자체의 SPOF | Medium | ⚠️ | etf_pipeline_healthy 플래그(C11)로 주식 경로 독립 유지 |
| 4 | Phase 7.0 Sprint 3 LIVE 게이트 | High | ⚠️ | A4 — LIVE 전환 체크리스트에 "Phase 4.10 Sprint 2 완료" 추가 |
| 5 | Phase 5 Sprint 3(성과 분석) 데이터 오염 | Medium | 정보 | Phase 4.10 Sprint 1 배포 이전 ETF 관련 성과 데이터는 생존 편향 플래그 표기 (Phase 5 범위) |
| 6 | 레버리지/인버스 ETF 분류의 종목명 패턴 매칭 한계 | Low | ⚠️ Sprint 1 | 네이밍 예외 ETF 존재 가능성. Sprint 3에서 `etf_leverage_type` 필드로 정식화되면 해소 |
| 7 | ETF 필터 탈락률 과도 (Sprint 3 배포 후) | Medium | ⚠️ | D8 — 1주일 모니터링, 30% 이상 시 컷오프 2.5%로 상향 검토 |
| 8 | Sprint 2 EOD NAV 누적(Phase 9 요구사항) 미구축 | Low | 정보 | Phase 9(백테스트) 착수 시 별도 EOD 수집 Phase 또는 Sprint 추가 |
| 9 | Sprint 1 폴백 하에서 일반 ETF 과괴리 매수 가능성 | Medium | ⚠️ Sprint 2 전환 전까지 | Sprint 2 완료 전 기간 동안 ETF 매매 비중을 기본 모드(반자동)에서만 허용하도록 운영 가이드. 완전 자동 모드는 Sprint 2 완료 후 ETF 허용 |
| 10 | FactorScorer factors 파라미터 부분 키 KeyError (Phase 4.7 #7 잔존) | Medium | ⚠️ | B7에서 `.get()` 방어로 동시 해소 |

---

## 완료 기준 (Phase 전체)

| # | 항목 | 기준 | 상태 |
|---|------|------|------|
| 1 | Sprint 1 프로덕션 배포 | 2026-04-21 장 개시 전 (KST 09:00 이전) | ⬜ |
| 2 | ETF 후보 2차 통과 시 크래시 없음 | pytest ETF 시나리오 3건+ 통과 | ⬜ |
| 3 | ETF 스코어링 실패가 주식 배치를 파괴하지 않음 | scorer 격리 테스트 통과 | ⬜ |
| 4 | 레버리지/인버스 ETF NAV 폴백 상태에서 신호 생성 안 됨 | signal_generator 테스트 통과 | ⬜ |
| 5 | Sprint 1 관찰 기간 (PAPER 24h + LIVE 72h) 무사 | warning 로그 기반 폴백 사용률 확인 | ⬜ |
| 6 | KIS inquire-price ETF nav 필드 실전 검증 | 모의거래 샘플 3종 조회 성공 | ⬜ |
| 7 | Sprint 2 — Redis NAV 캐시 동작 | `realtime:{code}:etf_nav` TTL 30초 갱신 확인 | ⬜ |
| 8 | Sprint 2 — etf_pipeline_healthy 플래그 독립 동작 | 주식 경로 영향 없음 확인 | ⬜ |
| 9 | Sprint 3 — 괴리율 절대 컷오프 동작 | 2% 초과 일반 ETF / 1.5% 초과 레버리지 ETF 제외 확인 | ⬜ |
| 10 | Sprint 3 — Stock.etf_leverage_type 필드 적재 | Alembic 적용 + 기존 ETF 시드 완료 | ⬜ |
| 11 | Sprint 3 — Sprint 1 폴백 제거 | grep 결과 `FIXME(phase4.10-sprint2)` 0건 | ⬜ |
| 12 | Sprint 3 — 폴백 사용률 < 1% 3일 연속 | 로그 기반 검증 | ⬜ |
| 13 | Phase 7.0 Sprint 3 LIVE 게이트 갱신 | 체크리스트에 "Phase 4.10 Sprint 2 완료" 추가됨 | ⬜ |
| 14 | Wiki 업데이트 | `wiki/data-collection-flow.md`, `wiki/external-apis.md` | ⬜ |
| 15 | DB/환경변수 변경 기록 | Railway 환경변수 추가 없음 확인, Alembic은 Sprint 3에서 1회 (etf_leverage_type) | ⬜ |

---

## 관련 Phase

| Phase | 관계 |
|-------|------|
| Phase 4.7 | 1차 스크리닝 스코어링 구조 수정 — 본 Phase는 그 연장선(2차 스크리닝) |
| Phase 4.9 | `pipeline_healthy` 플래그 패턴 — `etf_pipeline_healthy`에 재사용 |
| Phase 5 Sprint 3 | 성과 분석 — 본 Phase Sprint 1 이전 ETF 성과 데이터는 생존 편향 플래그 |
| Phase 7.0 Sprint 3 | LIVE 전환 — 본 Phase Sprint 2 완료를 LIVE 게이트 체크리스트에 추가 |
| Phase 9 | 백테스트 — EOD NAV 누적 파이프라인을 그때 검토 (본 Phase에서 보류) |
