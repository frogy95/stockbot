# 임계 재조정 후보 리포트 (Sprint 4 → 후속 hotfix 입력)

## 진단 결론

데이터셋 부족 (18 거래일 < 60 거래일 요구)으로 grid search 미수행.

현재까지 관측 결과:
- virtual_signals: 2026-05-07 9건, 2026-04-28 58건 (비거래일 사이 편차 큼)
- strategy_metrics_daily (2026-05-07): prev_close_volume_confirm 누적 약 50+건 (10분 슬롯 합산)
- 시뮬 pass율: 데이터셋 부족으로 산출 불가 → 실측 대비 격차 미확인

결론: **데이터 보강 후 grid search 재실행 권고**. 현 관측값 기반 부분 권고만 제시.

---

## 현행 임계값 (기본값 기준, env 미설정)

| 임계 | 모듈 | 현 기본값 | 환경변수 |
|------|------|---------|---------|
| G-Bt1 gap threshold | live_gate.py | 0.10 (10%p) | — |
| G-Bt2 CI lower bound | live_gate.py | 1.0 | — |
| G-Bt3 daily mean | live_gate.py | 1.5 | — |
| G-Bt3 zero-day ratio | live_gate.py | 0.30 (30%) | — |
| G-Bt3 lookback days | live_gate.py | 5 | — |
| G-Bt2 lookback days | live_gate.py | 30 | — |
| KS rebuild threshold | distribution_check.py | 0.05 (p<0.05) | — |

---

## 재조정 후보 (관측 기반 부분 권고)

| 임계 | 현 값 | 관측 | 권고값 | 근거 |
|------|------|------|--------|------|
| G-Bt3 일평균 (daily mean) | 1.5건 | 5/7: 9건, 4/28: 58건 | **현 값 유지** | 현재 2거래일 표본 부족, 단 9건은 통과 가능. 5거래일 관측 후 재평가 |
| G-Bt3 lookback days | 5일 | 2거래일만 실적 있음 | **현 값 유지** | 5거래일 누적 후 판단 가능. 조기 조정은 데이터 부족 상태의 과적합 위험 |
| volume_threshold (screening) | 모델 기본값 | prev_close_volume_confirm 누적 50+건/일 | 데이터 보강 후 결정 | grid search 미수행 — 현재 판단 불가 |
| KS rebuild threshold | 0.05 | 인위 트리거 테스트: pvalue=2.2e-59 | **현 값 유지** | 검출력 충분, 조정 필요 없음 |

---

## 재조정 적용 방식 (데이터 보강 완료 후)

### 단계 1: 일봉 백필

```bash
# 로컬
docker compose exec backend python -c "
import asyncio
from datetime import date, timedelta
from core.database import get_session_factory
from modules.backtest.historical_loader import backfill_missing_daily
async def main():
    sf = get_session_factory()
    async with sf() as s:
        n = await backfill_missing_daily(s, date.today()-timedelta(days=90), date.today())
        print(f'backfilled: {n}')
asyncio.run(main())
"
```

또는 API 호출:
```bash
curl -X POST http://localhost:8000/api/v1/backtest/backfill-daily \
  -H "Authorization: Bearer <admin_token>"
```

### 단계 2: 60일 백테스트 + grid search 재실행

백필 완료 후 WalkForwardRunner.run(n_days=60) 재실행.
tier별 pass_rate simulated vs actual 격차 확인 → 임계 재조정 필요 시 판단.

### 단계 3: 후속 hotfix 분리

grid search 결과에서 조정이 필요한 임계가 확인되면:
- 후속 hotfix `volume-threshold-recalibration` 브랜치 생성
- Railway 환경변수 또는 코드 default 변경 명시
- 변경 후 Paper 관찰 재시작 (G-Bt3 측정값 갱신)

---

## 데이터 부족 시 백업 계획

1. **KIS 일봉 API 백필** (1순위): rate limit 주의 (일 500건 제한 → 60일 × 200종목 = 12,000건, 분산 호출 필요)
2. **Phase 9 Sprint 0 분봉 백필** (2순위): 분봉 백필 완료 후 정밀 시뮬 교체와 동시 진행

---

## LIVE 토글 해제 로드맵

```
데이터 백필 완료 (60거래일)
  → 60일 백테스트 실행 (WalkForwardRunner)
  → G-Bt1 판정 (proxy simulated vs actual ≤ 10%p)
  → G-Bt2 판정 (Bootstrap CI 하한 ≥ 1.0)
  → Paper 5거래일 관찰 (G-Bt3: 일평균 ≥ 1.5, 0건 비율 ≤ 30%)
  → 3종 게이트 all_passed=True → LIVE 토글 해제
```

현재 상태: G-Bt1/G-Bt2 데이터 부족, G-Bt3 관찰 2거래일 진행 중.
예상 LIVE 토글 가능 시점: 60일 일봉 백필 완료 + Paper 5거래일 추가 관찰 후.
