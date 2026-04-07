
## Phase 계획 이력

- [Phase 0.5 계획](project_phase0.5.md) — 외부 API 탐색/검증 계획 수립 완료, 전문가 4명 검토 결과 포함
- [Phase 1 계획](project_phase1.md) — 개발 환경 + 한투 API 기반 계획 수립 완료, 전문가 5명 검토, 미확정 6건 확정
- [Phase 2 계획](project_phase2.md) — 데이터 수집 + 종목 스크리닝 계획 수립 완료, 전문가 5명 검토, Sprint 2->3 확장, 핵심 파라미터 10건 확정
- [Phase 2.5 계획](project_phase2.5.md) — ETF 마스터 적재 계획 수립 완료, 전문가 3명 검토, 단일 Sprint, mst 파싱+폴백+sanity check
- [Phase 2.6 계획](project_phase2.6.md) — KIS mst 파서 올바른 구현, 전문가 3명 검토, 단일 Sprint, 줄바꿈 분리+offset 61:63 수정
- [Phase 3 계획](project_phase3.md) — 매매 엔진 + 기본 알림, 전문가 5명 검토, 3 Sprint, 15건 파라미터 확정 (비상정지 -4%, 레버리지 5%, 당일 청산 14:50)
- [Phase 4 계획](project_phase4.md) — 웹 대시보드 MVP, 전문가 4명 검토, 2 Sprint, 22건 파라미터 확정 (한국 색상, 3중 모드 표시, 모드 전환 보호, JWT 24h, SWR 폴링)
- [Phase 4.5 계획](project_phase4.5.md) — 스케줄러 안정화 + 장애 복구, 전문가 4명 검토, 2 Sprint, pipeline_healthy 플래그 + ETF sanity ±30% + Redis 영속화
- [Phase 4.6 계획](project_phase4.6.md) — 데이터 수집 파이프라인 근본 수리, 전문가 4명 검토, 2 Sprint, rev.3: 수집 유효성 검증(CollectionValidator+CollectionResult) + 임계값 대폭 상향(1500건/50%/5%) + 실패 유형 분류 + ETN 공백 기록
- [Phase 4.7 계획](project_phase4.7.md) — 1차 스크리닝 스코어링 구조 수정, 전문가 4명 검토, 단일 Sprint, 3팩터 분리(A안 전원 합의) + 1차 임계값 60.0 + 2차 임계값 75.0
- [Phase 4.8 계획](project_phase4.8.md) — EOD 데이터 수집 내결함성 강화, 전문가 4명 검토, 2 Sprint, KIS 일봉 보조 수집(FHKST03010100) + 스케줄러 폴백 + 08:30 재시도 + 17건 파라미터 확정
- [Phase 4.9 계획](project_phase4.9.md) — 장전 파이프라인 복원력 강화, 전문가 4명 검토, 단일 Sprint, DB 기반 스크리닝 의존성(validate_screening_readiness) + pipeline_healthy=false 유지 + 재시도 후 재실행 + 11건 파라미터 확정
- [Phase 5 계획](project_phase5.md) — 1차 스크리닝 안정화 + 완전 자동 모드 + 성과 분석, 전문가 4명 검토, 3 Sprint, volume_ratio 1.5 + 적응형 [1.5,1.2] + 기본 후보 거래량 상위 15개 + Sprint 2 전 5거래일 관찰 필수
