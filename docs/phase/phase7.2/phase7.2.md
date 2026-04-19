# Phase 7.2: 매매 전략 진입 조건 개선 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-17)
> **ROADMAP 참조**: `ROADMAP.md` Phase 7.2
> **검토 리포트**:
>
> - `phase7.2-po-review.md` (정프로, PO)
> - `phase7.2-risk-review.md` (최리스크, 리스크관리)
> - `phase7.2-daytrader-review.md` (김단타, 단타 전문가)
> - `phase7.2-quant-review.md` (박퀀트, 퀀트 전문가)

---

## 개요

2026-04-17 LIVE 모니터링에서 발견된 **매매 신호 0건 문제**의 근본 원인을 해결하고, 전략의 진입 조건을 개선하는 Phase.

### 문제 진단

```
[문제 1] 장중 OHLC 데이터 미파싱 (인프라 결함)
  KIS H0STCNT0 WS 데이터에 STCK_OPRC(시가, idx 7), STCK_HGPR(고가, idx 8),
  STCK_LWPR(저가, idx 9) 필드가 포함되어 있으나 kis_realtime.py에서 파싱하지 않음.
  → signal_generator.py에서 open_price=prev_close, high/low=current_price로 폴백
  → gap_rate 항상 ~0 → breakout_ref 항상 prev_high
  → 갭 3%+ 분기 사실상 사문화 + 해당 분기에 자기자신 돌파(current_price<=current_price) 버그

[문제 2] 전일 고가 돌파 단일 진입 조건의 과도한 보수성 (전략 설계)
  2026-04-17 실측:
  - 059090: 현재가 20,350 / 전일고가 20,900 (550원 아래)
  - 052400: 현재가 69,300 / 전일고가 71,400 (2,100원 아래)
  → 2차 스크리닝 통과 종목이 매 30초 발생하지만 전략 단계에서 전부 탈락
  → 횡보/소폭 상승 장세에서 매매 신호 생성 불가
```

### 개선 파이프라인

```
[AS-IS]
WS 체결 → Redis(price/volume/CTTR만 저장) → snapshot(open=prev_close, high=low=current)
  → 전략: breakout_ref = prev_high → 돌파 실패 → 신호 0건

[TO-BE: Sprint 1 — 데이터 인프라 수정]
WS 체결 → Redis(price/volume/CTTR + 시가/고가/저가 저장) → snapshot(정확한 OHLC)
  → gap_rate 정상 계산 → 갭 분기 정상 동작

[TO-BE: Sprint 2 — 다층 진입 조건]
전략: 3단계 기준점
  ① 갭 3%+ → breakout_ref = open_price (갭 지지 확인)
  ② 비갭 prev_close 돌파 → 탐색적 진입 (낮은 confidence, 반 포지션)
  ③ 비갭 prev_high 돌파 → 확신 진입 (높은 confidence, 전체 포지션)
```

---

## 검토팀 확정 파라미터 (2026-04-17)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 김단타(단타), 박퀀트(퀀트) — 4명

### Sprint 1: 데이터 인프라 수정

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | H0STCNT0 파싱 필드 | price/volume/CTTR 등 8필드 | + STCK_OPRC(idx 7), STCK_HGPR(idx 8), STCK_LWPR(idx 9) 3필드 추가 | 전원 동의: KIS 공식 스펙에 이미 포함 |
| 2 | Redis 캐싱 키 | `realtime:{code}:execution` | 기존 JSON에 `open_price`, `high`, `low` 3필드 추가 | 윈에이피 패턴 유지 |
| 3 | snapshot 조립 | open_price=prev_close, high/low=current_price 폴백 | Redis 실시간 값 우선, 미수신 시에만 폴백 유지 | 전원 동의 |
| 4 | 갭 3%+ 분기 버그 | breakout_ref = snapshot.high (= current_price → 자기돌파 항상 False) | breakout_ref = snapshot.open_price (갭 지지 확인) | 김단타+최리스크: 갭 상승 후 시가 위 유지가 더 안전 |

