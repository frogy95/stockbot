# Phase 4.8: EOD 데이터 수집 내결함성 강화 — 실행 계획

> **Status**: Sprint 1 완료 (2026-04-03), Sprint 2 완료 (2026-04-05), Sprint 3 완료 (2026-04-05) — Phase 4.8 전체 완료
> **ROADMAP 참조**: `ROADMAP.md` Phase 4.8
> **검토 리포트**:
>
> - `phase4.8-po-review.md` (정프로, PO)
> - `phase4.8-risk-review.md` (최리스크, 리스크관리)
> - `phase4.8-quant-review.md` (박퀀트, 퀀트)
> - `phase4.8-api-review.md` (윤에이피, API 개발자)

---

## 개요

공공데이터포털(data.go.kr)의 전일 OHLCV 데이터가 장전(08:00) 수집 시점에 미게시되는 구조적 문제로 인해 1차 스크리닝이 0건 후보를 생성하는 치명적 장애가 발생했다. 이 문제는 앞으로도 반복될 수 있는 **데이터 소스 단일 장애점(SPOF)** 이다.

### 문제 분석

```
[현재 장애 흐름]
08:00 포털 수집 → 전일(Apr 2) 데이터 미게시 → Apr 1로 폴백
  → KIS ETF(Apr 2) 날짜와 혼재 → date_subq 오염 (hotfix 적용으로 해소)
  → 포털 수집 자체가 T-1 미달 → prev_volume=0 → 스크리닝 0건

[근본 원인]
주식 EOD 데이터 소스가 공공데이터포털 하나뿐 → 포털 장애/지연 시 대안 없음
```

### 해결 아키텍처

```
[개선된 장전 파이프라인]
08:00 포털 수집 시도
  ├─ 성공 (>=1500건, T-1 데이터) → 정상 진행
  └─ 실패 (0건 or T-2 이하)
       ├─ KIS 일봉 보조 수집 (전 활성 주식, source=kis_daily)
       │    ├─ 성공 (>=80% 수집률) → 보조 데이터로 스크리닝 진행
       │    └─ 실패 → 이중 실패 알림 + pipeline_healthy=false
       └─ 08:30 포털 재시도 (1회)
            ├─ 성공 → 포털 데이터 우선 사용
            └─ 실패 → KIS 보조 데이터로 진행 (이미 수집됨)
```

---

## 검토팀 확정 파라미터 (2026-04-02)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 윤에이피(API 개발자) — 4명

### KIS 일봉 보조 수집 파라미터

| #   | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|-----|------|----------|--------|------|------|
| 1   | KIS 일봉 API | 미구현 | **`FHKST03010100` (주식일별가격조회)** | 한투 REST API 공식 지원, OHLCV 제공 (윤에이피) | 윤에이피 |
| 2   | 일봉 조회 기간 | — | **전일 1일 (T-1만)** | OHLCV 1일치면 스크리닝 충분 (박퀀트) | 박퀀트 |
| 3   | 수정주가 옵션 | — | **"0" (미반영)** | 공공데이터포털과 일관성 유지 (윤에이피+박퀀트 합의) | 윤에이피 |
| 4   | 배치 크기 | — | **50종목 단위** | 중간 commit으로 부분 실패 복구 (정프로+윤에이피 합의) | 윤에이피 |
| 5   | source 태그 | — | **`"kis_daily"`** | ETF용 `"kis_rest"`와 구분 필수 (박퀀트) | 박퀀트 |
| 6   | 보조 수집 대상 | 전 종목 | **stocks 테이블 활성 주식 전체** | Rate Limit 범위 내, 실전 ~2분 (윤에이피) | 윤에이피 |
| 7   | 보조 수집 최소 성공률 | — | **80%** | 80% 미만이면 보조 수집도 실패로 판정 (최리스크) | 최리스크 |

### 스케줄러/폴백 파라미터

| #   | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|-----|------|----------|--------|------|------|
| 8   | 포털 실패 시 KIS 자동 전환 | 없음 | **validate_premarket 실패 시 즉시 KIS 보조 수집** | SPOF 해소의 핵심 (전원 합의) | 정프로 |
| 9   | 포털 재시도 시각 | 없음 | **08:30 (1회)** | 포털 데이터 지연 게시 대응, 09:00 장 시작 전 완료 (정프로) | 정프로 |
| 10  | 최대 재시도 횟수 | — | **1회 (08:30)** | 2회 이상은 불필요, KIS 보조가 이미 동작 (정프로+최리스크) | 정프로 |
| 11  | 재시도 성공 시 처리 | — | **포털 데이터 우선, KIS 보조 데이터와 공존 허용** | 포털이 정식 소스, KIS는 보조 (박퀀트) | 박퀀트 |

