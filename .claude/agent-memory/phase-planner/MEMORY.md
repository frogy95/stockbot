
## Phase 계획 이력

- [Phase 0.5 계획](project_phase0.5.md) — 외부 API 탐색/검증 계획 수립 완료, 전문가 4명 검토 결과 포함
- [Phase 1 계획](project_phase1.md) — 개발 환경 + 한투 API 기반 계획 수립 완료, 전문가 5명 검토, 미확정 6건 확정
- [Phase 2 계획](project_phase2.md) — 데이터 수집 + 종목 스크리닝 계획 수립 완료, 전문가 5명 검토, Sprint 2->3 확장, 핵심 파라미터 10건 확정
- [Phase 2.5 계획](project_phase2.5.md) — ETF 마스터 적재 계획 수립 완료, 전문가 3명 검토, 단일 Sprint, mst 파싱+폴백+sanity check
- [Phase 2.6 계획](project_phase2.6.md) — KIS mst 파서 올바른 구현, 전문가 3명 검토, 단일 Sprint, 줄바꿈 분리+offset 61:63 수정
- [Phase 3 계획](project_phase3.md) — 매매 엔진 + 기본 알림, 전문가 5명 검토, 3 Sprint, 15건 파라미터 확정 (비상정지 -4%, 레버리지 5%, 당일 청산 14:50)
- [Phase 4 계획](project_phase4.md) — 웹 대시보드 MVP, 전문가 4명 검토, 2 Sprint, 22건 파라미터 확정 (한국 색상, 3중 모드 표시, 모드 전환 보호, JWT 24h, SWR 폴링)
- [Phase 4.5 계획](project_phase4.5.md) — 스케줄러 안정화 + 장애 복구, 전문가 4명 검토, 2 Sprint, pipeline_healthy 플래그 + ETF sanity ±30% + Redis 영속화
- [Phase 4.6 계획](project_phase4.6.md) — 데이터 수집 파이프라인 근본 수리, 전문가 4명 검토, 2 Sprint, rev.2: KIS 조회/매매 도메인 분리 + Dockerfile --reload 제거 + 에러 전파 + 날짜 폴백 + pipeline_healthy 거짓양성 방지
