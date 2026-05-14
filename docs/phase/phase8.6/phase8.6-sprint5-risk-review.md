# Phase 8.6 Sprint 5 — 최리스크(리스크관리 전문가) 검토

> 작성일: 2026-05-14
> 검토 대상: Phase 8.6 Sprint 5 초안 (2026-05-13~14 모니터링 결과 14개 결함 처리)
> 페르소나: `docs/experts/risk-manager.md` — "리스크 관리는 절대적 / 최악의 시나리오 / 자동화된 손절 / 일일 손실 한도 초과 시 매매 중단 / 레버리지는 엄격"

---

## 1. 요약 — 🚨 **재검토 (Phase 8.7 LIVE 게이트 진입 절대 금지 신호 유지)**

`2026-05-14-monitoring-result.md` §16:30 핵심 발견 4가지 + advisor §5 권고 종합 → **현재 시스템은 무엇을 매매하는지 통계적으로 입증되지 않은 상태**. Phase 8.5 분기 D 4명 재리뷰에서 최리스크가 "🚨 시스템 신뢰도 적색 — LIVE 전환 절대 금지 신호" 라고 한 진단이 그대로 유지된다.

오늘 신호 2건 ≠ 시스템 신뢰도. 이유:

1. **2차 통과 종목 100%가 KIS WS execution null** — 체결 스트림 없이 신호가 발생했다 = fallback 경로(추정 데이터) 산물일 가능성 매우 높음
2. **fallback 발동 456건 / 신호 2건 = 1:228 비율** — 정상 신호의 잡음 대비 비중을 식별 불가
3. **단일 stage 72.2% 편중** — 신호가 한 진입 패턴에 몰려있다 = 시장 환경 변화 시 일괄 손실 위험
4. **R1 자동 발동 (오늘 신호 ≥1임에도)** — 안전망이 작동하긴 했지만 발동 사유가 plan과 어긋남 = 안전망 자체의 신뢰도 검증 필요

→ **이 상태에서 dry_run → LIVE 토글 시 즉시 일일 손실 한도 -2% 발동 후 매매 중단 가능성 매우 높음.** Phase 8.7 entry gate를 단순히 "신호 발생 ≥1" 로 두면 안 됨.

---

## 2. 항목별 검증 결과

### #6 KIS WS execution 35% 누락 — 🚨 **LIVE 자금 보호 P0 차단 사유**

LIVE 전환 시점에 35% 종목이 execution null = 35% 종목은 **실시간 가격을 보지 못하는 상태로 매매 신호가 발생**한다. 손절 트리거 가격도 fallback(추정/지연) 데이터로 평가하므로:

- 진짜 가격이 -3% 손절선 돌파했지만 fallback 데이터가 -2%로 보이면 → 손절 지연
- emergency_stop(-3%) 임계 발동도 지연 → daily_max_loss(-2%) 초과 후 발동

= **LIVE 전환 전 #6 root cause 해결 필수**. 현재 dry_run 유지가 정답.

#### 리스크 권고

- Phase 8.7 entry gate에 **"WS execution 누락률 ≤ 5%" (윤에이피 ≤10%보다 더 보수)** 추가 필수
- 누락률이 0%로 가지 않는 한 LIVE 전환 금지
- Sprint 5 진단 결과 KIS 한도가 root cause라 1차 풀 축소(20→18)로 대응한다면, **축소 후에도 ≤5% 유지 검증**

### #7 SECONDARY_POOL_FALLBACK_ENABLED unset 누락 — ⚠️ **R3 자가치유 신뢰도 결함, hotfix 필수**

`2026-05-14-monitoring-result.md` §16:10 — R3 unset 분기에 키 1개 누락. 안전망에 부분 결함이 있다 = 안전망 신뢰도가 검증되지 않은 상태에서 LIVE 전환은 절대 금지. **hotfix로 즉시 처리**.

추가 권고 (윤에이피 권고 승계 + 강화):

