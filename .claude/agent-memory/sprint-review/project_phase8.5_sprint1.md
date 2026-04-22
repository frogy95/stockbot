---
name: Phase 8.5 Sprint 1 검증 결과
description: Phase 8.5 Sprint 1 (관측성 강화) PR #162 코드 리뷰 + 자동 검증 결과 (2026-04-22)
type: project
---

2026-04-22 Phase 8.5 Sprint 1 sprint-review 완료.

**PR**: #162 (phase8.5-sprint1 → develop)
**테스트**: 929 passed / 1 failed (pre-existing: `test_ws_manager_env_max_subscriptions`, `PAPER.max_ws_subscriptions` 20 vs 기대값 25)

**코드 리뷰**: 이슈 없음 (80점 이상 없음)
- 프로덕션 와이어링 정상: `MomentumBreakoutStrategy(redis_client=..., session_factory=...)` main.py L160-163 주입 확인
- 전략 순수성 유지: `_metrics.py` 예외 흡수, TradeSignalData import 없음

**Medium 이슈 (Sprint 2 개선 권장, Phase 8.5 문서 미해결 사항 테이블에 기록)**:
- M1: `top-rejects` API limit=50 허용 vs Redis TOP_REJECT_SIZE=5 고정 불일치
- M2: heatmap UI HOUR_MINS 09:30 시작 — 09:00~09:20 수집됨 but UI 미표시

**API 검증**: score-histogram / stage-heatmap / top-rejects / virtual-signals 4종 모두 200

**Playwright**: /diagnostics 페이지 정상 렌더링, 실시간 데이터 표시 확인

**수동 검증 필요**:
- `alembic upgrade head` (3개 신규 테이블)
- 1.5거래일 관찰: 16:05 metrics_rollup job 확인
- virtual_signals 테이블 INSERT 확인 (주문 0건 격리 검증)
- Stage heatmap 13:00~14:00 prev_close_time_guard 카운트 확인

**Why:** 신호 0건 데드락 해소를 위한 관측성 인프라 선제 배포. Sprint 2 (풀 하한 폴백 + 동적 min_volume_floor)는 1.5거래일 관찰 후 착수.
**How to apply:** 다음 Sprint 2 시작 전 수동 검증 항목 완료 여부 확인 필요.
