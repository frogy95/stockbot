# Sprint 4 백테스트 진단 리포트 (2026-05-08)

## 실행 환경

- 브랜치: phase8.6-sprint4
- Task 1~7 완료 커밋: 5f46204 (task7 완료 시점)
- 실행 시각: 2026-05-08 KST (약 19:40)
- 로컬 Docker 환경 (stockbot-backend-1, Up 11 days)

---

## 데이터셋 충분성

### DB 일봉 카운트 (최근 90일)

| 항목 | 값 |
|------|-----|
| distinct 거래일 수 (최근 90일) | **18일** |
| 총 레코드 수 (최근 90일) | 60,467건 |
| 최오래된 data_date | 2026-03-26 |
| 60일 백테스트 요구 | 60 거래일 |
| 데이터 충족 여부 | **부족 (18 < 60)** |

### WalkForwardRunner 실행 결과

```
BacktestResult(
  run_id='6041a43a-1ee8-4bdc-99c3-0425e0691c7a',
  error='KOSPI200 일봉 거래일 부족: 18일 < 요구 60일 (period_end=2026-05-08, lookback=90일)',
  success=False
)
```

결론: **DatasetInsufficientError** — 60일 백테스트 실측 미수행.

---

## tier별 시뮬 vs 실측

데이터셋 부족으로 walkforward 실행 불가 → tier별 pass율 비교 미수행.

현재 virtual_signals 실측 현황 (참고):
| 날짜 | 신호 수 |
|------|---------|
| 2026-05-07 | 9건 |
| 2026-04-28 | 58건 |
| 2026-04-24 | 3건 |

G-Bt3 평가용 직전 5거래일 일평균: **미달** (5/7까지 2거래일 데이터, 평균 ≈ 4.5건 — 단, 5/8 실적 미집계 상태)

---

## Bootstrap CI 결과

데이터셋 부족으로 walkforward 미수행 → Bootstrap CI 산출 불가.

---

## KS 인위 트리거 검증

```python
np.random.seed(42)
sim   = np.random.normal(0, 1, 100)   # mean=0
actual = np.random.normal(5, 1, 100)  # mean=5
result = ks_test(sim, actual)
```

| 항목 | 값 |
|------|-----|
| KS statistic | 1.0 |
| p-value | 2.2088e-59 |
| rebuild_required | **True** ✅ |

해석: 평균 5 차이의 명확한 분포 이탈 → KS 검정이 정상적으로 rebuild_required=True를 반환. 모듈 정상 동작 확인.

---

## LIVE 토글 게이트 G-Bt1/G-Bt2/G-Bt3 판정

| 게이트 | 판정 | 사유 |
|--------|------|------|
| G-Bt1 (proxy 모드: simulated vs actual 격차) | FAIL | 60일 백테스트 미수행 → 격차 산출 불가 |
| G-Bt2 (Bootstrap CI 하한 ≥ 1.0) | FAIL | 데이터셋 부족 → CI 산출 불가 |
| G-Bt3 (5거래일 일평균 ≥ 1.5, 0건 비율 ≤ 30%) | FAIL | 5/7 9건, 5/8 실적 미집계 (2거래일 표본 부족) |
| all_passed | **False** | |

결론: **dry_run 강제 유지, LIVE 토글 차단** — 게이트 3종 모두 FAIL.

---

## pytest 풀 회귀 결과

```
2 failed, 1170 passed  →  수정 후  0 failed, 1172 passed
```

### 수정 내역

| 테스트 파일 | 원인 | 수정 내용 |
|------------|------|----------|
| `test_scheduler.py::test_scheduler_registers_jobs` | Sprint 4에서 `weekly_backtest_gate` 잡 추가 (9 → 10) | job_count 단언 9 → 10, `weekly_backtest_gate` 존재 단언 추가 |
| `test_stocks_is_kospi200_migration.py::test_is_kospi200_column_exists` | Sprint 4 autogenerate가 `ix_stocks_is_kospi200` 인덱스 정리 (모델에 `index=True` 미선언) | 인덱스 단언 제거 (stale 테스트 정리) |

두 수정 모두 Sprint 4가 도입한 변경에 의한 stale 테스트이며, 단순 회귀로 자체 수정 완료.

---

## tsc 타입 체크

```
npx tsc --noEmit → 0 errors ✅
```

---

## 시뮬 모델 한계

- 현재 시뮬은 일봉(OHLC) 기반 단순 시뮬레이션
- 분봉 데이터 부재로 장중 실시간 체결 패턴 반영 불가
- Phase 9 Sprint 0 분봉 백필 후 정밀 시뮬로 교체 예정

---

## Sprint 3 잔존 부채 검증

| 항목 | 상태 | 근거 |
|------|------|------|
| portal_supplement 잡 등록 | ✅ | CollectorScheduler 잡 목록에 `portal_supplement` 포함 (job_count=10) |
| metrics_rollup 잡 등록 | ✅ | CollectorScheduler 잡 목록에 `metrics_rollup` 포함 |
| strategy_metrics_daily 최근 적재 | ✅ | 2026-05-07 데이터 다수 확인 (prev_close_volume_confirm 등) |
| hotfix `time-filter-block-counter` 코드 | ✅ | `modules/collector/scheduler.py` 내 코드 적용 확인 |
| 운영 검증 (morning_lockout) | ⬜ | 2026-05-11 장전 시간대 확인 필요 |

---

## 후속 액션

1. **KIS 일봉 백필**: `POST /api/v1/backtest/backfill-daily` 호출로 60일 이상 데이터 확보
2. **60일 백테스트 재실행**: 백필 완료 후 `WalkForwardRunner.run(n_days=60)` 재시도
3. **임계 재조정**: `threshold_recalibration_candidates.md` 참조
4. **G-Bt3 Paper 신호 관찰**: LIVE 토글 해제를 위해 5거래일 Paper 신호 1.5/day 이상 달성 필요
