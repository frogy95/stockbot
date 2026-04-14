# Phase 6.2: 장전 수집 단순화 (KIS 주경로 + 포털 장후 보조) — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-14, rev.2 단순화)
> **ROADMAP 참조**: `ROADMAP.md` Phase 6.2
> **검토 리포트**:
>
> - `phase6.2-po-review.md` (정프로, PO) — rev.2
> - `phase6.2-risk-review.md` (최리스크, 리스크관리) — rev.2
> - `phase6.2-api-review.md` (윤에이피, API 개발자) — rev.2
> - `phase6.2-quant-review.md` (박퀀트, 퀀트) — rev.2

---

## 개요

2026-04-14 프로덕션 진단에서 발견된 **공공데이터포털 수집 타이밍 구조적 불일치** 문제를 **근본적으로 단순화**하여 해결한다.

### 핵심 인사이트 (사용자 지적, 코드 검증 완료)

1. **포털 08:00 호출은 구조적 실패**: 포털 정책 "T+1 영업일 13시 이후" → 08:00 호출은 항상 실패
2. **포털 필요 필드 = 2개뿐**: `market_cap`, `listed_shares` — KIS가 제공하지 않는 유일한 필드
3. **장후(16:00) 포털 수집이 가장 단순**: 포털 데이터가 확실히 존재하는 시간대

### 기존 vs 단순화 아키텍처

```
[기존: 하이브리드 — 3중 경로 + 상태 관리]

08:00 포털 시도 → 실패 → KIS 폴백 → portal_fresh=false
08:30 portal_fresh 확인 → 포털 재시도
14:00 portal_fresh 확인 → 포털 정식 수집
+ KIS streak 카운터 + 알림 승급 + pipeline_healthy 조건 강화

[단순화: 2경로 + 상태 없음]

08:00 KIS 일봉 직접 → OHLCV 수집 완료 (market_cap은 보정)
08:30 KIS 실패 시 → KIS 재시도 (포털 재시도 아님)
16:00 포털 보조 수집 → market_cap + listed_shares 갱신 (다음 거래일 품질 보장)
```

### 제거 항목

| 항목 | 제거 이유 |
|------|----------|
| 08:00 "기회주의적 포털 시도" | 구조적 실패 — 확실히 동작하는 KIS로 대체 |
| `portal_fresh` Redis 플래그 | 포털을 08:00에 호출하지 않으므로 추적 불필요 |
| `validate_portal_freshness` 신규 메서드 | portal_fresh 제거에 따라 불필요 |
| 08:30 포털 재시도 | KIS가 주 경로이므로 포털 재시도 무의미 |
| 14:00 `portal_afternoon_collect` | 16:00 수집으로 대체 |
| KIS 폴백 streak 카운터 | KIS가 주 경로이므로 "폴백" 개념 자체 소멸 |
| 알림 승급 로직 (streak 기반) | streak 제거에 따라 불필요 |
| `pipeline_healthy` 조건 강화 | KIS 성공 = premarket success → healthy (기존 로직 유지) |
| 백필 스크립트 (`backfill_portal.py`) | 기존 `trigger_premarket_date` API로 충분 |

---

## 검토팀 확정 파라미터 (2026-04-14, rev.2)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 윤에이피(API 개발자), 박퀀트(퀀트) — 4명
> **방향**: 전원 합의로 단순화 채택. 기존 하이브리드 대비 복잡도 대폭 감소, 스크리닝 품질 동등.

### 수집 아키텍처 파라미터

| # | 항목 | 기존 Phase 6.2 설계 | 확정값 (rev.2) | 근거 | 담당 |
|---|------|-------------------|---------------|------|------|
| 1 | 08:00 수집 경로 | 포털 시도 -> KIS 폴백 | **KIS 일봉 직접 호출** | 포털 08:00 = 구조적 실패, KIS 11일 실전 검증 (전원 합의) | 윤에이피 |
| 2 | 08:30 retry 동작 | 포털 재시도 (portal_fresh 기반) | **KIS 실패 시 KIS 재시도** | 포털 재시도 무의미, KIS 간헐 실패 대비 저비용 보험 (정프로+윤에이피) | 윤에이피 |
| 3 | 14:00 cron | portal_afternoon_collect 신규 | **제거** | 16:00으로 대체 (전원 합의) | — |
| 4 | 16:00 cron | 없음 | **portal_supplement_collect 신규** | 포털 데이터 확실한 시간대, 기존 collect_all 재사용 (윤에이피) | 윤에이피 |
| 5 | 16:00 수집 범위 | — | **전 종목** | 스크리닝 통과 종목만이면 다음 날 신규 후보 listed_shares 부재 (박퀀트) | 박퀀트 |
| 6 | 16:00 수집 목적 | — | **다음 거래일 스크리닝 품질 보장** | 당일 재스크리닝 불필요 (박퀀트+정프로 합의) | 박퀀트 |

