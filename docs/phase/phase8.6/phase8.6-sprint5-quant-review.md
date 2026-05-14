# Phase 8.6 Sprint 5 — 박퀀트(퀀트투자 전문가) 검토

> 작성일: 2026-05-14
> 검토 대상: Phase 8.6 Sprint 5 초안 (2026-05-13~14 모니터링 결과 14개 결함 처리)
> 페르소나: `docs/experts/quant-specialist.md` — "데이터가 말하게 하라 / 과적합 경계 / 단순한 전략이 살아남는다 / 표본 외 검증 필수 / 전략 간 상관관계 관리"

---

## 1. 요약 — ⚠️ **주의 (구조 변경 전에 측정 인프라부터 갖춰야 한다)**

사용자가 지목한 #11("임계 게임 패턴")의 본질을 더 정확히 정의할 필요가 있다. 현재 Phase 8.6 Sprint 2까지의 변경은 **tier(gap_open/prev_high/prev_close/volume_surge) 결합을 직렬 AND → 병렬 OR** 로 바꿨다. 그러나 `momentum_breakout` 전략 내부에는 stage 4종(min_volume_floor → breakout(prev_high) → volume_threshold → breakout_ref)이 **여전히 순차 AND**로 결합되어 있고, 한 종목이 stage k에서 reject되면 stage k+1은 평가되지도 않는다.

`2026-05-13-monitoring-result.md` §3.1~§3.2: 임계 hotfix 1회로 min_volume_floor 72.4% → 25.8%로 분산되었으나, 동시에 prev_close_time_guard / volume_threshold / breakout 이 22~26%로 부상했다. = **stage 4종 점유율 합이 100%로 고정되어 있고, 임계 1개 만지면 다른 stage가 자동으로 채운다.**

이것이 #11의 진짜 본체이다. *tier* 가 아닌 *stage* 의 직렬 결합. Sprint 2에서 OR 도입한 건 정답이었으나 한 층 아래에 직렬이 남아있다.

---

## 2. 항목별 검증 결과

### #6/#13/#14 (WS 누락, fallback 폭증, secondary 교체) — **퀀트 영역 아님**

윤에이피 영역. 단 통계적 영향:

