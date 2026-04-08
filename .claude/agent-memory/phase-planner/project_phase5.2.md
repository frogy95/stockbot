---
name: Phase 5.2 계획
description: KIS WebSocket 모의 환경 안정화 — 구독 수 초과 해결, 재연결 안정화, 2차 스크리닝 WS 연동
type: project
---

Phase 5.2: KIS WebSocket 모의 환경 안정화

**Why:** 모의 환경에서 WS 구독 수(35종목 x 2 tr_id = 70건)가 모의 한도(~40건)를 초과하여 재연결 반복, 2차 스크리닝 장중 마비.

**How to apply:**
- 단일 Sprint: 환경별 구독 제한(paper=20, live=35) + 재연결 로직(7회, 2초 백오프, 0.5초/종목 딜레이) + 2차 스크리닝 WS 연동 + 캐시 TTL 10초
- 전문가 4명 검토: 정프로(PO), 최리스크(리스크), 윤에이피(API), 김단타(단타)
- 핵심 파라미터 11건 확정
- Phase 6 이관: WS 장애 시 REST 폴백 감시, 장중 동적 우선순위 조정
