# 데이터베이스 스키마

PostgreSQL 16 기반. `backend/core/models/` 하위에 SQLAlchemy 모델 정의.

## 주요 테이블

### market_data (시장 데이터)

장전 수집된 일봉 데이터:

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BIGSERIAL | PK |
| `stock_code` | VARCHAR | 종목 코드 |
| `stock_name` | VARCHAR | 종목명 |
| `date` | DATE | 기준일 |
| `open` | INTEGER | 시가 |
| `high` | INTEGER | 고가 |
| `low` | INTEGER | 저가 |
| `close` | INTEGER | 종가 |
| `volume` | BIGINT | 거래량 |
| `market_cap` | BIGINT | 시가총액 |
| `listed_shares` | BIGINT | 상장주식수 |

### screening_candidates (스크리닝 후보)

1차 스크리닝 통과 종목:

| 컬럼 | 설명 |
|------|------|
| `stock_code` | 종목 코드 |
| `date` | 스크리닝 날짜 |
| `score` | 종합 스코어 |
| `factor_scores` | JSONB — 팩터별 점수 |

### trade_signals (매매 신호)

[[signal-generation|신호 생성기]]가 생성한 신호:

| 컬럼 | 설명 |
|------|------|
| `id` | PK |
| `stock_code` | 종목 코드 |
| `signal_type` | `buy` / `sell` |
| `confidence` | 신뢰도 (0.0~1.0) |
| `strategy_name` | 전략 이름 |
| `reason` | JSONB — 신호 근거 |
| `matched_tiers` | JSON list[str] — 병렬 OR 통과 tier (Phase 8.6 Sprint 2). 토글 OFF 시 NULL |
| `fallback` | BOOLEAN — 폴백 풀에서 보강된 종목 여부 (Phase 8.6 Sprint 1) |
| `status` | `pending` / `approved` / `rejected` / `executed` |
| `suggested_price` | 제안 진입가 |
| `created_at` | 생성 시각 |

### position_records (포지션)

현재 보유 포지션:

| 컬럼 | 설명 |
|------|------|
| `id` | PK |
| `stock_code` | 종목 코드 |
| `entry_price` | 평균 매수가 |
| `quantity` | 보유 수량 |
| `current_price` | 현재가 (갱신됨) |
| `unrealized_pnl` | 미실현 손익 |
| `status` | `open` / `closed` |

### trade_history (거래 내역)

청산된 거래 기록:

| 컬럼 | 설명 |
|------|------|
| `realized_pnl` | 실현 손익 |
| `return_pct` | 수익률 (%) |
| `strategy_name` | 사용된 전략 |

### stocks (종목 마스터)

| 컬럼 | 설명 |
|------|------|
| `stock_code` | 종목 코드 (PK) |
| `stock_name` | 종목명 |
| `is_kospi200` | BOOLEAN — KOSPI200 편입 여부 (Phase 8.6 Sprint 2 — ATR 캘리브레이션 모집단). 정적 백업: `data/kospi200_static_backup.json` |

### orders (주문)

| 컬럼 | 설명 |
|------|------|
| `fallback` | BOOLEAN — 폴백 풀에서 보강된 종목 신호 기반 주문 여부 (Phase 8.6 Sprint 1, 일별 폴백 신호율 산출용) |

### daily_screening_metrics (일별 스크리닝 메트릭)

| 컬럼 | 설명 |
|------|------|
| `date` | 기준일 |
| `fallback_signal_rate` | FLOAT — 일별 폴백 신호 비율 (M-F2, Phase 8.6 Sprint 1) |
| `tier_pass_rates` | JSONB — tier별 일별 통과율 (Phase 8.6 Sprint 2) |

### settings (시스템 설정)

| 컬럼 | 설명 |
|------|------|
| `key` | 설정 키 |
| `value` | 설정 값 (TEXT) |
| `description` | 설명 |

리스크 파라미터([[risk-management]]), 스코어링 가중치([[scoring-system]]) 등 저장.

## 인덱스 전략

- `market_data`: `(stock_code, date)` UNIQUE
- `trade_signals`: `(stock_code, status)` — pending 신호 중복 체크용
- `position_records`: `(stock_code, status)` — 오픈 포지션 조회용

## 마이그레이션

Alembic으로 관리. `backend/alembic/versions/` 참조.
