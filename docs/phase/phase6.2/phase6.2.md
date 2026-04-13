# Phase 6.2: 포털 수집 타이밍 정합성 + 재시도 정책 수정 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-14)
> **ROADMAP 참조**: `ROADMAP.md` Phase 6.2
> **검토 리포트**:
>
> - `phase6.2-po-review.md` (정프로, PO)
> - `phase6.2-risk-review.md` (최리스크, 리스크관리)
> - `phase6.2-api-review.md` (윤에이피, API 개발자)
> - `phase6.2-quant-review.md` (박퀀트, 퀀트)

---

## 개요

2026-04-14 프로덕션 진단에서 발견된 **공공데이터포털 수집 타이밍 구조적 불일치** 문제를 해결한다. 포털의 공식 갱신 정책("T+1 영업일 13시 이후")과 현재 스케줄(08:00 KST)이 충돌하여, 포털 수집이 구조적으로 실패하고 KIS 폴백으로만 11일간 운영되었다.

### 문제 분석

```
[현재 장애 흐름 — 3중 결함]

결함 1: 타이밍 불일치 (구조적)
  08:00 포털 호출 → T-1 데이터 요청
  포털 정책: T+1 영업일 13시 이후 배포
  → 08:00 시점에 데이터 미존재 → 항상 실패 (간헐 성공은 조기 배포 덕분)

결함 2: 재시도 스킵 (scheduler.py L668-682)
  08:00 포털 실패 → KIS 폴백 성공 → premarket.status = "success"
  08:30 _premarket_retry → "success" 확인 → 스킵
  → 포털에 T-1 데이터가 늦게 배포되어도 재호출하지 않음

결함 3: DB 검증 신호 미활용 (validator.py L218-270)
  validate_premarket_db: source='data_go_kr' 전용 검증
  → "DB 장전 데이터 건수 부족: 0 < 1500" 탐지하지만
  → 이 결과를 받아 재시도하는 트리거 없음

결과:
  market_data.source='data_go_kr' 최신일: 2026-04-03 (11일 갭)
  market_cap, listed_shares 미갱신 → 1차 스크리닝 시총 필터 열화
  오늘 1차 스크리닝 통과 2종목 (평소 ~30) — 인과관계 추정
```

### 해결 아키텍처: 하이브리드 (옵션 A+B)

전문가 4인 전원 합의로 **하이브리드 방식** 채택.

```
[개선된 수집 아키텍처]

08:00 premarket_pipeline (기존 유지, 기회주의적 포털 시도)
  ├─ 포털 시도 → 성공 시: 정상 진행 (조기 배포 활용)
  └─ 포털 실패 → KIS 폴백 → premarket.status = "success"
       └─ 단, portal_fresh = false (포털 데이터 미확보 플래그)

08:30 premarket_retry (조건 변경)
  ├─ 기존: premarket.status == "success" → 스킵
  └─ 변경: portal_fresh == true → 스킵 (DB에서 포털 T-1 건수 직접 확인)
       └─ portal_fresh == false → 포털 재시도

14:00 portal_afternoon_collect (신규 cron)
  ├─ portal_fresh == true → 스킵 (이미 수집됨)
  └─ portal_fresh == false → 포털 정식 수집 (T+1 13시 정책 준수)
       ├─ 성공 시: market_cap/listed_shares 갱신, [보완] 알림
       └─ 실패 시: 경고 로그 (이미 KIS로 운영 중)

[관찰성 강화]
  KIS 폴백 연속 카운터 (Redis)
  ├─ 1~2거래일: INFO 알림 유지
  ├─ 3거래일+: WARNING 승급 알림
  └─ 3거래일+ & 자동매매: pipeline_healthy=false (차단)
```

**핵심 원칙 (최리스크 확정)**:
- 14:00 포털 수집은 "다음 거래일" 스크리닝 품질 보장이 목적
- 당일 스크리닝은 08:00 결과(포털 or KIS)로 진행, 14:00 결과로 재스크리닝하지 않음
- KIS 폴백 1~2일은 정상 운영 허용, 3일+ 연속 시 자동매매 차단

---

## 검토팀 확정 파라미터 (2026-04-14)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 윤에이피(API 개발자), 박퀀트(퀀트) — 4명

### 포털 수집 타이밍 파라미터

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| 1 | 08:00 포털 호출 | 유지 | **유지 (기회주의적 시도)** | 조기 배포(09~11시) 시 이득, 실패해도 KIS 폴백 (전원 합의) | 윤에이피 |
| 2 | 14:00 포털 보조 cron | 없음 | **신규 추가 (14:00 KST)** | 포털 정책 T+1 13시 + 1시간 마진 (윤에이피) | 윤에이피 |
| 3 | 14:00 수집 목적 | — | **다음 거래일 스크리닝 품질 보장** | 당일 재스크리닝 불필요 (박퀀트+정프로 합의) | 박퀀트 |

