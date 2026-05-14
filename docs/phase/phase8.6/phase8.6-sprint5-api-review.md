# Phase 8.6 Sprint 5 — 윤에이피(Open API 전문가) 검토

> 작성일: 2026-05-14
> 검토 대상: Phase 8.6 Sprint 5 초안 (2026-05-13~14 모니터링 결과 14개 결함 처리)
> 페르소나: `docs/experts/api-developer.md` — "API는 언제든 실패 / Rate Limit은 70~80%까지만 / 토큰은 만료 전에 / 모의-실전 차이 과소평가 금지 / 연동 전 반드시 테스트"

---

## 1. 요약 — ❌ **재검토 (구조 변경 전 데이터 파이프라인 결함이 root cause로 보임)**

`2026-05-14-monitoring-result.md` §12:00 B / §16:30 4가지 핵심 발견 → "KIS WS 구독 누락 35%" 가 사실상 모든 표면 결함의 인과 시작점이다. 이걸 풀기 전에 `momentum_breakout` 구조 재설계로 가면 또 *임계 게임* 의 재판이 된다.

증상 인과 연쇄 (실측):

```
1차 풀 20개 중 execution null 7개 (35%)
  → 2차 통과 2/2 (025560, 036570) 100% execution 누락
  → fallback 강제 발동 (12:00 228 → 14:30 363 → 16:10 456, 4시간 +228)
  → secondary 통과 종목 12:00→14:30 사이 187870/086900 → 025560/036570 100% 교체 (#14)
  → fallback 보강 종목 위주로 stage 통과 → breakout 단일 stage 72.2% 편중 (#10)
  → 신호 2건 중 일부가 fallback 산물 가능성 → "신호 신뢰도 미입증" (#13)
```

→ 본질은 #6(WS execution 35% 누락). 나머지(#10/#13/#14)는 #6의 증상 또는 #6을 우회하려는 fallback의 부작용일 가능성이 매우 높다. 사용자가 지목한 #11(임계 게임)도 이 인과를 막은 후에 잔존하는지 재측정해야 한다.

---

## 2. 항목별 검증 결과

### #6 KIS WS execution 35% 누락 — ❌ **본질 최상위, Sprint 5 1순위 진단 대상**

문서·코드만으로 원인 후보 3개:

| 후보 | 검증 방법 | 비용 |
|------|-----------|------|
| A. **KIS 구독 한도 초과** — LIVE/Paper 1세션 당 H0STCNT0 동시 구독 한도(공식 41건, 실제 더 빡빡할 가능성) | 1차 풀 갱신 직후 KIS 구독 응답 코드/메시지 1일 캡처. Phase 5.2의 paper=25 / live=40 정책 기록 대조 | 진단 1일 |
| B. **1차 풀 갱신 vs WS subscribe 레이스** — 1차 풀이 09:30에 정해지는데 WS subscribe가 1차 풀 갱신 이전 코드로 묶여 있으면 신규 7개가 빠진다 | `realtime_screener` 1차 풀 갱신 후 → `kis_websocket.subscribe(codes)` 호출 시점/순서 코드 추적. trace 로그 1일 | 진단 0.5일 |
| C. **MST 동기화 타이밍** — Sprint 3에서 만든 `KOSPI200_MST_SYNC` kill-switch가 갱신 전 1차 풀에서 누락 종목을 만들 가능성 | 1차 풀 갱신 시점 ETF/주식 MST 동기화 상태 → subscribe 요청 코드 비교 | 진단 0.5일 |

> 공식 문서: KIS 실시간 시세 가입 한도는 계정당 41건. 동시에 H0STCNT0(체결) + H0STASP0(호가)를 따로 카운트하는지가 핵심. 호가는 20/20 정상 = 호가 슬롯은 멀쩡. 체결만 35% 누락은 **체결 슬롯 한도가 호가보다 더 작거나, 1차 풀 갱신 후 subscribe 호출이 부분 실패하고 재시도 없이 진행**하는 패턴이 의심.

#### 윤에이피 권고

