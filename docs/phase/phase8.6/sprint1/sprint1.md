# Sprint 1: 선행 패치 + DoR 가드레일 G1~G3 (Phase 8.6)

**Goal:** Phase 8.5 분기 D 손실을 빠르게 차단하고 (PO Sprint 2.6 안 흡수), Sprint 2 착수의 차단 해제 조건인 LIVE 자금 보호 가드레일(G1·G2·G3 + Phase 7.0 LIVE 파라미터 코드 잠금)을 구축한다.

**Architecture:**
- 폴백/플로어 파라미터(SECONDARY_POOL_FALLBACK_THRESHOLD=5, min_volume_floor 시간대 슬라이딩 0.3 09~11시)는 기존 `realtime_screener._apply_fallback`·`_resolve_min_volume_floor` 분기에 최소 침습 추가.
- M-F2(G1)는 `is_fallback` 플래그를 신호 → 주문 → 체결 → DB까지 전파하기 위한 컬럼·메타데이터 채널을 신설하여 일별 폴백 신호율 계산을 가능하게 만든다.
- 자동 롤백 R1~R4(G2)와 1차→2차 회로차단기(G3)는 신규 모듈 `modules/safety/` 아래에 두고 16:10 잡(또는 16:10 근처 신규 잡)에서 OR 평가 + Phase 8.6 변경분 일괄 비활성화 env 토글을 발동한다.
- Phase 7.0 LIVE 파라미터(max_position=2, position_size=5%, daily_max_loss=-2%, emergency_stop=-3%)는 `core/constants.py`에 `Final` 상수로 잠그고 빌드 실패 단위 테스트로 회귀 0건을 보장한다.
- 모든 신규 토글은 **dry_run 우선** — 신규 평가 로직만 활성화하고 실 거래 영향은 env 1줄로 즉시 원복 가능.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 async / Alembic / pytest / Redis / APScheduler / Next.js 16 / shadcn-ui

