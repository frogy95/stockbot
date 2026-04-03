---
name: Phase 4.8 Sprint 2 상태
description: 재시도 스케줄 + 알림 + 모니터링 — 계획 수립 완료 (2026-04-03)
type: project
---

Phase 4.8 Sprint 2 — 재시도 스케줄 + 알림 + 모니터링

**Why:** Sprint 1에서 KIS 폴백 수집기를 구현했지만, 포털 08:30 재시도/알림/cross-check가 누락. Phase 4.8 완료를 위해 Sprint 2 필요.

**How to apply:**
- 수정 파일 3개: scheduler.py, validator.py, 테스트 3개
- scheduler.py에 _premarket_retry (08:30 CronTrigger), _send_fallback_info_alert, _send_double_failure_alert 추가
- validator.py에 cross_check_prices (포털 vs KIS 종가 1% 괴리) 추가
- Sprint 1 이슈 #6: KIS 폴백 반환값 — 이미 `return kis_result.collected` 존재, 포털 실패 경로에서 `return result.collected`에 도달하지 않도록 확인 필요
- DB 스키마 변경 없음, 새 의존성 없음