### Sprint 2: 다층 진입 조건

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 5 | 진입 기준 | prev_high 단일 | prev_close(1단계) + prev_high(2단계) 다층 | 전원 합의: 실전 단타 표준 패턴 |
| 6 | prev_close 돌파 confidence 상한 | 없음 | 0.75 | 최리스크: prev_high 미돌파 상태에서 과도한 신뢰도 방지 |
| 7 | prev_close 돌파 momentum_score 스케일 | min(pct/5.0, 1.0) | min(pct/7.0, 1.0) * 0.7 | 박퀀트: 낮은 기준점 = 더 큰 돌파폭 요구 + 상한 제한 |
| 8 | prev_close 돌파 volume_threshold | breakout_pct 연동 (1.5~2.0) | 고정 2.5 (breakout_pct 연동 해제) | 박퀀트+김단타: 기준점 변경 시 breakout_pct 왜곡 방지 |
| 9 | prev_close 돌파 position_size | 100% (일반) | 50% (반 포지션) | 최리스크: 낮은 기준점 진입 시 리스크 반감 |
| 10 | 갭 돌파 momentum_score 상한 | 1.0 | 0.85 | 박퀀트: 갭 지지 확인이므로 prev_close보다 높게 |
| 11 | 일일 최대 거래 횟수 | 없음 | 10건/일 | 최리스크: 신호 증가 시 과도 매매 방지 |
| 12 | 13:00 이후 prev_close 돌파 | 허용 | 비활성화 (prev_high만 허용) | 김단타: 당일 청산(14:50)까지 시간 부족 |
| 13 | 당일 고가 갱신 진입 | — | Phase 7.2에서 미도입 | 김단타+최리스크: 추격매수 위험, 백테스트 후 도입 |
| 14 | Sprint 1→2 간 관찰 기간 | 없음 | 최소 2거래일 | 정프로+김단타: OHLC 수정만으로 신호 패턴 변화 관찰 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 | 장중 OHLC 데이터 파싱 수정 + 갭 분기 버그 수정 | H0STCNT0 파서 확장, Redis 캐싱 확장, snapshot 조립 수정, 갭 분기 로직 수정 | 없음 |
| 2 | 다층 진입 조건 + 리스크 안전장치 | prev_close 돌파 진입 추가, confidence 계층화, 반 포지션, 일일 거래 한도, 시간대 제한 | Sprint 1 + 2거래일 관찰 |

---

## Sprint 1 상세 — 장중 OHLC 데이터 파싱 수정

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/collector/sources/kis_realtime.py` | `EXECUTION_FIELD_MAP`에 `open_price: 7`, `high: 8`, `low: 9` 추가. `ExecutionData` dataclass에 `open_price: int`, `high: int`, `low: int` 필드 추가. `parse_execution()` 파싱 로직 확장 |
| `backend/modules/collector/scheduler.py` | WS 메시지 Redis 캐싱 시 `open_price`, `high`, `low` 3필드 추가 저장 |
| `backend/modules/screening/realtime_screener.py` | `_get_realtime_data()` 반환 dict에 `open_price`, `high`, `low` 포함. 2차 스크리닝 candidate dict에 전달 |
| `backend/modules/trading/signal_generator.py` | `_build_snapshot()`: Redis 실시간 `open_price`/`high`/`low` 우선 사용, 미수신 시에만 기존 폴백 유지. 주석 "KIS 체결 데이터에 intraday open/high/low 없음" 삭제 |
| `backend/modules/trading/strategies/momentum_breakout.py` | 갭 3%+ 분기: `breakout_ref = snapshot.high` → `breakout_ref = snapshot.open_price` 변경 |
| `backend/tests/` | kis_realtime 파서 테스트 확장 (3필드 파싱 검증), signal_generator snapshot 조립 테스트, momentum_breakout 갭 분기 테스트 |

### 프론트엔드

| 파일 | 수정 내용 |
|------|----------|
| 없음 | Sprint 1은 백엔드 전용 |

### 재사용 자산

| 기존 모듈 | 재활용 내용 |
|----------|------------|
| `backend/modules/collector/sources/kis_realtime.py` | 기존 EXECUTION_FIELD_MAP 패턴, parse_execution 구조 그대로 확장 |
| `backend/modules/collector/scheduler.py` | 기존 Redis 캐싱 JSON 구조에 필드만 추가 |
| `backend/core/clients/kis_rest.py` | StockPrice.open_price/high/low 이미 REST에서 파싱 — 동일 필드명 통일 |

---

## Sprint 2 상세 — 다층 진입 조건 + 리스크 안전장치

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/trading/strategies/momentum_breakout.py` | 3단계 기준점 로직: (1) 갭 3%+ → open_price, (2) 비갭 prev_close 돌파 → 탐색적 진입, (3) 비갭 prev_high 돌파 → 확신 진입. breakout_tier 변수 도입. prev_close 돌파 시 momentum_score 스케일 변경(min(pct/7.0,1.0)*0.7), confidence 상한 0.75 적용. prev_close 돌파 시 volume_threshold 고정 2.5. reason dict에 `breakout_tier` 추가 |
| `backend/modules/trading/strategies/momentum_breakout.py` | 13:00 이후 prev_close 돌파 비활성화 (시간 가드 추가) |
| `backend/modules/trading/strategies/momentum_breakout.py` | TradeSignalData.reason에 `breakout_tier: "prev_close" | "prev_high" | "gap_open"` 추가 |
| `backend/modules/trading/position_sizer.py` | `breakout_tier == "prev_close"` 시 position_size 50% 적용 (signal.reason에서 tier 참조) |
| `backend/modules/trading/risk_manager.py` | `daily_trade_count` 카운터 추가, 10건/일 초과 시 신규 진입 차단. `reset_daily_counters()`에 초기화 추가 |
| `backend/modules/trading/engine.py` | 주문 제출 전 `check_daily_trade_limit()` 호출 추가 |
| `backend/tests/` | 다층 진입 조건 테스트 (prev_close/prev_high/gap 각 분기), confidence 상한 테스트, 반 포지션 테스트, 일일 거래 한도 테스트, 13:00 시간 가드 테스트 |

