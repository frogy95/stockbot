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

## §4. 후속 액션 요약

| 결함 | 판정 | 액션 |
|------|------|------|
| #8 R1 발동 (self-clear 미호출) | 본질 결함 확정 | **Hotfix C 즉시 분리** (scheduler.py 2줄) |
| #9 G3 부등호 | 의도 일치 | 변경 없음, 문서 보강만(선택) |
| #11 stage 직렬 AND | tier OR + stage AND 혼합 구조 확인 | T2 walk-forward 후 Sprint 5 종합 보고에서 본격 결정 |

`pytest backend/tests/safety/ -v` PASS 유지 — 본 진단서는 코드 변경 없음.
