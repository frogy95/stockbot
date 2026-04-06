# Phase 4.9: 장전 파이프라인 복원력 강화 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-06)
> **ROADMAP 참조**: `ROADMAP.md` Phase 4.9
> **검토 리포트**:
>
> - `phase4.9-po-review.md` (정프로, PO)
> - `phase4.9-risk-review.md` (최리스크, 리스크관리)
> - `phase4.9-quant-review.md` (박퀀트, 퀀트)
> - `phase4.9-api-review.md` (윤에이피, API 개발자)

---

## 개요

2026-04-06 프로덕션 장애에서 발견된 **장전 파이프라인 복원력 부족** 문제를 해결한다. Phase 4.8에서 KIS 일봉 폴백을 구현했지만, 이중 실패(포털+KIS) 시에도 DB에 유효한 T-1 데이터가 존재함에도 불구하고 1차 스크리닝이 무조건 차단되는 설계 결함이 남아있다.

### 문제 분석

```
[현재 장애 흐름]
08:00 포털 수집 실패 → KIS 폴백도 실패 (이중 실패)
  → pipeline_status["premarket"]["status"] = "failed"
  → _primary_screen() → _check_dependency("primary_screen") → False
  → 스크리닝 스킵 → 당일 매매 전체 불능
  
[하지만 실제로는]
DB에 전일(T-1) 유효 데이터 1500건 이상 존재
  → 스크리닝에 필요한 데이터는 충분
  → 파이프라인 상태만으로 차단하는 것은 과잉 방어

[08:30 재시도 갭]
08:30 _premarket_retry 성공 → premarket "success"로 업데이트
  → 하지만 primary_screen은 이미 "skipped" → 재실행 트리거 없음
  → 장 시작(09:00)까지 스크리닝 미완료
```

### 해결 아키텍처

```
[개선된 의존성 체크]
_primary_screen() 호출 시:
  ├─ 1순위: pipeline_status["premarket"] == "success" → 정상 진행
  └─ 2순위: DB 데이터 충분성 검증 (validate_screening_readiness)
       ├─ T-1/T-2 데이터 >= 1500건 + null_ratio < 5% → 스크리닝 진행
       │    ├─ T-1 데이터: 정상 진행 (경고 없음)
       │    └─ T-2 데이터: 경고 알림 + 진행
       └─ 데이터 부족 → 스크리닝 스킵 (기존 동작)

[재시도 후 재실행]
08:30 _premarket_retry 성공 시:
  ├─ primary_screen "skipped" 확인
  └─ 후속 단계 재실행: _primary_screen() → _dart_collect() → _sentiment_collect()
```

**핵심 원칙 (최리스크 확정)**:
- `pipeline_healthy`와 `screening_ready`는 분리 개념
- 수집 실패 시 `pipeline_healthy=false` 유지 (자동 매매 차단)
- DB 데이터 충분하면 스크리닝은 허용 (반자동 모드에서 사용 가능)

---

## 검토팀 확정 파라미터 (2026-04-06)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 윤에이피(API 개발자) — 4명

### 스크리닝 의존성 전환 파라미터

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| 1 | 스크리닝 의존성 체크 방식 | pipeline_status 전용 | **pipeline_status 우선 + DB 폴백** | 파이프라인 상태보다 실제 데이터가 더 신뢰할 수 있는 지표 (전원 합의) | 윤에이피 |
| 2 | DB 데이터 충분성 임계값 | — | **1500건** | Phase 4.6 validate_premarket과 일관성 (박퀀트+최리스크 합의) | 박퀀트 |
| 3 | 허용 데이터 날짜 범위 | — | **T-1 정상, T-2 경고 허용** | T-2에서도 절대값 기준 필터는 유효하나 품질 경고 필요 (박퀀트+최리스크) | 박퀀트 |
| 4 | 허용 데이터 소스 | — | **`data_go_kr`, `kis_daily`** | screener의 date_subq와 일관성 (윤에이피) | 윤에이피 |
| 5 | DB 데이터 null_ratio 임계값 | — | **5% (close_price 기준)** | validate_premarket과 일관성 (박퀀트) | 박퀀트 |