### 상태 관리 파라미터

| # | 항목 | 기존 Phase 6.2 설계 | 확정값 (rev.2) | 근거 | 담당 |
|---|------|-------------------|---------------|------|------|
| 7 | portal_fresh 플래그 | Redis 키 신규 | **제거** | 포털 08:00 호출 없으므로 불필요 (전원 합의) | — |
| 8 | KIS streak 카운터 | Redis 키 신규 | **제거** | KIS 주 경로 → 폴백 개념 소멸 (전원 합의) | — |
| 9 | 알림 승급 (streak 기반) | 3거래일+ WARNING | **제거** | streak 제거에 따라 불필요 (전원 합의) | — |
| 10 | pipeline_healthy 조건 | + 포털 T-1 존재 | **기존 유지 (수정 없음)** | KIS 성공 = success → healthy (최리스크) | 최리스크 |

### DB 검증 파라미터

| # | 항목 | 기존 Phase 6.2 설계 | 확정값 (rev.2) | 근거 | 담당 |
|---|------|-------------------|---------------|------|------|
| 11 | validate_premarket_db 소스 | data_go_kr 전용 -> 확장 | **`source.in_(["data_go_kr", "kis_daily"])` 확장** | KIS 주 경로 반영 필수, 미수정 시 DB 검증 항상 실패 (윤에이피) | 윤에이피 |
| 12 | validate_portal_freshness | 신규 메서드 | **제거 (미생성)** | portal_fresh 제거에 따라 불필요 (윤에이피) | — |

### 백필 파라미터

| # | 항목 | 기존 Phase 6.2 설계 | 확정값 (rev.2) | 근거 | 담당 |
|---|------|-------------------|---------------|------|------|
| 13 | 백필 대상 기간 | 2026-04-04 ~ 2026-04-10 (5거래일) | **동일 유지** | 포털 source 누락 기간 | 윤에이피 |
| 14 | 백필 실행 방법 | scripts/backfill_portal.py 신규 | **기존 trigger_premarket_date API 활용** | 스크립트 신규 개발 불필요 (윤에이피) | 윤에이피 |
| 15 | 백필 일일 한도 | 2거래일/일 | **동일 유지** | 포털 Rate Limit 안전 마진 (윤에이피) | 윤에이피 |

### 리스크 관리 파라미터 (최리스크 확정)

| # | 항목 | 기존 Phase 6.2 설계 | 확정값 (rev.2) | 근거 | 담당 |
|---|------|-------------------|---------------|------|------|
| 16 | market_cap=0 처리 | 탈락 + 경고 강화 | **기존 보정 로직 유지 (수정 없음)** | 이미 listed_shares 보정 동작 중, 추가 수정 불필요 (최리스크+박퀀트) | 박퀀트 |
| 17 | KIS 폴백 시 자동매매 제한 | streak 3일+ 차단 | **제거 — KIS 성공이면 자동매매 정상** | KIS OHLCV로 3팩터 스코어링 영향 없음 (최리스크+박퀀트) | 최리스크 |
| 18 | 16:00 포털 연속 실패 경고 | 없음 | **로그 기반 WARNING (Redis 불필요)** | listed_shares stale 인지용, 차단은 불필요 (최리스크) | 최리스크 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 | 장전 수집 단순화 + 포털 장후 보조 | 08:00 KIS 직접, 08:30 KIS 재시도, 16:00 포털 cron, validate_premarket_db 수정, 과거 백필 | 없음 |

