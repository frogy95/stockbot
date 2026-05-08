# 매매 신호 생성

2차 스크리닝 통과 종목에 전략을 적용하여 `TradeSignal`을 생성. `trading/signal_generator.py` 구현.

## 생성 프로세스

```
screened_candidates (2차 스크리닝 결과)
  → 중복 신호 체크 (같은 종목 pending 신호 존재 시 스킵)
  → 안전모드 가드 (safe_mode:active 키 존재 시 발행 중단)
  → MarketSnapshot 조립 (DB + Redis 데이터)
  → 전략 적용 (strategy.generate_signal — 병렬 OR tier)
  → 신뢰도 필터 (MIN_CONFIDENCE = 0.6)
  → 일일 신호 한도 / 동시 보유 회로 체크
  → TradeSignal DB 저장 (matched_tiers, fallback 메타데이터 포함)
  → [[trading-modes|모드에 따라]] 승인 요청 또는 즉시 주문
```

## MarketSnapshot

전략에 입력되는 종목 상태 스냅샷:

| 필드 | 설명 |
|------|------|
| `stock_code` | 종목 코드 |
| `current_price` | 현재가 |
| `prev_close` | 전일 종가 |
| `prev_high` | 전일 고가 |
| `open_price` | 당일 시가 |
| `high` | 당일 고가 |
| `volume` | 당일 거래량 |
| `prev_volume` | 전일 거래량 |
| `trade_strength` | 체결강도 |
| `orderbook_ratio` | 호가잔량 비율 |
| `is_fallback` | 폴백 풀에서 보강된 종목 여부 (Phase 8.6 Sprint 1 — 신호/주문/체결까지 메타데이터 전파) |
| `now_kst` | 현재 시각 (시간대 슬라이딩 / 시간가드용) |

## 전략 인터페이스

```python
class Strategy(ABC):
    @property
    def name(self) -> str: ...

    async def generate_signal(
        self, snapshot: MarketSnapshot
    ) -> TradeSignalData | RejectedSignal:
        # 성공: TradeSignalData
        # 탈락: RejectedSignal(stage, detail) — 사유가 구조화되어 로그/알림에 활용
        ...
```

현재 구현: [[momentum-breakout-strategy]]. tier 결합 구조 상세는 [[tier-architecture]].

`RejectedSignal.stage`는 차단 지점을 식별한다 (`breakout`, `volume_threshold`, `trade_strength`, `atr_filter`, `confidence`, `prev_close_time_guard`, `temp_time_guard`, `safe_mode_active`, `quota_cap_blocked`, `fallback_atr_ceil` 등). engine은 구조화 로그로 기록하고 선택적으로 텔레그램 알림을 발송한다.

## TradeSignal 구조

| 필드 | 설명 |
|------|------|
| `stock_code` | 종목 코드 |
| `signal_type` | `buy` / `sell` |
| `confidence` | 신뢰도 (병렬 OR 통과 tier들의 평균) |
| `strategy_name` | 전략 이름 |
| `reason` | 신호 근거 (JSON) — `breakout_tier` 포함 |
| `matched_tiers` | 통과 tier list (JSON, Phase 8.6 Sprint 2 신규 컬럼). 토글 OFF 시 NULL |
| `fallback` | 폴백 풀에서 보강된 종목 여부 (BOOLEAN, Phase 8.6 Sprint 1) |
| `status` | `pending` / `approved` / `rejected` / `executed` |
| `suggested_price` | 제안 진입가 |

`matched_tiers`(예: `["gap_open"]`, `["prev_high","prev_close"]`)는 [[tier-architecture]] 병렬 OR 결과. `fallback`은 주문 → 체결 → DB까지 전파되어 일별 폴백 신호율(M-F2) 산출에 사용된다.

## 신뢰도 임계값

```python
MIN_CONFIDENCE = 0.6  # signal_generator.py
```

병렬 OR 통과 tier들의 confidence 평균이 0.6 미만이면 신호 생성 스킵.

## 중복 방지

같은 종목에 이미 `status=pending` 신호가 있으면 새 신호 생성 스킵.
진행 중인 포지션이 있는 종목도 신호 생성 제외 ([[risk-management]] 체크).

## 일일 신호 한도 / 동시 보유 회로

병렬 OR 직후에도 [[risk-management|일일 신호 한도 10건 + 동시 보유 2 포지션]]이 강제 적용된다 (`test_parallel_or_quota_cap`). 한도 도달 시 `quota_cap_blocked` 카운터 INCR.

## 안전모드 가드

ATR 캘리브레이션 폴백 3단(직전일 캐시 → HARD 정적 → 안전모드) 도달 시 `safe_mode:active` 키로 신호 발행이 `SAFE_MODE_TIMEOUT_MIN=120`분간 중단된다. 텔레그램 알림 발송. [[tier-architecture#폴백-3단]] 참조.

## 신호 이후 흐름

- 반자동: [[telegram-integration|텔레그램 승인 요청]] → 응답 대기
- 완전자동: 즉시 [[order-execution|주문 실행]]

체결 시 `signal.fallback` 메타데이터가 주문 → 체결 → `orders.fallback` DB 컬럼까지 전파되며, 일별 폴백 신호 비율은 `GET /api/v1/metrics/fallback-signal-rate` (M-F2 메트릭)로 노출된다.