### pipeline_healthy / screening_ready 분리 파라미터

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| 6 | DB 폴백 시 pipeline_healthy | "true" (조건부) | **"false" 유지** | 수집 실패 시 healthy=true 전환은 자동 매매 활성화 위험 — 절대 불가 (최리스크) | 최리스크 |
| 7 | 이중 실패 + DB 데이터 존재 시 | 미정 | **스크리닝 진행 + pipeline_healthy=false 유지 + 텔레그램 경고** | 스크리닝 허용하되 자동 매매 차단. 반자동 승인 기반만 가능 (최리스크) | 최리스크 |
| 8 | T-2 데이터 사용 시 알림 | 미정 | **텔레그램 경고 알림 발송** | T-2 데이터는 비상용. 사용자에게 반드시 고지 (최리스크+정프로) | 최리스크 |

### 재시도 후 재실행 파라미터

| # | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|---|------|----------|--------|------|------|
| 9 | 재시도 성공 후 재실행 범위 | primary_screen만 | **primary_screen + dart + sentiment** | 스크리닝만 재실행하면 후속 단계가 "skipped" 상태로 남음 (정프로) | 정프로 |
| 10 | 재실행 시 락 처리 | 미정 | **PIPELINE_RUNNING_KEY 확인, 실행 중이면 스킵** | 수동 트리거와 충돌 방지 (윤에이피) | 윤에이피 |
| 11 | DEPENDENCY_MAP 변경 | primary_screen 의존성 제거 | **유지 — primary_screen만 DB 폴백 오버라이드** | 다른 단계에 사이드 이펙트 방지 (윤에이피) | 윤에이피 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 | DB 기반 스크리닝 의존성 + 재시도 후 재실행 | validate_screening_readiness, _primary_screen DB 폴백, _premarket_retry 후속 재실행, 테스트 | 없음 |

---

## Sprint 1 상세 — DB 기반 스크리닝 의존성 + 재시도 후 재실행

### 백엔드

| 파일 | 작업 | 신규/수정 |
|------|------|----------|
| `backend/modules/collector/validator.py` | `validate_screening_readiness(session)` 메서드 추가 — DB에서 T-1/T-2 market_data 건수, null 비율, 소스별 건수 검증 | 수정 |
| `backend/modules/collector/scheduler.py` | `_primary_screen()` 의존성 체크 변경 — pipeline_status 우선 + DB 폴백 | 수정 |
| `backend/modules/collector/scheduler.py` | `_premarket_retry()` 성공 후 primary_screen + dart + sentiment 재실행 로직 추가 | 수정 |
| `backend/modules/collector/scheduler.py` | DB 폴백 스크리닝 시 텔레그램 알림 (경고/정보) 추가 | 수정 |
| `backend/tests/test_screening_readiness.py` | validate_screening_readiness 단위 테스트 | **신규** |
| `backend/tests/test_pipeline_db_fallback.py` | DB 폴백 스크리닝 + 재시도 후 재실행 통합 테스트 | **신규** |

### 프론트엔드

- 이 Sprint에서는 프론트엔드 변경 없음

### 재사용 자산

| 기존 모듈 | 재사용 방식 |
|-----------|-----------|
| `CollectionValidator.validate_premarket_db()` | 동일 쿼리 패턴 재사용 (source 필터만 확장) |
| `_check_dependency()` | 기존 로직 유지, primary_screen만 오버라이드 |
| `_update_step_status()` | 파이프라인 상태 기록 그대로 사용 |
| `_send_failure_alert()` / `_send_fallback_info_alert()` | 알림 패턴 확장 |
| `PIPELINE_RUNNING_KEY` | 재실행 시 락 확인에 사용 |
| `market_data` 테이블 인덱스 `(data_date, source)` | validate_screening_readiness 쿼리 성능 |

### 구현 상세

#### 1. validate_screening_readiness() — validator.py

