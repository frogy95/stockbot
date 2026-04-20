# Phase 9: 동시간대 Z-score + VWAP + 5분봉 가속도 지표 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-20)
> **ROADMAP 참조**: `ROADMAP.md` Phase 9
> **선행 Phase**: Phase 8 Sprint 1·2 (매매 신호 복구)
> **검토 리포트**:
>
> - `phase9-po-review.md` (정프로, PO)
> - `phase9-risk-review.md` (최리스크, 리스크관리)
> - `phase9-quant-review.md` (박퀀트, 퀀트 전문가)
> - `phase9-api-review.md` (윤에이피, API 개발자)

---

## 개요

**동시간대 N일 거래량 Z-score** + **VWAP 대비 가격 포지션** + **5분봉 거래량 가속도 지표**를 매매 전략의 confidence 프레임워크에 편입한다. 박퀀트 권고로 Phase 8 Sprint 5(5분봉 가속도)를 이 Phase로 통합하여 **지표 상관관계 관리 + 통합 설계 이익**을 얻는다.

사용자 지시(2026-04-20)에 따라 **"20거래일 데이터 축적이 정말 필수인지"를 비판적으로 재검토**한 결과, 대안 A(KIS 백필) + 대안 C(점진 활성화) 조합으로 **즉시 착수 가능한 범위**를 명확히 한다.

---

## ⚠️ 데이터 의존성 재검토 (사용자 지시 반영)

> 사용자 지시(2026-04-20): "진짜 데이터가 쌓인 상태에서 하는 게 맞는지 재검토해"

### 기존 전제

Phase 8(구) 초안은 "20거래일 이상의 `volume_5min_history` + VWAP Redis 누적"을 필수 조건으로 명시했다.

### 재검토 대안 3가지

#### 대안 A: KIS 과거 분봉 API로 백필

- **가능성**: ✅ KIS `inquire-time-itemchartprice` (tr_id: FHKST03010200) 사용 가능
- **제약 (윤에이피 검토)**:
  - 1회 호출 최대 30건 (약 2.5시간 분량) — 하루치 78슬롯은 3회 호출 필요
  - Range: 최대 30거래일까지만 안정 조회 (더 먼 과거는 누락 가능)
  - 수정주가 기준 — 분할/증자 30일 내 종목은 제외
  - **Rate Limit**: 80% 여유 적용 시 16req/s, 전체 배치 약 5분
  - buy/sell 분리 미제공 가능성 → total_vol만 백필
- **실전 제약**: 장중 서버 부하로 429 발생 → **18:00 이후 실행**

**결론**: Z-score의 total_vol 기반 조기 활성화 가능.

#### 대안 B: 모의/추정 기반 시뮬레이션

- **결론**: ❌ 기각. Phase 10(U자형 비선형)이 검증하려는 가정 위에 지표 구축은 순환 논리.

#### 대안 C: 부분 적용 (점진적 활성화)

- **접근**: 5거래일부터 Z-score 계산 시작, confidence 가중치를 축적 일수에 비례하여 적용
- **결론**: ✅ 권장. 리스크 관점(최리스크 R1)에서 구간 조정 필요

### 재검토 최종 결론

| 구분 | 기존 계획 | 재검토 후 |
|------|----------|---------|
| **Z-score (total_vol)** | 20거래일 대기 | **Sprint 1에서 대안 A(KIS 백필) + 대안 C(점진 활성화) 병행** |
| **Z-score (buy/sell 분리)** | 20거래일 대기 | 실시간 축적만 가능 (자연 축적) |
| **VWAP 실시간 계산** | 20거래일 대기 | **당일 장중 누적만 필요 → 즉시 착수 가능** |
| **VWAP 기반 전략 반영** | 20거래일 대기 | **Sprint 2에서 즉시 착수** |
| **백테스트 데이터셋** | 20거래일 대기 | 유지 (실시간 축적만 가능) |

### Phase 9 착수 조건 (재정의)

- ✅ Phase 8 Sprint 1·2 완료 (매매 신호 복구)
- ✅ KIS 과거 분봉 API 스펙 재확인 (Sprint 0 초반 MCP 조사)
- ⚠️ 20거래일 완전 축적은 **착수 조건이 아니라 Z-score 가중치 100% 활성화 조건**

