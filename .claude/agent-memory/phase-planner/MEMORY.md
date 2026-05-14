
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
- [Phase 6.2 계획](project_phase6.2.md) — 장전 수집 단순화 (KIS 주경로 + 포털 장후 보조), 전문가 4명 rev.2 검토, 단일 Sprint, 08:00 KIS 직접 + 16:00 포털 보조 + 상태관리 전면 제거
- [Phase 7.0 계획](project_phase7.0.md) — 매매 엔진 결함 수정 + LIVE 전환 준비, 전문가 4명 검토, 3 Sprint, P0 3건 + P1 2건 + P2 3건 + E2E 검증 + LIVE 게이트, 기존 Phase 7→7.1 리넘버링
- [Phase 7.0.1 계획](project_phase7.0.1.md) — KIS LIVE WS 연결 복구, 전문가 4명 검토, 단일 Sprint, ws_url /tryitout 경로 추가 + Railway Static IP + PAPER 별도 수정
- [Phase 7.2 계획](project_phase7.2.md) — 매매 전략 진입 조건 개선, 전문가 4명 검토, 2 Sprint, H0STCNT0 OHLC 파싱 추가(idx 7/8/9) + 다층 진입(prev_close+prev_high) + 갭 분기 open_price + 반포지션 50% + 일일 10건
- [Phase 7/8/9 로드맵](project_phase_data_roadmap.md) — 데이터 의존성 체인: 6.1→7.1(20일)→8(20일)→9(3~6개월), 착수 경고 기준 명기
- [Phase 8/9/10 재편성 계획](project_phase8_9_10.md) — 2026-04-20 사용자 A안 지시 반영, 전문가 4명 리뷰, Phase 7.1/7.2/8/9 초안을 8/9/10으로 재편성, Phase 9 데이터 의존성 재검토(KIS 백필+점진 활성화), Phase 10은 완화 불가 명시, Phase 10.1 분리
- [Phase 8.5 계획 제안](project_phase8.5.md) — 2026-04-22 신호 0건 교차 단절 브리지, 전문가 4명 페르소나 기반 리뷰, 2 Sprint (관측성+풀 폴백/동적 floor), 시간 슬라이딩·prev_close 연장 거부, Phase 9/10/10.1 순서 유지, ROADMAP 미반영(사용자 승인 대기)
- [Phase 8.5 Sprint 2.5 계획](project_phase8.5-sprint2.5.md) — 2026-04-23 advisor A안 채택, 파라미터 불변 + 인프라 보강 단일 Sprint, 6 Task (resolve_override 통합 + env 동기화 + 경고 배너 + fallback 카드 + phase8 DoD 재정의 + 5거래일 관찰 의사결정 트리 A~E), 브랜치 phase8.5-sprint2.5
- [Phase 8.6 계획](project_phase8.6.md) — 2026-04-28 분기 D 트리거 선제 착수, 신호 생성 로직 구조 재설계 (직렬 AND→병렬 OR + ATR 분위수 + volume_surge tier + DoR G1~G3 + walk-forward 60일), 4 Sprint, 38건 파라미터, 기존 Phase 8.6(LIVE 게이트) → Phase 8.7로 시프트, 기존 Phase 10.1(백로그) → Phase 10.1 자리 유지(Phase 10.2 폐기), 분기 D 4명 재리뷰 입력
- [Phase 8.6 Sprint 5 신설](project_phase8.6-sprint5.md) — 2026-05-14, Sprint 1~4 완료 후 모니터링 14개 결함 처리, 진단·측정 Sprint(T1~T8), Phase 8.7 entry gate 표면 카운트 폐기 → 10개 지표(WS 누락률 ≤5% / fallback 비중 ≤20% / 단일 stage ≤50% / 4h 교체율 ≤30% / Paper PnL 양 / 손절 ≥1 / R1~R4 plan-code 일치 / R3 전수 회귀 / G-Bt1 / G-Bt2) 재정의, hotfix 2건(#7 R3 unset Enum, #12 /screening/primary change_rate) 즉시 분리, #11 진짜 본체=stage 직렬 AND(tier는 Sprint 2에서 OR 완료), Sprint 1~4 본문 unchanged + DoD #9~#11 deprecated 표시, Sprint 6 placeholder, 4명 합의(API+퀀트+리스크+PO)