> **Sprint 2 제거 근거**: 상태 관리(portal_fresh, streak) 제거로 Sprint 1 작업량 대폭 감소. 백필은 기존 API 활용으로 별도 Sprint 불필요. Sprint 2에 있던 관찰성 강화(연속 실패 요약, 진단 쿼리)도 Sprint 1에 통합 가능.

---

## Sprint 1 상세 — 장전 수집 단순화 + 포털 장후 보조

### 백엔드

#### 수정 파일

| 파일 | 수정 내용 | 관련 파라미터 |
|------|----------|-------------|
| `backend/modules/collector/scheduler.py` | (1) `_premarket_collect`: 포털 제거 -> KIS 직접 호출 (2) `_premarket_retry`: 포털 재시도 -> KIS 재시도 (3) `_portal_supplement_collect`: 16:00 cron 신규 (4) `start()`에 16:00 cron 등록 | #1, #2, #3, #4 |
| `backend/modules/collector/validator.py` | `validate_premarket_db` 소스 조건 확장: `data_go_kr` -> `["data_go_kr", "kis_daily"]` | #11 |

#### 상세 수정 사항

**1. `_premarket_collect` 단순화 (scheduler.py L563-645)**

현재: 포털 시도 -> 실패 -> KIS 폴백 (3중 분기, 예외 경로에서도 폴백)

변경: KIS 일봉 직접 호출 (단일 경로)
```python
async def _premarket_collect(self) -> int:
    """08:00 KIS 일봉 전 종목 수집."""
    # pipeline 상태 초기화 (기존 유지)
    ...
    try:
        kis_result = await self._run_kis_daily_collect()
        kis_validation = self._validator.validate_kis_daily(kis_result)
        if kis_validation.passed:
            await self._update_step_status("premarket", "success", ...)
        else:
            await self._update_step_status("premarket", "failed", ...)
        await self._run_db_validation("premarket", "validate_premarket_db")
        return kis_result.collected
    except Exception as e:
        await self._update_step_status("premarket", "failed", error=str(e))
        await self._send_failure_alert("premarket", str(e))
        return 0
```

핵심 변경:
- `DataGoKrCollector` import/호출 제거
- `_run_kis_daily_fallback()` -> `_run_kis_daily_collect()` (이름 변경: 폴백이 아닌 주 경로)
- 포털 실패 분기, 이중 실패 분기, 예외 경로 폴백 분기 **전부 제거**
- cross-check 로직은 제거 (포털 데이터가 08:00에 없으므로 비교 불가)

**2. `_premarket_retry` 전환 (scheduler.py L668-726)**

현재: 포털 재시도 → 성공 시 스크리닝 재실행

변경: KIS 실패 시 KIS 재시도
```python
async def _premarket_retry(self) -> None:
    """08:30 KIS 재시도 — premarket이 실패 상태일 때만."""
    ...
    premarket_status = pipeline_status.get("premarket", {}).get("status")
    if premarket_status == "success":
        logger.info("KIS 재시도 스킵: premarket 이미 성공 상태")
        return
    # KIS 재시도
    kis_result = await self._run_kis_daily_collect()
    ...
    # 성공 시 스크리닝 재실행 (기존 로직 유지, L709-719)
```

핵심 변경:
- `DataGoKrCollector` 호출 -> `_run_kis_daily_collect()` 호출
- 스킵 조건: `premarket_status == "success"` 그대로 유지 (단순화)
- 성공 시 스크리닝 재실행 로직 그대로 유지

**3. `_portal_supplement_collect` 신규 (16:00 cron)**

```python
async def _portal_supplement_collect(self) -> None:
    """16:00 포털 보조 수집 — market_cap + listed_shares 갱신 (다음 거래일 품질 보장)."""
    today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
    if not is_trading_day(today):
        return
    try:
        async with self._session_factory() as db_session:
            collector = DataGoKrCollector(db_session)
            result = await collector.collect_all()
        if result.collected > 0:
            logger.info("16:00 포털 보조 수집 완료: collected=%d", result.collected)
        else:
            logger.warning("16:00 포털 보조 수집 0건")
    except Exception as e:
        logger.warning("16:00 포털 보조 수집 실패: %s", e)
```