---

## Sprint 분할 계획 (박퀀트 Q1 + 정프로 P1 반영, 4 Sprint)

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 0 | 데이터 수집 인프라 + KIS 백필 + 5분봉 가속도 | `volume_5min_history` 테이블, EOD 이관, VWAP Redis 누적, KIS 백필 배치, 5분봉 가속도 지표 | Phase 8 Sprint 1·2 완료 |
| 1 | Z-score 엔진 (점진 활성화) | 동시간대 Z-score 계산 + 점진 가중치 + confidence 반영 | Sprint 0 + 10거래일 축적 |
| 2 | VWAP 엔진 + 가격 포지션 | 실시간 VWAP + 가격 포지션 + confidence 반영 | Sprint 0 (독립 병행 가능) |
| 3 | 백테스트 데이터셋 + REST API | 축적 데이터 기반 신호 재현 + VWAP/Z-score 조회 API | Sprint 0~2 |

> **즉시 착수 가능**: Sprint 0, Sprint 2(VWAP). **데이터 축적 대기**: Sprint 1(10거래일+).

---

## 검토팀 확정 파라미터 (2026-04-20)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 윤에이피(API) — 4명

### Sprint 0: 데이터 수집 인프라 + KIS 백필 + 5분봉 가속도

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | `volume_5min_history` 테이블 | 초안 | stock_code, date, slot_index, buy_vol, sell_vol, total_vol, trade_count | 박퀀트 |
| 2 | VWAP Redis 키 | 미명시 | `vwap:{code}:{YYYYMMDD}:pv`, `:v` (TTL 2일) | 윤에이피 (A4) |
| 3 | KIS 백필 실행 시간대 | 미명시 | **18:00~23:00 한정** | 윤에이피 (A1) |
| 4 | KIS 백필 Rate Limit | 미명시 | **16req/s (공식 20의 80%)** | 윤에이피 (A2) |
| 5 | KIS 백필 range | 20거래일 | **최대 30거래일 (KIS 제약)** | 윤에이피 (A3) |
| 6 | KIS 백필 제외 조건 | 없음 | **30일 내 분할/증자 종목 제외** | 박퀀트 (Q3) + 윤에이피 |
| 7 | 토큰 갱신 가드 | 없음 | **만료 30분 전 자동 갱신** | 윤에이피 (A6) |
| 8 | 가속도 계산 윈도우 | 미명시 | 최근 5분봉 vs 직전 3슬롯 이동평균 | 박퀀트 |
| 9 | 가속도 가중치 | ±0.05 | **±0.05 (Sprint 0은 로깅만, Sprint 1 이후 활성)** | 김단타 (D3) |
| 10 | 가속도 시간대 스케일링 | 없음 | **09:30~10:30: 0.5 / 10:30~11:30: 1.0 / 11:30~13:00: 0.3 / 13:00~14:30: 1.0 / 14:30~: 비활성** | 김단타 (D3) |
| 11 | 가속도 유동성 필터 | 없음 | **일평균 거래량 50만 주 미만 종목 제외** | 김단타 (D4) |

### Sprint 1: Z-score 엔진

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 12 | Z-score 윈도우 | 20거래일 | 최근 20거래일 동시간대 | 박퀀트 |
| 13 | Z-score 점진 활성화 구간 | 5/10/20 거래일 | **10/15/20/30 거래일** | 최리스크 (R1) + 박퀀트 (Q2) |
| 14 | 점진 활성화 가중치 | 0%/20%/50%/100% | **0%(<10일) / 10%(10-15) / 30%(15-20) / 60%(20-30) / 100%(30+)** | 최리스크 (R1) |
| 15 | Z-score 임계값 | 2.0/3.0 | `z >= 2.0` 가중치 +0.05, `z >= 3.0` 가중치 +0.10 (위 활성화 비율 곱) | 박퀀트+최리스크 |
| 16 | 백필 데이터 정합성 검증 | 사후 비교 | **백필 전 1~2일 실시간 수집 후 통계 비교, 차이 10%+ 시 백필 제외** | 최리스크 (R2) + 박퀀트 |
| 17 | 정규성 위반 시 대체 | 미명시 | **비모수 통계(분위수 기반) 대체 가능** | 박퀀트 |

