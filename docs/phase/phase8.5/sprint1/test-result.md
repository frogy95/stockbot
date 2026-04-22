# Phase 8.5 Sprint 1 — 통합 검증 결과

실행 일시: 2026-04-22 14:15 KST

## 자동 검증 결과

| 검증 항목 | 명령 | 결과 |
|-----------|------|------|
| pytest 전체 | `docker compose exec backend pytest` | ✅ **929 passed, 1 failed** (실패는 Sprint 1 무관 — 아래 참조) |
| TypeScript 타입체크 | `docker compose exec frontend npx tsc --noEmit` | ✅ 에러 없음 |
| Alembic upgrade head | `docker compose exec backend alembic upgrade head` | ✅ `a430a1c931b2` 반영 |
| `/api/v1/metrics/score-histogram` | curl | ✅ 200 OK (실데이터: 27건 `>=75`, 20건 `90-100`) |
| `/api/v1/metrics/stage-heatmap` | curl | ✅ 200 OK |
| `/api/v1/metrics/top-rejects` | curl | ✅ 200 OK (빈 리스트) |
| `/api/v1/metrics/virtual-signals` | curl | ✅ 200 OK (빈 리스트) |
| 인증 401 확인 | 토큰 없이 호출 | ✅ 401 반환 |
| `/diagnostics` 페이지 렌더링 | Playwright | ✅ 4카드 정상 렌더 (`screenshot-diagnostics.png` 참조) |
| 사이드바 "신호 진단" 메뉴 | Playwright snapshot | ✅ 활성화 표시 |
| 가상 신호 격리 | `test_momentum_breakout_metrics.py` | ✅ `signals`/`orders` count 불변 assert PASS |
| 스케줄러 `metrics_rollup` job 등록 | `test_scheduler.py::test_scheduler_registers_jobs` | ✅ PASS (job_count=7, `metrics_rollup` 포함) |
| Redis counter TTL | `test_metrics_keys.py` + 수동 TTL 확인 | ✅ 7일(604800초) |

## Sprint 1 신규 테스트 (전부 PASS)

- `tests/test_metrics_keys.py` — 16 cases
- `tests/test_realtime_screener_metrics.py` — 3 cases
- `tests/test_momentum_breakout_metrics.py` — 6 cases (가상 신호 격리 포함)
- `tests/test_scheduler_metrics_rollup.py` — 3 cases (UPSERT + 예외 흡수)
- `tests/test_metrics_routes.py` — 5 cases (인증 401 포함)

소계: **33 cases 신규 추가, 전부 PASS.**

## 사전 존재 실패 (Sprint 1 영향 없음)

- `tests/test_ws_stability.py::test_ws_manager_env_max_subscriptions` — `PAPER.max_ws_subscriptions` 상수 값 `20` vs 테스트 기대값 `25` 불일치. Sprint 1 변경과 무관 (WS 모듈 · ws_manager는 본 스프린트 수정 대상 아님). 별도 핫픽스 또는 후속 스프린트에서 처리 권장.

## 실데이터 스모크 (장중)

검증 시각(14:15 KST) 기준 Redis 카운터에 실데이터가 이미 누적 중이며 API 응답에 그대로 반영됨:

- `score-histogram` today: 40-50 = 2, 60-70 = 5, 70-80 = 7, 80-90 = 7, 90-100 = 20, `>=75` = 27
- `top-rejects`: 0건 (`prev_close` tier가 현재 상대적으로 드물게 발동)
- `virtual_signals`: 0건

> ⬜ **수동 검증 필요**: 다음 거래일 16:05 APScheduler 트리거 후 `screening_metrics_daily` / `strategy_metrics_daily` 테이블에 행이 정상 UPSERT 되는지 확인 (로그 `metrics_rollup 완료: score_rows=... stage_rows=... date=YYYY-MM-DD`).

## 스크린샷

- `docs/phase/phase8.5/sprint1/screenshot-diagnostics.png` — `/diagnostics` 전체 페이지 (4카드 그리드 + 사이드바)

## 미완 / 후속

- Phase 8.5 Sprint 2에서 폴백 발동 통계 카드를 실제 데이터 바인딩으로 전환.
- `test_ws_stability` 실패는 별도 추적 필요.
