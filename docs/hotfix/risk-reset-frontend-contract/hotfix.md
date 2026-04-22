# Hotfix: 리스크 카운터 리셋 버튼 응답 계약 불일치 수정

**브랜치:** `hotfix/risk-reset-frontend-contract`
**담당자:** ChoiJiSeon
**리뷰어:** ChoiJiSeon
**상태:** ✅ 배포 완료
**배포일:** 2026-04-22

---

## 문제 분석

### 증상
프로덕션 대시보드의 "일일 리스크 카운터 초기화" 버튼이 클릭 시 항상 "리셋 실패" 오류 메시지를 표시함.

### 원인
프론트엔드 `resetRiskCounters()` 함수가 `{ ok: boolean, message: string }` 형태의 응답을 기대하였으나,
백엔드 `POST /api/v1/trading/risk/reset`은 `risk_status` dict (연속 손절 카운터, 비상 정지 플래그 등 포함)를 반환.
이로 인해 `result.ok === undefined → falsy` 판정 → 항상 실패 분기 진입.

실제로는 백엔드에서 리셋이 정상 수행되고 있었음:
- Railway 로그 `POST /api/v1/trading/risk/reset HTTP/1.1 200 OK` 확인
- Railway 로그 `당일 시작 잔고 캐시` 로그 정상 출력 확인

### 영향 범위
- 영향 기능: 대시보드 리스크 관리 카드의 "일일 리스크 카운터 초기화" 버튼
- 영향 사용자: 모든 사용자 (관리자 버튼 표시 시)
- 백엔드 리셋 동작 자체에는 문제 없음 — UI 피드백만 오작동

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `frontend/lib/api.ts` | `resetRiskCounters()` 반환 타입을 `{ ok: boolean; message: string }` → `Record<string, unknown>` (실제 risk_status dict)으로 수정, `throw`하지 않으면 성공으로 처리 |
| `frontend/components/risk/reset-button.tsx` | `handleReset`에서 `result.ok` 검사 제거, `await resetRiskCounters()` throw 미발생 시 `setDone(true)` 처리로 변경 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `42cf0c1` | fix(frontend): 리스크 카운터 리셋 버튼 응답 계약 불일치 수정 | 2026-04-22 |

---

## 검증

### 자동 검증
- TypeScript 타입 체크: `npx tsc --noEmit` 통과 여부 — deploy.md 참조
- Playwright 리셋 버튼 동작 검증: deploy.md 참조

### 수동 검증
- ⬜ `docker compose up --build` (코드 반영)
- ⬜ 프로덕션 대시보드에서 리셋 버튼 클릭 시 "✅ 리셋 완료" 메시지 표시 확인

---

## PR
- **URL:** (PR 생성 후 기입)
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
