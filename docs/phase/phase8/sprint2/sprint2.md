# Sprint 2: 다층 진입 조건 + 리스크 안전장치 + 이관 버그 수정 (Phase 8)

**Goal:** `momentum_breakout` 전략에 3단계 진입 분기(gap_open / prev_close / prev_high)와 `breakout_tier` 메타데이터를 도입하고, 반 포지션·일일 10건 한도·13:00 시간 가드 등 리스크 안전장치를 추가한다. 동시에 Sprint 1(OHLC) / Hotfix PR #153(리스크 리셋) / 2026-04-21 장 마감 직전 발견된 WS·텔레그램 이중 발송 버그 3종을 함께 수정한다.

**Architecture:**
- **전략 레이어**: `momentum_breakout.py`에 `breakout_tier: "gap_open" | "prev_close" | "prev_high"` 변수를 도입하고, 13:00 이후 prev_close 분기를 비활성화. prev_close tier는 `confidence` 상한 0.75·`momentum_score = min(pct/7.0,1.0)*0.7`·`volume_threshold=2.5` 고정 적용. `reason` dict에 `breakout_tier`를 포함시켜 engine 하류에서 활용.
- **사이징/리스크 레이어**: `PositionSizer`는 신호의 `breakout_tier == "prev_close"`이면 `size_ratio=0.5`를 받아 반 포지션. `RiskManager`는 `daily_trade_count` 카운터(Redis)를 추가하여 10건/일 초과 시 차단. engine.process_screening_results는 주문 제출 전 `check_daily_trade_limit()`을 호출하고 체결 콜백에서 `incr_daily_trade_count()`로 증가.
- **관측성/운영**: Sprint 1 회귀 픽스처 강화, engine 차단 사유 구조화 로그, Hotfix #153 프론트 리셋 버튼 연동.
- **2026-04-21 신규 버그 3종**: scheduler `_secondary_no_data_count` 가드를 15:10~15:30 동시호가 구간에 스킵, 재연결 시 구독 복원 후 발송되는 알림을 1통으로 통합, `_market_close`에서 일일 리포트 중복 발송 차단.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Redis 7 · APScheduler · Next.js 16 · React 19 · shadcn/ui · pytest / pytest-asyncio