### 프론트엔드

| 파일 | 수정 내용 |
|------|----------|
| 없음 | Sprint 2도 백엔드 전용. 대시보드 신호 페이지에 breakout_tier가 reason에 포함되어 자동 표시 |

### 재사용 자산

| 기존 모듈 | 재활용 내용 |
|----------|------------|
| `backend/modules/trading/strategies/momentum_breakout.py` | 기존 confidence 프레임워크 (4팩터 가중 평균) 구조 유지, momentum_score 스케일만 변경 |
| `backend/modules/trading/position_sizer.py` | 기존 `calc_quantity()` 로직에 tier 기반 size 조정만 추가 |
| `backend/modules/trading/risk_manager.py` | 기존 `daily_loss_count`, `consecutive_losses` 패턴과 동일하게 `daily_trade_count` 추가 |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 담당 | 배치 |
|---|------|--------|------|------|
| 1 | Sprint 1 OHLC 수정만으로 신호 발생 가능성 | 정보 | 김단타 | Sprint 1 배포 후 2거래일 관찰. 신호 빈도/품질에 따라 Sprint 2 범위 조정 가능 |
| 2 | prev_close 돌파 후 prev_high 저항에서 반락 | ⚠️ | 최리스크 | 반 포지션(50%) + confidence 상한(0.75)으로 리스크 제한. prev_high 돌파 시 추가 매수는 후속 Phase에서 검토 |
| 3 | 10:30~13:00 횡보 구간 false positive | ⚠️ | 김단타 | prev_close 돌파 volume_threshold 2.5 (고정)로 대응. 관찰 후 추가 상향 가능 |
| 4 | breakout_pct 계산 기준 | ⚠️ | 박퀀트 | prev_close 돌파 시 volume_threshold를 breakout_pct 연동에서 고정값(2.5)으로 분리하여 해결 |
| 5 | 당일 고가 갱신 진입 | 정보 | 김단타+최리스크 | Phase 7.2 범위 외. 백테스트 인프라 구축(Phase 9) 후 도입 검토 |
| 6 | 2차 스크리닝 N=1 상대 백분위 문제 | 정보 | 박퀀트 | Phase 7.0 미해결 #10. 신호 증가 시 자연 완화 기대, 근본 해결은 별도 Phase |
| 7 | Phase 7.0 Sprint 3 (E2E 검증) 선후관계 | ⚠️ | 정프로 | Phase 7.2 Sprint 1은 Phase 7.0 Sprint 3의 "신호 생성 1건+" 조건 충족에 필수. Sprint 1 먼저 완료 후 Phase 7.0 Sprint 3 재개 |

---

## Phase 7.0 Sprint 3과의 관계

Phase 7.0 Sprint 3 "E2E 검증 + LIVE 전환 게이트"의 성공 기준 중 "신호 생성 1건+"은 현재 전략이 매매 신호를 생성하지 못하는 상태에서 달성 불가능하다.

```
실행 순서:
Phase 7.2 Sprint 1 (OHLC 수정) → 2거래일 관찰
  → Phase 7.2 Sprint 2 (다층 진입) — 필요 시
  → Phase 7.0 Sprint 3 (E2E 검증) 재개
```

Phase 7.2 Sprint 1 완료 후 실제 신호가 발생하면, Phase 7.0 Sprint 3의 E2E 검증을 바로 시작할 수 있다. Sprint 2는 Sprint 1만으로 신호 품질이 부족한 경우에 진행한다.

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| H0STCNT0 OHLC 파싱 | Redis에 시가/고가/저가 정상 저장 확인 | ⬜ |
| snapshot 정합성 | open_price/high/low가 실시간 값으로 조립 확인 | ⬜ |
| 갭 분기 정상 동작 | 갭 3%+ 종목에서 open_price 기준 돌파 판정 | ⬜ |
| 매매 신호 생성 | 장중 1건 이상 신호 발생 (2거래일 연속) | ⬜ |
| 다층 진입 구현 | prev_close/prev_high 2단계 분기 동작 | ⬜ |
| confidence 계층화 | prev_close 돌파 시 confidence <= 0.75 확인 | ⬜ |
| 반 포지션 적용 | prev_close 돌파 시 position_size 50% 확인 | ⬜ |
| 일일 거래 한도 | 10건 초과 시 신규 진입 차단 확인 | ⬜ |
| 시간대 가드 | 13:00 이후 prev_close 돌파 비활성화 확인 | ⬜ |
| pytest 전체 통과 | 기존 + 신규 테스트 전체 통과 | ⬜ |
