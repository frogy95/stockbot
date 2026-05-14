# T2 Step 2 — #13 fallback 폭증 DB 측정 스냅샷

> Phase 8.6 Sprint 5 Task 2 Step 2 — Sprint 1 M-F2 인프라(`signals.fallback`, `orders.fallback`, `metrics:fallback:code:*`)를 활용해 fallback 신호율을 최근 7일 측정한다.
> **임계 변경 0건, 코드 변경 0건.**

## 데이터 소스

| 항목 | 위치 |
|------|------|
| 분자 (fallback=true 신호 수) | DB `trade_signals.fallback=TRUE` (Sprint 1 Task 3 도입) |
| 분모 (fallback 발동 종목 수) | Redis `metrics:fallback:code:*:{date}` (Sprint 1 M-F2 카운터) |
| 집계 endpoint | `GET /api/v1/metrics/fallback-signal-rate?date=YYYY-MM-DD` |
| 모델 정의 | `backend/core/models/trading.py:25` (`ix_trade_signals_fallback_created`), `:40` (`TradeSignal.fallback`), `:88` (`Order.fallback`) |

## 측정 — 프로덕션 endpoint 호출 (최근 7거래일)

**검증 명령:**
```bash
for d in 2026-05-14 2026-05-13 2026-05-12 2026-05-11 2026-05-08 2026-05-07 2026-05-06; do
  curl -s -H "Authorization: Bearer $TOKEN" "https://api.stockbot.choiji.kr/api/v1/metrics/fallback-signal-rate?date=$d"
done
```

**결과 (2026-05-15 02:46 KST 호출):**

| 날짜 (KST) | fallback_signals (분자) | fallback_triggered_codes (분모) | rate |
|------------|---------------------:|-----------------------------:|------|
| 2026-05-06 | 0 | 0 | null |
| 2026-05-07 | 0 | 0 | null |
| 2026-05-08 | 0 | 0 | null |
| 2026-05-11 | 0 | 0 | null |
| 2026-05-12 | 0 | 7 | 0.0 |
| 2026-05-13 | 0 | 5 | 0.0 |
| 2026-05-14 | 0 | 7 | 0.0 |

**7일 단순 평균 fallback_signals:** 0건
**7일 누적 fallback_triggered_codes:** 19
**7일 fallback_signals / triggered_codes:** 0 / 19 = **0.0**

## 판정

### 핵심 발견 — "fallback 폭증 456건" 주장과 raw 데이터 불일치

1. **`trade_signals.fallback=TRUE` 행은 최근 7거래일 0건**. Sprint 1 Task 3에서 도입한 `fallback` 컬럼은 정상적으로 존재하나, 어떤 trade_signal에도 fallback=true가 설정되지 않음.
2. **Redis 카운터(`fallback_triggered_codes`)는 정상 동작** — 5/12~14일 매일 5~7개 종목에서 fallback 트리거 발생. 즉 **fallback 발동 자체는 실제로 일어남**.
3. **격차의 의미**: fallback 발동(Redis) → trade_signal 생성(DB) 경로가 끊어져 있을 가능성. fallback 발동 시 별도 신호를 만들지 않고 폐기되거나, fallback 모드의 신호가 `fallback=true` 플래그 없이 저장되는 경로 결함 추정.

### E2 임계(§11.5, fallback 비중 ≤ 20%) 충족 여부

- 분자(fallback_signals) = 0, 분모(전체 신호) > 0 → **E2 임계 0% (≤ 20%) 충족**.
- 다만 이는 **fallback이 측정되지 않아서 발생하는 통과**임. fallback 발동이 실제로는 19건/7일 발생하므로 **계측 결함을 통한 가짜 통과** 가능성이 높음. E2 게이트를 신뢰 가능한 상태로 만들려면 fallback 신호의 trade_signal 저장 경로를 먼저 수정해야 함.

### "456건 폭증" 주장 출처 미확인

- 모니터링 보고서(2026-05-13/14 result.md)에 명시된 "fallback 456건"은 본 측정에서 0건. **모니터링 보고서가 다른 카운터를 인용했거나(예: Redis trigger 누적 vs DB 행 수), 측정 기준 윈도우/대상이 다름**. Task 5 종합 보고에서 출처 재확인 필요.

## 후속 액션 (Task 5 입력)

- [ ] **fallback 저장 경로 코드 추적**: secondary 폴백 발동 시 `signals.fallback=true`로 trade_signal을 저장하는 로직 라인 확인 (`backend/modules/screening/realtime_screener.py` + `backend/modules/trading/signal_engine.py` 추정).
- [ ] **"456건" 출처 재확인**: 5/13~14 모니터링 보고서에 인용된 fallback 수치가 어느 카운터인지 명시 요청 (Redis trigger 누적 vs trade_signal vs 별도 로그).
- [ ] **E2 측정 데이터 소스 확정** (Step 4 참조): fallback_signals 컬럼이 정상 채워지면 본 endpoint 그대로 7일 이동평균 사용 가능.

## 한계

- 로컬 stockbot DB는 `trade_signals.fallback=TRUE` 0건일 뿐 아니라 `trade_signals` 자체가 0건이라 로컬 검증 불가. 본 측정은 프로덕션 endpoint 결과만 의존.
- PnL 비교(폴백 종목 PnL vs 본 신호 PnL)는 prod `/api/v1/metrics/phase86-status` 추가 호출이 차단되어 본 스냅샷에서 산출 불가. Task 5에서 별도 수집.
- 폴백 종목 평균 보유 시간 또한 본 측정 범위 밖(positions/trade_history join 필요).

## 한계 보완을 위한 권고 (코드 변경 0건 유지)

- **임시 대응**: Railway CLI `railway run --service backend python -c "..."` 로 직접 SQL 실행하여 trade_signals의 fallback=true 행 누적 수를 prod에서 일일이 확인.
- **본질 대응**: Task 5 종합 보고에서 fallback 저장 경로 결함을 진단 항목으로 추가 — Sprint 6(또는 hotfix) 후보.
