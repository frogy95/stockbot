
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
- [Phase 5.1 계획](project_phase5.1.md) — change_rate 필터 수정, 전문가 4명 검토, 단일 Sprint, change_rate_min -2.0 + 적응형 [-2.0,-3.0] + 하락 종목 자동매매 금지 + 포지션 50%
- [Phase 5.2 계획](project_phase5.2.md) — KIS WS 모의 환경 안정화, 전문가 4명 검토, 단일 Sprint, rev.2: 재연결 버스트가 근본 원인(구독 수 초과 아님), paper=25종목 + 재연결 딜레이 0.5초/종목(핵심) + 7회/2초 백오프 + 캐시 TTL 10초
- [Phase 6 계획](project_phase6.md) — 스케줄러 + WS 복원력 강화, 전문가 4명 검토, 2 Sprint, 15건 파라미터 확정 (ConcurrencyError+좀비연결 수정, 가드 or, recovery 3단계, KIS REST 재시도 3회, is_trading_day 가드)
- [Phase 6.1 계획](project_phase6.1.md) — 거래량 시간가중 보정 + 5분봉 수집, 전문가 4명 1차+2차 검토, 돌파 강도 연동(5%+:1.5/3~5%:1.8/<3%:2.0) + MIN_VOLUME_FLOOR 0.5 + vol5m Redis 축적
- [Phase 6.2 계획](project_phase6.2.md) — 포털 수집 타이밍 정합성 + 재시도 정책 수정, 전문가 4명 검토, 2 Sprint, portal_fresh 기반 retry + 14:00 cron + KIS streak 3일 차단
- [Phase 7/8/9 로드맵](project_phase_data_roadmap.md) — 데이터 의존성 체인: 6.1→7(20일)→8(20일)→9(3~6개월), 착수 경고 기준 명기
