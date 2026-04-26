---
name: Phase 8.5 Sprint 2.5 계획
description: 2026-04-23 advisor A안 채택 인프라 보강 스프린트. 파라미터 불변, 6파일/75줄, resolve_override 통합 + 경고 배너 + 문서 DoD 동기화
type: project
---

Phase 8.5 Sprint 2.5 계획 수립 완료 (2026-04-23).

**배경**: Sprint 2 완료 후 advisor 권고안 중 "A안"(인프라 보강 + 관측성 + 문서 동기화) 채택. Sprint 2에서 확정된 파라미터 #1~#26은 전부 불변. "이미 확정된 동작을 더 안전하게 지탱하는 레일"만 깐다.

**커버 범위 (6 Task)**:
1. `core/settings_override.py::resolve_override` 통합 유틸 — Redis `settings:override:*` lookup을 3개 호출부(momentum_breakout / realtime_screener / scheduler) 단일 경유
2. `scripts/check_env_sync.py` + deploy.md Railway env 체크 항목
3. `/api/v1/metrics/override-status` + `OverrideBanner` 컴포넌트 (Telegram 미확인 대비 시각 경고)
4. fallback-stats 카드에 `is_rollback_active` 필드 (롤백 중 dimmed)
5. `docs/phase/phase8/phase8.md` Sprint 3 LIVE 게이트 DoD → D1~D7 재정의판 반영 (원안 "3거래일 연속" 폐기)
6. 통합 검증 + 5거래일 관찰 의사결정 트리(A~E) 확증

**Why**: Sprint 2 Task 5가 Redis override 규약을 설계했지만 각 호출부가 ad-hoc lookup 중이라 일관성 리스크. Phase 8.5 `phase8.5.md` Line 131~141에서 재정의한 DoD가 Phase 8 `phase8.md` 원본에 미반영 — Phase 8.6 Sprint 1 착수 시점에 혼선 예방.

**How to apply**:
- 브랜치: `phase8.5-sprint2.5` (기존 `phase8.5-sprint2`와 별도)
- 5거래일 관찰은 본 Sprint와 병행 진행 (Sprint가 관찰을 지연시키지 않음)
- 의사결정 트리 분기: A(LIVE 착수) / B(관측 +3일 연장) / C(Phase 10.1 검토) / D(자동 롤백 지속) / E(폴백 품질 불량)
- 분기 C/D/E는 전문가 4명 재리뷰 필수

**명시적 금지**: ATR_FILTER_PCT·MIN_VOLUME_FLOOR 분기값·폴백 파라미터·`SECONDARY_POOL_PASS_THRESHOLD=75.0` 변경 금지. 5거래일 관찰 단축 금지. DB 스키마 변경 없음.