### 재시도 정책 파라미터

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| 4 | 08:30 retry 스킵 조건 | `premarket.status == "success"` | **`portal_fresh == true` (DB 직접 확인)** | KIS 폴백 성공과 포털 수집을 독립 판단 (윤에이피+최리스크) | 윤에이피 |
| 5 | portal_fresh 판정 기준 | 없음 | **source='data_go_kr', data_date >= T-1, 건수 >= 1500** | validate_premarket 임계값과 일관성 (윤에이피+박퀀트) | 윤에이피 |
| 6 | 14:00 수집 전 스킵 조건 | — | **portal_fresh == true (08:00/08:30 성공 시 스킵)** | 중복 수집 방지 (윤에이피) | 윤에이피 |

### 알림 및 관찰성 파라미터

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| 7 | KIS 폴백 연속 카운터 | 없음 | **Redis 키: `scheduler:kis_fallback_streak`** | 연속 폴백 일수 추적 (최리스크) | 최리스크 |
| 8 | 알림 승급 임계값 | INFO만 | **3거래일 연속 → WARNING 승급** | 3일 연속 폴백 = 구조적 문제 신호 (정프로+최리스크 합의) | 정프로 |
| 9 | 자동매매 차단 임계값 | 없음 | **KIS 폴백 3거래일 연속 시 pipeline_healthy=false** | 시총 데이터 열화 한계 (최리스크) | 최리스크 |
| 10 | 포털 연속 실패 알림 빈도 | 매 실패 시 | **3회 초과 시 일 1회 요약** | 알림 피로 방지 (윤에이피) | 윤에이피 |

### validate_premarket_db 수정 파라미터

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| 11 | validate_premarket_db 소스 | `source == "data_go_kr"` 전용 | **`source.in_(["data_go_kr", "kis_daily"])` 로 확장** | screening_readiness와 일관성 (윤에이피) | 윤에이피 |
| 12 | 신규 validate_portal_freshness | 없음 | **포털 전용 최신성 체크 메서드 추가** | retry/14:00 스킵 판단에 사용 (윤에이피) | 윤에이피 |

### 백필 파라미터

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| 13 | 백필 대상 기간 | 미정 | **2026-04-04 ~ 2026-04-10 (5거래일)** | 포털 source 누락 기간 (4/06 일, 4/05 토 제외) | 윤에이피 |
| 14 | 백필 일일 한도 | 없음 | **2거래일/일** | 포털 Rate Limit 안전 마진 (윤에이피) | 윤에이피 |
| 15 | 백필 실행 방법 | 미정 | **기존 trigger_premarket_date API 활용** | scheduler.py L505-527 이미 구현됨 (윤에이피) | 윤에이피 |

### market_cap 안전장치 (최리스크+박퀀트 합의)

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| 16 | market_cap=0 처리 | 시총 필터 탈락 | **탈락 유지 + 경고 로그 강화** | 부정확한 0값 통과보다 탈락이 안전 (최리스크+박퀀트 합의) | 박퀀트 |
| 17 | KIS 폴백 1~2일 운영 | 정상 | **정상 운영 (포지션 제한 없음)** | stocks.listed_shares 보정으로 대부분 커버 (박퀀트) | 박퀀트 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 | 포털 수집 정합성 + 재시도 정책 수정 | retry 조건 변경, 14:00 cron, portal_fresh 체크, 알림 승급, KIS 폴백 카운터, validate_premarket_db 수정 | 없음 |
| 2 | 과거 데이터 백필 + 관찰성 강화 | 4/4~4/10 포털 백필, 백필 스크립트, 포털 연속 실패 요약 알림, 진단 쿼리 | Sprint 1 |

---

## Sprint 1 상세 — 포털 수집 정합성 + 재시도 정책 수정

### 백엔드

#### 수정 파일

| 파일 | 수정 내용 | 관련 파라미터 |
|------|----------|-------------|
| `backend/modules/collector/scheduler.py` | (1) `_premarket_retry` 조건 변경: portal_fresh 기반 (2) `_portal_afternoon_collect` 신규 cron 추가 (3) `start()`에 14:00 cron 등록 (4) KIS 폴백 streak 카운터 (Redis) (5) 알림 승급 로직 | #4, #5, #6, #7, #8, #9 |
| `backend/modules/collector/validator.py` | (1) `validate_premarket_db` 소스 확장 (2) `validate_portal_freshness` 신규 메서드 | #11, #12 |
| `backend/modules/collector/scheduler.py` (알림) | (1) `_send_fallback_streak_alert` 신규 (2) 폴백 streak 3일+ 시 pipeline_healthy=false | #8, #9, #10 |

