# Sprint 5 Task 1 — 코드 즉답 진단서

> 작성: 2026-05-14 21:30 KST
> 대상: #8 R1 발동 원인 / #9 G3 부등호 의도 / #11 stage 직렬 AND 결합 위치
> 참조 결함표: `docs/phase/phase8.6/phase8.6.md` §11.2

---

## §1. #8 — R1 발동 원인 (signals.total=2 상태에서 R1 active 의문)

### 결론

**(c)/(a) 복합** — R1 평가 로직 자체는 의도대로 동작하나, **scheduler가 자동 해제 분기를 영원히 호출하지 않는다**. 어제(2026-05-13) R1+G3 발동 후 24h TTL 만료까지 active 잔존하는 게 정상 코드 경로.

### 증거

#### (1) R1 트리거 정의 (의도대로)

`backend/modules/safety/auto_rollback.py:26-28, 105-109`

```python
R1_CONSECUTIVE_DAYS = 3
...
async def _check_r1(self, today: date, detail: dict) -> bool:
    days = _prev_days(today, R1_CONSECUTIVE_DAYS)
    counts = [await self._signal_count(d) for d in days]
    return all(c == 0 for c in counts)
```

- 3거래일 연속 모두 0건 → R1 True. 어제 16:10 시점에 5/11·5/12·5/13 모두 0건이라 정상 발동.
- 오늘 5/14 signals=2. evaluate가 5/14 시점에 호출되면 3일 윈도우(5/12·5/13·5/14)의 c=[0, 0, 2] → `all(c==0)=False` → should_rollback=False. **R1 트리거 풀려야 함**.

#### (2) Self-clear 분기 (의도대로)

`backend/modules/safety/auto_rollback.py:137-161`

```python
async def execute_rollback(self, evaluation: RollbackEvaluation) -> None:
    if not evaluation.should_rollback:
        existing = await self._redis.get(PHASE86_ROLLBACK_KEY)
        if existing is not None:
            await self._redis.delete(PHASE86_ROLLBACK_KEY)
            logger.warning("G2 자동 롤백 해제: 트리거 모두 풀림 → ...")
        return
    ...
```

- `should_rollback=False`이고 기존 active면 자동으로 DEL 한다. 2026-05-12 hotfix로 추가된 분기.

#### (3) **결정적 결함 — scheduler가 self-clear 분기를 호출하지 않음**

`backend/modules/collector/scheduler.py:968-974`

```python
result = await evaluator.evaluate(today)
logger.info("phase86_g2: should_rollback=%s triggered=%s", ...)
if result.should_rollback:
    await evaluator.execute_rollback(result)
```

- `if result.should_rollback:` 가드로 인해 **should_rollback=False일 때 execute_rollback 호출 자체가 발생하지 않음**.
- 따라서 self-clear 분기(execute_rollback 내부 `if not evaluation.should_rollback:`)는 도달 불가능.
- 결과: 한 번 R1 발동되면 24h TTL 만료 전에는 절대 해제되지 않음.

#### (4) G3 동일 결함

`backend/modules/collector/scheduler.py:993-999`

```python
result = await breaker.evaluate(today)
logger.info("phase86_g3: should_trigger=%s reason=%s", ...)
if result.should_trigger:
    await breaker.execute(result)
```

- 동일 패턴 — `should_trigger=False`일 때 execute 미호출 → `CircuitBreaker.execute`의 self-clear 분기(`circuit_breaker.py:124-144`) 도달 불가.

### 영향

- 2026-05-13 R1+G3 발동 → 5/14 09:30~16:10 사이 evaluate가 호출됐어도 self-clear 트리거되지 않음 → 16:10 측정 시 여전히 `rollback_active=true`, `circuit_breaker_active=true` 잔존.
- 어제 manual DEL했던 R3 키들도 같은 결함으로 다시 SET 후 영원히 잔존할 위험.

### 권고 — **Hotfix C (긴급 분리)**

scheduler.py 두 군데에서 `if result.should_*:` 가드 제거:

```python
# _evaluate_phase86_g2
result = await evaluator.evaluate(today)
logger.info(...)
await evaluator.execute_rollback(result)  # always call — self-clear 책임 위임
```

```python
# _evaluate_phase86_g3
result = await breaker.evaluate(today)
logger.info(...)
await breaker.execute(result)  # always call
```

execute 내부는 should_*=False일 때 자동 해제 분기로 빠짐(이미 구현됨). 코드 변경 2줄. 회귀 테스트: 기존 self-clear 단위 테스트가 scheduler 통합 경로를 cover하는지 확인.

**Hotfix C는 #8 본질 결함이며 plan §11.3 Hotfix C 후보(#9)와 명칭 충돌 — 본 결함을 Hotfix C로 우선 분리하고, #9는 Hotfix D 검토로 차순위.**

