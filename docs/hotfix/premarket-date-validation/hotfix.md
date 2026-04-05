# Hotfix: 포털 수집기 API 응답 날짜 불일치 미감지

**브랜치:** `hotfix/premarket-date-validation`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-06

---

## 문제 분석

### 증상

공공데이터포털(DataGoKrCollector)이 이전 거래일 데이터를 반환해도 "수집 성공"으로 판정 → 1차 스크리닝 후보 종목 0건 연쇄 장애 발생.

### 원인

`DataGoKrCollector.collect_all()`이 API 응답의 실제 `basDt`와 요청 `target_date`를 비교하지 않아, 포털이 당일 데이터를 미배포한 상태에서 이전 거래일 데이터를 반환해도 감지 불가.

### 영향 범위

- 장전(08:00) premarket_pipeline 실행 시 포털 API가 이전 날짜 데이터를 반환하는 경우
- 1차 스크리닝 candidates 0건 → 장중 매매 신호 0건 연쇄 장애
- KIS fallback이 발동되어야 하나 collected=0 판정이 없어 fallback 미발동

---

## 수정 내용

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/sources/data_go_kr.py` | 첫 페이지 수신 시 `basDt` vs `target_date` 비교, 불일치 시 `collected=0` 즉시 반환 |
| `backend/tests/test_data_go_kr.py` | 날짜 불일치/일치 테스트 2건 추가, 기존 테스트 날짜 mock 보정 |
| `backend/tests/test_collection_validator.py` | collected=0 시 validation 실패 확인 테스트 추가 |
| `backend/tests/test_phase2_sprint1_integration.py` | 기존 통합 테스트 날짜 mock 보정 |

### 핵심 로직

```python
# 첫 페이지에서 API 응답 날짜 검증
if page == 1:
    actual_date = items[0].get("basDt", "").strip()
    if actual_date and actual_date != target_date:
        logger.warning("포털 응답 날짜 불일치: requested=%s, actual=%s", target_date, actual_date)
        return CollectionResult(collected=0, data_date=actual_date, null_counts=null_counts)
```

### 커밋 이력

| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `4cf4003` | fix: 포털 수집기 API 응답 날짜 불일치 미감지 — basDt 검증 추가로 stale 데이터 수집 차단 | 2026-04-06 |

---

## 검증

### 자동 검증

- pytest 전체: 681 passed, 0 failed
- pytest 타겟(test_data_go_kr + test_collection_validator): 34 passed, 0 failed

### 수동 검증

- ⬜ docker compose up --build (코드 반영)
- ⬜ 다음 거래일 08:00 premarket_pipeline 실행 시 포털 날짜 불일치 → collected=0 → KIS fallback 발동 확인 (Railway 로그)

---

## PR

- **URL:** (PR 생성 후 업데이트)
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료

---

## 후속 스프린트 대상

- ETF data_date 하드코딩 수정 (`kis_collector.py:71`)
- ETF DB 검증 기준일 수정 (`validator.py:254`)
- 08:30 재시도 방어 강화 (`scheduler.py:581`)
- collected 카운터 정밀화 (`data_go_kr.py:196-201`)