### 스크리닝 소스 필터 파라미터

| #   | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|-----|------|----------|--------|------|------|
| 12  | date_subq source 필터 | `data_go_kr`만 | **`data_go_kr` OR `kis_daily`** | 보조 수집 데이터도 스크리닝에 포함 (박퀀트+최리스크 합의) | 박퀀트 |
| 13  | market_cap 부재 시 | — | **KIS 일봉에 시총 없으면 stocks.listed_shares 기반 추정 또는 시총 필터 면제** | KIS 일봉에 시총 미포함 (박퀀트 주의, 최리스크 보수적 합의: 면제보다 추정 우선) | 박퀀트 |
| 14  | 혼합 소스 날짜 관리 | — | **포털+KIS 동일 날짜만 사용, 날짜 불일치 시 최신 날짜 우선** | 날짜 오염 재발 방지 (최리스크) | 최리스크 |

### 알림/모니터링 파라미터

| #   | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|-----|------|----------|--------|------|------|
| 15  | 이중 실패 시 알림 | 없음 | **텔레그램 긴급 알림 + pipeline_healthy=false 유지** | 데이터 없이 매매는 절대 불가 (최리스크) | 최리스크 |
| 16  | 보조 수집 사용 알림 | 없음 | **텔레그램 정보성 알림 (보조 수집 전환됨)** | 운영 가시성 (정프로) | 정프로 |
| 17  | 데이터 cross-check | 없음 | **양쪽 모두 있는 종목에서 종가 1% 이상 괴리 시 warning 로깅** | 데이터 무결성 모니터링 (박퀀트) | 박퀀트 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 ✅ | KIS 일봉 보조 수집기 + 스케줄러 폴백 | KIS 일봉 API 메서드, KISDailyCollector, 스케줄러 폴백 로직, 스크리닝 소스 필터 확장 | 없음 |
| 2 ✅ | 재시도 스케줄 + 알림 + 모니터링 | 08:30 재시도 job, 텔레그램 알림, cross-check 로깅, 검증 강화 | Sprint 1 |
| 3 ✅ | 장전 파이프라인 체인 구조 전환 | 개별 CronTrigger 6개 제거, `_run_scheduled_pipeline()` 래퍼 추가, 08:00 단일 CronTrigger 등록, 테스트 수정 | Sprint 2 |

---

## Sprint 1 상세 — KIS 일봉 보조 수집기 + 스케줄러 폴백 ✅ 완료

> PR #77 머지 완료 (2026-04-03). 661개 테스트 통과. Medium 이슈 1건: KIS 폴백 성공 시 반환값 오류 → Sprint 2에서 개선 권장.

### 백엔드

| 파일 | 작업 | 신규/수정 |
|------|------|----------|
| `backend/core/clients/kis_rest.py` | `get_daily_price(stock_code, start_date, end_date)` 메서드 추가 | 수정 |
| `backend/modules/collector/sources/kis_daily_collector.py` | KIS 일봉 보조 수집기 클래스 (배치 수집, source="kis_daily") | **신규** |
| `backend/modules/collector/scheduler.py` | `_premarket_collect()` 폴백 로직: 포털 실패 시 KIS 보조 수집 호출 | 수정 |
| `backend/modules/collector/validator.py` | `validate_kis_daily()` 보조 수집 검증 메서드 추가 | 수정 |
| `backend/modules/screening/screener.py` | `_fetch_today_and_prev()` date_subq source 필터: `data_go_kr` OR `kis_daily` | 수정 |
| `backend/modules/screening/screener.py` | market_cap 부재 시 stocks.listed_shares 기반 추정 로직 | 수정 |

### 프론트엔드

- 이 Sprint에서는 프론트엔드 변경 없음

### 재사용 자산

| 기존 모듈 | 재사용 방식 |
|-----------|-----------|
| `KISRestClient._request()` | 인증/Rate Limit/재시도 로직 그대로 사용 |
| `TokenBucketThrottler` | 배치 간 딜레이 자동 적용 |
| `CollectionResult` dataclass | 수집 결과 표준 반환 |
| `CollectionValidator` | 새 검증 메서드 추가 |
| `market_data` 테이블 | source="kis_daily"로 구분 저장, 스키마 변경 없음 |
| `KISCollector._save_etf_price()` 패턴 | 동일 upsert 패턴 재사용 |

