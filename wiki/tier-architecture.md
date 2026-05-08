# 병렬 OR tier 구조

Phase 8.6 Sprint 2(2026-04-29, v2.8.0 prod)에서 도입된 신호 생성 핵심 구조. 직렬 AND 게이트 → 병렬 OR 다중 진입 경로로 재설계되었다.

## 배경

Phase 8.5 v2.6.1 5거래일 관찰에서 분기 D(`auto_rollback_2d_zero_signals`)가 발동되어, 직렬 AND tier 구조의 곱셈 0 결함이 확인되었다. 시뮬 2nd-screening pass율 38.9% vs 실측 ~3% (10배 이상 괴리).

## 직렬 AND → 병렬 OR

```
[기존 — 분기 D 시점]
gap_open / prev_high / prev_close
       └─→ 공통 ATR 5% + 2차pass75 + breakout AND 결합 → 신호

[현재 — Phase 8.6 Sprint 2]
gap_open ──┐
prev_high ─┼─→ 각 tier 독립 sub-게이트 평가
prev_close ┘     └─→ 통과 tier ≥ 1 → matched_tiers list[str] 기록 + 신호 발행
```

토글: `PARALLEL_OR_TIER_ENABLED=true` (기본). `false` 설정 시 Sprint 1 직렬 동작 100% 복원 (Kill-switch).

## tier별 sub-게이트

각 tier는 독립적으로 평가되며, 하나라도 통과하면 신호가 발행된다.

| Tier | sub-게이트 | 진입 시간 |
|------|-----------|----------|
| `gap_open` | `gap_rate ≥ 3%` AND `ATR ∈ [0.025, ATR_CEIL_HARD=0.08]` AND `current_price > open_price` (매물 흡수 컷) | TEMP_TIME_GUARD_SPRINT2 적용 시 09:10~ |
| `prev_high` | `current_price > prev_high × 1.001` (breakout) AND `ATR ∈ [ATR_FLOOR, ATR_CEIL_DYNAMIC]` | 09:10 ~ 13:00 |
| `prev_close` | 시간가드(13:00) AND `current_price > prev_close × 1.001` AND **5분봉 거래량 컨펌** (양봉 2연속 OR vol_5m ≥ 직전 4봉 평균 ×2) | 09:10 ~ 13:00 |

**임시 시간가드** (`TEMP_TIME_GUARD_SPRINT2=true`, 기본): 09:00~09:10 / 14:30+ 모든 tier 차단. Sprint 3 본 가드 도입 시 제거 예정.

**gap_open 시초가 컷** — 시초가 ≥ 현재가 시 매물 흡수 실패로 간주하여 거름.

## ATR 동적 캘리브레이션

`ATR_FILTER_PCT=0.05` 정적 상한 → KOSPI200 분위수 기반 동적 상한 + 하한.

- **하한**: `ATR_FLOOR=0.025` (모든 tier 공통, gap_open 포함)
- **상한 (일반 tier)**: `ATR_CEIL_DYNAMIC = min(ATR_CEIL_HARD=0.08, P80 × ATR_CEIL_MULT=1.2)`
- **상한 (gap_open)**: `ATR_CEIL_HARD=0.08` 절대 한계 (우회 X — Sprint 2 v2 수정)
- **상한 (폴백 종목)**: `ATR_CEIL_FALLBACK=0.05` 고정 (동적 미적용)

### 캘리브레이션 잡 (08:35)

`modules/screening/atr_calibration.py`. APScheduler `CronTrigger(hour=8, minute=35)`로 실행.

1. KOSPI200 종목 로드 (`stocks.is_kospi200=True` → 부족 시 `data/kospi200_static_backup.json` 폴백)
2. 종목별 20일 ATR 계산 (`ATR_CALIBRATION_WINDOW_DAYS=20`)
3. **방식 분기**: `ATR_CALIBRATION_METHOD=sma` (단순평균) 또는 `ewma` (λ=0.94)
4. **IQR ×1.5 트리밍** — outlier 제거 후 분포 산출
5. P80 × 1.2 → `ATR_CEIL_DYNAMIC`, HARD 0.08로 캡
6. Redis 저장 (TTL 3거래일):
   - `metrics:atr:ceil:{date}` — 진입에 실제 사용
   - `metrics:atr:dist:{date}` — P10/P20/P50/P80/P95 + sample_n
   - `metrics:atr:ceil_grid:{date}` — shadow 그리드 `{1.0, 1.1, 1.2, 1.3}` × P80
7. 단면 P80 vs 시계열 P80 차 ≥0.015 시 `quant_dist_drift_warn` 카운터 INCR + 텔레그램 알림

### 폴백 3단

캘리브레이션 실패 시 단계적 폴백:

| 단계 | 조건 | 동작 |
|------|------|------|
| 1단 | `market_data` 결측 ≥30종 OR KOSPI200 마스터 <10종 | 직전일 Redis 캐시 (TTL 3거래일) 재사용 |
| 2단 | 직전일 캐시도 부재 | `ATR_CEIL_HARD=0.08` 정적 사용 |
| 3단 | 2단 폴백 누적 ≥3회 (`metrics:atr:ceil:fallback_count`) | **안전모드** — `safe_mode:active` Redis 키 설정, `SAFE_MODE_TIMEOUT_MIN=120`분간 신호 발행 중단 + 텔레그램 알림 |

누수 방지: 캘리브레이션 쿼리는 `trade_date < CURRENT_DATE` (당일 행 미포함, 단위 테스트로 보장).

## 신호 메타데이터

병렬 OR 결합 결과는 `signals.matched_tiers` JSON 컬럼에 list[str]로 영속화된다. 토글 OFF 시 NULL.

- **confidence 산식**: 통과 tier들의 **평균** (최댓값 X — 보수 채택)
- 공통 게이트(`min_volume_floor`, `volume_threshold`, `trade_strength`, `confidence ≥ MIN_CONFIDENCE`)는 OR 결합 후 한 번만 적용

## 관측성

- `shadow:tier:{name}:{passed|failed}:{date}` — tier별 독립 shadow 평가 카운터
- `metrics:quant:sim_vs_real_diff:{date}` — shadow 통과율 vs 실제 신호 통과율 절대차. ≥0.15 시 텔레그램 알림 (분기 D 회귀 1주 내 자동 감지)
- tier 페어와이즈 **phi coefficient** + 조건부 P(B|A) — Pearson 대신 binary correlation. 목표선 phi ≤ 0.3, P(B|A) ≤ 0.5
- API:
  - `GET /api/v1/metrics/tier-pass-rate`
  - `GET /api/v1/metrics/tier-correlation`
  - `GET /api/v1/metrics/sim-vs-real-diff`

## 일일 한도와 회로

병렬 OR 직후에도 [[risk-management|일일 신호 한도 10건 + 동시 보유 2 포지션]]이 강제 적용된다 (`test_parallel_or_quota_cap`). matched_tiers 추가는 R1~R4 자동 롤백 산식 분모/분자에 영향 없음 (`test_parallel_or_r1_r4_isolation`로 격리 보장).

G3 회로차단기는 OR 모드에서 통과율이 N배가 되어 오발동될 수 있어, "체결 손실 누적" 임계로 일시 전환 또는 OR 모드 전용 보정 계수(`G3_OR_MODE_MULT`) 적용.

## 관련 문서

- 신호 생성 흐름: [[signal-generation]]
- 전략 상세: [[momentum-breakout-strategy]]
- 자동 롤백 R1~R4 + Phase 7.0 잠금: [[risk-management]]
- Phase 8.6 Sprint 1 가드레일: [[risk-management#dor-가드레일-g1g3]]