### Sprint 2: VWAP 엔진

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 18 | VWAP 계산 방식 | `Σ(price × vol) / Σ(vol)` | 유지 (O(1) Redis 누적) | 박퀀트 |
| 19 | 가격 포지션 임계값 | ±0.5% | `price > VWAP * 1.005` 매수 우위, `< VWAP * 0.995` 매도 우위 | 박퀀트+김단타 |
| 20 | 전략 가중치 | ±0.05 | 매수 우위 +0.05, 매도 우위 -0.05 (confidence 상한 유지) | 최리스크 |
| 21 | **장 초반 비활성화** | 없음 | **09:00~09:30 VWAP 지표 비활성화** | 최리스크 (R3) |
| 22 | VWAP Redis TTL | 미명시 | **2일** (EOD 이관 여유) | 윤에이피 (A4) |

### Sprint 3: 백테스트 + REST API

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 23 | 백테스트 데이터셋 범위 | Sprint 0 이후 축적분 | 유지 | 박퀀트+정프로 |
| 24 | 백테스트 분할 | 미명시 | **TimeSeriesSplit, n=5 (look-ahead bias 제거)** | 박퀀트 (Q2 in Phase 10) + 최리스크 (R4) |
| 25 | REST API 엔드포인트 | 미명시 | `/api/v1/indicators/vwap/{code}`, `/api/v1/indicators/zscore/{code}?slot={slot}` | 윤에이피 |
| 26 | API Rate Limit | 미명시 | **10req/s (UI 용)** | 윤에이피 (A5) |

### 공통: 지표 상관관계 관리

| # | 항목 | 확정값 | 근거 |
|---|------|--------|------|
| 27 | **상관관계 점검 의무화** | Sprint 1·2 완료 시 가속도/Z-score/VWAP 포지션 상관계수 계산. > 0.7 쌍 발견 시 가중치 축소/통합 | 박퀀트 (Q4) |

---

