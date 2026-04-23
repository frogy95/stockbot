---
name: Phase 8.5 Sprint 2 검증 결과
description: Phase 8.5 Sprint 2 코드 리뷰 + 자동 검증 결과 요약 (2026-04-23)
type: project
---

Phase 8.5 Sprint 2 — 풀 하한 폴백 + 동적 MIN_VOLUME_FLOOR PR #170 리뷰 완료.

**Why:** Sprint 2는 신호 발생 데드락(교차 불가 구조) 해제를 위한 핵심 변경 — 검증 완료 후 develop 머지 대기.

**How to apply:** 다음 sprint-review 시 이 결과를 기준으로 잔여 수동 검증 항목 추적.

## 검증 결과

- pytest: 956 passed / 1 failed (기존 플레이크, Sprint 2 무관)
- 코드 리뷰 이슈: Critical/High 0건, Medium 1건 (M3: import bisect 인라인 — 동작 무관)
- API 검증: fallback-stats, top-rejects(limit 5/10), shadow-heatmap, stage-heatmap 모두 정상
- Playwright: /diagnostics, /screening 2차 탭 정상
- Sprint 1 M1/M2 해결 확인: top-rejects limit 상한 5 강제, heatmap 09:00 시작 수정

## 수동 미완 항목

- Railway 환경변수 8종 추가 확인 (MIN_VOLUME_FLOOR_MODE 등)
- 배포 후 5거래일 관찰: 폴백 발동 여부 + 신호 승률/손실률
- 16:10 자동 롤백 job 실제 동작 확인 (수 거래일 관찰 필요)
