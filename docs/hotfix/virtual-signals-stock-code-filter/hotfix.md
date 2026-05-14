# Hotfix: virtual-signals stock_code 필터 미구현 수정

**브랜치:** `hotfix/virtual-signals-stock-code-filter`
**담당자:** frogy95
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-05-14

---

## 문제 분석

### 증상

`GET /api/v1/metrics/virtual-signals?stock_code=005930` 호출 시 `stock_code` 파라미터가 무시되고 모든 종목의 가상 신호 records가 반환됨. 단일 종목 trace 불가.

### 원인

2026-05-14 09:30 Phase 8.6 A안(real-momentum) 첫 검증 모니터링 점검 중 발견.
`backend/api/routes/metrics.py` `/virtual-signals` 핸들러가 `stock_code` Query 파라미터를 함수 시그니처에 선언하지 않아 요청 파라미터를 수신하지 못했고, SQLAlchemy 쿼리에도 `where` 조건이 없어 항상 전체 결과를 반환했음.

### 영향 범위

- `/api/v1/metrics/virtual-signals` endpoint에 `stock_code` 파라미터를 지정해 호출하는 클라이언트 (모니터링 trace 용도)
- 기존 호출(파라미터 미지정) 동작 변화 없음 — 회귀 위험 없음

---

## 수정 내용

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/api/routes/metrics.py` | `stock_code: str | None = Query(None)` 파라미터 추가 + `stmt.where(VirtualSignal.stock_code == stock_code)` 조건부 필터 추가 |
| `backend/tests/test_metrics_routes.py` | `stock_code` 필터 동작 검증 테스트 1종 추가 |

### 커밋 이력

| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `527dc8b` | fix(metrics): /virtual-signals stock_code 필터 미구현 수정 | 2026-05-14 |

---

## 검증

### 자동 검증

- pytest `tests/test_metrics_routes.py`: 7/7 passed (신규 1종 포함)
- 타겟 API 검증: `GET /api/v1/metrics/virtual-signals?stock_code={종목코드}` 단일 종목 필터 동작 확인

### 수동 검증

- ⬜ Railway 자동 배포 후 헬스체크 healthy 확인
- ⬜ `docker compose up --build` (코드 반영)

---

## PR

- **URL:** (PR 생성 후 기입)
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