---

## Sprint 2 상세 — 재시도 스케줄 + 알림 + 모니터링 ✅ 완료

> PR #78 머지 대기 (2026-04-05). 674개 테스트 통과. Medium 이슈 1건: `_premarket_retry` 성공 후 cross_check_prices 호출 누락 → Phase 5에서 개선 권장.

### 백엔드

| 파일 | 작업 | 신규/수정 |
|------|------|----------|
| `backend/modules/collector/scheduler.py` | 08:30 포털 재시도 CronTrigger job 추가 | 수정 |
| `backend/modules/collector/scheduler.py` | 보조 수집 전환 텔레그램 알림, 이중 실패 긴급 알림 | 수정 |
| `backend/modules/collector/validator.py` | 데이터 cross-check (포털 vs KIS 종가 1% 괴리 warning) | 수정 |
| `backend/modules/collector/scheduler.py` | 재시도 성공 시 포털 데이터 우선 로직 | 수정 |

### 프론트엔드

- 이 Sprint에서는 프론트엔드 변경 없음

### 재사용 자산

| 기존 모듈 | 재사용 방식 |
|-----------|-----------|
| `_send_failure_alert()` | 알림 패턴 확장 (정보성 알림 추가) |
| `CronTrigger` | 기존 스케줄러 패턴 동일 |
| `_update_step_status()` | 파이프라인 상태 추적 그대로 사용 |
| `DEPENDENCY_MAP` | 재시도 job은 premarket 의존으로 등록 |

---

## Sprint 3 상세 — 장전 파이프라인 체인 구조 전환 ✅ 완료

> PR #80 머지 대기 (2026-04-05). 678개 테스트 통과. 코드 리뷰 이슈 없음.
>
> **배경**: 스케줄러의 개별 CronTrigger 구조는 KIS 폴백 수집(~3~5분)이 08:10 이전에 완료되지 않으면 primary_screen이 스킵되어 당일 자동 스크리닝이 전체 무력화되는 설계 결함. 수동 복구용 `run_premarket_pipeline()`은 이미 올바른 체인 방식으로 구현되어 있으므로, 이를 자동 스케줄에도 적용한다.
>
> **검토 보고서**: `docs/phase/phase4.8/phase4.8-sprint3-review.md` (전문가 4명 전원 합의)

### 백엔드

| 파일 | 작업 | 신규/수정 |
|------|------|----------|
| `backend/modules/collector/scheduler.py` | `start()`: 장전 CronTrigger 6개 제거 (`premarket_collect`, `etf_master_collect`, `primary_screen`, `etf_collect`, `dart_collect`, `sentiment_collect`) | 수정 |
| `backend/modules/collector/scheduler.py` | `_run_scheduled_pipeline()` 래퍼 메서드 추가 (락 선점 + `run_premarket_pipeline()` 호출) | 수정 |
| `backend/modules/collector/scheduler.py` | `start()`: `_run_scheduled_pipeline` 08:00 CronTrigger 단일 등록 | 수정 |
| `backend/tests/test_pipeline_chain.py` | 체인 파이프라인 동작 검증 테스트 (성공/실패/락 충돌 시나리오) | **신규** |

### 유지 대상

| 항목 | 이유 |
|------|------|
| `market_open`, `market_close`, `market_open_recovery`, `premarket_retry`, `secondary_screen` CronTrigger | 체인 외 독립 실행 job — 유지 |
| 개별 수동 트리거 API (`trigger_premarket`, `trigger_etf` 등) | 디버깅/운영용 — 유지 |
| `run_premarket_pipeline()` 수동 트리거 | 장애 복구용 — 유지 |

### 구현 상세

#### `_run_scheduled_pipeline()` 래퍼

```python
async def _run_scheduled_pipeline(self) -> None:
    """08:00 CronTrigger용 장전 파이프라인. 락 선점 후 체인 실행."""
    existing = await self._redis.get(PIPELINE_RUNNING_KEY)
    if existing:
        logger.warning("파이프라인 이미 실행 중 — 자동 스케줄 스킵")
        return
    await self._redis.set(PIPELINE_RUNNING_KEY, "auto", ttl=STATE_TTL)
    await self.run_premarket_pipeline()
```

#### 체인 실행 순서 (`run_premarket_pipeline` 기존 구현 그대로)