#### 상세 수정 사항

**1. `_premarket_retry` 조건 변경 (scheduler.py L668-726)**

현재:
```python
premarket_status = pipeline_status.get("premarket", {}).get("status")
if premarket_status == "success":
    logger.info("포털 재시도 스킵: premarket 이미 성공 상태")
    return
```

변경:
```python
portal_fresh = await self._check_portal_freshness()
if portal_fresh:
    logger.info("포털 재시도 스킵: 포털 T-1 데이터 이미 존재")
    return
```

**2. `_check_portal_freshness` 신규 메서드**

```python
async def _check_portal_freshness(self) -> bool:
    """DB에서 포털 데이터 T-1 이내 1500건 이상 존재 여부 확인."""
    async with self._session_factory() as db_session:
        result = await self._validator.validate_portal_freshness(db_session)
        return result.passed
```

**3. `_portal_afternoon_collect` 신규 cron (14:00 KST)**

```python
async def _portal_afternoon_collect(self) -> None:
    """14:00 포털 보조 수집 — 포털 미확보 시에만 수집."""
    today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
    if not is_trading_day(today):
        return
    portal_fresh = await self._check_portal_freshness()
    if portal_fresh:
        logger.info("14:00 포털 수집 스킵: 이미 확보됨")
        return
    # 포털 수집 실행 (pipeline_status 초기화 없음)
    try:
        async with self._session_factory() as db_session:
            collector = DataGoKrCollector(db_session)
            result = await collector.collect_all()
        validation = self._validator.validate_premarket(result)
        if validation.passed:
            await self._send_portal_补完_alert(result.collected)
            # KIS 폴백 streak 리셋
            await self._redis.delete("scheduler:kis_fallback_streak")
        else:
            logger.warning("14:00 포털 수집 실패: %s", validation.failure_reason)
    except Exception as e:
        logger.warning("14:00 포털 수집 예외: %s", e)
```

**4. KIS 폴백 streak 카운터**

- `_premarket_collect`에서 KIS 폴백 성공 시: streak 증가
- 포털 수집 성공 시: streak 리셋
- streak 값에 따른 분기: 1~2일 INFO, 3일+ WARNING + pipeline_healthy=false

**5. `start()` cron 등록 추가 (scheduler.py L338)**

```python
# 14:00 포털 보조 수집
self._scheduler.add_job(
    self._portal_afternoon_collect,
    CronTrigger(hour=14, minute=0, timezone=tz),
    id="portal_afternoon",
    misfire_grace_time=MISFIRE_GRACE_TIME,
)
```

**6. validate_premarket_db 수정 (validator.py L218-270)**

현재: `MarketData.source == "data_go_kr"`
변경: `MarketData.source.in_(["data_go_kr", "kis_daily"])`

**7. validate_portal_freshness 신규 (validator.py)**

```python
async def validate_portal_freshness(self, session: AsyncSession) -> ValidationResult:
    """포털 데이터 T-1 이내 존재 여부 확인."""
    today = datetime.now(KST).date()
    prev_day = get_prev_trading_day(today, n=1)
    stmt = select(func.count()).where(
        MarketData.data_date >= prev_day,
        MarketData.source == "data_go_kr",
    )
    result = await session.execute(stmt)
    count = result.scalar_one()
    if count >= 1500:
        return ValidationResult(passed=True, ...)
    return ValidationResult(passed=False, ...)
```

### 프론트엔드

이 Phase에서는 프론트엔드 변경 없음.

### 재사용 자산

| 기존 모듈 | 재사용 방식 |
|----------|----------|
| `CollectionValidator.validate_premarket` | portal_freshness 검증 로직의 기반 |
| `DataGoKrCollector.collect_all` | 14:00 cron에서 그대로 호출 |
| `_send_fallback_info_alert` | 알림 승급 로직의 기반 패턴 |
| `trigger_premarket_date` (scheduler.py L505) | 백필에서 그대로 사용 |
| Redis `pipeline_healthy` 키 | streak 기반 healthy 판정에 재사용 |
| `_are_core_steps_healthy` 로직 | portal_fresh 조건 추가 확장 |

---

## Sprint 2 상세 — 과거 데이터 백필 + 관찰성 강화

### 백엔드

#### 수정/신규 파일

