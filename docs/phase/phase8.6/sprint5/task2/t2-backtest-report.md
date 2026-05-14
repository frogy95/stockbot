# T2 Step 1 — #10 breakout 72.2% 편중 walk-forward 진단 보고서

> Sprint 4 walkforward 인프라(`backend/modules/backtest/walkforward.py`)를 재활용한 60거래일 진단.
> 신규 백테스트 코드 작성 없음 — `WalkForwardRunner.run` + `simulate_tier_pass_rate` 호출만.

## 데이터셋 진단

- 요청: `period_end=2026-05-15, n_days=60`
- 보유: KOSPI200 일봉(`data_go_kr`/`kis_daily`) 21거래일 (2026-03-26 ~ 2026-05-12)
- 충족 요구: 60거래일 (`is_dataset_sufficient`: box≥20 AND trend≥20 AND total≥60)

## 정식 WalkForwardRunner.run — 실패

60거래일 + box≥20 + trend≥20 데이터 부족으로 `WalkForwardRunner._fail` 분기로 처리됨 (`DatasetInsufficientError` 메시지를 `BacktestRun.error`에 저장).

```
데이터셋 미충족: box=21, trend=0, total=21 (요구: box≥20, trend≥20, total≥60)
```

- 보유 21일 중 trend=0 (KOSPI200이 박스권 시기) → `trend≥20` 게이트 미통과
- box는 21 ≥ 20 충족, total 21 < 60 미통과
- → 정식 60일 walkforward 진행 불가, partial 진단(아래)으로 대체

## Partial 진단 (보유 일수 기준)

- 사용 일수: 21거래일 (요청 60일 중 보유분)
- regime 분류: box=21일 / trend=0일 / sigma_long_term=2.4722

### tier별 reject_rate 분포 (시뮬, 단순 모델)

| tier | reject_all | reject_box | reject_trend | pass_simulated | pass_actual_db |
|------|-----------:|-----------:|-------------:|---------------:|---------------:|
| gap_open | 0.7619 | 0.7619 | n/a | 0.2381 | 0.0000 |
| prev_high | 0.9048 | 0.9048 | n/a | 0.0952 | 0.0000 |
| prev_close | 0.7143 | 0.7143 | n/a | 0.2857 | 0.0000 |
| volume_surge | 0.2857 | 0.2857 | n/a | 0.7143 | 0.0000 |

## #10 결론 (정량 판정)

> 임계 변경 0건. raw 산출만 제공하고 후속 Task 5에서 통합 판정.

### 본질 결함 vs 자연 분포 — **판정 불가**

- **정식 60일 walkforward 미수행** — 로컬 KIS 일봉 캐시 21거래일(< 60일 요구) + trend=0일 (< 20일 요구). #10의 '자연 분포 vs 구조 결함' 정량 판정 **불가**.
- Partial 21일 시뮬 reject 분포는 KOSPI200 박스권 시기 일별 평균 등락률 기반 단순 모델 결과로 prod momentum_breakout/volume_surge 진입과 직접 대응하지 않음 (`walkforward.py:5` docstring 명시 한계).
- 본 인프라가 산출하는 tier는 4종(`gap_open` / `prev_high` / `prev_close` / `volume_surge`)이며, '72.2% breakout 편중' 주장의 'breakout'은 prod `trade_signals.strategy_name` 분류(`momentum_breakout` 전략 1건 → matched_tiers 다수)와 다른 분류 체계. **개념 매핑 미정의** — 사용자/검토자가 '편중'의 정의를 다시 명세할 필요.

### Partial 시뮬에서 관찰된 분포 (단순 모델, 박스권 21일)

- **prev_high reject 0.90 (최고) → volume_surge reject 0.29 (최저)** — 즉 단순 모델 시뮬에선 volume_surge가 가장 자주 통과. 이는 박스권에서 |pct| 작은 일이 많아 prev_high(2σ) 임계 도달 빈도 낮고, volume_surge(price_threshold=0.5%) 임계가 가장 느슨해서 발생.
- prod 분포와 정반대일 가능성 — prod은 volume_surge dry_run + 임계 더 빡빡함. 본 시뮬 결과를 prod 편중 판정에 직접 적용 금지.

### actual_db 0 — 로컬 trade_signals 0건

`compute_actual_pass_rate`가 4 tier 모두 0.0 반환 — 로컬 stockbot DB에 trade_signals 행이 0건이라 정상 동작. prod에서 재실행 필요.

## 후속 액션 (Task 5 입력)

1. **KIS 일봉 백필** (Phase 9 Sprint 0 또는 별도 핫픽스): 90~120거래일 보강 → `WalkForwardRunner.run` 정상 동작.
2. **prod `trade_signals` 직접 집계**: `SELECT strategy_name, count(*) FROM trade_signals GROUP BY 1 WHERE created_at > now() - interval '14 days'` 로 실제 strategy 분포 측정 — '72.2% breakout' 출처 재확인.
3. **분봉 백필 후 정밀 시뮬 교체**: walkforward.py docstring(Phase 9 Sprint 0) 계획 그대로 진행.

## 검증 명령 재현

```bash
docker compose exec backend python -m scripts.diagnostic.run_stage_reject_breakdown \
  --days 60 --output docs/phase/phase8.6/sprint5/task2/t2-backtest-report.md
```

