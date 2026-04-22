# Phase 8.5 Sprint 1 — 통합 검증 계획

## 자동 검증 항목

- ✅ pytest 전체 통과 (Sprint 1 신규 33 cases 포함)
- ✅ TypeScript 타입 체크 에러 없음
- ✅ /api/v1/metrics/* 4종 엔드포인트 200 OK
- ✅ /diagnostics 페이지 렌더링 + 4카드 스크린샷
- ✅ 가상 신호 격리 (signals/orders 테이블 count 불변 assert, test_momentum_breakout_metrics.py)
- ✅ Alembic upgrade head 반영 확인
- ✅ 스케줄러 `metrics_rollup` job 등록 확인

## 수동 검증 항목 (권장)

- ⬜ 관측성 실데이터 스모크: 장 중 14:00 이후 Redis 카운터 증가 → 16:05 집계 → DB 행 존재
- ✅ 브라우저에서 `/diagnostics` 접속 → 4카드 시각 확인 (Playwright 대행)
- ✅ 레이아웃 반응형 (1열 / 2열 그리드) 확인 — md:grid-cols-2 적용
