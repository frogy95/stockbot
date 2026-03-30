---
name: Phase 2 Sprint 1 계획 상태
description: Phase 2 Sprint 1 (핵심 데이터 수집 — 공공데이터포털 + 한투 WS/REST + 체결강도) 완료 상태
type: project
---

Phase 2 Sprint 1 완료 (2026-03-29).

**Why:** 장전 일괄 수집(공공데이터포털) + 장중 실시간 수집(한투 WS/REST) 2단계 수집 체계 구축.

**How to apply:**
- 브랜치: phase2-sprint1
- PR: https://github.com/frogy95/stockbot/pull/5
- Task 8개: screening_results 테이블 → 공공데이터포털 수집기 → WS 파서 → 체결강도 → WS 매니저 → ETF 수집기 → 스케줄러 → 통합 테스트
- 공공데이터포털: 6회 API 호출로 전 종목(~2,880개) OHLCV/시총 일괄 수집
- 한투 WS: H0STCNT0(체결), H0STASP0(호가) 파싱, 35종목 상한
- 체결강도: 5분 윈도우 기반 매수/매도 비율 직접 계산
- APScheduler: 장전(08:00) / 장중(09:00~15:30) / 장후 스케줄
- 리뷰 지적: DB 세션 독립 생성, screening_results created_at/updated_at 추가
