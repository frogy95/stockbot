---
name: Phase 4.6 Sprint 1 계획 수립
description: Phase 4.6 Sprint 1 (근본 수리 + KIS 도메인 분리 + 유효성 검증) 계획 수립 완료
type: project
---

Phase 4.6 Sprint 1 계획 수립 완료 (2026-04-02).

**Why:** 데이터 수집 파이프라인이 며칠째 실패 중 — Dockerfile --reload 무한 재시작, KIS 도메인 미분리로 ETF 시세 전량 실패, 0건 수집도 success 기록. 8개 Task로 분할하여 체계적 수리.

**How to apply:**
- Sprint 문서: `docs/phase/phase4.6/sprint1/sprint1.md`
- 브랜치: `phase4.6-sprint1`
- Task 8개: Dockerfile 수정, KIS 도메인 분리, CollectionResult/Validator 도입, 수집기 4종 개선, scheduler 통합, 테스트
- Phase 2 (Task 4/5/6)는 병렬 실행 가능 (파일 소유권 겹침 없음)
- 주의: inquiry_client는 항상 LIVE 환경, KIS_APP_KEY 미설정 시 warning만 (서버 차단 안 함)
- 주의: CollectionValidator의 T-2 거래일 판정은 주말만 건너뜀, 공휴일은 Sprint 2에서 추가
- 주의: naver collect_sentiments의 CollectionResult.collected는 뉴스 건수가 아닌 종목 수 기준
