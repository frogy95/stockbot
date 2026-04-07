---
name: Phase 5 계획
description: Phase 5 — 1차 스크리닝 안정화 + 완전 자동 모드 + 성과 분석, 전문가 4명 검토, 3 Sprint, 12건 파라미터 확정
type: project
---

Phase 5 계획 수립 완료 (2026-04-07).

**Why:** 프로덕션 모니터링에서 1차 스크리닝 통과 0건 발견 (volume_ratio >= 2.0에 88% 탈락). 기존 Phase 5(완전 자동+성과분석)에 스크리닝 안정화를 Sprint 1로 선행 배치.

**How to apply:**
- Sprint 1: 스크리닝 안정화 (volume_ratio 1.5, 적응형 [1.5,1.2], prev_volume 5일 평균 폴백, 기본 후보 거래량 상위 15개 2차 직접 투입, date.today() KST 전환 5개 파일)
- Sprint 2: 완전 자동 모드 (Sprint 1 배포 후 **5거래일 관찰 필수** — 최리스크 확정)
- Sprint 3: 성과 분석 대시보드
- 전문가: 정프로(PO), 최리스크(리스크), 박퀀트(퀀트), 김단타(단타) 4명
- 핵심 확정사항: 적응형 최저 1.2 (1.0 금지), 기본 후보 반자동만+50% 사이징, risk_manager.py KST 최우선
- Phase 6 이관: 장세 판별 모듈, rolling z-score, IC 기반 가중치
