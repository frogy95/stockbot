# Phase 4.9 검토 리포트 — 윤에이피 (API 개발자)

> **검토일**: 2026-04-06
> **검토 대상**: Phase 4.9 장전 파이프라인 복원력 강화 아키텍처 초안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| DB 기반 의존성 전환 구현 방식 | ✅ 통과 |
| validate_screening_readiness() 설계 | ✅ 통과 |
| _premarket_retry 후 재실행 로직 | ⚠️ 주의 — 동시성 고려 필요 |
| 허용 소스 필터 | ✅ 통과 |

---

## 2. 항목별 검증 결과

### validate_screening_readiness() 구현
- 기존 `validate_premarket_db()`와 유사한 패턴 — DB 쿼리로 건수/null 비율 검증
- **차이점**: source 필터에 `kis_daily`도 포함해야 함 (validate_premarket_db는 data_go_kr만 검증)
- **쿼리 성능**: market_data 테이블에 `(data_date, source)` 인덱스가 있으므로 빠름
- **구현 위치**: `CollectionValidator`에 추가하는 것이 기존 패턴과 일관적

### _premarket_retry 후 재실행
- 현재 `_premarket_retry()`는 독립 CronTrigger (08:30)로 실행
- 재시도 성공 후 `_primary_screen()` + 후속 단계를 호출하려면 **PIPELINE_RUNNING_KEY 락 충돌 주의**
- 08:00 체인 파이프라인이 이미 완료되었으므로 락은 해제된 상태
- **단, 수동 트리거(run_premarket_pipeline)가 동시에 실행 중일 수 있음** → 락 확인 필수

### 동시성 시나리오
```
08:00 체인: premarket(실패) → primary_screen(스킵) → ... → 완료 → 락 해제
08:30 retry: premarket 재시도 성공 → primary_screen 재실행 시도
           → 이때 수동 trigger가 동시에 실행 중이면?
           → PIPELINE_RUNNING_KEY 확인 후 이미 실행 중이면 재실행 스킵
```

### DEPENDENCY_MAP 변경 영향
- 초안에서 `DEPENDENCY_MAP["primary_screen"]`에서 `["premarket"]` 제거를 제안
- **이 변경은 불필요**: primary_screen 내부에서 DB 검증을 하면 됨
- DEPENDENCY_MAP을 유지하되, `_check_dependency` 대신 `validate_screening_readiness`로 대체
- 또는 `_check_dependency`에 DB 폴백 로직을 추가하는 방식도 가능
- **권고**: DEPENDENCY_MAP은 유지하되, primary_screen 전용 의존성 체크를 오버라이드

---

## 3. 파라미터 조정 권고

| # | 항목 | 초안값 | 권고값 | 근거 |
|---|------|--------|--------|------|
| 3 | 허용 데이터 소스 | data_go_kr, kis_daily | **동일 유지** | screener의 date_subq와 일관성 |
| 추가 | 재실행 시 락 타임아웃 | 미정 | **락 확인 후 이미 실행 중이면 스킵** | 수동 트리거와 충돌 방지 |
| 추가 | 재실행 대상 단계 | primary_screen만 | **primary_screen + dart + sentiment** | PO(정프로)와 합의: 후속 단계도 포함 |

---

## 4. 리스크 및 대안

| 리스크 | 심각도 | 대안 |
|--------|--------|------|
| _premarket_retry에서 _primary_screen 직접 호출 시 에러 전파 | ⚠️ Medium | try/except로 감싸고, 실패 시 기존 상태 유지 |
| validate_screening_readiness DB 쿼리 실패 | ⚠️ Low | 쿼리 실패 시 기존 pipeline_status 기반 체크로 폴백 |
| DEPENDENCY_MAP 변경으로 다른 단계에 사이드 이펙트 | ⚠️ Medium | DEPENDENCY_MAP은 그대로 유지, primary_screen만 오버라이드 |

---

## 5. 최종 의견

**승인**. 구현 난이도가 낮고 기존 패턴(CollectionValidator, pipeline_status)을 재사용할 수 있어 안전한 변경. 핵심 주의사항:
1. DEPENDENCY_MAP은 그대로 유지 — primary_screen의 의존성 체크만 DB 기반으로 오버라이드
2. _premarket_retry 성공 후 재실행 시 PIPELINE_RUNNING_KEY 락 확인 필수
3. validate_screening_readiness의 소스 필터를 screener와 상수 공유
