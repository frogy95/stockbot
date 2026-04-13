---
name: Phase 7/8/9 데이터 의존성 로드맵
description: Phase 7~9 데이터 의존성 체인 및 착수 경고 기준 — 축적 미완 시 AI 경고 필수
type: project
---

Phase 7~9 데이터 의존성 로드맵 (2026-04-13 확정)

의존성 체인:
- Phase 6.1 → Phase 7: 5분봉 Redis(vol5m:*) 최소 20거래일 축적
- Phase 7 → Phase 8: 시간대별 DB(volume_5min_history) + VWAP 최소 20거래일 축적
- Phase 8 → Phase 9: 실전 운영 데이터 최소 3~6개월 축적

착수 경고 기준:
- Phase 7: vol5m:* 키 < 20거래일 → 경고
- Phase 8: volume_5min_history < 20거래일 → 경고
- Phase 9: 운영 < 3개월 → 경고

각 Phase에서 구축하는 후속 인프라:
- Phase 6.1: 5분봉 Redis 수집 (Phase 7용)
- Phase 7: 시간대별 DB + VWAP Redis 수집 (Phase 8용)
- Phase 8: VWAP 엔진 + 백테스트 데이터셋 (Phase 9용)

**Why:** 데이터 부족 상태 착수 → 과적합/통계 유의성 부족 → 실전 손실 직결.

**How to apply:** 
1. Phase 착수 지시 시 축적 상태를 확인 (Redis DBSIZE 또는 DB COUNT)
2. 미달이면 경고 발생, 사용자 명시적 Override 없으면 진행 불가
3. Override 시 제약 조건을 Phase 문서에 기록
