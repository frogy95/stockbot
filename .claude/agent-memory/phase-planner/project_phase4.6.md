---
name: Phase 4.6 계획
description: 데이터 수집 파이프라인 근본 수리 — Dockerfile --reload 제거, 에러 전파 수정, data_go_kr 날짜 폴백, pipeline_healthy 거짓 양성 방지
type: project
---

Phase 4.6: 데이터 수집 파이프라인 근본 수리
- 계획 수립: 2026-04-02
- 전문가 검토: 정프로(PO), 최리스크(리스크), 윤에이피(API), 김단타(단타) — 4명
- Sprint 2개: S1 근본수리(--reload 제거+에러전파+날짜폴백), S2 데이터품질+통합검증
- 핵심 파라미터 12건 확정
  - Dockerfile --reload 제거 (최우선)
  - premarket 최소 100건, ETF 시세 최소 10%
  - 모의환경 ETF optional, 실전 required
  - data_go_kr 날짜 폴백 최대 7일
  - pipeline_healthy = status + 건수 동시 확인
  - market_data 신선도 T-2 거래일 이내
  - 한국거래소 2026년 휴장일 하드코딩

**Why:** 데이터 수집이 며칠째 실패하면서 매매 시스템 전체가 무력화. Dockerfile --reload이 근본 원인.
**How to apply:** Sprint 1에서 --reload 제거 + 에러 전파를 우선 수정하고, Sprint 2에서 데이터 품질/통합 검증.

주의사항:
- stocks.updated_at NULL: pg_insert on_conflict_do_update에서 ORM onupdate 미작동 → 명시적 func.now() 필요
- 공공데이터포털 T+1 지연은 코드로 완전 해결 불가
- Phase 4.5 Sprint 2(프론트엔드 시스템 관리)는 Phase 4.6 완료 후 진행
