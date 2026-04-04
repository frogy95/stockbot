---
name: Phase 4.8 계획
description: EOD 데이터 수집 내결함성 강화 — 공공데이터포털 SPOF 해소, KIS 일봉 보조 수집, 스케줄러 폴백/재시도
type: project
---

Phase 4.8: EOD 데이터 수집 내결함성 강화 (2026-04-02 계획 수립)

**Why:** 공공데이터포털 전일 OHLCV가 장전(08:00)에 미게시되면 1차 스크리닝 0건 → 전체 매매 파이프라인 마비. 앞으로도 반복 가능한 구조적 SPOF.

**How to apply:**
- Sprint 1: KIS 일봉 보조 수집기(KISDailyCollector) + 스케줄러 폴백 로직 + 스크리닝 소스 필터 확장
- Sprint 2: 08:30 포털 재시도 + 텔레그램 알림 + cross-check 모니터링
- 전문가 4명 검토: PO(정프로), 리스크(최리스크), 퀀트(박퀀트), API(윤에이피)
- 핵심 파라미터 17건 확정: KIS FHKST03010100, 배치 50종목, source="kis_daily", 보조 수집 성공률 80%, 재시도 1회(08:30)
- 주의: 모의거래 Rate Limit(초당 1건)으로 전 종목 수집 ~42분 → inquiry_client(실전) 사용 권고
- 주의: KIS 일봉에 시가총액 미포함 → stocks.listed_shares 기반 추정 필요