```
08:00 CronTrigger → _run_scheduled_pipeline()
    ├→ _premarket_collect()      (완료 후)
    ├→ _etf_master_collect()     (완료 후)
    ├→ _primary_screen()         (완료 후, primary_screener 가드 유지)
    ├→ _etf_collect()            (완료 후)
    ├→ _dart_collect()           (완료 후)
    └→ _sentiment_collect()
08:30 CronTrigger → _premarket_retry()   (체인 외 독립 실행, 유지)
```

### 주의사항

| # | 항목 | 심각도 |
|---|------|--------|
| 1 | `PIPELINE_RUNNING_KEY` 락 선점을 래퍼에서 처리 — 수동/자동 충돌 방지 | ⚠️ 필수 |
| 2 | `if self._primary_screener:` 가드 체인 내 유지 | ⚠️ 필수 |
| 3 | `premarket_retry` job은 체인 밖 독립 유지 | ⚠️ 필수 |
| 4 | 파이프라인 전체 소요 시간 로깅 (09:00 전 완료 모니터링) | 권고 |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 담당 | 대응 |
|---|------|--------|------|------|
| 1 | ~~KIS 일봉 API(`FHKST03010100`)가 모의거래에서 지원되지 않을 가능성~~ | ~~⚠️~~ | 윤에이피 | ✅ 해결 — `inquiry_client`(실전 조회 전용) 사용으로 Sprint 1에서 해소 |
| 2 | ~~모의거래 Rate Limit(초당 1건)으로 전 종목 수집 시 ~42분 소요~~ | ~~⚠️~~ | 윤에이피 | ✅ 해결 — `inquiry_client` 사용으로 실전 Rate Limit 적용 |
| 3 | ~~KIS 일봉에 시가총액/상장주식수 미포함~~ | ~~⚠️~~ | 박퀀트 | ✅ 해결 — stocks.listed_shares * close_price 추정 로직 구현 (Sprint 1) |
| 4 | 포털+KIS 이중 실패 시 매매 불가 | ✅ 확정 | 최리스크 | pipeline_healthy=false 유지, 매매 자동 중단 (기존 메커니즘) |
| 5 | 포털 재시도 성공 시 KIS 보조 데이터와 공존 | ⚠️ | 박퀀트 | 스크리닝에서 동일 종목/날짜에 두 소스 있으면 data_go_kr 우선 |
| 6 | ~~KIS 폴백 성공 시 `_premarket_collect()` 반환값이 포털 실패 건수를 반환~~ | ~~⚠️ Medium~~ | - | ✅ 해결 — Sprint 2에서 `return kis_result.collected` 경로 확인 완료 (PR #78) |
| 7 | `_premarket_retry` 재시도 성공 후 cross_check_prices 호출 누락 | ⚠️ Medium | - | Sprint 2 코드 리뷰 발견. Phase 5에서 개선 권장 — 재시도 성공 후에도 cross-check 실행 필요 |
| 8 | **장전 파이프라인 복원력 부족** — KIS fallback이 장 전 시간대에 완료 불가 + premarket 실패 시 DB 데이터 있어도 스크리닝 차단 | 🔴 High | - | 2026-04-06 프로덕션 장애로 발견. 수정 계획: [premarket-pipeline-resilience.md](../../../../.claude/plans/premarket-pipeline-resilience.md) |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| KIS 일봉 API 연동 | `get_daily_price()` 메서드 구현 + 단위 테스트 통과 | ✅ 완료 |
| KIS 보조 수집기 | `KISDailyCollector` 전 활성 주식 배치 수집, source="kis_daily" | ✅ 완료 |
| 스케줄러 폴백 | 포털 실패 시 KIS 보조 수집 자동 전환 | ✅ 완료 |
| 스크리닝 소스 필터 | date_subq에서 data_go_kr OR kis_daily 인식 | ✅ 완료 |
| 포털 재시도 | 08:30 자동 재시도 (1회) | ✅ 완료 |
| 텔레그램 알림 | 보조 수집 전환/이중 실패 알림 | ✅ 완료 |
| 데이터 cross-check | 종가 1% 괴리 warning 로깅 | ✅ 완료 |
| pipeline_healthy 연동 | 보조 수집 성공 시 healthy, 이중 실패 시 false | ✅ 완료 |
| 통합 테스트 | 포털 실패 → KIS 폴백 → 스크리닝 정상 동작 시나리오 | ✅ 완료 |
| 장전 파이프라인 체인 전환 | 08:00 단일 CronTrigger, 개별 장전 job 제거, 락 보호 | ✅ 완료 |
