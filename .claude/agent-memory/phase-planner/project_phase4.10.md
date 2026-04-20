---
name: Phase 4.10 계획
description: ETF 2차 스크리닝 KeyError 근본 해결 + KIS inquire-price 기반 장중 NAV 파이프라인 구축 + 괴리율 절대 컷오프 리스크 안전장치
type: project
---

## Phase 4.10 — ETF 2차 스크리닝 근본 해결 + NAV 파이프라인 (2026-04-20 계획)

**배경**: 프로덕션 2차 스크리닝 31% 실패율 (45회 중 14회 KeyError: 'tracking_error_factor'). ETF가 2차 필터 통과 시 확정 크래시 + 해당 배치의 주식 신호까지 동반 소실 (SPOF 전파).

**근본 원인**: (1) NAV 데이터 파이프라인 부재, (2) realtime_screener ETF 분기 누락, (3) scorer 계약 불일치, (4) SPOF 격리 부재, (5) ETF 회귀 테스트 전무.

**전문가 검토 수렴 결과 (4명)**:

1. Sprint 3개 분리 (긴급 지혈 / NAV 연동 / 정식 운영). 단일 Sprint 통합 기각 — 31% 장애 진행 중이므로 즉시 지혈 필요.
2. NAV 소스: KIS inquire-price 응답 필드(`nav`, `etf_dspr`)를 Redis 캐시(`realtime:{code}:etf_nav`, TTL 30초) — 별도 API 연동 없음, DB 스키마 변경 없음, EOD NAV는 Phase 9로 보류.
3. 장중 iNAV만 사용 (EOD NAV 불필요). market_data.nav 컬럼 추가 안 함.
4. 레버리지/인버스 ETF는 NAV 폴백 상태에서 signal_generator 완전 제외 (Sprint 1부터). 임시는 종목명 패턴 매칭, Sprint 3에서 Stock.etf_leverage_type 필드로 정식화.
5. 괴리율 절대 컷오프 (Sprint 3): 일반 ETF 2%, 레버리지/인버스 1.5%. 1차 스크리닝 조기 필터 3%.
6. scorer.score_candidates 내부에서 stock/ETF 각각 try/except 격리 — ETF 실패가 주식 배치를 파괴하지 않도록.

**Sprint 구성**:
- Sprint 1 (0.5~1일, 2026-04-21 장 개시 전 배포 목표): ETF 분기 폴백 + SPOF 격리 + 레버리지 제외 + 회귀 테스트
- Sprint 2 (1~2일, Sprint 1 배포 후 24h PAPER + 72h LIVE 관찰 통과 후 착수): KIS NAV 실시간 연동 + etf_pipeline_healthy
- Sprint 3 (1.5~2일, Sprint 2 배포 후 3일 관찰 후 착수): 절대 컷오프 + Stock.etf_leverage_type Alembic + Sprint 1 폴백 제거

**주요 파라미터 27건 확정** (A: Sprint 구성 4건, B: Sprint 1 9건, C: Sprint 2 14건, D: Sprint 3 9건 — 중복 포함).

**Why**: Phase 4.7이 1차 스크리닝 스코어링 구조 수정(3팩터 분리)이므로 2차 스크리닝 스코어링 구조 수정은 4.x 시리즈의 직접 연장. Phase 4.5~4.9가 모두 긴급 장애 대응이므로 4.10도 같은 맥락에서 검색/추적. Phase 2.7로 분류 가능성 검토했으나 "스코어링 구조" 주제 일치가 더 중요.

**How to apply**:
- Sprint 1은 반드시 "크래시 방지"에 범위 한정. scorer 리팩토링 금지, 1차 스크리너 건드리기 금지. market_data 스키마 변경 금지.
- Sprint 1 폴백 코드에 `# FIXME(phase4.10-sprint2):` 주석 필수. Sprint 3 완료 시 grep 0건 검증.
- Sprint 2 착수 전 모의거래에서 KODEX 200(069500)/레버리지(122630)/인버스(114800) 3종 샘플 조회로 KIS inquire-price 응답 nav 필드 타입/단위 실측 검증 필수.
- Phase 7.0 Sprint 3 LIVE 전환 게이트 체크리스트에 "Phase 4.10 Sprint 2 완료" 조건 추가.
- etf_pipeline_healthy는 주식 경로 pipeline_healthy와 독립 관리 — ETF 장애가 주식 매매를 차단하지 않도록.

**재사용 패턴**:
- Phase 4.9 `_send_stale_data_alert` 텔레그램 알림 패턴 → Sprint 2 NAV 장애 알림에 재사용.
- Phase 4.6 LIVE inquire_client 원칙 → Sprint 2 KIS NAV 조회에 적용.
- Phase 6 Sprint 2 재시도/백오프 로직 → Sprint 2 kis_collector.get_etf_nav에 재사용.
- Phase 4.7 FactorScorer factors 파라미터 미해결 #7 → Sprint 1 B7에서 `.get()` 방어로 동시 해소.

**주의사항(향후 Phase에 전파할 것)**:
- 임시 폴백(0.0 하드코딩)의 영구화/미전파 리스크는 이번에 두 번째 재발(커밋 ade1d9d에 이어). 향후 Phase에서 폴백 도입 시 반드시 (a) warning 로깅, (b) FIXME 주석, (c) 제거 게이트 3중 방어 강제.
- ETF 도메인 결정에는 반드시 김단타(단타) 전문가 리뷰 포함 — 이번에 iNAV vs EOD NAV, 괴리율 스코어링 vs 컷오프 구분 등 실무 관점 수정 사항 다수 발생.