```python
async def validate_screening_readiness(self, session: AsyncSession) -> ValidationResult:
    """DB에 스크리닝 가능한 데이터가 충분한지 검증.
    
    검증 항목:
    - T-2 이내 market_data 건수 >= 1500
    - close_price null 비율 < 5%
    - 소스: data_go_kr OR kis_daily
    
    Returns:
        ValidationResult with details: {total_count, null_ratio, data_date, sources}
    """
    today = datetime.now(KST).date()
    boundary = get_prev_trading_day(today, n=2)
    
    # 소스 필터: screener의 date_subq와 일치
    sources = ["data_go_kr", "kis_daily"]
    
    # 전체 건수 + 최신 날짜
    total_stmt = select(
        func.count(), func.max(MarketData.data_date)
    ).where(
        MarketData.data_date >= boundary,
        MarketData.source.in_(sources),
    )
    result = await session.execute(total_stmt)
    total_count, latest_date = result.one()
    
    if total_count < 1500:
        return ValidationResult(
            passed=False,
            failure_type="data_insufficient",
            failure_reason=f"DB 스크리닝 데이터 부족: {total_count} < 1500",
            details={"total_count": total_count, "boundary_date": str(boundary)},
        )
    
    # null 비율
    null_stmt = select(func.count()).where(
        MarketData.data_date >= boundary,
        MarketData.source.in_(sources),
        MarketData.close_price.is_(None),
    )
    null_result = await session.execute(null_stmt)
    null_count = null_result.scalar_one()
    null_ratio = null_count / total_count
    
    if null_ratio >= 0.05:
        return ValidationResult(
            passed=False,
            failure_type="data_quality",
            failure_reason=f"close_price null 비율 초과: {null_ratio:.1%}",
            details={"total_count": total_count, "null_ratio": null_ratio},
        )
    
    # 소스별 건수 (디버깅용)
    source_stmt = select(
        MarketData.source, func.count()
    ).where(
        MarketData.data_date >= boundary,
        MarketData.source.in_(sources),
    ).group_by(MarketData.source)
    source_result = await session.execute(source_stmt)
    source_counts = {row[0]: row[1] for row in source_result.all()}
    
    # T-2 경고 판정
    prev_trading_day = get_prev_trading_day(today, n=1)
    is_stale = latest_date is not None and latest_date < prev_trading_day
    severity = "warning" if is_stale else "info"
    
    return ValidationResult(
        passed=True,
        severity=severity,
        details={
            "total_count": total_count,
            "null_ratio": null_ratio,
            "latest_date": str(latest_date),
            "source_counts": source_counts,
            "is_stale": is_stale,
        },
    )
```

#### 2. _primary_screen() 의존성 오버라이드 — scheduler.py

```python
async def _primary_screen(self) -> dict:
    """08:10 1차 스크리닝: DB 정적 필터 + 팩터 스코어링."""
    # 1순위: 기존 pipeline_status 기반 의존성 체크
    dep_ok = await self._check_dependency("primary_screen")
    
    if not dep_ok:
        # 2순위: DB 데이터 충분성 검증 (폴백)
        try:
            async with self._session_factory() as db_session:
                readiness = await self._validator.validate_screening_readiness(db_session)
            if readiness.passed:
                logger.warning(
                    "premarket 실패지만 DB 데이터 충분 — 스크리닝 진행 (DB 폴백): %s",
                    readiness.details,
                )
                if readiness.severity == "warning":
                    await self._send_stale_data_alert(readiness.details)
            else:
                logger.warning("스크리닝 스킵: premarket 실패 + DB 데이터 부족 (%s)", readiness.failure_reason)
                await self._update_step_status("primary_screen", "skipped", error=readiness.failure_reason)
                return {"skipped": True, "candidates": 0, "passed": 0}
        except Exception as e:
            logger.warning("DB 충분성 검증 실패 — 기존 의존성 체크 따름: %s", e)
            await self._update_step_status("primary_screen", "skipped")
            return {"skipped": True, "candidates": 0, "passed": 0}
    
    # 이하 기존 스크리닝 로직 동일
    ...
```

#### 3. _premarket_retry() 후속 재실행 — scheduler.py

