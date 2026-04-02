---
name: Phase 4.6 계획
description: 데이터 수집 파이프라인 근본 수리 — KIS 도메인 분리 + 수집 유효성 검증 체계(CollectionValidator) + 에러 전파 + pipeline_healthy 강화
type: project
---

Phase 4.6: 데이터 수집 파이프라인 근본 수리 (rev.3)
- 계획 수립: 2026-04-02, rev.3 수정: 2026-04-02
- 전문가 검토: 정프로(PO), 최리스크(리스크), 윤에이피(API), 김단타(단타) — 4명, rev.3까지 3회 검토
- Sprint 2개: S1 근본수리+도메인분리+유효성검증, S2 데이터품질+DB후검증+통합검증
- 핵심 파라미터 30건 확정 (rev.3에서 13건 추가/수정)

rev.3 주요 변경 (2026-04-02):
  - **premarket 최소 건수 100 -> 1,500** (KOSPI+KOSDAQ ~3,700 중 40% 이상)
  - **ETF 시세 최소 수집률 10% -> 50%** (LIVE 도메인 전환으로 상향 가능)
  - **close_price/volume null 비율 < 5%** (핵심 시세 필드)
  - **data_date 유효 범위 T-2 거래일 이내** (T-3 이전 매매 위험)
  - **CollectionResult dataclass 도입** (수집기 반환값 확장)
  - **CollectionValidator 별도 클래스** (검증 로직 분리, 테스트 용이)
  - **실패 유형 분류** (retryable/permanent)
  - **primary_screen 0건 = warning** (시장 침체 시 정상, failed 아님)
  - **dart/sentiment 0건 = warning** (보조 데이터, 파이프라인 차단 불필요)
  - **pipeline_status JSON 확장** (+ collected_count + validation dict)
  - **ETN 시세 수집 공백 기록** (Phase 5 범위)
  - **수집 범위 이원화 기록** (주식=T+1, ETF=당일, ETN=없음)

rev.2 주요 파라미터 (유지):
  - KIS 조회/매매 도메인 분리 (inquiry_client=LIVE, trading_client=TRADING_ENV)
  - inquiry Throttler/TokenManager 독립
  - 서버 시작 시 KIS_APP_KEY 존재 검증
  - ETF 시세 모의/실전 모두 required

**Why:** 0건 수집도 success 기록 + 건수 미달도 검증 없음 -> pipeline_healthy 거짓 양성 -> 매매 엔진에 쓰레기 데이터 공급 위험. 유효성 검증은 에러 전파의 자연스러운 확장.
**How to apply:** Sprint 1에서 CollectionResult + CollectionValidator를 도입하고, 각 수집기의 반환값을 확장하며, scheduler.py에서 validator 결과에 따라 status 업데이트. 임계값은 1주일 운영 후 보정.

주의사항:
- KISRestClient/KISTokenManager 클래스 자체는 수정 불필요 — 인스턴스만 분리
- 유효성 검증 임계값(1500건, 50%, 5%)은 초기 보수적 설정. 1주일 운영 후 보정 필요
- ETN 시세 수집은 Phase 5 범위 (마스터만 있고 시세 없음, 매매 대상 아님)
- 공공데이터포털 ETF/ETN API 별도 존재 여부 미확인 (Phase 5에서 조사)
- Phase 4.5 Sprint 2(프론트엔드 시스템 관리)는 Phase 4.6 완료 후 진행
