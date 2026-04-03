---
name: Phase 4.8 Sprint 1 상태
description: KIS 일봉 보조 수집기 + 스케줄러 폴백 — 계획 수립 완료
type: project
---

Phase 4.8 Sprint 1 — KIS 일봉 보조 수집기 + 스케줄러 폴백

**Status:** 계획 수립 완료 (2026-04-02)

**Why:** 공공데이터포털 SPOF 해소 — 전일 OHLCV 미게시 시 1차 스크리닝 0건 장애 방지

**How to apply:** 5개 Task (KIS REST 메서드 -> 보조 수집기 -> 스케줄러 폴백 -> 소스 필터 확장 -> 통합 테스트). 모두 순차 의존성.

**주의사항:**
- inquiry_client(실전 조회 전용) 사용 — 모의거래에서 FHKST03010100 미지원 가능성
- market_cap은 KIS 일봉에 미포함 → stocks.listed_shares * close_price 추정
- source="kis_daily"로 태깅, "kis_rest"(ETF)와 구분
- 배치 50종목 단위 commit (부분 실패 복구)
- 보조 수집 최소 성공률 80%