- Sprint 5 첫 Task는 위 A/B/C 3개 후보를 **trace로 좁히기**. 단순 가설로 코드 손대지 말 것.
- KIS 측 한도가 root cause면 1차 풀 상한을 20→18로 축소 (체결 슬롯 여유 확보) 또는 우선순위 큐(score 기준) + 잔여 슬롯 polling 방식.
- B/C가 root cause면 subscribe 응답 코드 0 미확인 시 1회 재시도 + 누락 종목만 분리 재구독 + Telegram 알림 (Phase 6 KIS WS 안정화 인프라 재사용).

### #7 `SECONDARY_POOL_FALLBACK_ENABLED` unset 분기 누락 — ⚠️ **즉시 hotfix 가능, 단 단순 안 함**

`2026-05-14-monitoring-result.md` §16:10 Redis 키 직접 확인 표에서 4/5 키 unset 정상, 1개만 잔존 = R3 자가치유 분기에 키 이름 누락. 단순 추가 fix.

권고:

- Hotfix로 분리 가능. 단 PR #228(R3 unset 분기 추가)의 키 enumeration 누락이 1회 발생 = 다른 키도 누락 가능성. **전체 settings:override:* 키 enumeration 단일 진실 소스(예: `SettingsOverrideKey` Enum)** 도입을 같이 묶을 것.
- 단순 키 추가만 하면 다음에 또 키 추가 시 같은 결함 반복.

### #8 R1 자동 발동 원인 의문 (signals=2임에도 active) — ❌ **본질, Sprint 5 진단 대상**

`2026-05-14-monitoring-result.md` §16:10 시나리오 매트릭스 첫 줄. 오늘 신호 ≥1 인데 R1 active. 가능 원인:

| 후보 | 검증 |
|------|------|
| 어제(05-13) R1 active 상태가 자동 해제 분기를 통과하지 못함 (개장 시 자동 unset 분기 누락) | 05-15 개장 시 자동 해제 여부 관찰. monitoring-result §16:10 4️⃣ 권고 그대로 |
| R1 트리거 조건이 "오늘 0건"이 아닌 다른 정의(예: rolling 3일 합산?) | `auto_rollback.py` 코드 trace |
| pass_rate=10%에서 G3와 R1이 같이 발동되는 결합 트리거가 있음 | 코드 trace |

윤에이피는 이 영역 직접 영역 아니지만, **자가치유 분기 = 인프라**라는 관점에서 #7과 묶어 처리할 것.

### #9 G3 임계 조건 불일치 — ⚠️ **hotfix 전에 코드 의도 확인 필수**

`2026-05-14-monitoring-result.md` §16:10 "G3 임계 조건이 `≤ 10%`" → 코드 추정이다. plan 문서가 "≥10% 미발동" 가정이었는데 코드가 "<10%" 또는 "≤10%" 중 어느 쪽인지 확정되지 않음.

권고: **hotfix 후보로 못박지 말 것**. Sprint 5 진단 1번에 "코드 확인 → 의도대로면 plan 문서 수정 / 의도와 다르면 hotfix" 로 분기 처리.

### #10 breakout 72.2% 편중 — #6 해결 후 재측정

`2026-05-14-monitoring-result.md` §16:30 "장 마감 최종 reject 분포: breakout 208 (72.2%) / min_volume_floor 46 (16.0%) / volume_threshold 32 (11.1%)" — breakout 단일 압도. 단 이 분포는 **fallback 종목이 stage 통과 종목의 다수**일 때 자연스럽게 한 stage로 쏠릴 수 있음. #6 해결 후 fallback 비중이 정상화되면 분포도 재측정해야 한다.

### #11 임계 게임 패턴 — ⚠️ **#6/#10 해결 후에도 잔존 시에만 구조 변경**

advisor 검증 결과: **Sprint 2에서 *tier* 는 병렬 OR로 갔지만, `momentum_breakout` 내부 *stage* (min_volume_floor → breakout → volume_threshold → breakout_ref) 는 여전히 순차 차단**. 이게 #11의 진짜 본체.

stage 결합 구조는 Sprint 5에서 **측정 우선 → 변경 검토** 순으로 진행. 측정 없이 OR로 바꾸면 #4 위험(병렬 OR로 신호 폭증)이 재현된다.