```python
async def _premarket_retry(self) -> None:
    """08:30 포털 재시도 ..."""
    # ... 기존 재시도 로직 ...
    
    if validation.passed:
        # 기존: 상태 업데이트 + 알림
        ...
        
        # 신규: primary_screen이 "skipped" 상태면 후속 단계 재실행
        pipeline_status = await self._get_pipeline_status()
        screen_status = pipeline_status.get("primary_screen", {}).get("status")
        if screen_status == "skipped":
            existing = await self._redis.get(PIPELINE_RUNNING_KEY)
            if existing:
                logger.warning("파이프라인 실행 중 — 재시도 후 재실행 스킵")
                return
            logger.info("포털 재시도 성공 → 스크리닝 + 후속 단계 재실행")
            try:
                await self._primary_screen()
                await self._dart_collect()
                await self._sentiment_collect()
            except Exception as e:
                logger.exception("재시도 후 재실행 실패: %s", e)
```

#### 4. 텔레그램 알림 추가 — scheduler.py

```python
async def _send_stale_data_alert(self, details: dict) -> None:
    """T-2 데이터로 스크리닝 진행 시 [경고] 알림 발송."""
    if self._telegram_bot is None:
        return
    msg = (
        f"<b>[경고]</b> DB 폴백 스크리닝 — T-2 데이터 사용\n"
        f"최신 데이터: {details.get('latest_date')}\n"
        f"건수: {details.get('total_count')}건\n"
        f"소스: {details.get('source_counts')}"
    )
    await self._telegram_bot.send_notification(msg)
```

### 주의사항

| # | 항목 | 심각도 |
|---|------|--------|
| 1 | validate_screening_readiness의 소스 필터를 screener의 date_subq와 반드시 동일하게 유지 | ⚠️ 필수 |
| 2 | pipeline_healthy=false 유지 원칙: DB 폴백 스크리닝이 성공해도 healthy 전환 금지 | 🔴 필수 |
| 3 | _premarket_retry 후 재실행 시 PIPELINE_RUNNING_KEY 락 확인 | ⚠️ 필수 |
| 4 | validate_screening_readiness 쿼리 실패 시 기존 의존성 체크로 폴백 (안전한 실패) | ⚠️ 필수 |
| 5 | T-2 데이터 사용 시 텔레그램 경고 알림 발송 | 권고 |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 담당 | 대응 |
|---|------|--------|------|------|
| 1 | T-2 데이터로 모멘텀 팩터 왜곡 가능성 | ⚠️ Low | 박퀀트 | 5일 윈도우에서 1일 차이는 통계적으로 미미. 로깅으로 모니터링 |
| 2 | validate_screening_readiness와 screener 소스 필터 불일치 가능성 | ⚠️ Medium | 윤에이피 | 소스 리스트를 상수로 공유하여 동기화 |
| 3 | _premarket_retry 후 재실행과 수동 트리거 충돌 | ⚠️ Medium | 윤에이피 | PIPELINE_RUNNING_KEY 락 확인으로 방지 |
| 4 | DB 폴백 스크리닝 성공 → pipeline_healthy=true 전환 리스크 | 🔴 High | 최리스크 | _are_core_steps_healthy() 로직이 premarket "success"를 요구하므로 자연 차단. 단, 코드 리뷰에서 재확인 필수 |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| validate_screening_readiness | DB 데이터 충분성 검증 메서드 구현 + 단위 테스트 | ⬜ |
| _primary_screen DB 폴백 | premarket 실패 시 DB 검증 폴백 동작 | ⬜ |
| pipeline_healthy 분리 | DB 폴백 스크리닝 성공해도 pipeline_healthy=false 유지 | ⬜ |
| _premarket_retry 후 재실행 | 재시도 성공 시 primary_screen + dart + sentiment 자동 재실행 | ⬜ |
| 텔레그램 알림 | DB 폴백 경고 + T-2 경고 알림 | ⬜ |
| 통합 테스트 | 이중 실패 → DB 폴백 스크리닝 + 재시도 성공 → 재실행 시나리오 | ⬜ |
| phase4.8 이슈#7 해결 확인 | cross_check_prices 호출 이미 구현 확인 → 문서 업데이트 | ⬜ |
