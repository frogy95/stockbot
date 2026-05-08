# Phase 8.6 Sprint 3 — 5/8 관찰 결과 (v2.9.0 배포 직후 1거래일)

> 모니터링 4회 (08:42 atr / 13:29 / 14:31 / 15:34 / 16:15 KST)
> 환경: Sprint 3 v2.9.0 배포 (PR #201 머지 04:01:35Z) + hotfix `time-filter-block-counter` 배포 (PR #204 머지 04:22:26Z)

## 게이트 평가

| 게이트 | 지표 | 측정값 | 판정 |
|--------|------|--------|------|
| G1 (ATR 캘리브레이션) | sample_n ≥ 200 | **224** | ✅ PASS |
| G1 | ceil 동적 산출 | **0.0739** (P80×1.2) | ✅ PASS |
| G1 | safe_mode None | None | ✅ PASS |
| G1 | fallback_count = 0 | 0 | ✅ PASS |
| G1 | 2영업일 안정 (5/7+5/8) | 217 → 224 | ✅ PASS (안정 향상) |
| G2 (병렬 OR 신호) | signals ≥ 1건 | **0건** | ❌ FAIL (단일 영업일) |
| G2 누적 | 5/7 + 5/8 연속 | **2거래일 연속 0** | ⚠️ R1 발동 1거래일 남음 |
| G3 (시뮬-실측) | sim_vs_real_diff ≤ 0.15 | 측정 불가 (신호 0) | INFO |
| R1 자동 롤백 | rollback_active | None (inactive) | ✅ PASS |
| Auto Rollback (R2/R3/R4) | active | None | ✅ PASS |
| KOSPI200 | is_kospi200 count | 226종 유지 | ✅ PASS |

## Sprint 3 변경분 운영 검증

### Task 4 fix (scheduler 잡 키 적재 누락) — ✅ 검증 완료
5/7에서 None이었던 두 키가 5/8 정상 적재:
- `scheduler:last_portal_supplement = 2026-05-08T16:00:27.772792+09:00`
- `scheduler:last_metrics_rollup = 2026-05-08T16:05:16.248386+09:00`

`_portal_supplement_collect` / `_rollup_daily_metrics` 본문에 추가한 `_save_last_timestamp` 호출이 정상 동작.

### Hotfix `time-filter-block-counter` — ⚠️ 운영 검증 보류
- `metrics:time_filter:morning_lockout:2026-05-08` = None
- `metrics:time_filter:afternoon_lockout:2026-05-08` = None
- `metrics:time_filter:gap_open_morning_exception:2026-05-08` = None

원인 분석:
1. **morning_lockout (09:00~09:10)**: hotfix 배포가 13:22 KST → 09:10 이후 적용 → 미반영 시간대
2. **afternoon_lockout (14:30+)**: TradingEngine `engine_block reason=eod_blocked` 가드가 strategy 호출보다 *먼저* 동작 → `should_block_entry` 미도달 → 카운터 영영 0
3. 코드 자체는 pytest 4 PASS로 정상

**첫 정식 검증 시점**: 5/11(월) 09:05~09:10 morning_lockout 발동 시

### Sprint 3 핵심 기능
- `volume_surge` tier: dry_run 신호 0건 (활성 시간 09:30~14:00 내 후보 0)
- 시간 필터 본 가드: 호출 경로는 정상, 카운터는 EOD 가드와 중복으로 미발동 (afternoon)
- 우선순위 큐: 신호 자체가 없어 단일 신호 발행 검증 불가

## 신호 0건 근본 원인 (Railway 로그 분석)

### 14:30 이전 (signal_generator 동작)
모든 reject가 `volume_threshold` 단일 사유:
```
전략 거부 [volume_threshold]: 950160
  detail: volume_ratio=1.26, volume_threshold=2.0,
          breakout_pct=2.20, breakout_tier=prev_high
```
- `volume_ratio 1.26 vs 임계 2.0` — **1.6배 갭**
- 2차 스크리닝 통과 종목이 항상 1종 (코드 950160 — Kodex 200 ETF 추정)
- 체결강도 12~15 / 데이터없음 3~6 / 호가비율 1로 다른 종목 탈락

### 14:30 이후 (TradingEngine eod_blocked)
```
engine_block stock=- reason=eod_blocked
```
strategy 평가 자체 차단 → 시간 필터 도달 안 함

## 종합 판정

**5/8 1거래일 결과: G1 PASS / G2 FAIL / G3 INFO / 인프라 PASS**

5/7 CONDITIONAL GO 이후 5/8 추가 관찰에서 G1 안정성은 강화되었으나 G2 신호 부재가 누적. R1 발동 위험 임박 (5/11 1거래일 더 0건이면 자동 롤백).

**판정: CONDITIONAL — Sprint 4 즉시 착수 사유 추가 발생**

근본 원인이 Sprint 3 변경(volume_surge / 시간 필터 / 우선순위 큐)이 아니라 **2차 스크리닝 통과 종목 단일 + 거래량 임계 2.0의 시장 부적합**임이 확인됨. Sprint 3 핵심 안전장치(dry_run, R3, 우선순위 큐)는 모두 정상 동작 또는 검증 보류 상태.

## Sprint 4 권고 액션 (우선순위 순)

### P0 — R1 발동 회피 (5/11 이전 처리)
1. **2차 스크리닝 임계 완화**:
   - 현재: 체결강도 12~15 / 호가비율 1로 18~19종 탈락 → 1종 통과
   - 검토: 체결강도 임계 ↓, 호가비율 임계 ↓, 또는 1차 스크리닝 풀 확대
2. **volume_threshold 재검토**:
   - 현재 prev_high tier 임계 2.0
   - 5/8 측정 1.26 (1.6배 갭) — 시장 변동성 대비 과도하게 타이트
   - 검토: 1.5~1.6 또는 동적 산출

### P1 — Hotfix 운영 검증
3. **EOD 가드 vs 시간 필터 중복 차단 정리**:
   - afternoon_lockout 카운터는 사실상 무용
   - 시간 필터 본 가드의 운영 가치 재고 (morning_lockout만 의미 있음)
4. **5/11 morning_lockout 카운터 첫 정식 검증**:
   - hotfix `record_block` 적재 정상 동작 확인

### P2 — Sprint 3 잔존 부채
5. **R3 위험 모니터링**:
   - tier 다양성 1종(950160 단일) 5거래일 연속 시 R3 발동
   - 5/8 + 5/9(휴일) → 5/11 + 5/12 + 5/13 + 5/14 + 5/15 5거래일 누적 시 발동 가능

## 다음 액션

- **5/11(월)**: 추가 관찰 1거래일
  - G2 신호 ≥ 1건 발생 → R1 발동 회피 + Sprint 3 dry_run 정식 검증
  - G2 0건 → R1 자동 발동 (parallel_or_tier:rollback_active=True 자동 설정)
  - morning_lockout 카운터 첫 검증
- **Sprint 4 즉시 착수**: `/sprint-planner` 호출, P0 액션 우선