- 단순 키 추가가 아닌 **SettingsOverrideKey Enum 단일 진실 소스 + R3 unset 분기 enum.iter 기반** 으로 변경. 다음 키 추가 시 자동 포함.
- **R3 자가치유 분기 전체 회귀 테스트** 추가: 각 키에 대한 SET → 조건 해제 → unset 자동 검증.

### #8 R1 자동 발동 원인 의문 — 🚨 **안전망 신뢰도 검증 필수**

오늘 신호 ≥1 임에도 R1 active = 안전망이 의도와 다르게 작동하고 있을 가능성. 박퀀트 권고대로 plan §5.5 vs 코드 1:1 대조. **plan-code 불일치는 안전망 핵심에서 절대 허용 안 됨**.

리스크 관점 추가 권고:

- R1 발동 시 Telegram 알림에 **"발동 사유" + "trigger condition snapshot"** 을 함께 전송. 운영자가 plan과 어긋난 발동을 즉시 인지하도록.
- 05-15 (금) 개장 시 자동 해제 분기 검증 → 자동 해제 안 되면 **수동 clear 금지** + **plan §6.3 원칙 적용 (자가치유 분기 검증 기회로 활용)**.

### #9 G3 임계 부등호 — ⚠️ **단위 테스트 + 명시화 필수**

코드 의도부터 확인 후 결정. 박퀀트 권고대로 `pass_rate < 0.10` 로 변경 시:

- 단위 테스트: `assert pass_rate == 0.10` ⇒ no trigger / `assert pass_rate == 0.099` ⇒ trigger
- plan §3 G3 문구도 "< 10%" 로 명시 (현재 "<10% 3거래일 연속")
- "그 외 임계 부등호도 일제 점검" 을 Sprint 5 진단 sub-체크리스트로 추가

### #10/#13/#14 — #6 종속, 단 통계적 위험 잔존

윤에이피/박퀀트 검토 승계. **단 #14(secondary 통과 100% 교체) 는 리스크 관점 독립 위험**:

- LIVE에서 4시간 만에 보유 종목 100% 교체되면 회전매매 수수료 폭증
- Sprint 5 진단에서 secondary 통과 종목의 *체결 가능성* 측정 필요 (단순 통과율 아닌, 실제 진입 후 청산까지 frequency)

### #11 임계 게임 / stage 결합 — 변경 전 안전 측정 필수

박퀀트 권고(shadow mode 측정 → 시뮬 → 도입)에 리스크 강화 권고:

