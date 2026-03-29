---
name: Phase 1 Sprint 2 계획 상태
description: Phase 1 Sprint 2 (한투 API 연동 + 토큰 관리 + 모의/실전 전환) 완료 상태
type: project
---

Phase 1 Sprint 2 완료 (2026-03-29).

**Why:** 한투 API(REST + WebSocket) 연동으로 실시간 시세 수신 및 주문 인프라 확보.

**How to apply:**
- 브랜치: phase1-sprint2
- PR: https://github.com/frogy95/stockbot/pull/3
- 한투 토큰 자동 갱신 (Redis 캐싱, 만료 시 재발급)
- TRADING_ENV 플래그로 모의/실전 전환 (도메인, APP_KEY/SECRET, 계좌번호, tr_id 일괄 전환)
- 모의거래 Rate Limit 초당 1건 스로틀링 내장