## Sprint 0 상세 — 데이터 수집 인프라 + KIS 백필 + 5분봉 가속도

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/db/migrations/*.py` | `volume_5min_history` 테이블 마이그레이션 (Alembic) |
| `backend/modules/collector/volume_aggregator.py` | Redis `vol5m:*` → DB 이관 EOD 배치 |
| `backend/modules/collector/scheduler.py` | WS 체결 수신 시 VWAP Redis 누적 (`pv`, `v`) |
| `backend/modules/collector/kis_minute_backfill.py` | KIS 과거 분봉 백필 서비스 (신규) |
| `backend/modules/indicators/volume_acceleration.py` | 5분봉 가속도 계산 (신규, 로깅 전용) |
| `backend/modules/screening/corporate_actions.py` | 분할/증자 이력 테이블 조회 (백필 제외 조건용) |
| `backend/tests/collector/` | 백필/이관 테스트 |
| `backend/tests/indicators/` | 가속도 계산 테스트 |

### 재사용 자산

- Phase 6.1의 Redis `vol5m:*` 수집 파이프라인
- `KisRestClient` + `KisAuthService` (토큰 자동 갱신)

### 구현 주의사항

- KIS API 스펙 재확인을 **Sprint 0 초반 1일차에 MCP로 수행** (`mcp__kis-code-assistant-mcp__search_domestic_stock_api`)
- 백필은 스크리닝 대상(약 20~50종목)만 → 일일 운영 부하 최소
- VWAP Redis 누적은 기존 WS 메시지 처리 루프에 `INCRBYFLOAT` 2회만 추가 (성능 영향 미미)

---

## Sprint 1 상세 — Z-score 엔진 (점진 활성화)

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/indicators/volume_zscore.py` | 동시간대 Z-score 계산 (신규) |
| `backend/modules/indicators/sample_size_weighting.py` | 축적 일수별 가중치 함수 (10/15/20/30) |
| `backend/modules/trading/strategies/momentum_breakout.py` | confidence 프레임워크에 Z-score 가중 편입 |
| `backend/tests/indicators/test_volume_zscore.py` | Z-score 단위 테스트 + 비모수 대체 테스트 |

### 주의사항

- **Sprint 1 배포 직전 백필 정합성 검증 필수** (항목 16)
- 정규성 위반 시 비모수 통계(분위수 기반) 대체 경로 미리 구현

---

## Sprint 2 상세 — VWAP 엔진 + 가격 포지션

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/indicators/vwap_engine.py` | 실시간 VWAP 조회 서비스 (신규) |
| `backend/modules/trading/strategies/momentum_breakout.py` | confidence 프레임워크에 VWAP 포지션 가중 편입 + 09:30 이전 비활성 가드 |
| `backend/tests/indicators/test_vwap_engine.py` | 단위 테스트 |

---

## Sprint 3 상세 — 백테스트 데이터셋 + REST API

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/backtest/dataset_builder.py` | 축적 데이터 기반 신호 재현 데이터셋 생성 (신규) |
| `backend/modules/backtest/timeseries_split.py` | TimeSeriesSplit 유틸 (신규) |
| `backend/api/v1/indicators.py` | VWAP/Z-score 조회 API (신규) |
| `backend/tests/backtest/` | 데이터셋 + split 단위 테스트 |

### 프론트엔드 (선택적 미니멀)

| 파일 | 수정 내용 |
|------|----------|
| `frontend/app/dashboard/indicators/page.tsx` | VWAP/Z-score 시각화 (운영자 모니터링용) |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 담당 | 배치 |
|---|------|--------|------|------|
| 1 | KIS 과거 분봉 API의 buy/sell 분리 지원 여부 | ⚠️ | 윤에이피 | Sprint 0 초반 MCP 조사 |
| 2 | 과거 분봉과 실시간 체결 기반 거래량 스케일 차이 | ⚠️ | 박퀀트 | 백필 전 1~2일 실시간 비교 검증 |
| 3 | Z-score 점진 활성화 초기 구간 오탐 영향 | ⚠️ | 최리스크 | 10일 이상 로깅 전용 (R1 반영) |
| 4 | 지표 상관관계 (가속도/Z-score/VWAP) | ⚠️ | 박퀀트 | Sprint 1·2 후 상관계수 의무 점검 (Q4) |
| 5 | VWAP 장 초반 오탐 | ⚠️ | 최리스크 | 09:30 이전 비활성 (R3) |
| 6 | 백테스트 데이터셋 규모 (Phase 10 활용) | 정보 | 박퀀트 | Sprint 3에서 라벨링 기준 확정 |
| 7 | Sprint 2 병행 가능성 | 정보 | 정프로 | VWAP는 축적 대기 불필요 → Sprint 0 완료 후 즉시 착수 가능 |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| volume_5min_history 테이블 | 마이그레이션 + EOD 이관 배치 | ⬜ |
| VWAP Redis 누적 | 실시간 체결 → pv/v 누적 확인 | ⬜ |
| KIS 과거 분봉 백필 | 20종목 × 5거래일+ 백필, 제외 조건 동작 | ⬜ |
| 백필 정합성 검증 | 실시간 수집 데이터와 통계 비교, 차이 < 10% | ⬜ |
| 5분봉 가속도 지표 | 시간대 스케일링 + 유동성 필터 동작 | ⬜ |
| Z-score 점진 활성화 | 축적 일수별 가중치 자동 조정 | ⬜ |
| 실시간 VWAP 엔진 | 장중 종목별 VWAP O(1) 조회 | ⬜ |
| 09:30 이전 비활성 | VWAP 가드 확인 | ⬜ |
| VWAP 전략 반영 | 가격 포지션 ±0.05 확인 | ⬜ |
| 지표 상관관계 점검 | 가속도/Z-score/VWAP 상관계수 계산 | ⬜ |
| REST API | VWAP/Z-score 조회 엔드포인트 | ⬜ |
| 백테스트 데이터셋 | TimeSeriesSplit 기반 분할 | ⬜ |
| pytest 전체 통과 | 기존 + 신규 테스트 | ⬜ |
