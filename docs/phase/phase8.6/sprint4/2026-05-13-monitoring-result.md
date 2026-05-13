# 2026-05-13 (수) — Phase 8.6 신호 발생 검증 모니터링 결과

> 작성: 2026-05-13 16:30 KST
> 계획 문서: `2026-05-13-monitoring-plan.md`
> 한 줄 결론: **신호 0건 마감 — 그러나 한 달간 0건의 진짜 본질(전략 설계 모순)을 014680 trace로 규명. A안(real-momentum) hotfix 배포 완료. 내일(2026-05-14)이 진짜 검증일.**

---

## 1. 점검 일정별 결과

| 시각 | 핵심 측정 | 판정 |
|------|----------|------|
| 08:56 (사전) | observation-daily 정상, rollback inactive | ✅ |
| 09:30 (1차) | vol5m=120, orderbook=20, atr_filter 2건 | ✅ Go (PARALLEL OFF 검증) |
| 12:00 (2차) | signals=0, min_volume_floor 72.4% 압도 | ❌ Hold — A+B hotfix 결정 |
| 14:30 (3차) | signals=0, A+B hotfix 효과 확인 (atr_filter 0%, min_volume_floor 압도 해소), 새 압도 stage 부상 | ❌ Hold — 임계 게임 무한 루프 자각 |
| 16:10 (4차) | 🚨 R1+G3+R3 자동 발동 (auto_rollback_2d_zero_signals) | ❌ — 안전망은 정상 작동 |
| 16:30 (종합) | 014680 trace로 본질 규명 + A안 real-momentum hotfix | ✅ 본질 진단 완료 |

---

## 2. 합격/불합격 판정 (monitoring-plan.md §3 기준 5개 항목)

| 조건 | 합격 기준 | 측정값 | 판정 |
|------|-----------|--------|------|
| 데이터 파이프라인 | vol5m ≥ 800, orderbook ≥ 15 | vol5m=**1520** (16:10), orderbook=**20** (09:30, 마감 후 만료) | ✅ |
| PARALLEL OFF 검증 | `prev_close_volume_confirm` + `gap_open_absorb` ≤ 5건 | **0건** (전일 누적) | ✅ |
| 신호 생성 | total ≥ 1건 (어떤 tier든) | **0건** | ❌ |
| 자가치유 검증 (G2/G3 unset 분기) | 작동 또는 미발동 | 조건 악화로 SET 분기 정상 작동 (unset 자체 트리거 안 됨) | ✅ 시스템 정상 |
| 임계 통과 분포 (단일 stage ≤ 50%) | ≤ 50% | 전일: min_volume_floor 23.8%, prev_close_time_guard 19.3% (max 26%) | ✅ Hotfix A+B 후 분산화 |

**종합 판정**: 5개 중 **4개 합격, 1개 불합격(신호 0건)**. 신호 0건은 임계 문제가 아닌 전략 설계 모순으로 규명.

---

## 3. 두 차례 Hotfix 진행 기록

### 3.1 hotfix/phase86-atr-volume-floor-relax (12:25 KST, PR #231/#232)

- `momentum_breakout.py:33` `ATR_FILTER_PCT` 0.05 → **0.07**
- Railway 환경변수 `MIN_VOLUME_FLOOR_HARD` 0.3 → **0.25**
- 효과: atr_filter 12:00 이후 0건 (완전 해소), min_volume_floor 압도(72.4%) 해소
- 한계: 새 압도 stage(prev_close_time_guard 25.8%, volume_threshold 22.7%, breakout 22.7%) 부상

### 3.2 hotfix/phase86-real-momentum-strategy (16:30 KST, PR #233/#234)

- `filters.py:14` `PrimaryFilters.change_rate_max` 7.0 → **30.0**
- `filters.py:23` `SecondaryFilters.trade_strength_min` 100.0 → **80.0**
- 효과 (예상): 상한가/급등 모멘텀 종목이 1차/2차 풀에 진입 가능

---

## 4. 진짜 본질 진단 — 014680 Trace 결과

### 4.1 시장 환경 (불장 확정)

| 종목 | 변동률 |
|------|--------|
| KODEX 200 (069500) | **+2.98%** (전형적 불장) |
| SK하이닉스 (000660) | +7.68% |
| 삼성전자 (005930) | +1.79% |
| **014680 한솔케미칼** | **+12.0%** 🚀 |
| 009150 LG | +7.41% |
| 042700 한미반도체 | +6.09% |

→ "박스권" 가설 폐기. **불장이고, 우리 1차 풀에 모멘텀 종목 다수 보유**.

### 4.2 Smoking Gun 발견

| # | 발견 | 위치 | 영향 |
|---|------|------|------|
| 1 | **`change_rate_max=7.0`** 1차 컷오프 | `filters.py:14` | +7% 초과 모멘텀 종목 자동 제외 |
| 2 | **`trade_strength_min=100.0`** 2차 컷오프 | `filters.py:23` | 상한가 모멘텀(매도 호가 비어 CTTR<100) 자동 배제 |
| 3 | 014680 실측 CTTR=**50.0** | KIS realtime | 임계 100의 절반 — 즉시 탈락 |
| 4 | 014680 realtime data **null** | `/collector/realtime/014680` | 데이터 미수집 시 즉시 reject |