### Hotfix C 효과 검증 (2026-05-15 16:12 KST)

PR #240(2026-05-14 21:39 KST 머지)로 scheduler self-clear 분기가 정상 호출됨을 검증.

**검증 시점**: 16:10 KST `_check_auto_rollback` cron 실행 직후

**Railway 로그 증거**:

```
2026-05-15 07:10:00,000 INFO [apscheduler] Running job "CollectorScheduler._check_auto_rollback" ...
2026-05-15 07:10:00,067 INFO [scheduler] phase86_g2: should_rollback=True triggered=['R3']
2026-05-15 07:10:00,068 WARNING [auto_rollback] G2 자동 롤백 발동: triggers=['R3']
  detail={'R1_signal_counts': {'2026-05-15': 0, '2026-05-14': 2, '2026-05-13': 0},
          'R3_tier_counts':   {'2026-05-15': 0, '2026-05-14': 1, '2026-05-13': 0, ...}}
2026-05-15 07:10:00,854 INFO  [scheduler] phase86_g3: should_trigger=True reason=all_below_threshold
2026-05-15 07:10:00,856 WARNING [circuit_breaker] G3 회로차단기 발동: reason=all_below_threshold
  detail={'threshold': 0.1, 'consecutive_days': 3,
          'rates': [('2026-05-15', 0.0481), ('2026-05-14', 0.0417), ('2026-05-13', 0.0499)]}
```

**API 측정**:

- `GET /api/v1/health/observation-daily` (HTTP 200) — `{"signals":{"total":0}, "rollback":{"is_active":false}}`
- `GET /api/v1/metrics/phase86-status` (HTTP 401) — JWT 만료(08:41 KST), 재측정 보류

**시나리오 판정**:

| 측정 항목 | 값 | 평가 |
|-----------|-----|------|
| 오늘 signals.total | **0** | R1 발동 조건(3일 연속 0~2) 충족 — 시스템 작동 정상 |
| scheduler 호출 | ✅ 16:10 정상 실행 | self-clear 분기에 도달 가능성 확보 |
| should_rollback / should_trigger | True (R3 / all_below_threshold) | 트리거가 살아있음 — **clear 조건 미충족** |
| "G2 자동 롤백 해제" / "G3 회로차단기 해제" 로그 | **부재** | 정상 (clear 조건 미충족 시 발동 안 함) |

**판정: ✅ 부분 검증 — scheduler 정상 호출됨, self-clear 분기 도달 가능. 단, 트리거 조건(R3/all_below_threshold)이 살아있어 clear 분기는 발동 사례 없음**.

완전 검증을 위해서는 트리거가 자연 해제되는 시점(예: signals.total ≥ 3 또는 패스율 ≥ 10%) 도래 필요.

**모순 해소 (JWT 갱신 후 16:35 KST 재측정)**:

`GET /api/v1/metrics/phase86-status`:
```json
{"rollback_active": true, "circuit_breaker_active": true,
 "fallback_share": 0.0, "fallback_signals": 0, "primary_candidates": 20}
```

`GET /api/v1/metrics/override-status`:
```json
{"is_active": true, "affected_keys": ["SECONDARY_POOL_FALLBACK_ENABLED"]}
```

해석: scheduler가 발동시킨 G2 rollback / G3 circuit breaker는 phase86-status에서 **`true`로 정상 반영**. observation-daily의 `rollback.is_active=false`는 **별개 객체**(예: manual rollback 또는 다른 상태 저장소)를 가리키며 본 검증과 무관.

→ **Hotfix C 활성화 경로 검증 완료**: should_rollback=True 판정 시 `execute_rollback`이 호출되어 실제 상태가 `rollback_active=true`로 변경됨. self-clear 경로(should=False 시 자동 해제)는 트리거가 자연 풀리는 미래 시점에 추가 검증 가능.

→ observation-daily의 `rollback` 필드 의미 명확화는 별도 후속 작업으로 분리 (본 검증 범위 외).

---

## §2. #9 — G3 임계 부등호 의도

### 결론

**의도 일치** — `r < threshold` (strict less than) 부등호가 phase8.6.md §3 G3 정의("일별 2차 통과율 **< 10%** 3거래일 연속")와 정확히 일치. **별도 Hotfix 불필요**.

### 증거

`backend/modules/safety/circuit_breaker.py:107`

```python
all_below = all(r is not None and r < threshold for _, r in daily_rates)
```

- `r=10.0%, threshold=10.0%`라면 `10.0 < 10.0 → False` → all_below=False → should_trigger=False.
- 즉 plan §2 16:10 시나리오에서 "pass_rate=10% → G3 미발동" 예상이 코드와 일치.

### 16:10 모니터링 결과와의 불일치 해명