| 파일 | 수정 내용 | 관련 파라미터 |
|------|----------|-------------|
| `backend/scripts/backfill_portal.py` | 포털 백필 스크립트 (날짜 범위 지정, 일일 한도 준수) | #13, #14 |
| `backend/modules/collector/scheduler.py` | 포털 연속 실패 요약 알림 (3회 초과 시 일 1회) | #10 |
| `backend/api/routes/collector.py` | 백필 트리거 API 엔드포인트 (옵션) | #15 |

#### 상세 작업

**1. 포털 백필 실행**

기존 `trigger_premarket_date` API를 활용하여 5거래일 백필:
- 2026-04-04 (금)
- 2026-04-07 (월)
- 2026-04-08 (화)
- 2026-04-09 (수)
- 2026-04-10 (목)

일일 2거래일씩 나눠서 실행 (3일 소요).

**2. 백필 스크립트 (`backend/scripts/backfill_portal.py`)**

```python
# 사용법: python -m scripts.backfill_portal --start 20260404 --end 20260410 --daily-limit 2
```

**3. 포털 연속 실패 요약 알림**

- Redis에 `scheduler:portal_fail_count` 카운터
- 3회 초과 시 매 실패 알림 대신 일 1회 요약: "포털 수집 N일 연속 실패 중"

**4. 진단 쿼리 (listed_shares 커버리지)**

```sql
-- stocks.listed_shares NULL 종목 수 확인
SELECT count(*) FROM stocks WHERE is_active = true AND listed_shares IS NULL;
-- 포털 소스별 최신 날짜 확인
SELECT source, max(data_date), count(*) FROM market_data GROUP BY source;
```

### 검증 방법

| 검증 항목 | 방법 | 기대 결과 |
|----------|------|----------|
| 포털 백필 완료 | `SELECT count(*), data_date FROM market_data WHERE source='data_go_kr' AND data_date BETWEEN '2026-04-04' AND '2026-04-10' GROUP BY data_date` | 각 거래일 1500건+ |
| market_cap 갱신 | `SELECT count(*) FROM market_data WHERE source='data_go_kr' AND data_date = '2026-04-10' AND market_cap IS NOT NULL` | 1500건+ |
| listed_shares 커버리지 | `SELECT count(*) FROM stocks WHERE is_active = true AND listed_shares IS NULL` | 0~50건 이하 (신규 IPO) |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 대응 | Sprint |
|---|------|--------|------|--------|
| 1 | 14:00 수집과 08:00 수집이 같은 날 같은 데이터를 중복 upsert | 낮음 | portal_fresh 스킵 조건으로 방지, DB unique 제약조건이 이중 보호 | 1 |
| 2 | 포털 자체 장기 장애(1주+) 시 매일 14:00 실패 | 중간 | 연속 실패 요약 알림으로 알림 피로 방지, 수동 개입 유도 | 2 |
| 3 | stocks.listed_shares NULL 종목이 예상보다 많을 경우 | 중간 | Sprint 2 진단 쿼리로 확인 후 필요 시 KIS API에서 listed_shares 보조 수집 검토 | 2 |
| 4 | 14:00 포털 성공 후 당일 스크리닝에 미반영 | 낮음 | 설계 의도: 다음 거래일 품질 보장 목적. 당일 재스크리닝은 리스크 대비 가치 낮음 (박퀀트+정프로 합의) | — |
| 5 | KIS 폴백 streak 3일 차단이 수익 기회 상실 유발 | 중간 | 자동매매만 차단, 반자동은 허용 (최리스크 확정) | 1 |
| 6 | 공공데이터포털 Rate Limit (일 1,000건) 백필 시 초과 가능성 | 낮음 | 일 2거래일 한도 + 호출 수 계산으로 안전 마진 확보 (윤에이피) | 2 |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| 08:30 retry가 KIS 성공과 독립적으로 포털 재시도 | portal_fresh 기반 스킵 조건 동작 | ⬜ |
| 14:00 cron이 포털 미확보 시 정상 수집 | 포털 T-1 데이터 1500건+ 확보 | ⬜ |
| KIS 폴백 streak 3일+ 시 WARNING 알림 | 텔레그램 알림 발송 확인 | ⬜ |
| KIS 폴백 streak 3일+ 시 pipeline_healthy=false | Redis 키 확인 | ⬜ |
| validate_premarket_db 소스 확장 | data_go_kr + kis_daily 모두 카운트 | ⬜ |
| 4/4~4/10 포털 백필 완료 | 각 거래일 1500건+ 확인 | ⬜ |
| 포털 연속 실패 요약 알림 동작 | 3회 초과 시 일 1회 요약 | ⬜ |
| 기존 테스트 전부 통과 | `pytest -v` 전체 PASS | ⬜ |