**Sprint 기간:** 2026-04-22 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 8 Sprint 1 (854 passed, PR #149 / v2.3.0 배포) + Hotfix PR #153 (risk-counter-reset)
**브랜치명:** `phase8-sprint2`

---

## 제외 범위

- **E2E Paper 검증 1사이클 / LIVE 전환 게이트** — Phase 8 Sprint 3
- **시스템 관리 UI (스케줄러/수동 트리거/포지션 카드/카운트다운)** — Phase 8 Sprint 4
- **성과 분석 보강 (MDD/Sharpe/보유시간/시간대 분포)** — Phase 8 Sprint 5
- **5분봉 가속도 / Z-score / VWAP 통합 지표** — Phase 9 Sprint 0
- **당일 고가 갱신 진입 (4단계 tier)** — Phase 10.1 이관
- **2차 스크리닝 N=1 상대 백분위 하이브리드 스코어링** — Phase 10.1 이관
- **리스크 대시보드 확장 (연속 손절/쿨다운/비상정지 시각화)** — MEMORY project_next_tasks Task4 "선택" 항목, 본 Sprint는 데이터만 노출하고 시각화는 Sprint 4와 묶어 처리

---

## 실행 플랜

의존성 그래프:
- **Phase 1 (순차, 원래 Sprint 2 범위)**: 전략 tier 도입(Task1) → 사이저 size_ratio 연동(Task2) → 리스크 매니저 일일 한도(Task3) → engine 배선 + 13:00 가드(Task4)
- **Phase 2 (병렬 가능, Sprint 1/Hotfix 이관)**: OHLC 회귀 픽스처(Task5) ⟂ 차단 사유 관측성(Task6) ⟂ 프론트 리셋 버튼(Task7) — 각 Task가 다른 파일 소유
- **Phase 3 (순차, 2026-04-21 버그)**: WS false-positive 가드(Task8) → 재연결 이중 구독 알림(Task9) → 일일 리포트 중복(Task10) — 모두 `scheduler.py` + `notifier/manager.py` 파일을 건드리므로 순차
- **Phase 4 (통합 검증)**: pytest 전체 회귀 + 수동 검증 가이드(Task11)

### Phase 1 (순차 — 다층 진입 + 리스크)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | `momentum_breakout` 3단계 분기 + `breakout_tier` + confidence 상한 + 13:00 가드 | 백엔드 | `feature-dev:feature-dev` |
| Task 2 | `PositionSizer` `breakout_tier == "prev_close"` 시 반 포지션 (size_ratio=0.5) | 백엔드 | — |
| Task 3 | `RiskManager` 일일 거래 한도 10건/일 + Sprint 3 전 3건/일 환경변수 오버라이드 | 백엔드 | — |
| Task 4 | `engine.process_screening_results` 연결 + 체결 콜백 카운터 증가 + `seed_settings.py` 신규 키 | 백엔드 | `systematic-debugging` |

### Phase 2 (병렬 가능 — 이관 작업)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | OHLC 파싱 회귀 테스트 픽스처 강화 (H0STCNT0 idx 7/8/9, 갭 3%+ 단위 테스트화) | 백엔드 | — |
| Task 6 | engine 차단 사유 6지점 구조화 로그 + 선택적 텔레그램 알림 | 백엔드 | — |
| Task 7 | 프론트 리스크 상태 페이지에 `POST /api/v1/trading/risk/reset` 리셋 버튼 연동 | 프론트엔드 | `frontend-design` |

### Phase 3 (순차 — 2026-04-21 신규 버그)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 8 | `_secondary_no_data_count` 가드에 동시호가(15:10~15:30) 구간 스킵 | 백엔드 | `systematic-debugging` |
| Task 9 | 재연결 시 텔레그램 알림 1통 통합 (이중 발송 제거) | 백엔드 | `systematic-debugging` |
| Task 10 | `_market_close` 일일 리포트 중복 발송 차단 (Redis 1회 잠금) | 백엔드 | `systematic-debugging` |

### Phase 4 (통합 검증)

| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 11 | pytest 전체 회귀 + 수동 검증 가이드 작성 | 전체 | — |

> **팀 실행**: Phase 2는 파일 소유권이 분리되어 있어 백엔드(Task5, Task6) / 프론트엔드(Task7) 병렬 실행이 자연스럽다. Phase 1·3은 동일 모듈 체인이므로 순차 실행.

---

### Task 1: `momentum_breakout` 3단계 진입 분기 + `breakout_tier`

**skill:** `feature-dev:feature-dev` — 전략 로직은 `snapshot`, `SignalGenerator`, `PositionSizer`, `engine` 4개 파일과 연쇄 영향이 있어 사전 탐색 필요.

**Files:**
- Modify: `backend/modules/trading/strategies/momentum_breakout.py` (갭 분기 86~91줄 + confidence/momentum_score 181~195줄 + reason dict 228~242줄)
- Modify: `backend/modules/trading/strategy.py` (`TradeSignalData.reason`에 tier 규약만 주석으로 명시 — 코드 변경 없음)
- Modify: `backend/tests/test_momentum_breakout.py`

**Step 1: 테스트 작성 (TDD)**
- `_make_snapshot()` 헬퍼에 `current_time: datetime | None = None` 파라미터 추가 (13:00 가드 테스트용). 기본값은 10:00 KST
- 신규 테스트:
  - `test_gap_open_tier_sets_breakout_tier_and_uses_open_price`: gap_rate=3.5%, current_price=open+1% → reason["breakout_tier"] == "gap_open"
  - `test_prev_close_tier_requires_intraday_prev_close_breakout`: gap_rate=0.5%, current_price > prev_close (but < prev_high) → reason["breakout_tier"] == "prev_close"
  - `test_prev_high_tier_when_breaks_prev_high`: gap_rate=0.5%, current_price > prev_high → reason["breakout_tier"] == "prev_high"
  - `test_prev_close_tier_confidence_cap_0_75`: prev_close tier에서 모든 점수가 만점이어도 confidence <= 0.75
  - `test_prev_close_tier_momentum_score_scales_pct_7_times_0_7`: pct=7.0%, momentum_score == min(7.0/7.0, 1.0) * 0.7 == 0.7
  - `test_prev_close_tier_volume_threshold_fixed_2_5`: prev_close tier에서 `breakout_pct` 값과 무관하게 volume_threshold == 2.5
  - `test_prev_close_tier_disabled_after_1300_kst`: current_time=13:30 KST + prev_close tier 조건만 충족 → RejectedSignal(stage="prev_close_time_guard")
  - `test_gap_open_tier_uses_existing_volume_threshold_logic`: gap_open/prev_high tier는 기존 1.5~2.0 로직 유지 회귀 확인
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py -v`
- 예상: 신규 테스트 FAIL

**Step 2: 전략 로직 확장**
- 갭 분기 (86~91줄) 교체:
  ```
  if gap_rate >= 0.03:
      breakout_ref = snapshot.open_price
      breakout_tier = "gap_open"
  elif snapshot.current_price > snapshot.prev_high:
      breakout_ref = snapshot.prev_high
      breakout_tier = "prev_high"
  else:
      breakout_ref = snapshot.prev_close
      breakout_tier = "prev_close"
  ```
- prev_close tier 13:00 가드: `_KST` 기반 `datetime.now(_KST).time() >= time(13, 0)` 이고 `breakout_tier == "prev_close"`이면 `self._reject(snapshot, "prev_close_time_guard", {...})` 반환. (테스트 주입용 `_now` 의존성 주입 패턴은 기존 `calc_market_progress()`의 `now_kst` 선택 인자 패턴을 참조. `generate_signal` 시그니처에는 영향 없이 내부 helper로 분리)
- volume_threshold 분기: `breakout_tier == "prev_close"`이면 `volume_threshold = 2.5` (강도 연동 무시), 나머지는 기존 로직 유지
- momentum_score 계산:
  - `prev_close`: `min((current_price - breakout_ref)/breakout_ref * 100 / 7.0, 1.0) * 0.7`
  - `gap_open`: `min(pct / 5.0, 1.0) * 0.85` (확정 파라미터 #11 상한 0.85 적용)
  - `prev_high`: 기존 `min(pct / 5.0, 1.0)` 유지
- confidence 계산 후 `breakout_tier == "prev_close"`이면 `confidence = min(confidence, 0.75)` 상한 적용
- `reason` dict에 `"breakout_tier": breakout_tier` 추가 (기존 `breakout_ref`와 병존)
- 검증: `docker compose exec backend pytest tests/test_momentum_breakout.py -v`
- 예상: PASS

**Step 3: simplify 검토**
- 13:00 가드 helper 분리 (`_is_prev_close_tier_blocked(now_kst)`)로 테스트성 확보, 전략 클래스 외부 함수로 추출 금지 (응집도 유지)
- `breakout_tier` 결정 블록이 else-if 3단계로 단순화되어 있음을 재확인 — 절차형 코드 유지

**Step 4: 커밋**
```
git add backend/modules/trading/strategies/momentum_breakout.py backend/tests/test_momentum_breakout.py
git commit -m "feat(phase8-sprint2): task1 — momentum_breakout 3단계 tier(gap_open/prev_close/prev_high) + 13:00 가드 + confidence 상한"
```

**완료 기준:**
- ⬜ 3단계 tier 판정 테스트 PASS (8개 신규 테스트)
- ⬜ `reason["breakout_tier"]`가 항상 값 존재
- ⬜ 기존 회귀 테스트(21개) 모두 PASS

---

### Task 2: `PositionSizer` 반 포지션 (prev_close tier)

**skill:** — (기존 `size_ratio` 파라미터 재활용, 단순 흐름 확장)

**Files:**
- Modify: `backend/modules/trading/engine.py` (signal.reason["breakout_tier"] 읽어 size_ratio 결정)
- Modify: `backend/tests/test_position_sizer.py` 또는 `test_engine.py`

**Step 1: 현황 확인**
- `PositionSizer.calculate()`는 이미 `size_ratio: float = 1.0` 파라미터 수용 (Phase 5 Sprint 1). `PositionSizer` 자체는 수정 불필요
- `engine.process_screening_results` 160줄 `size_ratio = candidate.get("position_size_ratio", 1.0)` 로직에 tier 기반 계산 병합 필요

**Step 2: 테스트 작성**
- 기존 `test_engine.py` 또는 새 `test_engine_tier_sizing.py`에 다음 케이스 추가:
  - `test_prev_close_tier_applies_half_size_ratio`: signal.reason["breakout_tier"]=="prev_close" → PositionSizer.calculate 호출 인자 size_ratio == 0.5 (또는 candidate.position_size_ratio가 0.5였으면 min(0.5, 0.5) == 0.5)
  - `test_prev_high_tier_keeps_size_ratio_1_0`: breakout_tier=="prev_high" → size_ratio == 1.0 (candidate 플래그 없을 시)
  - `test_candidate_position_size_ratio_overrides_when_smaller`: candidate가 0.3 지정 + tier=prev_close → 최종 size_ratio == 0.3 (더 보수적)
- 검증: `docker compose exec backend pytest tests/test_engine.py -v -k size_ratio` (또는 새 파일)
- 예상: FAIL

**Step 3: engine.py 분기 추가**
- `size_ratio` 결정을 다음으로 변경:
  ```
  candidate_ratio = candidate.get("position_size_ratio", 1.0)
  tier = signal.reason.get("breakout_tier", "prev_high")
  tier_ratio = 0.5 if tier == "prev_close" else 1.0
  size_ratio = min(candidate_ratio, tier_ratio)
  ```
- logger.info로 결정된 size_ratio 및 tier 기록 (Task 6 관측성과 연계)
- 검증: `docker compose exec backend pytest tests/test_engine.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/trading/engine.py backend/tests/test_engine.py
git commit -m "feat(phase8-sprint2): task2 — prev_close tier에 size_ratio=0.5 반 포지션 적용"
```

**완료 기준:**
- ⬜ prev_close tier 시 size_ratio=0.5 적용 테스트 PASS
- ⬜ candidate 플래그가 더 작으면 그 값 유지 (min)
- ⬜ prev_high/gap_open tier는 기존 동작 유지

---

### Task 3: `RiskManager` 일일 거래 한도 10건/일

**skill:** — (기존 Redis 카운터 패턴 재활용)

**Files:**
- Modify: `backend/modules/trading/risk_manager.py` (`DEFAULTS`, `can_trade`, `check_daily_trade_limit`, `incr_daily_trade_count` 추가)
- Modify: `backend/scripts/seed_settings.py` (신규 키 `daily_max_trade_count`)
- Modify: `backend/tests/test_risk_manager.py`

**Step 1: 설계 확인**
- 신규 Redis 키: `risk:daily_trade_count` — `reset_daily_counters()`에서 삭제
- 신규 설정 키: `daily_max_trade_count` (category="risk", default="10", value_type="int")
- 환경변수 오버라이드: Sprint 3 착수 전까지 `DAILY_MAX_TRADE_COUNT_OVERRIDE` 환경변수가 있으면 우선 (LIVE 초기 3건/일 대응). 설정 → 환경변수 → 기본값 10 순서 (환경변수가 제일 우선)
- 주의: 한도 카운터 증가 시점은 `engine.on_order_filled` (체결 완료 후) — 주문 제출 시점이 아님. 체결 실패 주문은 카운터 미증가 (Task 4에서 배선)

**Step 2: 테스트 작성**
- 신규 테스트 (`test_risk_manager.py`):
  - `test_check_daily_trade_limit_returns_true_when_below_limit`: Redis 카운터=3, 한도=10 → True (매매 가능)
  - `test_check_daily_trade_limit_returns_false_at_limit`: 카운터=10 → False
  - `test_incr_daily_trade_count_increments_and_expires`: incr 후 Redis 값=1, TTL > 0 (당일 종료까지)
  - `test_can_trade_blocks_when_daily_trade_limit_reached`: can_trade 결과 allowed=False + reason에 "일일 거래 횟수" 포함
  - `test_reset_daily_counters_clears_trade_count`: reset_daily_counters 호출 후 카운터 키 삭제 확인
  - `test_env_override_applies_lower_limit`: monkeypatch `DAILY_MAX_TRADE_COUNT_OVERRIDE=3` → 카운터=3, 한도=3이므로 False
- 검증: `docker compose exec backend pytest tests/test_risk_manager.py -v`
- 예상: FAIL

**Step 3: RiskManager 확장**
- `DEFAULTS`에 `"daily_max_trade_count": "10"` 추가
- 상단 상수 `REDIS_DAILY_TRADE_COUNT = "risk:daily_trade_count"`
- 메서드 추가:
  - `async def incr_daily_trade_count(self) -> int`: Redis INCR + 첫 증가 시 TTL 86400초 설정
  - `async def check_daily_trade_limit(self) -> bool`: 카운터 < 한도 시 True
  - `def _get_daily_trade_limit(self) -> int`: env override 먼저 확인, 없으면 `_get_int("daily_max_trade_count")`
- `can_trade()`에 체크 삽입 — `check_time_restriction` 바로 다음 순서
- `reset_daily_counters()`에 `await self._redis.delete(REDIS_DAILY_TRADE_COUNT)` 추가
- 검증: `docker compose exec backend pytest tests/test_risk_manager.py -v`
- 예상: PASS

**Step 4: seed_settings 키 추가**
- SEED_DATA에 `("daily_max_trade_count", "10", "int", "risk", "일일 최대 거래 횟수")` 추가
- Alembic 마이그레이션 불필요 (값 추가만)

**Step 5: 커밋**
```
git add backend/modules/trading/risk_manager.py backend/scripts/seed_settings.py backend/tests/test_risk_manager.py
git commit -m "feat(phase8-sprint2): task3 — 일일 거래 한도 10건/일 + env override (Sprint 3 전 3건)"
```

**완료 기준:**
- ⬜ Redis `risk:daily_trade_count` 카운터 동작
- ⬜ 10건 초과 시 can_trade → blocked
- ⬜ `DAILY_MAX_TRADE_COUNT_OVERRIDE=3` 환경변수로 제한
- ⬜ reset_daily_counters에서 카운터 삭제

---

### Task 4: `engine` 배선 (체결 콜백 카운터 증가 + pytest 통합)

**skill:** `systematic-debugging` — 체결 경로가 `order_manager._filled_callback` → `engine.on_order_filled`로 연결되어 있어 어느 지점에서 카운터를 증가시킬지 영향도 분석 필요.

**Files:**
- Modify: `backend/modules/trading/engine.py` (`on_order_filled` 본체에 `await self._risk_manager.incr_daily_trade_count()` 추가)
- Modify: `backend/tests/test_engine.py` 또는 `test_engine_integration.py`

**Step 1: 영향 범위 분석 (systematic-debugging)**
- `on_order_filled`은 매수 체결 시에만 호출됨 확인 (매도/청산은 `_execute_exit` 경로)
- 중복 증가 방지: 동일 `order_id`로 두 번 호출되는 케이스 유무 — `order_manager._execute_order`에서 filled callback은 1회만 보장되는지 확인 (Phase 7.0 Sprint 1 구조)
- "거래 횟수"의 정의: 매수 진입만 카운트할지, 매수+매도 각각 셀지 — **진입(매수 체결) 1회 = 거래 1건**으로 확정 (확정 파라미터 #12 "10건/일"은 진입 횟수)

**Step 2: 테스트 작성**
- `test_on_order_filled_increments_daily_trade_count`: signal_data=TradeSignalData 주입하여 on_order_filled 호출 → risk_manager.incr_daily_trade_count 1회 호출 확인
- `test_process_screening_results_blocked_when_daily_limit_reached`: can_trade에서 daily_trade_limit 차단 시 order_manager.submit_order 미호출 확인
- 검증: `docker compose exec backend pytest tests/test_engine.py -v`
- 예상: FAIL

**Step 3: engine 수정**
- `on_order_filled` 본체에 카운터 증가 추가:
  ```
  if isinstance(signal_data, TradeSignalData):
      await self._position_manager.open_position(signal_data, quantity, filled_price)
      try:
          await self._risk_manager.incr_daily_trade_count()
      except Exception:
          logger.exception("일일 거래 카운터 증가 실패 — 포지션 생성은 이미 완료됨")
  ```
- 검증: `docker compose exec backend pytest tests/test_engine.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/trading/engine.py backend/tests/test_engine.py
git commit -m "feat(phase8-sprint2): task4 — 체결 콜백에서 일일 거래 카운터 증가 (진입 1회 = 1건)"
```

**완료 기준:**
- ⬜ on_order_filled 시 카운터 1 증가
- ⬜ 한도 초과 시 주문 제출 차단
- ⬜ 카운터 증가 실패가 포지션 생성을 막지 않음 (에러 격리)

---

### Task 5: OHLC 파싱 회귀 테스트 픽스처 강화 (Sprint 1 A안 이관)

**skill:** — (테스트 코드 보강 전용)

**Files:**
- Modify: `backend/tests/test_kis_realtime.py` (H0STCNT0 idx 7/8/9 헬퍼 강화)
- Modify: `backend/tests/test_momentum_breakout.py` (갭 3%+ 단위 테스트 추가, Task1과 별개로 갭 open_price 회귀만 남김)

**Step 1: 목적 재확인**
- Phase 8 Sprint 1 완료 후 착수 조건 A안 중 ⏸️③④⑤ 항목이 "Sprint 2 Task1 회귀 테스트로 흡수"로 연기됨
- Sprint 1에서 이미 21개 테스트가 PASS 중이지만, **idx 7/8/9 헬퍼는 `_make_execution_body(open_price=69500, high=70100, low=69000)` 기본값으로만 검증**되어 있어 경계값 커버리지가 부족함

**Step 2: 픽스처 강화**
- `test_kis_realtime.py`에 경계값 테스트 추가:
  - `test_parse_execution_handles_ohlc_zero_values`: OHLC 3필드가 "0" 문자열일 때 int(0) 정상 반환
  - `test_parse_execution_handles_large_ohlc_values`: 100만원대 고가 종목 (예: LG생활건강) 시뮬레이션
  - `test_parse_execution_field_offset_sanity`: idx 7/8/9가 EXECUTION_FIELD_MAP의 "open_price"/"high"/"low" 키와 일치하는지 역매핑 검증
- `test_momentum_breakout.py`에 정식 단위 테스트 추가 (기존 test_gap_breakout_uses_open_price_as_ref는 유지):
  - `test_gap_breakout_uses_redis_realtime_ohlc`: snapshot.open_price가 Redis 실시간 값이라는 전제로 breakout_ref 매핑 확인 (integration 성격)
- 검증: `docker compose exec backend pytest tests/test_kis_realtime.py tests/test_momentum_breakout.py -v`
- 예상: 추가 테스트 모두 PASS (기능은 Sprint 1에서 이미 구현됨)

**Step 3: 커밋**
```
git add backend/tests/test_kis_realtime.py backend/tests/test_momentum_breakout.py
git commit -m "test(phase8-sprint2): task5 — OHLC 파싱 회귀 픽스처 강화 (Sprint 1 A안 이관)"
```

**완료 기준:**
- ⬜ idx 7/8/9 경계값 3개 이상 커버
- ⬜ 갭 3%+ 단위 테스트 명시화

---

### Task 6: engine 차단 사유 관측성 개선 (Hotfix #153 후속)

**skill:** — (구조화 로깅 + 선택적 알림, 기존 logger.info 패턴 확장)

**Files:**
- Modify: `backend/modules/trading/engine.py` (process_screening_results 내 6개 차단 지점에 구조화 로그 추가)
- Modify: `backend/tests/test_engine.py`

**Step 1: 차단 지점 6개 식별**
engine.py process_screening_results 내 차단 지점:
1. pipeline_healthy != "true" (113~116줄)
2. eod_liquidator.is_entry_blocked() (119~121줄)
3. risk_result.allowed=False (148~153줄)
4. mode=="manual" skip (137~140줄)
5. balance 조회 실패 (169~171줄)
6. quantity == 0 (176~178줄)

**Step 2: 테스트 작성**
- `test_engine_structured_block_log_fields`: caplog로 각 차단 지점의 로그 메시지에 공통 필드 `{stock_code, block_reason, mode, breakout_tier?}` 포함 확인
- `test_engine_sends_telegram_alert_only_for_risk_and_pipeline_blocks`: risk 차단·pipeline_unhealthy만 notifier 호출, 나머지는 로그만
- 검증: `docker compose exec backend pytest tests/test_engine.py -v -k block`
- 예상: FAIL

**Step 3: 구조화 로그 적용**
- 헬퍼 메서드 `_log_block(stock_code, reason, extra={})` 추가 — logger.info with extra dict
- 선택적 텔레그램 알림: `reason in {"pipeline_unhealthy", "risk_blocked"}`이고 notifier 있으면 `send_system_alert("risk_warning", details)` 호출 (기존 `send_system_alert` 재사용)
- 6개 지점에 `self._log_block(...)` 주입 (기존 logger.info/warning 제거 또는 대체)
- 스팸 방지: 동일 (stock_code, reason) 조합에 대해 Redis TTL 5분 dedup (키 `engine:block:dedup:{code}:{reason}`) — notifier 호출에만 적용, 로그는 그대로 남김
- 검증: `docker compose exec backend pytest tests/test_engine.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/trading/engine.py backend/tests/test_engine.py
git commit -m "feat(phase8-sprint2): task6 — engine 차단 사유 6지점 구조화 로그 + 선택적 텔레그램 알림"
```

**완료 기준:**
- ⬜ 6개 차단 지점 모두 `_log_block` 경유
- ⬜ risk_blocked / pipeline_unhealthy만 텔레그램 알림
- ⬜ 5분 dedup으로 스팸 방지

---

### Task 7: 프론트 리스크 리셋 버튼 연동 (Hotfix #153 UI)

**skill:** `frontend-design` — shadcn/ui 다이얼로그·버튼 조합, 디자인 탐색 필요.

**Files:**
- Modify: `frontend/app/(dashboard)/page.tsx` — 대시보드에 있는 리스크 상태 카드에 "일일 카운터 리셋" 버튼 추가
  - (실제 리스크 상태 UI 위치는 `rg "risk-status"`로 재확인)
- Modify: `frontend/lib/api.ts` — `resetRiskCounters()` 클라이언트 함수 추가
- Create: `frontend/components/risk/reset-button.tsx` — shadcn `AlertDialog` 기반 2단계 확인 버튼 컴포넌트 (LIVE/PAPER 배지 + 경고 문구 + 확인 체크박스)
- Modify: `frontend/components/risk/risk-status-card.tsx` (또는 기존 대시보드 섹션 파일)

**Step 1: 백엔드 엔드포인트 확인**
- Hotfix PR #153에서 `POST /api/v1/trading/risk/reset`이 이미 추가됨 (`backend/api/routes/trading.py`에 8줄 신규)
- Task7 시작 전 실제 엔드포인트 경로와 응답 스키마 확인:
  ```
  docker compose exec backend python -c "from fastapi.routing import APIRoute; from api.routes.trading import router; print([r.path for r in router.routes if 'reset' in r.path])"
  ```

**Step 2: API 클라이언트 함수 추가**
- `frontend/lib/api.ts`에 추가:
  ```
  export async function resetRiskCounters(): Promise<{ ok: boolean; message?: string }> {
    return apiPost('/trading/risk/reset', {});
  }
  ```

**Step 3: 컴포넌트 구현 (frontend-design 스킬 적용)**
- shadcn `AlertDialog` 기반:
  - 트리거: `<Button variant="destructive" size="sm">일일 리스크 카운터 리셋</Button>`
  - 제목: "리스크 카운터를 리셋하시겠습니까?"
  - 설명: "연속 손절 / 비상 정지 / 일일 거래 카운터가 모두 0으로 초기화됩니다. 현재 모드: {trading_env === 'live' ? 'LIVE 실전' : 'PAPER 모의'}"
  - LIVE 모드일 때 `<Badge variant="destructive">⚠️ LIVE 실전</Badge>` 표시
  - 확인 체크박스 "위험을 이해했습니다" 체크 시에만 Confirm 버튼 활성화
  - Confirm 클릭 시 `resetRiskCounters()` 호출 + 토스트(sonner) 성공/실패 알림
  - 로딩 중 버튼 disabled
- 대시보드 리스크 상태 카드에 버튼 삽입

**Step 4: 타입 체크 + 수동 검증**
- `cd frontend && npx tsc --noEmit` → 에러 없음
- Playwright 스모크 (선택): 로그인 → 대시보드 → "일일 리스크 카운터 리셋" 버튼 노출 확인
- 검증: Docker backend 기동 후 버튼 클릭 → Redis `risk:consecutive_loss_count` 삭제 확인

**Step 5: 커밋**
```
git add frontend/app/\(dashboard\)/page.tsx frontend/lib/api.ts frontend/components/risk/reset-button.tsx frontend/components/risk/risk-status-card.tsx
git commit -m "feat(phase8-sprint2): task7 — 프론트 리스크 카운터 리셋 버튼 + 2단계 확인 다이얼로그"
```

**완료 기준:**
- ⬜ 대시보드에서 리셋 버튼 노출
- ⬜ LIVE/PAPER 배지 표시
- ⬜ 2단계 확인 (체크박스 + Confirm)
- ⬜ 성공/실패 토스트
- ⬜ tsc --noEmit 통과

---

### Task 8: WS false-positive 재연결 가드 (동시호가 구간 스킵)

**skill:** `systematic-debugging`

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (2차 스크리닝 내 `_secondary_no_data_count` 가드 블록, ~965~980줄)
- Modify: `backend/tests/test_scheduler.py`

**Step 1: 원인 분석 (systematic-debugging)**
- 사용자 관찰 (2026-04-21 15:22/15:24/15:27/15:29 KST 재현 확정): `_secondary_no_data_count >= 5` 조건이 동시호가 시간대(15:10~15:30)에 오발동. 동시호가에는 체결 틱이 발생하지 않아 샘플 10종목 중 데이터 0건이 정상임에도 WS 재연결을 트리거
- 2차 스크리닝은 30초 주기 → 15:10~15:30(20분) 동안 약 40회 실행, 5회 연속 0건이면 재연결 발생 → 재연결 시도가 이중 구독 (Task 9)과 일일 리포트 중복 (Task 10)을 연쇄 유발

**Step 2: 테스트 작성**
- `test_secondary_screen_skips_no_data_guard_during_closing_auction`: now=15:15 KST에서 data_count=0이어도 `_secondary_no_data_count`가 증가하지 않고 0 유지
- `test_secondary_screen_no_data_guard_active_during_regular_hours`: now=10:00 KST, data_count=0, 5회 누적 → `_reconnect_ws` 호출 확인 (기존 회귀)
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v -k no_data`
- 예상: FAIL

**Step 3: 가드 수정**
- `_secondary_screen` 함수 내 `_secondary_no_data_count` 블록 앞에 동시호가 스킵:
  ```
  now_kst = datetime.now(_KST)
  if time(15, 10) <= now_kst.time() < time(15, 30):
      # 동시호가 구간 — 체결 틱 미발생이 정상
      self._secondary_no_data_count = 0
      logger.debug("동시호가 구간 — no_data 가드 스킵")
      return
  ```
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler.py
git commit -m "fix(phase8-sprint2): task8 — 동시호가(15:10~15:30) 구간에서 WS no-data 가드 스킵"
```

**완료 기준:**
- ⬜ 15:10~15:30 재연결 미발동
- ⬜ 일반 장중(~15:10) no_data 가드 유지

---

### Task 9: 재연결 시 텔레그램 알림 이중 발송 제거

**skill:** `systematic-debugging`

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (`_reconnect_ws` 767~769줄)
- Modify: `backend/tests/test_scheduler.py`

**Step 1: 원인 분석 (systematic-debugging)**
- 사용자 관찰: 재연결 1회마다 `[자동 복구] WS 재연결 + 재구독 완료 (20종목)` + `(30종목)` 2통 발송. 백엔드 로그는 `_reconnect_ws` 1회만 기록
- 가설:
  1. `_market_open`에서도 `_reconnect_ws`와 유사한 알림을 보낼 수 있음 → 코드 확인 필요
  2. `ws_manager.subscribe`가 내부적으로 알림을 보내는지 확인
  3. `_on_ws_reconnect_success` 콜백과 `_reconnect_ws` 본체의 `send_notification`이 모두 동작할 수 있음 (line 767~769) → `_on_ws_reconnect_success`가 알림을 보내지 않는지 재확인 (현재 코드상 체결강도 웜업만 수행, 알림 없음)
  4. `_secondary_screen` 재진입 시 새 구독 수와 이전 구독 수가 모두 알림에 실림 — Task8 수정으로 근본 해소되는 지 상관관계 분석 필요
- 실제 원인 특정은 Task 8 수정 후 현상 재현 로그 수집 1회 필요. 본 Task는 **보수적 수정** 수행:
  - `_reconnect_ws`의 알림 문자열을 `f"<b>[자동 복구]</b> WS 재연결 완료 (구독 {count}종목, reason={reason})"`로 통합
  - 알림 발송 직전 Redis dedup 키 `ws:reconnect:notified:{YYYYMMDD}:{HHMM}` TTL 60초 설정 — 동일 분 내 중복 알림 차단
  - `_market_open_recovery`의 "복구 성공" 알림도 동일 dedup 키로 통합 검사

**Step 2: 테스트 작성**
- `test_reconnect_ws_sends_single_notification_within_minute`: 60초 내 2회 연속 재연결 시도 → telegram.send_notification 1회만 호출 확인
- `test_reconnect_ws_allows_notification_after_dedup_ttl_expires`: Redis ttl 만료 후 재연결 → 알림 재발송 확인
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v -k reconnect`
- 예상: FAIL

**Step 3: dedup 로직 추가**
- 헬퍼 `async def _send_reconnect_alert(self, reason: str, sub_count: int)`:
  - Redis key `ws:reconnect:notified` (TTL 60초)로 gate
  - gate 통과 시만 `self._telegram_bot.send_notification(...)` 호출
- `_reconnect_ws`, `_market_open_recovery` 복구 성공 알림을 모두 이 헬퍼 경유로 전환
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler.py
git commit -m "fix(phase8-sprint2): task9 — WS 재연결 알림 60초 dedup으로 이중 발송 제거"
```

**완료 기준:**
- ⬜ 동일 분 내 재연결 알림 1통 제한
- ⬜ dedup TTL 만료 후 정상 발송

---

### Task 10: 일일 리포트 중복 발송 차단

**skill:** `systematic-debugging`

**Files:**
- Modify: `backend/modules/collector/scheduler.py` (`_market_close` 866~872줄)
- Modify: `backend/modules/notifier/manager.py` (`send_daily_report` 상단에 dedup 가드 옵션)
- Modify: `backend/tests/test_scheduler.py` 또는 `test_notifier_manager.py`

**Step 1: 원인 분석 (systematic-debugging)**
- 사용자 관찰: `_market_close` 1회 실행에 일일 리포트 텔레그램 2회 전송. 백엔드 `일일 마감 리포트 발송 완료` 로그는 1회만
- 가설:
  1. APScheduler misfire로 `_market_close`가 2번 트리거되지만 첫 호출만 정상 로그 → 두 번째는 예외로 조기 종료하여 로그 안 남음. 그러나 send_daily_report는 이미 완료되어 있음 → 2회 모두 성공
  2. Telegram 봇의 `send_notification`이 내부 재시도로 2회 API call 호출
  3. 동일 `chat_id`에 웹훅과 폴링이 동시 동작하여 사용자 단말에서 2회 수신
- 실제 원인 특정은 로그/Telegram send API call 횟수 수집 1회 필요. 본 Task는 **보수적 수정** 수행:
  - `scheduler._market_close`에 Redis 1회 잠금 키 `scheduler:daily_report:sent:{YYYYMMDD}` (TTL=86400초) 설정 — 이미 존재하면 `send_daily_report` 스킵

**Step 2: 테스트 작성**
- `test_market_close_sends_daily_report_once_per_day`: `_market_close`를 연속 2회 호출 → notifier_manager.send_daily_report 1회만 호출
- `test_market_close_resends_daily_report_on_next_day`: 다른 날짜 키 → 호출 허용
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v -k daily_report`
- 예상: FAIL

**Step 3: dedup 잠금 추가**
- `_market_close` 내 일일 리포트 블록을:
  ```
  today_str = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).strftime("%Y%m%d")
  lock_key = f"scheduler:daily_report:sent:{today_str}"
  if await self._redis.get(lock_key):
      logger.info("일일 리포트 중복 발송 방지 — 오늘 이미 발송됨")
  else:
      try:
          await self._notifier_manager.send_daily_report(self._session_factory)
          await self._redis.set(lock_key, "1", ttl=86400)
          logger.info("일일 마감 리포트 발송 완료")
      except Exception:
          logger.exception("일일 마감 리포트 발송 실패")
  ```
- 검증: `docker compose exec backend pytest tests/test_scheduler.py -v`
- 예상: PASS

**Step 4: 커밋**
```
git add backend/modules/collector/scheduler.py backend/tests/test_scheduler.py
git commit -m "fix(phase8-sprint2): task10 — 일일 리포트 당일 1회 발송 잠금 (Redis 86400초)"
```

**완료 기준:**
- ⬜ 1일 1회 발송 보장
- ⬜ 다음 날 재발송 허용
- ⬜ 실패 시 lock 미설정 (재시도 가능)

---

### Task 11: 통합 회귀 + 수동 검증 가이드

**skill:** — (최종 검증은 sprint-dev의 verification-before-completion 자동 적용)

**Files:**
- Create: `docs/phase/phase8/sprint2/validation-notes.md` (배포 후 수동 검증 체크리스트)
- Modify: `docs/phase/phase8/sprint2/sprint2.md` (본 문서의 최종 검증 표 status 업데이트)

**Step 1: 전체 pytest 회귀**
- 검증: `docker compose exec backend pytest -v`
- 예상: 모든 테스트 PASS (Task 1~10 신규 + 기존 854 passed). Sprint 1의 pre-existing fail(test_ws_manager_env_max_subscriptions)은 별도 이슈

**Step 2: 프론트 타입 체크**
- 검증: `docker compose exec frontend npx tsc --noEmit`
- 예상: 에러 없음

**Step 3: 수동 검증 가이드 작성**
- `validation-notes.md`에 배포 후 체크리스트 작성:
  - **Redis 키 검증**: `risk:daily_trade_count`, `scheduler:daily_report:sent:YYYYMMDD`, `ws:reconnect:notified` 키 생성 확인
  - **다층 tier 관찰 (2거래일)**: trade_signals 테이블의 `reason->breakout_tier` 값 분포 (gap_open / prev_close / prev_high 각 1건+ 목표)
  - **13:00 가드**: 13:00 이후 prev_close tier 거부 로그 확인
  - **일일 10건 한도**: 당일 누적 매수 체결이 10건에 도달 시 `can_trade` 차단 로그
  - **Sprint 3 전 3건/일 제한 검증**: Railway에 `DAILY_MAX_TRADE_COUNT_OVERRIDE=3` 환경변수 설정 여부
  - **동시호가 구간**: 15:10~15:30 재연결 미발동 확인
  - **재연결 알림 / 일일 리포트**: 1통/1회 발송 확인
  - **프론트 리셋 버튼**: LIVE 배지 노출 + 2단계 확인 + Redis 키 삭제 확인

**Step 4: deploy.md 플레이스홀더 추가**
- deploy.md에 "Sprint 2 배포 후 수동 검증 항목"으로 체크리스트 링크 추가 (sprint-review가 결과 기록)

**Step 5: 커밋**
```
git add docs/phase/phase8/sprint2/sprint2.md docs/phase/phase8/sprint2/validation-notes.md deploy.md
git commit -m "docs(phase8-sprint2): task11 — 통합 회귀 결과 + 수동 검증 가이드"
```

**완료 기준:**
- ⬜ pytest 전체 PASS
- ⬜ tsc --noEmit 통과
- ⬜ validation-notes.md 작성
- ⬜ deploy.md 수동 검증 플레이스홀더

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 | status |
|-----------|------|-----------|--------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전원 PASS | ⬜ |
| momentum_breakout (tier) | `docker compose exec backend pytest tests/test_momentum_breakout.py -v` | 신규 8개 + 기존 21개 PASS | ⬜ |
| risk_manager | `docker compose exec backend pytest tests/test_risk_manager.py -v` | daily_trade_count 관련 6개 PASS | ⬜ |
| scheduler (no_data / reconnect / daily_report) | `docker compose exec backend pytest tests/test_scheduler.py -v -k "no_data or reconnect or daily_report"` | 신규 6개 PASS | ⬜ |
| engine | `docker compose exec backend pytest tests/test_engine.py -v` | 신규 block/size_ratio/on_order_filled 테스트 PASS | ⬜ |
| 프론트 타입 체크 | `docker compose exec frontend npx tsc --noEmit` | 에러 없음 | ⬜ |
| 프론트 리셋 버튼 (수동) | 로그인 → 대시보드 → 리셋 버튼 클릭 → Redis `risk:consecutive_loss_count` 삭제 | 삭제 확인 | ⬜ |
| seed_settings 신규 키 | `docker compose exec backend python -m scripts.seed_settings` 재적용 후 `daily_max_trade_count=10` 존재 | DB에 row 존재 | ⬜ |
| 배포 후 tier 관찰 (2거래일) | `SELECT reason->>'breakout_tier', COUNT(*) FROM trade_signals GROUP BY 1;` | 3 tier 모두 출현 | ⬜ |
| 동시호가 가드 (배포 후) | 15:10~15:30 백엔드 로그에 "동시호가 구간 — no_data 가드 스킵" 존재 | 로그 존재 | ⬜ |
| 재연결 알림 dedup (배포 후) | 60초 내 2회 재연결 시 텔레그램 1통만 수신 | 1통만 수신 | ⬜ |
| 일일 리포트 dedup (배포 후) | 15:30 이후 텔레그램 일일 리포트 1건만 수신 | 1건만 수신 | ⬜ |

---

## 수동 검증 체크리스트 (Phase 8 확정 파라미터 + Sprint 2 이관 항목)

- ⬜ 배포 직후 `daily_max_trade_count` settings row 존재 확인
- ⬜ 프론트 리스크 리셋 버튼 노출 + 2단계 확인 동작
- ⬜ 2거래일 연속 `breakout_tier` 3종 모두 1건 이상 관찰
- ⬜ 일일 10건 초과 시 can_trade 차단 (로그 확인)
- ⬜ Sprint 3 착수 전 Railway `DAILY_MAX_TRADE_COUNT_OVERRIDE=3` 설정
- ⬜ 15:10~15:30 WS 재연결 미발동 2거래일 연속 확인
- ⬜ 재연결 시 텔레그램 알림 1통 제한
- ⬜ 일일 리포트 당일 1회 발송 확인

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 완화책 |
|---|------|--------|--------|
| 1 | prev_close tier와 prev_high tier 경계 ambiguity — current_price == prev_high 때 어느 tier? | 정보 | 구현 시 `current_price > prev_high` 우선 판정 → prev_high tier. Task 1 테스트에 경계값 포함 |
| 2 | daily_trade_count 증가 지점(체결 콜백) 장애 시 카운트 누락 | ⚠️ | 로그 + 에러 격리 (포지션 생성은 정상 완료). 필요 시 Phase 8 Sprint 3에서 positions 테이블 기반 재집계 로직 추가 검토 |
| 3 | 재연결 이중 알림 근본 원인 미확정 | ⚠️ | Task 9는 dedup으로 증상 차단. Sprint 2 배포 후 로그 재수집하여 원인 특정 — 필요 시 Phase 8 Sprint 4에 별도 Task |
| 4 | 일일 리포트 이중 발송 근본 원인 미확정 | ⚠️ | Task 10은 Redis lock으로 차단. Telegram 봇 로그/API 호출 횟수 병행 관찰 필요 |
| 5 | 동시호가 가드가 15:30 후 WS 종료 흐름에 영향? | 정보 | `_market_close`는 15:30에 실행 — 가드는 15:30 미만에서만 동작하므로 영향 없음 |
| 6 | `DAILY_MAX_TRADE_COUNT_OVERRIDE`는 실행 시점에 읽어야 하는가, 부팅 시점인가? | 정보 | 매 호출마다 `os.getenv` 조회 (Redis 대비 비용 미미) — LIVE 게이트 통과 후 override 제거만으로 10건/일 복귀 가능 |
| 7 | breakout_tier 도입으로 기존 `reason` dict 사용처 영향 | 정보 | signal_generator/engine/position_manager에서 `reason.get("breakout_tier", "prev_high")` 기본값으로 역호환 |
| 8 | Hotfix #153은 phase8-sprint1 브랜치에 없음 — phase8-sprint2는 develop 기반이므로 포함 | 정보 | 브랜치 생성 시 develop 최신(#156까지) 포함 확인 완료 |

---

## 완료 기준

- ⬜ Task 1~11 모두 완료 (커밋 존재)
- ⬜ `docker compose exec backend pytest -v` 전체 통과
- ⬜ `docker compose exec frontend npx tsc --noEmit` 에러 없음
- ⬜ breakout_tier 3종 모두 코드 레벨 단위 테스트 통과
- ⬜ 일일 거래 한도 10건/일 + env override 동작 확인
- ⬜ Task 8~10 수정으로 2026-04-21 재현 시나리오 해소 (단위 테스트 수준)
- ⬜ 프론트 리스크 리셋 버튼 노출 + Playwright 스모크(선택) 통과
- ⬜ validation-notes.md 작성 완료