### 4.3 시스템 정체성의 모순

| 시스템 표방 | 실제 동작 |
|------------|----------|
| "단타 모멘텀 매매" | +7% 이상 오른 종목 1차에서 자동 제외 |
| "급등주 잡기" | 매수만 폭주(CTTR<100) 종목 2차에서 자동 제외 |
| "실시간 추격" | 실시간 데이터 갭 종목 즉시 탈락 |

**현재 전략의 정체**: "+0~+7% 안정 상승 + 매수/매도 균형 잡힌 종목" 매수 — 진짜 단타와 무관한 **순한 균형 매수 전략**.

---

## 5. 자동 안전망 발동 기록 (16:10 KST)

| 게이트 | 상태 | 발동 사유 |
|--------|------|----------|
| **R1** (auto_rollback) | 🚨 발동 | `auto_rollback_2d_zero_signals` (2일 연속 0건) |
| **G3** (circuit_breaker) | 🚨 발동 | pass_rate 0% (signals 0 / candidates 20) |
| **R3** (override) | 🚨 발동 | `MIN_VOLUME_FLOOR_MODE=legacy` + `SECONDARY_POOL_FALLBACK_ENABLED=False` 강제 |

**시스템 평가**: 안전망 자체는 의도대로 정상 작동. 다만 R3 강제로 A안 hotfix의 `MIN_VOLUME_FLOOR_HARD=0.25` 효과가 차폐된 상태.

---

## 6. 다음 액션 (monitoring-plan.md §6 대체 — A안 진짜 모멘텀 검증 단계)

### 6.1 즉시 (장 개장 전, 2026-05-14)

| # | 작업 | 담당 |
|---|------|------|
| 1 | **R3 강제 활성 해제** — Railway SSH로 Redis 키 6개 DEL (`phase86:rollback:active`, `phase86:circuit_breaker:active`, `settings:override:*`) | ⬜ 사용자 |
| 2 | Railway 환경변수 `MIN_VOLUME_FLOOR_HARD=0.25` 유지 확인 | ⬜ 사용자 |
| 3 | PR #233 main 배포 완료 + Railway 빌드 확인 | ✅ 완료 |

### 6.2 2026-05-14 (목) — 진짜 모멘텀 첫 검증일

| 시각 | 점검 |
|------|------|
| 09:00 | 장 개장 (자동) |
| 09:30 | 1차 풀 진입 확인 — +7% 이상 종목이 포함되는가 |
| 12:00 | signals.total ≥ 1 검증, 2차 통과 종목 수 ≥ 5 확인 |
| 14:30 | 오후장 누적 + stage 분포 |
| 16:10 | G2/G3 발동 여부 (오늘 발동 상태에서 unset 분기 작동 검증) |
| 16:30 | 종합 보고 — `docs/phase/phase8.6/sprint4/2026-05-14-monitoring-result.md` |

### 6.3 2026-05-14에 신호 ≥ 1건 발생 시

- A안 hotfix 효과 입증 → momentum_breakout 게이트들 본격 운영
- Sprint 4 G-Bt1~3 walk-forward 백테스트로 임계 재조정 (단계 C 본격 착수)
- dry_run → LIVE 전환 검토는 Sprint 4 게이트 통과 후

### 6.4 2026-05-14에도 신호 0건이면

- 추가 trace 항목:
  1. 1차 풀에 +7% 이상 종목 실제로 진입했는가 (안 했으면 1차 다른 필터 더 있음)
  2. 2차 통과 종목 수 (여전히 2개면 trade_strength_min 추가 완화 또는 다른 게이트 압도)
  3. momentum_breakout 평가 trace에 +7% 종목 등장 여부
- 검토 대상: realtime data 수집 파이프라인 (`execution: null` 빈도), `_get_realtime_data` 폴백 로직

---

## 7. 오늘의 교훈 (process)

1. **"임계 완화" hotfix는 첫 발견 후 보통 옳지만, 2회 이상 반복되면 본질 의심해야 함**. 오늘은 임계 hotfix 1회(A+B) → 새 압도 stage 부상 → 즉시 본질 trace로 전환한 것이 결정적이었음.
2. **종목 단위 trace > 통계 분포**. stage-heatmap 분포만 보면 임계 게임에 빠진다. 014680 단일 종목의 1차→2차→momentum_breakout 전체 경로 추적이 본질을 드러냈음.
3. **시장 환경 가설은 외부 데이터로 빠르게 검증**. 사용자의 "요즘 불장" 지적 후 KIS price API로 5분 안에 가설 폐기. 가설을 오래 끄는 것이 가장 큰 손실.

---

## 8. 참고

- **계획 문서**: `2026-05-13-monitoring-plan.md`
- **Hotfix PR**: #231, #232 (atr+floor), #233, #234 (real-momentum)
- **코드 변경 위치**: `backend/modules/screening/filters.py`, `backend/modules/trading/strategies/momentum_breakout.py`
- **R3 해제 스크립트**: `scripts/ops/clear_phase86_keys.py` (develop 브랜치)
- **다음 결과 문서**: `docs/phase/phase8.6/sprint4/2026-05-14-monitoring-result.md` (내일 작성)