**Sprint 기간:** 2026-04-29 ~ (사용자 검토 후 구현, 4~6일 예상)
**이전 스프린트:** Phase 8.5 Sprint 2.5 (✅ 완료, PR #172) — 인프라 보강 + 관측성·문서 정합성
**브랜치명:** `phase8-sprint1` (worktree 사용 금지, develop 기반)

---

## 제외 범위 (이번 Sprint에서 하지 않음)

- 병렬 OR tier 분리 (Sprint 2)
- ATR 분위수 캘리브레이션 잡 (Sprint 2)
- `volume_surge` tier 신설 + 시간대 필터(09:00~09:10·14:30+) (Sprint 3)
- 60일 Walk-forward 백테스트 + KS/카이제곱 자동 감지 (Sprint 4)
- 폴백 종목 일일 -1% 별도 한도 (Sprint 2 또는 Sprint 3 — risk_manager 변경 동반)
- VI 재개 tier, 테마 모멘텀 가중치, 피라미딩, 2차 점수 하이브리드 (모두 Phase 10.2)

---

## 실행 플랜

> **의존성 분석**: G1 메타데이터 채널이 깔려야 G2 R4(폴백 비중)와 G3 회로차단기가 정확히 측정된다. 따라서 **Phase 1(G1 + 즉시 적용 폴백/플로어 파라미터) → Phase 2(G2 + G3) → Phase 3(잠금 + UI + 통합 검증)** 순서로 진행한다.

### Phase 1 (순차 — G1 메타데이터 + Sprint 2.6 흡수 패치)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | Phase 7.0 LIVE 파라미터 `Final` 상수 잠금 + 빌드 실패 테스트 (회귀 0건 보장 — 다른 Task의 안전망) | 백엔드 | — |
| Task 2 | 폴백 임계 5종 상향 + min_volume_floor 시간대 슬라이딩 0.3 (09~11시) | 백엔드 | — |
| Task 3 | G1 — `is_fallback` 메타데이터 신호 → 주문 전파 + DB 컬럼 마이그레이션 + M-F2 API | 백엔드 | `feature-dev:feature-dev` |

### Phase 2 (순차 — G2 + G3, Phase 1 완료 후)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | G2 — 자동 롤백 R1~R4 OR 트리거 모듈 + env 토글 + 16:10 잡 | 백엔드 | — |
| Task 5 | G3 — 1차→2차 통과율 회로차단기 모듈 + Phase 8.6 변경분 일괄 비활성화 env | 백엔드 | — |

### Phase 3 (병렬 가능 — UI + 통합 검증)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | M-F2 카드 + R1~R4 다중 트리거 시각화 (대시보드) | 프론트엔드 | `frontend-design` |
| Task 7 | DoR 4종 통합 검증 + Paper 1거래일 회귀 검증 + deploy.md 환경변수 등록 | 전체 | `superpowers:verification-before-completion` |

> **팀 실행**: Phase 3 Task 6·7은 파일 소유권이 겹치지 않아 병렬 가능. Phase 1·2는 동일 Task가 직전 Task 결과(컬럼/env)를 직접 참조하므로 순차 강제.

---

### Task 1: Phase 7.0 LIVE 파라미터 코드 잠금 + 회귀 방지 테스트

**skill:** —

**Files:**
- Create: `backend/core/constants.py`
- Create: `backend/tests/core/test_phase70_locked_constants.py`

**Step 1: 테스트 작성 (회귀 시 빌드 실패)**
- `backend/tests/core/test_phase70_locked_constants.py` 생성
- 검증 내용:
  - `from core.constants import LIVE_MAX_POSITION_COUNT, LIVE_POSITION_SIZE_PCT, LIVE_DAILY_MAX_LOSS_PCT, LIVE_EMERGENCY_STOP_PCT` 임포트 성공
  - 4개 상수의 값이 정확히 `2, 5.0, -2.0, -3.0`
  - `typing.get_type_hints` 또는 `typing.Final` 메타데이터 검사로 `Final[...]` 타입임을 확인 (`typing._SpecialForm` / `__metadata__` 활용)
  - 모듈 내에 위 상수를 재할당하는 `=` 라인이 없음을 정적 검사 (텍스트 grep으로 충분)
- 검증: `docker compose exec backend pytest tests/core/test_phase70_locked_constants.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 잠금 상수 모듈 생성**
- `backend/core/constants.py` 생성:
  ```python
  """Phase 7.0 LIVE 파라미터 코드 레벨 잠금 (리스크 G9).

  본 상수는 Phase 8.6 어떤 변경에서도 수정 금지. 변경 시 회귀 테스트가 빌드를 실패시킨다.
  """
  from typing import Final

  LIVE_MAX_POSITION_COUNT: Final[int] = 2
  LIVE_POSITION_SIZE_PCT: Final[float] = 5.0
  LIVE_DAILY_MAX_LOSS_PCT: Final[float] = -2.0
  LIVE_EMERGENCY_STOP_PCT: Final[float] = -3.0
  ```
- 본 상수는 **참조 전용**. 기존 `seed_settings.py` / DB settings 키 동작은 그대로 유지하되, 향후 Phase 8.6 어떤 변경에서도 위 4개 값을 변경하지 못하도록 만드는 게이트로 사용.
- 검증: `docker compose exec backend pytest tests/core/test_phase70_locked_constants.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/constants.py backend/tests/core/test_phase70_locked_constants.py
git commit -m "feat(phase8.6-sprint1): task1 — Phase 7.0 LIVE 파라미터 Final 상수 잠금 + 회귀 방지 테스트"
```

**완료 기준:**
- ⬜ pytest `test_phase70_locked_constants.py` 통과
- ⬜ 4개 상수 모두 `Final[...]` 타입으로 선언

---

### Task 2: 폴백 임계 5종 상향 + min_volume_floor 시간대 슬라이딩 0.3 (09~11시)

**skill:** —

**Files:**
- Modify: `backend/core/config.py` (env 추가)
- Modify: `backend/modules/screening/realtime_screener.py` (`_apply_fallback` `need` 산출에 영향 없음 — 임계만 상향)
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (`_resolve_min_volume_floor`에 시간대 슬라이딩)
- Modify: `backend/tests/test_realtime_screener.py` (임계 5 검증)
- Modify: `backend/tests/strategies/test_momentum_breakout.py` (시간대 슬라이딩 검증)
- Modify: `.env.example` (신규 env 주석 추가)

**Step 1: 테스트 작성 (실패하는 케이스 먼저)**
- `test_momentum_breakout.py`에 신규 테스트 케이스 추가:
  - `test_resolve_min_volume_floor_morning_window_returns_0_3`: snapshot.now_kst가 09:30 / tier=prev_high / strong=False → 결과 0.3 (현재 코드는 0.5)
  - `test_resolve_min_volume_floor_afternoon_window_keeps_legacy`: now_kst가 13:00 / tier=prev_high → 0.5 유지
  - `test_resolve_min_volume_floor_morning_window_respects_hard_floor`: hard_floor=0.4로 오버라이드 시 max(0.3, 0.4) = 0.4 강제
- `test_realtime_screener.py`에 폴백 임계 검증 케이스 추가/수정 (passed_count=4 → 폴백 발동, 5종까지 backfill).
- 검증: `docker compose exec backend pytest tests/test_realtime_screener.py tests/strategies/test_momentum_breakout.py -v`
- 예상: FAIL (3 신규 케이스)

**Step 2: 폴백 임계 상향 (config 기본값 변경)**
- `backend/core/config.py`:
  - `SECONDARY_POOL_FALLBACK_THRESHOLD: int = Field(default=3, ...)` → `default=5`
  - `SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP: int = Field(default=5, ge=1, le=10, description="폴백 보강 종목 수 상한 (Sprint 1 — 분기 D 풀 협소 대응)")` 신규 추가 (현재는 `SECONDARY_POOL_MAX - passed_count`로만 제한되므로 명시적 상한)
- `realtime_screener.py:257~262`의 `need` 계산식에 신규 hard cap min을 추가:
  ```python
  need = max(min(
      settings.SECONDARY_POOL_FALLBACK_THRESHOLD - passed_count,
      settings.SECONDARY_POOL_MAX - passed_count,
      settings.SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP,
  ), 0)
  ```

**Step 3: min_volume_floor 시간대 슬라이딩 추가**
- `momentum_breakout.py:_resolve_min_volume_floor`:
  - 함수 시그니처에 `now_kst: datetime | None = None` 매개변수 추가 (기존 호출부 호환을 위해 default None, None이면 `_now_kst()` 호출)
  - 모드 = "dynamic" 분기 안에서 `result` 결정 직후, **HARD floor 강제 적용 직전**에 다음 추가:
    ```python
    # Phase 8.6 Sprint 1 — 시간대 슬라이딩 (09:00~11:00 → 0.3, 그 외 유지)
    if 9 <= now_kst.hour < 11:
        result = min(result, 0.3)
    ```
  - 기존 strong 분기로 0.4가 나와도 09~11시는 0.3으로 더 완화.
- 호출부 (264, 437)에 `now_kst=snapshot.now_kst` (또는 `_now_kst()`) 전달 (snapshot에 시각이 없으면 함수 내부 fallback).
- 검증: `docker compose exec backend pytest tests/test_realtime_screener.py tests/strategies/test_momentum_breakout.py -v`
- 예상: PASS

**Step 4: .env.example 업데이트 + 커밋**
- `.env.example`에 신규/변경 env 주석 추가:
  ```
  # Phase 8.6 Sprint 1 — 분기 D 손실 차단 (PO Sprint 2.6 흡수)
  SECONDARY_POOL_FALLBACK_THRESHOLD=5            # v2.6.1 3 → 5
  SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP=5    # 폴백 보강 상한
  ```
- 커밋:
```
git add backend/core/config.py backend/modules/screening/realtime_screener.py backend/modules/trading/strategies/momentum_breakout.py backend/tests/test_realtime_screener.py backend/tests/strategies/test_momentum_breakout.py .env.example
git commit -m "feat(phase8.6-sprint1): task2 — 폴백 임계 5종 + min_volume_floor 시간대 슬라이딩 0.3 (09~11시)"
```

**완료 기준:**
- ⬜ pytest 신규 3 케이스 + 기존 케이스 모두 PASS
- ⬜ `.env.example`에 신규 env 명시 (Railway 수동 설정 필요 — Task 7에서 deploy.md 등록)

---

### Task 3: G1 — `is_fallback` 메타데이터 전파 + DB 컬럼 + M-F2 API

**skill:** `feature-dev:feature-dev` (다중 모듈 전파 — realtime_screener·signal_generator·order_manager·models·api·alembic 5+ 파일)

**Files:**
- Modify: `backend/core/models/trading.py` (TradeSignal·Order 모델에 `fallback` 컬럼)
- Create: `backend/alembic/versions/{timestamp}_phase86_sprint1_fallback_metadata.py`
- Modify: `backend/modules/trading/signal_generator.py` (candidate.is_fallback → reason JSON·fallback 컬럼)
- Modify: `backend/modules/trading/order_manager.py` (또는 주문 생성 진입점 — signal.fallback → orders.fallback 전파)
- Create: `backend/api/routes/diagnostics.py` (또는 metrics.py 확장 — 둘 중 metrics.py 확장 권장)
- Modify: `backend/api/routes/metrics.py` (`GET /api/v1/metrics/fallback-signal-rate`)
- Create: `backend/tests/test_g1_fallback_metadata_propagation.py`

**Step 1: 테스트 작성 (회귀 + 신규)**
- `backend/tests/test_g1_fallback_metadata_propagation.py`:
  - 시나리오 1: candidate에 `is_fallback=True` 포함 → SignalGenerator가 `TradeSignal.reason["fallback"]=True` + DB 컬럼 `fallback=True`로 저장
  - 시나리오 2: 일반 후보 (is_fallback 미설정 또는 False) → `fallback=False`
  - 시나리오 3: 신호 → 주문 변환 시 `Order.fallback`이 부모 신호의 값을 그대로 승계
  - 시나리오 4: M-F2 API — 그날 fallback=True 신호 / fallback 발동 종목수 비율 산출
- 검증: `docker compose exec backend pytest tests/test_g1_fallback_metadata_propagation.py -v`
- 예상: FAIL

**Step 2: DB 모델 + Alembic 마이그레이션**
- `core/models/trading.py`:
  - `TradeSignal`에 `fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")` 추가
  - `Order`에 동일 컬럼 추가
- Alembic 마이그레이션 파일 생성 (수동 작성):
  - 두 컬럼 server_default `false` 추가
  - 인덱스 `ix_trade_signals_fallback_created`(`fallback`, `created_at`) 추가 — M-F2 일별 집계 성능
- 검증: `docker compose exec backend alembic upgrade head` 성공

**Step 3: SignalGenerator + 주문 생성 경로에 전파**
- `signal_generator.py`:
  - `generate_signals()` 내부에서 `candidate.get("is_fallback", False)` → `TradeSignal(fallback=..., reason={...,"fallback": ...})`로 저장
  - `TradeSignalData` dataclass에도 `fallback: bool = False` 필드 추가하여 후속 단계에 전달
- `modules/trading/order_manager.py` (또는 engine 주문 진입점):
  - `Order` 생성 시 `fallback=signal.fallback` 명시
  - 기존 `signal_json` JSONB에도 `fallback` 키 보존 (이중 안전)

**Step 4: M-F2 API 엔드포인트 추가**
- `backend/api/routes/metrics.py`에 추가:
  ```python
  @router.get("/metrics/fallback-signal-rate")
  async def fallback_signal_rate(date: str | None = None, ...):
      """일별 폴백 신호율 (M-F2).

      반환: {
          "date": "YYYY-MM-DD",
          "fallback_signals": int,            # 그날 fallback=True 신호 수
          "fallback_triggered_codes": int,    # 그날 폴백 발동 종목 수 (Redis metrics:fallback:code:*:{date})
          "rate": float | None                # = fallback_signals / fallback_triggered_codes (0 분모 방지)
      }
  ```
- 검증: `curl -s "http://localhost:8000/api/v1/metrics/fallback-signal-rate?date=2026-04-29" | jq .`
- 예상: 정상 JSON

**Step 5: 커밋**
```
git add backend/core/models/trading.py backend/alembic/versions/*_phase86_sprint1_fallback_metadata.py backend/modules/trading/signal_generator.py backend/modules/trading/order_manager.py backend/modules/trading/strategy.py backend/api/routes/metrics.py backend/tests/test_g1_fallback_metadata_propagation.py
git commit -m "feat(phase8.6-sprint1): task3 — G1 is_fallback 메타데이터 신호→주문 전파 + DB 컬럼 + M-F2 API"
```

**완료 기준:**
- ⬜ Alembic 마이그레이션 적용 + 컬럼 2개 존재
- ⬜ pytest test_g1_* 4 시나리오 PASS
- ⬜ M-F2 API 정상 응답 (분모 0일 때 `rate=null`)

---

### Task 4: G2 — 자동 롤백 R1~R4 OR 트리거 모듈 + 16:10 잡

**skill:** —

**Files:**
- Create: `backend/modules/safety/__init__.py`
- Create: `backend/modules/safety/auto_rollback.py`
- Create: `backend/tests/safety/test_auto_rollback.py`
- Modify: `backend/core/config.py` (env 5종 추가)
- Modify: `backend/modules/collector/scheduler.py` (16:10 또는 16:15 잡 등록)
- Modify: `.env.example`

**Step 1: 테스트 작성 (R1~R4 4종 + OR 결합)**
- `tests/safety/test_auto_rollback.py`:
  - `test_r1_zero_signal_3days_consecutive`: 가짜 일별 신호수 [0,0,0] → R1 발동
  - `test_r1_with_2days_does_not_trigger`: [0,0,5] → R1 미발동
  - `test_r2_fallback_trigger_rate_50pct_3days`: 일별 (폴백 발동 종목수 / 1차 통과 풀) ≥ 0.5 가 3일 → R2 발동
  - `test_r3_tier_diversity_one_5days`: 5일 모두 활성 tier 종류 ≤ 1 → R3 발동
  - `test_r4_fallback_signal_share_70pct_1day`: 어느 1일에 (fallback 신호 / 전체 신호) ≥ 0.7 → R4 발동
  - `test_or_combination_any_one_trigger`: R1만 발동해도 `should_rollback=True`
  - `test_env_toggle_disables_individual_trigger`: `AUTO_ROLLBACK_R3_ENABLED=False` → R3 입력 충족해도 미발동
  - `test_rollback_action_disables_phase86_changes_only`: 발동 시 `PHASE86_*_ENABLED` 일괄 False 전환 (Phase 8.5 폴백은 별도 — 본 모듈에서 비활성화하지 않음)
- 검증: `docker compose exec backend pytest tests/safety/test_auto_rollback.py -v`
- 예상: FAIL

**Step 2: auto_rollback.py 구현**
- `modules/safety/auto_rollback.py`:
  - `class AutoRollbackEvaluator`:
    - 입력: redis_client, settings, telegram bot (선택)
    - 메서드:
      - `async def evaluate(now_kst: datetime) -> dict`: 직전 N거래일 데이터 조회 후 R1~R4 각각 평가, 최종 `should_rollback`(OR), 발동 트리거 ID 리스트 반환
      - `async def execute_rollback(triggers: list[str]) -> None`: Redis override key로 `phase86:rollback:active=true` 저장(TTL 24h) + Telegram 알림(`_send_failure_alert` 패턴 재사용)
    - R1~R4 입력 데이터 소스:
      - R1: `daily_signal_count` (DB `trade_signals` group by date)
      - R2: `metrics:fallback:triggered:{date}` Redis 카운터 / 1차 풀 크기 (별도 측정 필요 — 일단 v0은 폴백 발동 종목수 / 폴백 임계×N 비율로 근사하거나 `daily_screening_metrics` 테이블 도입 고려; **v0은 R2를 "폴백 발동 일수 ≥ 3일 연속"의 단순 카운트로 시작**하고 향후 더 정확한 분모 도입은 Sprint 2로 이관)
      - R3: 신호의 `reason["tier"]` 분포 그룹화 — Sprint 2에서 tier 다양화 작업과 함께 정합성 확보
      - R4: `count(fallback=true) / count(*)` per date (Task 3 컬럼 활용)

**Step 3: env 추가 + 16:10 잡 등록**
- `core/config.py`:
  ```python
  AUTO_ROLLBACK_ENABLED: bool = Field(default=True, ...)
  AUTO_ROLLBACK_R1_ENABLED: bool = Field(default=True, ...)
  AUTO_ROLLBACK_R2_ENABLED: bool = Field(default=True, ...)
  AUTO_ROLLBACK_R3_ENABLED: bool = Field(default=False, ...)  # Sprint 2 tier 분리 후 True
  AUTO_ROLLBACK_R4_ENABLED: bool = Field(default=True, ...)
  ```
- `modules/collector/scheduler.py`:
  - 16:10 (또는 기존 보고 잡과 충돌 시 16:15) `AutoRollbackEvaluator.evaluate` 호출 잡 신규 등록
  - 발동 시 즉시 `execute_rollback` 호출 + Telegram 알림
- 검증: `docker compose exec backend pytest tests/safety/test_auto_rollback.py tests/test_scheduler.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/safety/ backend/tests/safety/ backend/core/config.py backend/modules/collector/scheduler.py .env.example
git commit -m "feat(phase8.6-sprint1): task4 — G2 자동 롤백 R1~R4 OR 트리거 + 16:10 잡 + env 토글"
```

**완료 기준:**
- ⬜ R1~R4 8개 테스트 시나리오 PASS
- ⬜ env 토글로 개별 트리거 비활성화 동작
- ⬜ 발동 시 Phase 8.5 폴백은 영향 없음 (테스트 검증)

---

### Task 5: G3 — 1차→2차 통과율 회로차단기

**skill:** —

**Files:**
- Create: `backend/modules/safety/circuit_breaker.py`
- Create: `backend/tests/safety/test_circuit_breaker.py`
- Modify: `backend/core/config.py` (env 추가)
- Modify: `backend/modules/collector/scheduler.py` (Task 4 16:10 잡과 동일 시점에 CircuitBreaker도 평가)
- Modify: `.env.example`

**Step 1: 테스트 작성**
- `test_circuit_breaker.py`:
  - `test_pass_rate_below_10pct_3days_triggers`: 일별 2차 통과율(폴백 제외) [3%, 5%, 8%] → 발동
  - `test_pass_rate_above_threshold_does_not_trigger`: [12%, 8%, 11%] → 미발동
  - `test_threshold_env_override`: `CIRCUIT_BREAKER_THRESHOLD=0.05` → [3%, 4%, 6%]도 R3을 깸으로 미발동(6%>5%)
  - `test_trigger_disables_phase86_and_phase85_fallback`: 발동 시 `PHASE86_*_ENABLED=False` + `SECONDARY_POOL_FALLBACK_ENABLED=False`로 Redis override 설정 (Phase 8.5 폴백도 차단 — DoR §3 G3 명시)
- 검증: 예상 FAIL

**Step 2: circuit_breaker.py 구현**
- 일별 2차 통과율(폴백 제외) = `daily_screening_metrics.passed_count / daily_screening_metrics.candidate_count` 또는 `realtime_screener` 결과를 기록하는 기존 메트릭 레디스 카운터 활용
- (현시점에 정확한 분모 메트릭이 미존재할 경우, **본 Task에서 Redis counter 한 쌍** `metrics:secondary:passed:{date}` / `metrics:secondary:candidate:{date}`을 `realtime_screener.screen()` 종점에서 increment하는 코드를 함께 추가)
- 3거래일 연속 < 임계 시 Redis override 2종 설정 + Telegram 알림

**Step 3: env + 잡 연결**
- `CIRCUIT_BREAKER_ENABLED: bool = True`
- `CIRCUIT_BREAKER_PASS_RATE_THRESHOLD: float = 0.10`
- `CIRCUIT_BREAKER_CONSECUTIVE_DAYS: int = 3`
- 16:10 잡에서 `AutoRollbackEvaluator` 호출 직후 `CircuitBreaker.evaluate()` 호출

**Step 4: 커밋**
```
git add backend/modules/safety/circuit_breaker.py backend/modules/screening/realtime_screener.py backend/tests/safety/test_circuit_breaker.py backend/core/config.py backend/modules/collector/scheduler.py .env.example
git commit -m "feat(phase8.6-sprint1): task5 — G3 1차→2차 통과율 회로차단기 + counter 인프라"
```

**완료 기준:**
- ⬜ 4개 테스트 시나리오 PASS
- ⬜ 발동 시 Phase 8.5 폴백 동시 차단 검증
- ⬜ Redis counter pair 일별 증가 검증

---

### Task 6: M-F2 카드 + R1~R4 다중 트리거 시각화

**skill:** `frontend-design`

**Files:**
- Create: `frontend/components/diagnostics/fallback-signal-rate-card.tsx`
- Create: `frontend/components/diagnostics/auto-rollback-multi-trigger.tsx`
- Modify: `frontend/app/(dashboard)/observation/page.tsx` (또는 기존 진단 페이지)
- Modify: `frontend/lib/api.ts` (필요 시 새 fetcher 추가)

**Step 1: M-F2 카드**
- `/api/v1/metrics/fallback-signal-rate` 호출 (SWR + 60초 폴링)
- 표시: 오늘 폴백 신호율(%), 7일 이동평균, 폴백 발동 종목수 / 폴백 신호수
- 비율이 70% ≥ 시 빨간색 경고 (R4 임계 시각화)

**Step 2: R1~R4 트리거 카드**
- 4개 트리거 각각 임계 진행률 (`현재 일수 / 임계 일수`) progress bar
- 임박 시 (남은 1일) 노란색, 발동 시 빨간색 + 발동 시각

**Step 3: dashboard 페이지에 배치**
- 기존 observation 또는 diagnostics 페이지 상단에 두 카드 추가
- 검증: `cd frontend && npx tsc --noEmit` + 로컬 브라우저 확인

**Step 4: 커밋**
```
git add frontend/components/diagnostics/ frontend/app/ frontend/lib/api.ts
git commit -m "feat(phase8.6-sprint1): task6 — M-F2 카드 + R1~R4 다중 트리거 시각화"
```

**완료 기준:**
- ⬜ npx tsc --noEmit 에러 0
- ⬜ 두 카드 정상 렌더 + 폴링 동작

---

### Task 7: DoR 통합 검증 + Paper 1거래일 회귀 + deploy.md 환경변수 등록

**skill:** `superpowers:verification-before-completion`

**Files:**
- Modify: `deploy.md` (Railway 수동 환경변수 등록 항목 추가)
- Modify: `docs/phase/phase8.6/sprint1/sprint1.md` (DoD 섹션 결과 기록)
- Create: `docs/phase/phase8.6/sprint1/integration-validation.md` (통합 검증 결과)

**Step 1: 전체 pytest 실행**
- `docker compose exec backend pytest -v`
- 모든 신규 + 기존 테스트 PASS
- 실패 시 해당 Task로 회귀 (단순 회귀 인 경우 본 Task 안에서 fix + 재실행)

**Step 2: 프론트 타입체크**
- `cd frontend && npx tsc --noEmit` → 0 errors

**Step 3: Paper 1거래일 회귀 (가능한 경우)**
- 로컬 Docker로 Paper 모드 1사이클 (또는 mocked replay) 실행
- `signals.fallback=true` 1건 이상 DB 기록 확인
- M-F2 API 응답 정상

**Step 4: DoR 4종 체크 + deploy.md 환경변수 등록**
- DoR §3 4종 (G1·G2·G3 + Phase 7.0 잠금) 모두 ✅ 표시
- `deploy.md`의 수동 검증 항목에 다음 추가:
  ```
  ## Phase 8.6 Sprint 1 — Railway 환경변수 추가 확인
  - ⬜ SECONDARY_POOL_FALLBACK_THRESHOLD=5
  - ⬜ SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP=5
  - ⬜ AUTO_ROLLBACK_ENABLED=true
  - ⬜ AUTO_ROLLBACK_R1_ENABLED=true
  - ⬜ AUTO_ROLLBACK_R2_ENABLED=true
  - ⬜ AUTO_ROLLBACK_R3_ENABLED=false  # Sprint 2 tier 분리 후 true 전환
  - ⬜ AUTO_ROLLBACK_R4_ENABLED=true
  - ⬜ CIRCUIT_BREAKER_ENABLED=true
  - ⬜ CIRCUIT_BREAKER_PASS_RATE_THRESHOLD=0.10
  - ⬜ CIRCUIT_BREAKER_CONSECUTIVE_DAYS=3
  ```

**Step 5: 커밋**
```
git add deploy.md docs/phase/phase8.6/sprint1/
git commit -m "docs(phase8.6-sprint1): task7 — DoR 통합 검증 결과 + Railway 환경변수 등록"
```

**완료 기준:**
- ⬜ pytest 전체 통과
- ⬜ npx tsc --noEmit 0 errors
- ⬜ DoR 4종 모두 ✅ 명시
- ⬜ deploy.md Railway 환경변수 10종 등록

---

## 위험 / 검증 매트릭스

> 기준: `.claude/rules/dev-process.md` §5

| 검증 항목 | 본 Sprint 적용 | 비고 |
|-----------|----------------|------|
| `pytest -v` 백엔드 통합 | ✅ Task 7 (전체) | Phase별로도 부분 실행 |
| API curl/httpx 검증 | ✅ M-F2 API | Task 3 단위 + Task 7 통합 |
| 데모 모드 API | ✅ M-F2 데모 | Task 7 |
| Playwright UI | ✅ 다이어그노스틱 페이지 | Task 7 |
| `docker compose up --build` | ⬜ Task 7 | DB 컬럼 추가 — 빌드 검증 |
| `alembic upgrade head` | ✅ Task 3 (`fallback` 컬럼) | DB 변경 |
| KIS API 실거래 확인 | — | 본 Sprint는 KIS 호출 패스 변경 없음 |
| UI 디자인 시각 품질 | ⬜ Task 6 + Task 7 | 사용자 수동 |

### 알려진 위험

1. **R2 분모(1차 풀 크기) 메트릭 부재** — 본 Sprint v0에서는 "폴백 발동 일수 ≥3일 연속"으로 단순화. 정확한 분모(=일별 1차 풀 크기)는 Sprint 2 tier 분리 작업에서 함께 정비.
2. **R3(tier 다양성)는 현재 1종(prev_high) 고정 상태** — Sprint 1 시점에는 `AUTO_ROLLBACK_R3_ENABLED=False` 기본값으로 두고, Sprint 2 병렬 OR 완료 후 True 전환. 본 Sprint는 모듈/테스트만 준비.
3. **G3 회로차단기의 분모(2차 candidate 수)** — 기존 메트릭 부재 시 Task 5에서 Redis counter pair 직접 추가. 누락 시 G3 검증 불가 → Task 5 첫 단계에서 정합성 확인.
4. **Alembic 마이그레이션 회귀 위험** — Task 3에서 `fallback` 컬럼 추가 시 `server_default="false"` 명시로 기존 데이터 NULL 회피. Paper Docker에서 `alembic upgrade head` 성공 확인.
5. **dry_run 안전 가드 위반 위험** — 본 Sprint는 폴백 임계/플로어/메타데이터/롤백 신호 평가만 변경. 실 거래 경로(주문 발행·체결) 로직 변경 없음 → 리스크 P0 가드레일 유지.

---

## 신규 환경변수 (Railway 수동 설정 필요)

`.env.example`에 추가하고 sprint-close 시 deploy.md에 `Railway 환경변수 추가 확인:` 형식으로 등록한다.

| 변수 | 기본값 | 용도 | Task |
|------|--------|------|------|
| `SECONDARY_POOL_FALLBACK_THRESHOLD` | `5` | 폴백 발동 임계 (3 → 5 상향) | Task 2 |
| `SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP` | `5` | 폴백 보강 종목수 상한 | Task 2 |
| `AUTO_ROLLBACK_ENABLED` | `true` | G2 자동 롤백 마스터 토글 | Task 4 |
| `AUTO_ROLLBACK_R1_ENABLED` | `true` | R1: 0건 3일 연속 | Task 4 |
| `AUTO_ROLLBACK_R2_ENABLED` | `true` | R2: 폴백 발동 일수 3일 연속 (v0) | Task 4 |
| `AUTO_ROLLBACK_R3_ENABLED` | `false` | R3: tier 1종 5일 연속 (Sprint 2 후 true) | Task 4 |
| `AUTO_ROLLBACK_R4_ENABLED` | `true` | R4: 폴백 비중 ≥70% 1일 | Task 4 |
| `CIRCUIT_BREAKER_ENABLED` | `true` | G3 회로차단기 마스터 | Task 5 |
| `CIRCUIT_BREAKER_PASS_RATE_THRESHOLD` | `0.10` | 2차 통과율 임계 | Task 5 |
| `CIRCUIT_BREAKER_CONSECUTIVE_DAYS` | `3` | 연속 일수 | Task 5 |

---

## 최종 검증 계획 (Task 7)

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 모든 신규 + 기존 테스트 PASS |
| Phase 7.0 회귀 방지 | `docker compose exec backend pytest tests/core/test_phase70_locked_constants.py -v` | 4 PASS |
| G1 메타데이터 전파 | `docker compose exec backend pytest tests/test_g1_fallback_metadata_propagation.py -v` | 4 PASS |
| G2 R1~R4 | `docker compose exec backend pytest tests/safety/test_auto_rollback.py -v` | 8 PASS |
| G3 회로차단기 | `docker compose exec backend pytest tests/safety/test_circuit_breaker.py -v` | 4 PASS |
| Alembic 마이그레이션 | `docker compose exec backend alembic upgrade head` | 성공 |
| M-F2 API | `curl -s http://localhost:8000/api/v1/metrics/fallback-signal-rate \| jq .` | `{date, fallback_signals, fallback_triggered_codes, rate}` |
| 프론트 타입체크 | `cd frontend && npx tsc --noEmit` | 0 errors |
| Paper 1거래일 회귀 | 로컬 Docker Paper 1사이클 | `signals.fallback=true` 1건 이상 |

---

## DoR 체크리스트 (Sprint 종료 시)

- ⬜ G1 (M-F2 산출 가능 + 메타데이터 전파) — Task 3
- ⬜ G2 (R1~R4 다중 트리거) — Task 4
- ⬜ G3 (회로차단기) — Task 5
- ⬜ Phase 7.0 LIVE 파라미터 코드 잠금 — Task 1

위 4개 모두 ✅ 후에만 Sprint 2 착수 가능 (Phase 8.6 §3 DoR).

---

## 참조

- Phase 문서: `docs/phase/phase8.6/phase8.6.md` (특히 §3 DoR, §5 확정 파라미터 #21~#27, §6 Sprint 1 상세)
- 분기 D 4명 재리뷰: `docs/phase/phase8.5/phase8.5-branch-d-{po,risk,quant,daytrader}-review.md`
- ROADMAP: `ROADMAP.md` Phase 8.6 절 (1271줄~)
- Phase 8.5 Sprint 2.5 인프라 자산: OverrideBanner 패턴, env 자동 동기화 스크립트, Redis counter + 일별 집계 패턴
- 수정 대상 코드:
  - `backend/modules/screening/realtime_screener.py` (`_apply_fallback`)
  - `backend/modules/trading/strategies/momentum_breakout.py` (`_resolve_min_volume_floor`)
  - `backend/modules/trading/signal_generator.py` / `order_manager.py` / `engine.py`
  - `backend/core/models/trading.py` (TradeSignal · Order)
  - `backend/api/routes/metrics.py` (M-F2 신규 엔드포인트)
  - `backend/modules/collector/scheduler.py` (16:10 잡)
