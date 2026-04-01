---
name: Phase 4.5 계획
description: 스케줄러 안정화 + 장애 복구 Phase 계획 — 2026-04-01 장전 장애 대응, 2 Sprint, 전문가 4명 검토
type: project
---

Phase 4.5: 스케줄러 안정화 + 장애 복구
- 2026-04-01 장전 테스트 장애 6건 근본 해결
- Sprint 1 (백엔드): Redis 영속화, 스케줄 의존성, pipeline_healthy, 매매 엔진 차단, ETF sanity ±30%, health/readiness, 수동 파이프라인 API, 텔레그램 장애 알림
- Sprint 2 (프론트엔드): 시스템 페이지, 파이프라인 스테퍼, 수동 트리거 버튼, 적응형 폴링

**Why:** 선행 스케줄 실패에도 후속 진행 → 잘못된 데이터 기반 매매 위험. In-memory 상태는 Railway 재시작 시 소실.

**How to apply:** Sprint 1이 긴급 (04/02 08:00 장전 전 배포 목표). pipeline_healthy 기본값은 항상 false(보수적). ETF sanity는 prev<200이면 변동률 스킵.

핵심 확정 파라미터:
- ETF sanity: ±10% → ±30% (prev<200 스킵)
- pipeline_healthy 기본값: false
- Redis TTL: 86400초 (24h)
- 상태 폴링: 5초(실행중) / 30초(유휴)

전문가 검토: 정프로(PO) + 최리스크(리스크) + 윤에이피(API) + 한유엑(UX)
- 최리스크 핵심 지적: 후속 스케줄 중지만으로 불충분, 매매 엔진도 pipeline_healthy 확인 필요
- 윤에이피 핵심 지적: 선행 가드 패턴 권장 (listener 대신), BackgroundTasks + 폴링 패턴