### #12 `/screening/primary` 응답에 change_rate 없음 — ⚠️ **즉시 hotfix 가능**

`2026-05-14-monitoring-result.md` §09:30 합격 기준 #1 "측정 불가" 발견. 운영 진단용 read API 스키마에 `change_rate` 노출만 추가 = 단순 hotfix.

권고: **단순 hotfix로 분리**. response_model에 필드 추가 + 단위 테스트.

### #13 fallback 폭증 (오늘 456건) — #6 종속

#6 종속. WS execution 35% 누락이 fallback을 강제 발동시키는 구조면 본질 결함 해소 시 자연 감소. Sprint 5 진단 Task에서 fallback 발동 인과(WS 누락 코드와의 1:1 대응)를 trace로 확인.

### #14 secondary 통과 종목 시간대 변동 — #6 종속

#6 종속. 4시간 만에 187870/086900 → 025560/036570 100% 교체 = fallback 보강 종목 풀이 시간대마다 바뀐다는 의미. #6 root cause면 fallback 비중이 줄면서 안정될 것.

---

## 3. 파라미터 조정 권고 (원래값 → 권고값 + 근거)

윤에이피 영역에서는 **파라미터 변경 권고 없음**. Sprint 5는 진단 우선 Sprint이지 임계 변경 Sprint가 아님.

다만 #6 진단 결과 후보 A(KIS 구독 한도 초과) 채택 시:

| 파라미터 | 현재 | 권고 후보 | 근거 |
|---------|------|----------|------|
| `PRIMARY_POOL_SIZE` | 20 | **18** (또는 우선순위 큐 + 잔여 슬롯 polling) | 체결 슬롯 ≤ 호가 슬롯 시 1차 풀 상한을 체결 슬롯에 맞춰 축소 |

→ Sprint 5 진단 후 Sprint 6에서 결정. 지금 변경 금지.

---

## 4. 리스크 및 대안

### 리스크

1. **#6 진단 1일에 끝나지 않을 위험**: KIS 공식 문서가 체결/호가 슬롯 분리를 명시 안 함 → 실측 + KIS 고객센터 문의 필요할 수 있음. Sprint 5 진단 Task 기간을 **3~5일**로 잡되, 2일 후 진척 없으면 Telegram 알림 + 사용자 결정.
2. **trace 로그 폭증**: WS subscribe 응답 코드 + 1차 풀 갱신 시점 동시 trace = 일일 로그량 +30% 이상 가능. Railway 로그 보관기간 7일 한도 고려. Trace 모드는 `WS_TRACE_ENABLED=true` env 토글로 ON/OFF.
3. **5월 15일(금) 모니터링이 진단 데이터 수집의 1차 기회** — 진단 코드를 15일 장 시작 전에 배포해야 함. Sprint 5 첫 24h가 critical path.

### 대안

- 진단 우선 Sprint 5 (윤에이피 권고) vs 구조 재설계 Sprint 5 (사용자 초안) — 후자가 진행되면 #6이 결함으로 잔존한 채로 stage OR 결합을 도입 → **2주 후 같은 패턴 재발**할 가능성 70%+.
- Sprint 5를 "진단" + Sprint 6을 "진단 결과 기반 구조 변경" 으로 분리하는 것이 보수적이고 안전.

---

## 5. 결론

- **Sprint 5 1순위 = #6 WS execution 35% 누락 진단 (A/B/C 후보 trace)**
- #7/#12는 즉시 hotfix 분리 (#7는 enumeration 단일 진실 소스 묶음으로)
- #9는 코드 의도 확인 후 hotfix 여부 결정
- #8/#10/#13/#14는 #6 해결 후 재측정 — #6 root cause면 자연 해소
- #11(stage 결합 OR)은 #6/#10 해결 후 stage 분포 정상화 측정 후에만 변경 검토
- 미검증 trace 3건(realtime data 폴백, R3 자동 SET 시점, momentum_breakout +7% trace)은 Sprint 5 sub-체크리스트로 포함
- Phase 8.7 entry gate에 **"WS execution 누락률 ≤ 10%" 신규 추가 필수**
