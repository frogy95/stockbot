# 스크리닝 파이프라인

전 종목(~2,880개)에서 매매 후보를 좁혀가는 2단계 파이프라인.

## 전체 흐름

```
전 종목 (2,880개)
  ↓ [1차 스크리닝 — 장전 08:00]
후보 종목 (수십 개)
  ↓ [2차 스크리닝 — 장중 09:00~]
  ↓ [풀 협소 시 폴백 보강 (Phase 8.5 + Phase 8.6 Sprint 1)]
매매 신호 대상 (소수)
  ↓ [신호 생성]
TradeSignal → 주문 실행
```

## 1차 스크리닝 (장전)

`screening/screener.py` 구현.

**입력**: 공공데이터포털에서 수집한 전 종목 일봉 데이터 (DB 기반)

**필터 조건**:
- 최소 거래량: 전일 거래량 임계값 이상
- 변동성 범위: ATR 기반 적정 변동성 구간
- 시가총액 하한: 소형주 제외
- 상장 기간: 신규 상장 초기 제외
- 거래 정지/관리종목 제외

**출력**: 후보 종목 목록 (종목코드, 스코어) → DB 저장

[[screening-factors]], [[scoring-system]] 참조.

## 2차 스크리닝 (장중)

`screening/realtime_screener.py` 구현.

**입력**: 1차 통과 종목의 실시간 시세/체결 데이터 (Redis 기반)

**필터 조건** (동적):
- 실시간 거래량 조건: 전일 대비 시간가중 보정
- 체결강도: [[websocket-management|WebSocket]] 수신 체결강도 임계값
- 호가 잔량: 매수/매도 불균형 감지
- 돌파 조건: [[momentum-breakout-strategy|전일/당일 고가 돌파]]

**출력**: `screened_candidates` 리스트 → [[signal-generation]]에 전달

### 풀 하한 폴백 (Phase 8.5 + Phase 8.6 Sprint 1)

2차 통과 종목 수가 임계 미만일 때 `_apply_fallback`이 폴백 풀에서 보강:

| env | 기본값 | 비고 |
|-----|--------|------|
| `SECONDARY_POOL_FALLBACK_THRESHOLD` | `5` | 임계 (v2.6.1 3 → 5, 분기 D 풀 협소 대응) |
| `SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP` | `5` | 보강 종목 수 상한 |

폴백 보강 종목은 `is_fallback=true` 메타데이터를 신호 → 주문 → 체결 → DB(`signals.fallback`, `orders.fallback`)까지 전파한다 (Phase 8.6 Sprint 1 G1). 폴백 종목은 ATR 동적 상한 미적용, `ATR_CEIL_FALLBACK=0.05` 고정.

### `min_volume_floor` 시간대 슬라이딩 (Phase 8.6 Sprint 1)

`momentum_breakout._resolve_min_volume_floor`에서 시간대 분기:

| 시간대 | floor |
|-------|-------|
| 09:00 ~ 11:00 | **0.3** |
| 그 외 | 0.5 (strong=False) / 0.4 (strong=True) / 0.6 (전일 거래량 부진) |

HARD floor 0.3 적용 직전에 슬라이딩이 우선 적용된다.

## ATR 동적 캘리브레이션 (Phase 8.6 Sprint 2)

`screening/atr_calibration.py` 모듈이 매일 08:35 KOSPI200 ATR 분위수를 산출하여 신호 생성에 사용할 동적 상한을 Redis에 저장한다. 상세: [[tier-architecture#atr-동적-캘리브레이션]].

## ETF 처리

공공데이터포털 API가 ETF를 미포함. ETF 스크리닝은 별도 소스에서 수집 필요. 현재는 일반 주식 위주로 동작.

KOSPI/KOSDAQ 인버스, 레버리지 ETF는 PRD 범위에 포함되나 구현은 확장 예정.

## 스크리닝 결과 저장

- 1차 결과: `screening_candidates` 테이블 — [[database-schema]]
- 2차 결과: 직접 신호 생성으로 전달 (Redis 경유)

## 종목 후보 수 관리

- 목표: 1차 통과 수십 개, 2차 통과 소수
- 너무 많으면 장중 REST API Rate Limit 초과 위험
- 너무 적으면 매매 기회 부족 → 폴백 보강 발동