- **shadow mode는 LIVE 자금 영향 0 보장 (Phase 8.6 §5.6 #32 dry_run 기본값 원칙 승계)**
- 측정 결과 stage OR 결합 도입 시 신호 폭증 가능 → **Sprint 6 도입 전 일일 신호 한도 10건 → 5건 일시 축소** 권고
- volume_surge tier dry_run 상태 유지

### 미검증 trace 3건 — Sprint 5 안전망 진단 필수

특히 **R3 자동 SET 로직** 미관찰은 큰 결함. 안전망이 *언제* *왜* 발동했는지 사후 추적 불가 = 운영 부적격. Sprint 5에서 R3 SET/UNSET 시점·조건·trigger value 를 모두 일별 audit log에 적재.

---

## 3. 파라미터 조정 권고

### Sprint 5 진단 단계 — Phase 7.0 LIVE 파라미터는 코드 잠금 유지 (§5.2 G9)

**변경 0건**. 기존 5개 hotfix 모두 유지 (사용자 명시).

리스크 추가 잠금 권고:

| 파라미터 | 현재 | 권고 | 근거 |
|---------|------|------|------|
| `LIVE_TRADING_ENABLED` | false | **false 잠금** (Sprint 5/6 동안) | 진단 미완 + 안전망 부분 결함 |
| `VOLUME_SURGE_DRY_RUN` | true | **true 잠금** | Phase 8.6 §5.3 #17 유지 |
| 일일 신호 한도 | 10건 | **5건** (Sprint 6 stage OR 도입 시) | 신호 폭증 보호 |

### Phase 8.7 entry gate — 보수적 임계 권고

advisor §5 + 박퀀트 §3 추가 권고에 리스크 강화 더하기:

| 지표 | 목표 (advisor) | 리스크 강화 권고 | 근거 |
|------|---------------|-----------------|------|
| WS execution 누락률 | ≤ 10% | **≤ 5%** | 손절 가격 신뢰도 |
| fallback 신호 비중 (M-F2) | ≤ 30% | **≤ 20%** | 신호 신뢰도 |
| 단일 stage 점유율 | ≤ 50% | ≤ 50% (그대로) | 시장 환경 변화 분산 |
| Secondary 4h 교체율 | ≤ 50% | **≤ 30%** | 회전매매 수수료 |
| Paper 신호 PnL | 양(+) | **양(+) AND 손실 거래 ≤ 일일 한도 -2% 내** | 한도 검증 |
| 손절 체결 발생 | ≥ 1 | ≥ 1 (그대로) | 손절 로직 1차 검증 |
| **추가 신규** | — | **자동 롤백 R1~R4 모든 트리거 plan-code 일치 단위 테스트 통과** | 안전망 신뢰도 |
| **추가 신규** | — | **R3 자가치유 분기 전수 회귀 (settings:override:* 모든 키)** | 자가치유 결함 잔존 방지 |

### Phase 7.0 LIVE 파라미터 — 코드 잠금 영구 유지 (§5.2 G9)

`max_position=2`, `position_size=5%`, `daily_max_loss=-2%`, `emergency_stop=-3%` — Sprint 5/6 어떤 변경에서도 수정 금지.

---

## 4. 리스크 및 대안

### 리스크

1. **사용자가 Sprint 5/6 일정 압박으로 Phase 8.7 entry gate를 완화하려 할 위험** — 최리스크 P0: 거부. 일정보다 안전.
2. **shadow mode 도입이 운영 부하 → 운영자가 비활성화 유혹** — `SHADOW_MODE_ENABLED` env 토글은 가지되, 비활성화 시 Telegram 알림 자동 전송 + 일일 dashboard에 "shadow off" 배지 (Phase 8.5 Sprint 2.5 OverrideBanner 패턴 재사용).
3. **Sprint 5 진단 결과가 "#6은 KIS 한도 한계라 fix 불가"로 나올 시나리오** — 이 경우 LIVE 전환은 KIS 한도 풀릴 때까지 무기한 보류. 사용자 결정 항목.
4. **5월 15일(금) 진단 데이터 수집 실패 시** — 다음 거래일(월) 까지 1차 진단 지연. Sprint 5 timeline에 reserve day 포함.

### 대안

- 만약 #6 fix가 불가능하다면 **1차 풀을 KIS 슬롯 한도 내로 절대 보장**하는 우선순위 큐 + **execution 정상 종목만 신호 발행 대상**으로 제한. 누락 종목은 dry_run으로만 평가.

---

## 5. 결론

- 🚨 **Phase 8.7 LIVE 게이트 진입 절대 금지 신호 유지** (분기 D 시점부터 변함없음)
- Sprint 5 = 진단 + 안전망 신뢰도 검증 Sprint. 임계 변경 0건, dry_run 기본값 유지, LIVE_TRADING_ENABLED false 잠금.
- #7 (R3 unset enumeration), #9 (G3 부등호) hotfix는 분리 처리하되 회귀 테스트 강제.
- Phase 8.7 entry gate 신규 8개 지표 (위 표) — 사용자 "표면 통과형 게이트 X" 요청에 응답. 8개 모두 통과해야 LIVE.
- Phase 7.0 LIVE 파라미터 (max_position=2, position_size=5%, daily_max_loss=-2%, emergency_stop=-3%) 코드 잠금 영구.
- 안전망 R1~R4 plan-code 1:1 단위 테스트 + R3 자가치유 전수 회귀 = Phase 8.7 entry gate 의 P0 신규 조건.