- fallback 비중이 정량화되지 않은 상태(M-F2 산출은 됐으나 신호 비중 #15 G-F 충족 미확인)에서 신호 2건이 통계적으로 "구조 신호" 인지 "fallback 잡음" 인지 식별 불가.
- `2026-05-14-monitoring-result.md` §16:30 "fallback 신호 비중 (M-F2)" 추정값 미산출 → **Sprint 5 진단에서 G-F 산출 우선**.

### #8 R1 발동 원인 — **통계 트리거 정의 문제**

`2026-05-14-monitoring-result.md` §16:10 시나리오 매트릭스 — signals=2임에도 R1 active. 가능 원인 중 하나:

- R1이 "오늘 신호 ≥1 이면 무발동" 분기를 거치지 않고 "rolling window 누적 합산"으로 평가되고 있을 가능성. Phase 8.6 Sprint 1 §5.5 #23 권고는 "0건 3거래일 연속" 인데 코드 구현이 "3거래일 누적 ≤1" 로 들어갔다면 오늘 신호 ≥1 이어도 어제+그제+오늘=2 이므로 1 이하 또는 그근처에 걸쳐 발동했을 가능성.

권고: Sprint 5 진단 Task에서 `AutoRollbackEvaluator.evaluate_r1` 코드를 plan §5.5와 1:1 대조. 통계 트리거는 **불확실성 모드(rolling vs daily)** 가 다양해서 plan-code 불일치가 가장 흔한 결함이다.

### #9 G3 임계 `≤10%` vs `≥10% 미발동` — **부등호 문제**

박퀀트 표준 권고: 임계는 **strict inequality + Boolean 명시** 로 작성. `pass_rate < 0.10` 인지 `pass_rate <= 0.10` 인지가 운영에서 매번 모호하게 등장한다.

- 만약 실제 코드가 `pass_rate <= 0.10` 이면 정확히 10%에서 발동 (오늘 신호 2/20 = 10.0% 발동) = 부등호 1개 차이.
- 권고: `pass_rate < 0.10` 으로 변경 + 단위 테스트 `assert pass_rate == 0.10` ⇒ no trigger 추가.

이건 hotfix 가능하나 윤에이피 권고대로 **코드 의도부터 확인** 후 결정.

### #10 breakout 72.2% 편중 — **stage 분포 측정 인프라 부재가 더 큰 문제**

`2026-05-14-monitoring-result.md` §16:30. 한 stage가 70% 이상 점유하는 건 단타 모멘텀 전략에서 **이상하지 않다**. 진짜 모멘텀이면 breakout(prev_high 돌파)이 dominant stage 가 되는 게 자연. 문제는 **이 분포가 정상인지 비정상인지 판단할 baseline이 없다**.

권고: Sprint 5 진단 Task에서 walk-forward 백테스트 60일 데이터(Sprint 4 산출물)로 **stage 분포 baseline** 산출. 시뮬에서 breakout 점유율이 60~80%면 오늘 72.2%는 정상. 시뮬이 40% 정도면 #6/#7 영향으로 편중.

### #11 임계 게임 패턴 — **stage 직렬 AND 결합이 진짜 본체**

본 리뷰 §1 참조. 진짜 변경 대상은:

```python
# 현재 (의사 코드)
def evaluate_momentum_breakout(stock):
    if not pass_min_volume_floor(stock): return reject("min_volume_floor")
    if not pass_breakout(stock):         return reject("breakout")
    if not pass_volume_threshold(stock): return reject("volume_threshold")
    if not pass_breakout_ref(stock):     return reject("breakout_ref")
    return signal()
```

이걸:

```python
# Sprint 5 진단 후 검토 (즉시 변경 X)
def evaluate_momentum_breakout(stock):
    stages = [eval_min_volume_floor, eval_breakout, eval_volume_threshold, eval_breakout_ref]
    results = [s(stock) for s in stages]  # 모든 stage 평가 (직렬 차단 X)
    # 결합 정책: (a) 다수결 ≥3/4, (b) 가중치 합, (c) 핵심 stage(breakout) 필수 + 나머지 다수결
```

→ 단, 박퀀트 §3.3 "단순한 전략이 살아남는다" 원칙: 위 (a)~(c) 중 무엇이 맞는지 모름. Sprint 5에서 시뮬 검증 후 결정.

#### 단계적 권고

1. **Sprint 5 진단**: 모든 stage 평가하도록 코드 변경 (reject 없이 점수만 매기는 shadow mode 추가) → 종목별 stage 통과 패턴을 로깅. 임계 변경 X. dry_run X. **측정만 한다.**
2. **Sprint 6**: 측정 데이터로 결합 정책 후보 시뮬 비교 → 채택.
3. dry_run 5일 → walk-forward 60일 backtest → KS 검정 → 본격 도입.

### #16 미검증 trace 3건 — **퀀트 영역**

- **momentum_breakout 평가 경로에 +7% 종목 도달 여부**: A안 hotfix(`change_rate_max 7→30`)로 1차 풀에는 진입했음(`2026-05-14-monitoring-result.md` §09:30 momentum_factor 94.91 종목 확인). 단 2차 통과율(2/20=10%)이 낮아 평가 경로 자체에 거의 도달 안 함. trace 필요.
- **`_get_realtime_data` 폴백 로직**: #6과 묶음. fallback 발동 코드 경로 확인.
- **R3 자동 SET 로직**: monitoring-result에 시점/조건 미관찰. Sprint 5 진단 sub-체크리스트.

---

## 3. 파라미터 조정 권고

### Sprint 5 진단 단계 — **임계 변경 0건 (의도적)**

기존 5개 적용 hotfix(change_rate_max 30, trade_strength_min 80, ATR_FILTER_PCT 0.07, MIN_VOLUME_FLOOR_HARD 0.25, virtual-signals filter) — **모두 유지**. Sprint 5에서 추가 완화/되돌리기 안 함. 측정 노이즈 방지.

### Sprint 6 검토 후보 (Sprint 5 진단 결과 의존, 지금 결정 X)

| 후보 | 진단 결과 if | 권고 변경 |
|------|-------------|----------|
| stage 결합 정책 (a) 다수결 ≥3/4 | shadow mode 측정에서 다수결 ≥3/4 통과율 ≥ 30% | 도입 검토 |
| stage 결합 정책 (b) 가중치 | shadow mode에서 가중치 학습 후 OOS R² > 0 | 도입 검토 |
| breakout_ref reference 동적화 | shadow mode에서 reference 시점 변경 시 통과율 +X%p | 도입 검토 |

→ **Sprint 5 진단 결과 없이 위 후보를 미리 못박지 않음.**

### Phase 8.7 entry gate 통계 기준 권고

advisor §5 후보 표에 박퀀트가 추가 권고:

| 지표 | 목표 | 통계 근거 |
|------|------|----------|
| fallback 신호 비중 (M-F2) | ≤ 30% (5거래일 평균) | Phase 8.6 분기 D 시 ≈100% → 70%p 개선 = 본질 해결 신호 |
| 단일 stage 점유율 | ≤ 50% | shadow mode baseline 확인 후 조정 가능 |
| WS execution 누락률 | ≤ 10% (1차 풀 대비) | 윤에이피 권고 승계 |
| 신호 발생 종목 일중 안정성 (4h 교체율) | ≤ 50% | 100% 교체 = fallback 의존 — `2026-05-14-monitoring-result.md` §12:00 B 측정 |
| Paper 신호 PnL 5거래일 누적 | 양(+) | 신호 신뢰도 입증 (Sharpe 계산은 표본 < 30일이라 보조) |
| 손절 체결 발생 | ≥ 1 (Paper 5거래일) | Phase 8.7 §Sprint 1 DoD 신규 항목 |

박퀀트 추가 권고:

- **walk-forward Sprint 4 결과 (KS 검정 p, Bootstrap CI 하한) 를 entry gate G-Bt1/G-Bt2 로 유지** — 사용자가 "표면 통과형 게이트 X" 라고 했지만 walk-forward는 표면이 아니라 정공법.
- 단 G-Bt3(Paper 5거래일 G-A/G-B 동시 충족)은 위 표 기반으로 **재정의** 필수. 그대로 두면 phase8.6 내부 모순.

---

## 4. 리스크 및 대안

### 리스크

1. **stage 결합 OR 변경 시 신호 폭증** — 현재 일일 한도 10건 + 우선순위 큐 있지만 1주 70건+ 가능 (Phase 8.6 §9 알려진 리스크 #4 재현). **shadow mode 측정 → 시뮬 검증 → 도입** 3단계 강제.
2. **shadow mode 로깅이 운영 부하**: 종목당 4 stage × 일일 1차 풀 20 × 평가 빈도(분당 1회 가정) = 일 24,000건 stage 로그. Redis stream으로 처리 가능. Sprint 5 진단 Task의 인프라 부담.
3. **임계 미세조정 욕망 차단** — Sprint 5에서 사용자가 "stage 1개만 더 만지면 신호 늘 것 같다"고 요청해도 거부. 측정 진행 중 임계 변경 = 측정 노이즈.

### 대안

- Sprint 5 진단 데이터가 5거래일 부족 → 시뮬 데이터 60일로 보강. Sprint 4 walk-forward 인프라 재사용.

---

## 5. 결론

- **#11 임계 게임의 진짜 본체 = stage 직렬 AND 결합**. 사용자 진단 정확하나 변경 대상은 stage 결합이지 tier 결합이 아님 (tier는 이미 Sprint 2에서 OR).
- Sprint 5는 **측정 인프라 구축 Sprint** — shadow mode 도입 + stage 통과 패턴 일일 로깅 + fallback 비중 G-F 산출 + #6/#8/#9 진단.
- 임계 변경 0건, dry_run 변경 0건. 측정만.
- Sprint 6은 측정 결과 의존 — 지금 스펙 못박지 말 것.
- Phase 8.7 entry gate는 advisor §5 + 박퀀트 추가 권고 표 기반으로 재정의. walk-forward Sprint 4 결과(G-Bt1/G-Bt2)는 유지, G-Bt3만 교체.