핵심 설계:
- 기존 `DataGoKrCollector.collect_all()` 그대로 사용 — 신규 코드 최소화
- 전 종목 수집 (스크리닝 통과 종목만이면 다음 날 신규 후보 누락 위험)
- 실패 시 경고 로그만 (KIS 데이터로 운영 중이므로 장애 아님)
- pipeline_status 업데이트 **없음** (장전 파이프라인과 독립)

**4. `start()` cron 등록 (scheduler.py L338)**

```python
# 16:00 포털 보조 수집 (market_cap + listed_shares 갱신)
self._scheduler.add_job(
    self._portal_supplement_collect,
    CronTrigger(hour=16, minute=0, timezone=tz),
    id="portal_supplement",
    misfire_grace_time=MISFIRE_GRACE_TIME,
)
```

08:30 `premarket_retry` cron은 유지 (KIS 재시도 용도로 전환).

**5. validate_premarket_db 수정 (validator.py L218-270)**

현재: `MarketData.source == "data_go_kr"`
변경: `MarketData.source.in_(["data_go_kr", "kis_daily"])`

이 수정이 없으면 08:00 KIS 수집 후 DB 검증이 항상 실패 ("건수 부족: 0 < 1500").

**6. 과거 데이터 백필 (수동, 기존 API 활용)**

기존 `trigger_premarket_date` API (scheduler.py L505-527)로 5거래일 백필:
- 2026-04-04 (금), 2026-04-07 (월), 2026-04-08 (화), 2026-04-09 (수), 2026-04-10 (목)
- 하루 최대 2거래일씩 실행 (포털 Rate Limit 안전 마진)
- Sprint Task로 포함, 배포 후 수동 실행

### 프론트엔드

이 Phase에서는 프론트엔드 변경 없음.

### 재사용 자산

| 기존 모듈 | 재사용 방식 |
|----------|----------|
| `KISDailyCollector.collect_all()` | 08:00 주 수집 + 08:30 재시도에서 직접 호출 |
| `DataGoKrCollector.collect_all()` | 16:00 포털 보조 수집에서 그대로 사용 |
| `CollectionValidator.validate_kis_daily()` | 08:00 KIS 수집 결과 검증 |
| `trigger_premarket_date` (scheduler.py L505) | 백필에 그대로 사용 |
| `_run_db_validation` 패턴 | validate_premarket_db 호출 패턴 동일 |
| 기존 pipeline_status/pipeline_healthy 로직 | 수정 없이 그대로 유지 |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 대응 | Sprint |
|---|------|--------|------|--------|
| 1 | 16:00 포털 장기 장애(5일+) 시 listed_shares stale | 낮음 | 유상증자/액면분할 종목은 극소수. 주 1회 진단 쿼리로 모니터링 (최리스크) | 1 |
| 2 | 신규 IPO 종목 listed_shares=NULL → 시총 필터 탈락 | 낮음 | 16:00 포털 정상 시 당일 반영. 일 0~2건 → 실질 영향 미미 (박퀀트) | — |
| 3 | KIS REST API 자체 장기 장애 | 중간 | 08:30 KIS 재시도 + 기존 pipeline_healthy=false 로직 (이미 구현) | — |
| 4 | 포털 Rate Limit (일 1,000건) 백필 시 초과 | 낮음 | 하루 최대 2거래일 한도 유지 (윤에이피) | 1 |
| 5 | 08:00 `_premarket_collect` 리팩토링 범위가 클 수 있음 | 중간 | 포털 코드 제거이므로 삭제 위주 — 추가 코드보다 안전 (정프로) | 1 |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| 08:00 KIS 일봉 직접 수집 동작 | KIS 수집 성공 + premarket status=success | ⬜ |
| 08:30 retry가 KIS 재시도로 전환 | premarket 실패 시 KIS 재시도 동작 확인 | ⬜ |
| 16:00 포털 보조 수집 동작 | 포털 수집 성공 + market_cap/listed_shares 갱신 확인 | ⬜ |
| validate_premarket_db 소스 확장 | data_go_kr + kis_daily 모두 카운트 | ⬜ |
| 포털 관련 불필요 코드 제거 | portal_fresh, streak, 알림 승급 코드 없음 확인 | ⬜ |
| 4/4~4/10 포털 백필 완료 | 각 거래일 포털 source 데이터 존재 확인 | ⬜ |
| 기존 테스트 전부 통과 | `pytest -v` 전체 PASS | ⬜ |
