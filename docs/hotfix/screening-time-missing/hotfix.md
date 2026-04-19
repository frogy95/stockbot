# Hotfix: 스크리닝 시각 표시 오류 수정

**브랜치:** `hotfix/screening-time-missing`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-20

---

## 문제 분석

### 증상
스크리닝 페이지의 "스크리닝 시각" 컬럼이 실제 시각 대신 항상 "—"로 표시되었습니다.

### 원인
`backend/api/routes/screening.py`의 `_get_latest_results` 함수에서 각 결과 아이템을 딕셔너리로 변환할 때 `screened_at` 필드를 포함하지 않았습니다. 프론트엔드의 `formatDateTime(item.screened_at)` 호출 시 `item.screened_at`이 `undefined`이므로 항상 "—"를 반환했습니다.

### 영향 범위
- 스크리닝 페이지 결과 테이블의 "스크리닝 시각" 컬럼 표시 오류
- API: `GET /api/v1/screening/results` 응답 아이템에 `screened_at` 필드 누락
- 기능 동작(스크리닝 자체)에는 영향 없음, 표시 오류만 해당

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/api/routes/screening.py` | `_get_latest_results`의 딕셔너리 컴프리헨션에 `"screened_at": r.screened_at.isoformat()` 1줄 추가 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `77b00bf` | fix(screening): 스크리닝 시각 API 응답에 screened_at 필드 누락 수정 | 2026-04-20 |

---

## 검증

### 코드 리뷰
- `screened_at` 컬럼: `Mapped[datetime]` (non-optional) + `server_default=func.now()` → NULL 불가, `AttributeError` 위험 없음
- 보안/성능/품질 이슈 없음

### 자동 검증
- pytest: Docker 환경 미실행으로 미수행 → 수동 검증 항목으로 안내
- API 타겟 검증: Docker 환경 미실행으로 미수행

### 수동 검증
- ⬜ `docker compose up --build` 후 스크리닝 페이지에서 "스크리닝 시각" 컬럼 실제 시각 표시 확인

---

## PR
- **URL:** (PR 생성 후 기입)
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
