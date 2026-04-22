---
name: Phase 8.5 Sprint 1 현황
description: Phase 8.5 Sprint 1 (관측성 강화) 계획 수립 완료 및 핵심 구현 포인트
type: project
---

# Phase 8.5 Sprint 1 — 관측성 강화

- 계획 수립: 2026-04-22
- 상태: planned (sprint-dev 대기)
- 브랜치: `phase8.5-sprint1`
- 실행 명세: `docs/phase/phase8.5/sprint1/sprint1.md`
- PR: (생성 후 기입)

## Task 구성 (8개)

1. Alembic 마이그레이션 3종: `screening_metrics_daily`, `strategy_metrics_daily`, `virtual_signals`
2. `core/metrics_keys.py` 키 규약 + `RedisClient.incr` 유틸
3. 2차 스크리닝 `total_score` 히스토그램 Redis 기록 (`>=75`와 10점 bucket 동시 기록)
4. 전략 stage 카운터 + 가상 신호 로깅 (13:00~14:00 `prev_close_time_guard` 한정, 실제 주문 절대 발생 X)
5. 16:05 APScheduler job — Redis counter → DB 일별 upsert
6. `/api/v1/metrics/*` 4종 (score-histogram / stage-heatmap / top-rejects / virtual-signals) + Redis LIST `metrics:strategy:top_reject` 보강
7. 프론트 `/diagnostics` 페이지 + 카드 4개 (카드 4는 Sprint 2용 플레이스홀더)
8. E2E 검증 + 가상 신호 격리 확증 (signals/orders 테이블 count 불변 assert)

## 핵심 주의사항

- **가상 신호 경로는 `TradeSignalData` 생성 금지**. `_metrics.py`에서 해당 import 물리적 금지. Task 8에서 `signals`/`orders` count assert로 방어.
- **Post-decision side-effect**: 기존 `_reject()`/`screen()` 반환 로직 절대 변경 금지. 카운터 기록은 반환 직전 측면 호출만.
- **카드 4 (폴백 통계)는 Sprint 1에서 placeholder만** (Coming Soon 표시, 실데이터 바인딩 금지).
- **16:00 포털 수집과 16:05 메트릭 집계는 서로 다른 job id, 5분 오프셋으로 충돌 회피**.
- **KST 타임존**: `date.today()` 금지, 반드시 `datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()` 사용 (Railway UTC 대응).
- **Redis TTL**: score 히스토그램/stage 카운터 모두 7일(604800s) TTL 최초 생성 시만 적용, 기존 키 TTL 유지.
- **`MomentumBreakoutStrategy.__init__` 시그니처**: optional `redis_client=None, session_factory=None` 기본값 유지 — 기존 테스트 회귀 방지.
- **score 75점 이중 기록 규약**: 75점 이상은 `>=75` + 해당 10점 bucket 2개 키 동시 INCR. Task 2 `score_bucket_for` 반환 리스트가 이를 보장.

## Sprint 2 (미착수) 예고 의존성

Sprint 1 배포 후 1.5거래일 관찰 → Sprint 2에서 아래 항목 소비:
- `screening_metrics_daily` 데이터로 `pass_threshold=75.0` 재평가 근거 확보
- `strategy_metrics_daily`에서 stage 병목 식별 → 동적 `MIN_VOLUME_FLOOR` 분기 근거
- `virtual_signals` 테이블로 13:00 가드 완화 여부 Phase 10.1 재평가

## 파일 변경 범위

- 백엔드 신규: 4파일 (metrics 모델, metrics_keys, api/routes/metrics, strategies/_metrics)
- 백엔드 수정: 5파일 (realtime_screener.py, momentum_breakout.py, scheduler.py, redis.py, main.py)
- 백엔드 테스트: 5신규
- 프론트엔드 신규: 5파일 (diagnostics 페이지 + 카드 4)
- 프론트엔드 수정: 2파일 (api.ts, sidebar 네비게이션)
- Alembic: 1 revision
