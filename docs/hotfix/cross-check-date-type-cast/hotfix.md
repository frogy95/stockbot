# Hotfix: cross_check_prices 날짜 타입 불일치 수정

**브랜치:** `hotfix/cross-check-date-type-cast`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-06

---

## 문제 분석

### 증상
종가 교차검증(`cross_check_prices`)이 항상 실패하여 1% 초과 괴리 종목을 감지하지 못함.
PostgreSQL 오류: `operator does not exist: date = character varying`

### 원인
`cross_check_prices(session, data_date: date)` 함수가 Python `date` 타입만 처리하도록 정의되어 있으나,
호출 측 `scheduler.py`에서 `"YYYYMMDD"` 형식의 문자열(str)을 전달하여 PostgreSQL 쿼리에서 타입 불일치 오류 발생.

### 영향 범위
- 영향 기능: `collector.validator.cross_check_prices` — 포털 vs KIS 종가 교차검증
- 심각도: non-blocking (종가 교차검증 실패 시 오류 무시하고 계속 진행)
- 실 영향: 종가 교차검증이 항상 실패하여 1% 초과 괴리 종목 감지 불가 (내부 품질 로직 무력화)

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/validator.py` | 함수 시그니처 `date | str` 유니온 타입으로 변경, 문자열 입력 시 `datetime.strptime("%Y%m%d").date()` 변환 로직 추가 |

### 변경 요약
1. 함수 시그니처: `data_date: date` → `data_date: date | str`
2. 함수 본문 첫 줄에 타입 가드 추가:
   ```python
   if isinstance(data_date, str):
       data_date = datetime.strptime(data_date, "%Y%m%d").date()
   ```

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `5f3fddd` | fix(collector): cross_check_prices 날짜 타입 불일치 수정 | 2026-04-06 |

---

## 검증

### 자동 검증
- pytest 전체: (PR 생성 후 결과 업데이트)
- 타겟 API 검증: 해당 없음 (내부 로직, 엔드포인트 노출 없음)

### 수동 검증
- ⬜ docker compose up --build (코드 반영)
- ⬜ 다음 거래일 08:00 premarket_pipeline 실행 시 cross_check_prices 정상 동작 확인 (Railway 로그)

---

## PR
- **URL:** https://github.com/frogy95/stockbot/pull/92
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
