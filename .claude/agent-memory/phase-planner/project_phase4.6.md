---
name: Phase 4.6 계획
description: 데이터 수집 파이프라인 근본 수리 — KIS 조회/매매 도메인 분리 + Dockerfile --reload 제거 + 에러 전파 수정 + pipeline_healthy 거짓양성 방지
type: project
---

Phase 4.6: 데이터 수집 파이프라인 근본 수리 (rev.2)
- 계획 수립: 2026-04-02, rev.2 수정: 2026-04-02
- 전문가 검토: 정프로(PO), 최리스크(리스크), 윤에이피(API), 김단타(단타) — 4명
- Sprint 2개: S1 근본수리(--reload 제거+도메인분리+에러전파+날짜폴백), S2 데이터품질+통합검증
- 핵심 파라미터 17건 확정 (rev.2에서 5건 추가)
  - Dockerfile --reload 제거 (최우선)
  - **KIS 조회/매매 도메인 분리** (inquiry_client=항상 LIVE, trading_client=TRADING_ENV)
  - **inquiry Throttler 독립** (LIVE 기준 0.07초)
  - **inquiry TokenManager 독립** (LIVE 전용 인스턴스)
  - **서버 시작 시 KIS_APP_KEY 존재 검증**
  - premarket 최소 100건, ETF 시세 최소 10%
  - ETF 시세 모의/실전 모두 **required** (rev.2 변경: optional -> required)
  - data_go_kr 날짜 폴백 최대 7일
  - pipeline_healthy = status + 건수 동시 확인
  - market_data 신선도 T-2 거래일 이내
  - 한국거래소 2026년 휴장일 하드코딩

**Why:** ETF 시세 전량 실패의 근본 원인은 "모의 API 한계"가 아니라 "도메인 라우팅 설계 결함". 조회 tr_id(FHKST*)는 환경 무관 고정값인데, TRADING_ENV=paper이면 모의 도메인으로 라우팅되어 HTTP 500 반환.
**How to apply:** Sprint 1에서 --reload 제거 + 도메인 분리 + 에러 전파를 우선 수정. KISRestClient 내부 수정 없이 인스턴스 2개 생성으로 해결. main.py lifespan에서 이중 초기화.

주의사항:
- KISRestClient/KISTokenManager 클래스 자체는 수정 불필요 — 인스턴스만 분리
- Redis 토큰 키 자동 분리: kis:live:access_token / kis:paper:access_token
- TRADING_ENV=live 시 Rate Limit 공유 가능성 -> Phase 5에서 검토
- stocks.updated_at NULL: pg_insert on_conflict_do_update에서 ORM onupdate 미작동
- 공공데이터포털 T+1 지연은 코드로 완전 해결 불가
- Phase 4.5 Sprint 2(프론트엔드 시스템 관리)는 Phase 4.6 완료 후 진행