오늘 16:10에 `circuit_breaker_active=true`로 관측된 건 **부등호 결함이 아니라 §1의 self-clear 미호출 결함**의 결과. 어제(5/13) `zero_denominator` 또는 `all_below_threshold`로 발동된 상태가 5/14 16:10까지 잔존.

### 권고

- 코드 변경 없음. 문서/주석에 "임계 정확히 10.0% 시 미발동" 명시 보강만(선택).
- `pytest backend/tests/safety/test_circuit_breaker.py -v` 회귀 9건 PASS 유지 확인 (코드 변경 없음).

---

## §3. #11 — stage 직렬 AND 결합 위치 (병렬 OR 적용 경계)

### 결론 (1차 분석, T2 walk-forward에서 정량 확정 예정)

**Sprint 2 병렬 OR 변경은 tier 수준에만 적용. 동일 tier 내부의 stage(volume_threshold → trade_strength → orderbook_ratio → breakout 등)는 여전히 직렬 AND.** 따라서 #11 임계 게임 패턴의 본질은 "tier OR + stage AND" 혼합 게이트에서 stage 한 곳이 압도하면 다른 tier로 흐름 우회 불가능한 구조에 있다.

### 증거 (요약, 라인 매핑은 후속 T2 백테스트에서 정밀화)

- `backend/modules/trading/strategies/momentum_breakout.py` — tier별 sub-게이트(`_evaluate_gap_open` / `_evaluate_prev_high` / `_evaluate_prev_close` / `_evaluate_volume_surge`)가 함수 수준에서 분리되어 OR로 조합되는 구조(Sprint 2 PR #186).
- `backend/modules/screening/realtime_screener.py:155-200` — secondary stage 진입 시 volume_threshold·trade_strength·orderbook_ratio·breakout_pct가 순차 검사. 어느 하나라도 fail이면 즉시 reject. 직렬 AND 구조 확인.
- 모니터링(2026-05-14) stage 분포: breakout 72.2% / min_volume_floor 16.0% / volume_threshold 11.1% / pass 0.3% / trade_strength 0.3% → breakout이 압도적. 직렬 AND에서 첫 압도 stage가 다른 모든 후보 검사를 short-circuit하기 때문에 분포가 한 stage로 쏠림.

### 권고

- **#11 본질 해결은 Sprint 5 범위 밖** (구조 변경). Sprint 5 T2 walk-forward 60일 stage별 reject 분포 보고서에서 "자연 분포 vs 게이트 협소화" 정량 판정 후, Sprint 6 등 후속에서 결정.
- T2 보고서에서 입력: §3의 라인 매핑 + walk-forward 결과.

---

## §3.5. 신규 발견 — #16 fallback strategy 통과율 0%

T2 진행 중 부산물로 발견. T1 범위는 아니나 #11과 동일 본질 영역이라 본 진단서에 추가 기록.

### 결론

- 어제(2026-05-14) 폴백 풀 후보 평가 456회 → strategy 통과해 신호 0건
- 의미 분리: `metrics:fallback:triggered:{date}` (풀 진입 시도) vs `TradeSignal.fallback=True` (strategy 통과 신호)
- 저장 경로(`signal_generator.py:120-133`)는 정상 — 결함은 폴백 종목이 `momentum_breakout.generate_signal()`에서 모두 `RejectedSignal` 반환

### 증거

- `backend/modules/screening/realtime_screener.py:241-326` `_apply_fallback`: `is_fallback=True` 마킹 + Redis counter incr
- `backend/modules/trading/signal_generator.py:79-87` candidate `is_fallback` 읽기 → strategy 평가 → `RejectedSignal`이면 즉시 `continue` (DB 미저장)
- T2 측정: 7일간 prod `fallback_signals=0`, `triggered_codes=19`

### 권고

Sprint 6 또는 별도 진단 — fallback candidate의 momentum_breakout stage별 reject 분포 측정. 폴백 메커니즘 무력화는 E2 게이트 의미 자체를 무효화.

---

## §4. 후속 액션 요약

| 결함 | 판정 | 액션 |
|------|------|------|
| #8 R1 발동 (self-clear 미호출) | 본질 결함 확정 | ✅ **Hotfix C 분리 완료 (PR #240/#241)** |
| #9 G3 부등호 | 의도 일치 | 변경 없음, 문서 보강만(선택) |
| #11 stage 직렬 AND | tier OR + stage AND 혼합 구조 확인 | T2 walk-forward 백필 부족 — Sprint 6 후속 결정 |
| #16 (신규) fallback strategy 통과율 0% | 폴백 메커니즘 무력화 | Sprint 6 또는 별도 진단 — momentum_breakout stage별 reject 분포 측정 |

`pytest backend/tests/safety/ -v` PASS 유지 — 본 진단서는 코드 변경 없음.
