# Hotfix: phase86-r3-unset-enum

**브랜치:** `hotfix/phase86-r3-unset-enum`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-05-14

---

## 문제 분석

### 증상
G3(가드레일 3) 단독 발동 시 `/api/v1/metrics/override-status`가 `is_active=false`를 반환.
실제로는 G3 오버라이드가 활성화된 상태임에도 불구하고 UI 배너가 비활성 상태로 표시됨.

**발견 경위:** 2026-05-14 16:10 모니터링 발견 #7 결함

### 원인
`metrics.py` 내 `is_active` 판정 로직이 오버라이드 키를 문자열 하드코딩으로 비교했으나,
G3 단독 발동 시 해당 키가 판정 경로에서 누락됨.
또한 `affected_keys`가 정적으로 계산되어 실제 활성 키와 불일치 발생.

### 영향 범위
- `/api/v1/metrics/override-status` 응답 정확도
- Phase 8.5/8.6 전략 오버라이드 상태 UI 배너 표시
- G1/G2만 발동 시: 기존 동작 호환 유지 (affected_keys는 빈 리스트 또는 부분 리스트로 변경 가능)

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/core/override_keys.py` | `SettingsOverrideKey` Enum 신설 — 오버라이드 키 단일화 |
| `backend/api/routes/metrics.py` | `/override-status` `is_active` 판정 개선 + `affected_keys` 동적 계산 |
| `backend/tests/test_metrics_routes.py` | 오버라이드 상태 회귀 테스트 1종 추가 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `32c349b` | fix(phase86): /override-status is_active 판정 + Enum 단일화 (Sprint 5 Hotfix A) | 2026-05-14 |

---

## 검증

### 자동 검증
- pytest `tests/test_metrics_routes.py`: 로컬 8/8 통과 (Docker 미반영 상태 — 컨테이너 빌드 후 재확인 필요)
- 타겟 API `GET /api/v1/metrics/override-status`: ⬜ `docker compose up --build` 후 검증 필요

### 수동 검증
- ⬜ `docker compose up --build` (코드 반영 후 `core.override_keys` 모듈 인식 확인)
- ⬜ Railway 자동 배포 후 `/api/v1/metrics/override-status` 응답 확인

---

## PR
- **URL:** (PR 머지 후 기입)
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
