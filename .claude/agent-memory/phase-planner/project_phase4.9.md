---
name: Phase 4.9 계획
description: 장전 파이프라인 복원력 강화 — DB 기반 스크리닝 의존성 전환, 재시도 후 재실행, pipeline_healthy 분리
type: project
---

Phase 4.9: 장전 파이프라인 복원력 강화 계획 수립 완료 (2026-04-06)

**Why:** 2026-04-06 프로덕션 장애 — 이중 실패(포털+KIS) 시 DB에 유효 T-1 데이터 있어도 스크리닝 차단. Phase 4.8 이슈 #8 (High) 해결.

**How to apply:**
- 전문가 4명 검토 (정프로, 최리스크, 박퀀트, 윤에이피), 11건 파라미터 확정
- 단일 Sprint: DB 기반 스크리닝 의존성 + 재시도 후 재실행
- 핵심 파라미터: DB 충분성 임계값 1500건, T-1 정상/T-2 경고, pipeline_healthy=false 유지 원칙
- 최리스크 핵심 조건: pipeline_healthy와 screening_ready 분리 — DB 폴백 성공해도 자동 매매 차단
- Phase 4.8 이슈 #7 (cross_check_prices 누락)은 이미 해결 확인 → 문서 업데이트 완료
