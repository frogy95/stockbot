---
name: Phase 6 계획
description: 스케줄러 + WS 복원력 강화 계획 수립 완료, 전문가 4명 검토, 2 Sprint, 15건 파라미터 확정
type: project
---

Phase 6 계획 수립 완료 (2026-04-12). 2026-04-10 프로덕션 장애 분석 결과 기반.

**Why:** 장전 수집 -> 스크리닝 -> WS 구독 전체 파이프라인 실패. Phase 5.2에서 WS 재연결 안정화했으나 실 운영에서 추가 결함 발견.

**How to apply:**
- Sprint 1: 치명적 버그 5건 + Phase 5.2 미해결 #6(좀비 연결) + is_trading_day 핵심 가드 + WS open_timeout/subscribe 가드
- Sprint 2: KIS REST 재시도/백오프 + recovery 단계적 재시도(09:05/09:10/09:15) + premarket 예외 KIS 폴백 + 나머지 is_trading_day 가드
- 전문가: 정프로(PO), 최리스크(리스크관리), 윤에이피(API), 김단타(단타) 4명 검토
- 핵심 결정: KIS REST 재시도는 kis_daily_collector.py에만 적용(주문 API 제외), Phase 5.2 미해결 #6 Sprint 1에서 해결, 기존 Phase 6 범위(모바일/센티멘트/DART)는 Phase 7로 이관
- 15건 파라미터 확정 (phase6.md "검토팀 확정 파라미터" 표 참조)
