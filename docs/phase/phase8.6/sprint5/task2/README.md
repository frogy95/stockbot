# Phase 8.6 Sprint 5 — Task 2 (T2) 산출물 인덱스

> **목표:** 코드 변경 최소, Sprint 4 walkforward 인프라 + Sprint 1 M-F2 DB 컬럼 재활용으로 #10/#13/#14 본질 결함 정량 판정. 임계 변경 0건.
> **실행 일자:** 2026-05-15 (Sprint 5 Task 2)
> **브랜치:** `phase8.6-sprint5`
> **선행 의존:** Sprint 4 walkforward (`backend/modules/backtest/walkforward.py`) + Sprint 1 Task 3 fallback 컬럼.

## 산출물

| 파일 | 대상 결함 | 결론 요약 |
|------|-----------|-----------|
| `t2-backtest-report.md` | #10 breakout 72.2% 편중 | **판정 불가** — KIS 일봉 캐시 21일/60일, prod 재실행 필요. partial 시뮬 결과 첨부. |
| `t2-fallback-db-snapshot.md` | #13 fallback 폭증 (456건 주장) | **fallback_signals=0 (7일)** — 폭증 주장 raw 미재현, fallback 발동 19건은 정상 카운트. trade_signal 저장 경로 결함 추정. E2 임계(≤ 20%) 충족(가짜 통과). |
| `t2-secondary-churn-db-snapshot.md` | #14 secondary 4h 100% 교체율 | **부분 재현, 일별 변동 0~71%** — 측정 1(점검시각 4h 비교)에서 churn 1.0 다수, 측정 2(13:30 분할)에서 평균 0.41. hysteresis 부재 가설 강한 지지지만 단정 불가. |

## E2 측정 데이터 소스 확정 (DoD S5-6 일부)

§11.5 entry gate E2(fallback 신호 비중 ≤ 20%) **측정 데이터 소스 = M-F2 인프라 재사용**:

- **분자**: `trade_signals.fallback=TRUE` 카운트 (Sprint 1 Task 3 컬럼)
- **분모**: Redis `metrics:fallback:code:*:{date}` 카운트 (Sprint 1 M-F2 카운터)
- **endpoint**: `GET /api/v1/metrics/fallback-signal-rate?date=YYYY-MM-DD` (이미 구현됨, `backend/api/routes/metrics.py:354`)
- **대시보드**: Sprint 1 Task 3 카드 `fallback-signal-rate-card.tsx` 그대로 재사용 — 신규 카드 작성 없음
- **이동평균 산식**: 7일 단순 평균 (현재 7일 rate=null/0.0 분포로 임계 미달 추세, 단 fallback_signals=0 자체가 측정 결함일 가능성 → Task 5에서 재검증)

## 코드 변경 / 회귀

- 신규 진단 스크립트 2종 (`backend/scripts/diagnostic/run_stage_reject_breakdown.py`, `secondary_churn.py`).
- 기존 코드 / 임계 / 환경변수 변경 **0건**.
- `pytest tests/test_screener.py tests/safety/` 회귀 검증은 본 README 하단 참조.

## 후속 Task 5(종합 보고)에 영향 줄 결정사항

1. **#10 판정 불가** → KIS 일봉 백필을 Sprint 6 또는 별도 핫픽스로 분리 결정 필요.
2. **#13 fallback 저장 경로 결함 의심** → secondary 폴백 발동 코드(`backend/modules/screening/realtime_screener.py`)에서 `trade_signal.fallback=True` 저장 누락 가능성 — Sprint 6 또는 hotfix 후보.
3. **"456건"·"72.2%"·"4h 100%" 모니터링 수치 출처 재확인 필요** — 본 측정과 raw에서 일치하지 않음. Task 5 종합 보고에서 모니터링 카운터 vs DB 컬럼 매핑 명세.
