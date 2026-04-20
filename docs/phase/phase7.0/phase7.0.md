# Phase 7.0: 매매 엔진 치명적 결함 수정 + LIVE 전환 준비 — 실행 계획

> **Status**: Sprint 2 완료 (2026-04-16)
> **ROADMAP 참조**: `ROADMAP.md` Phase 7.0
> **검토 리포트**:
>
> - `phase7.0-po-review.md` (정프로, PO)
> - `phase7.0-risk-review.md` (최리스크, 리스크관리)
> - `phase7.0-daytrader-review.md` (김단타, 단타 전문가)
> - `phase7.0-api-review.md` (윤에이피, API 개발자)

---

## 개요

2026-04-15 phase-planner 평가에서 발견된 **매매 엔진 치명적 결함 3건**을 수정하고, 파라미터 오보정을 교정한 뒤, Paper 모드 E2E 검증을 통과하여 LIVE 전환 게이트를 열기 위한 긴급 Phase.

### 발견된 치명적 결함 (P0)

```
[결함 #1] 포지션 가격 갱신 미연결
  engine._monitor_positions_loop()
    → check_exit_conditions() 호출
    → BUT update_prices() 미호출
    → current_price 영구 고정 → 손절/익절/트레일링 전부 불능

[결함 #2] 체결 후 포지션 미생성
  order_manager._execute_order()
    → status="filled" DB 업데이트
    → BUT engine.on_order_filled() 미호출
    → 포지션 미생성 → 유령 주문 (잔고에 있으나 시스템에서 추적 불가)

[결함 #3] 청산 조건 판정 후 실제 청산 미실행 (검토 중 추가 발견)
  engine._monitor_positions_loop()
    → check_exit_conditions() 결과 로깅만
    → 매도 주문 발송 없음 + close_position() 미호출
    → 손절/익절 조건 충족해도 포지션 유지
```

### 수정 후 완전한 매매 파이프라인

```
스크리닝 → 신호 생성 → 리스크 체크 → 주문 제출
  → 체결 확인 → [콜백] 포지션 생성
  → [모니터 루프] 가격 갱신 → 청산 조건 체크 → 매도 주문 → 포지션 종료
  → 리스크 카운터 업데이트 → 알림
```

---

## 검토팀 확정 파라미터 (2026-04-15)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 김단타(단타), 윤에이피(API) — 4명

### 결함 수정 방향 확정

| # | 항목 | 원래 설계 | 확정 방향 | 근거 |
|---|------|----------|----------|------|
| 1 | 가격 갱신 소스 | 없음 | WS Redis 캐시 우선 + REST 폴백 | 윤에이피: realtime:{code} 활용, 김단타: 5초 간격 적절 |
| 2 | 가격 갱신 시간대 | 없음 | 09:00~15:30만 실행 | 김단타: 장외 잘못된 청산 방지 |
| 3 | 체결→포지션 연결 | 미연결 | 콜백 패턴 (on_filled_callback) | 윤에이피: 순환 참조 방지 |
| 4 | signal 정보 전달 | 없음 | Order 모델에 signal_json 컬럼 추가 | 윤에이피: 콜백에서 signal 정보 필요 |
| 5 | 청산 매도 방식 | 없음 | 시장가 고정 + 3회 폴링 | 김단타: 빠른 청산 최우선 |
| 6 | cancel 실패 처리 | 무시+시장가 진행 | return (시장가 발송 중단) | 최리스크+윤에이피: 이중 주문 방지 |
| 7 | 체결가 역산 | 없음 | tot_ccld_amt / tot_ccld_qty | 윤에이피: 모의/실전 동일 필드 |

### 파라미터 조정 확정

| # | 항목 | 원래값 | 확정값 | 근거 |
|---|------|--------|--------|------|
| 8 | trade_strength_min (2차 필터) | 120.0 | 100.0 | 전원 동의: CTTR 100=균형, 120은 모의 환경에서 과도 |
| 8a | trade_strength_min (전략) | 70.0 | 100.0 | CTTR 기준 통일: 100 미만=매도 우세 종목 제외 |
| 9 | max_candidates | 30 | 20 | 전원 동의: WS 구독 한도(25) 대비 여유 + 집중도 |
| 10 | daily_loss_pct 분모 | 활성 포지션 원금 | 당일 시작 잔고 (Redis 캐시) | 최리스크: 전액 청산 후 재진입 차단 |
| 11 | record_loss 트리거 | stop_loss만 | realized_pnl < 0 전체 | 최리스크: trailing/eod 손실 누락 방지 |
| 12 | trailing_highs 저장 | 인메모리 dict | Redis HSET | 전원 동의: 서버 재시작 시 소실 방지 |
| 13 | REST 폴백 타임아웃 | 없음 | 3초 | 윤에이피: 시세 조회 지연 시 다음 루프 |
| 14 | 청산 매도 폴링 | 없음 | 최대 3회, 2초 간격 | 윤에이피+김단타: 빠른 청산 + API 부하 균형 |

### LIVE 전환 초기 운영 파라미터 (최리스크+김단타 공동 확정)

| # | 파라미터 | Paper 값 | LIVE 초기 (첫 주) | LIVE 안정 후 |
|---|----------|---------|-------------------|-------------|
| 15 | max_position_count | 5 | 2 | 3 |
| 16 | position_size_pct | 10% | 5% | 10% |
| 17 | daily_max_loss_pct | -3% | -2% | -3% |
| 18 | emergency_stop_pct | -4% | -3% | -4% |
| 19 | 거래 모드 | auto | semi-auto | auto (1주 관찰 후) |
| 20 | 초기 자본금 | - | 50만원 이하 | 검증 후 증액 |
| 21 | max_candidates (LIVE) | 20 | 10 | 20 |
| 22 | trade_strength_min (LIVE) | 100.0 | 100.0 | 110.0 (1주 관찰 후) |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| ✅ 1 | P0 치명적 결함 + P1 수정 | 가격 갱신 연결, 체결→포지션 콜백, 청산 매도 실행, 이중 주문 방지, 파라미터 조정 | 없음 |
| ✅ 2 | P2 리스크 개선 | daily_loss_pct 분모 수정, record_loss 확장, 트레일링 Redis 이관, in-flight 중복 매도 방지 | Sprint 1 |
| 3 | E2E 검증 + LIVE 전환 게이트 | Paper E2E 1사이클, 5거래일 관찰, LIVE 초기 파라미터 적용 | Sprint 2 |

---

## Sprint 1 상세 — P0 치명적 결함 + P1 수정 ✅ 완료

> PR #132 머지 완료 (2026-04-15). pytest 817 passed. 코드 리뷰 이슈 없음.

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/trading/engine.py` | `_monitor_positions_loop`: (1) `_collect_price_updates()` 신규 메서드로 가격 수집, (2) `update_prices()` 호출, (3) 청산 대상에 `_execute_exit()` 실행 |
| `backend/modules/trading/engine.py` | `_collect_price_updates()`: Redis realtime:{code} → current_price 추출. WS 미수신 시 REST 폴백 (throttler 경유) |
| `backend/modules/trading/engine.py` | `_execute_exit()`: 시장가 매도 주문 → 체결 폴링(3회) → `close_position()` 호출 |
| `backend/modules/trading/engine.py` | `_monitor_positions_loop`: 장 시간(09:00~15:30) 가드 추가 |
| `backend/modules/trading/order_manager.py` | `__init__`: `on_filled_callback` 파라미터 추가 |
| `backend/modules/trading/order_manager.py` | `_execute_order`: 체결 성공 시 콜백 호출. signal 정보는 Order.signal_json에서 복원 |
| `backend/modules/trading/order_manager.py` | `_execute_order` 실전 경로: cancel 실패 시 `return` (이중 주문 방지) |
| `backend/modules/trading/order_manager.py` | `submit_order`: signal 정보를 Order.signal_json에 저장 |
| `backend/modules/trading/order_manager.py` | `_execute_order`: 체결가 역산 — `tot_ccld_amt / tot_ccld_qty` |
| `core/models/trading.py` | `Order` 모델에 `signal_json` (JSON 컬럼) 추가 |
| `alembic/versions/` | Order.signal_json 마이그레이션 |
| `backend/modules/screening/filters.py` | `trade_strength_min`: 120.0 → 100.0 (CTTR 기준), `max_candidates`: 30 → 20 |
| `backend/modules/trading/strategies/momentum_breakout.py` | 체결강도 조건: 70.0 → 100.0 (CTTR 기준 통일) |
| `backend/main.py` | `OrderManager` 생성 시 `on_filled_callback=engine.on_order_filled` 연결 |
| `backend/tests/` | 기존 테스트 수정 + 신규 테스트: 가격 갱신 루프, 체결 콜백, 청산 실행, 이중 주문 방지 |

### 프론트엔드

| 파일 | 수정 내용 |
|------|----------|
| 없음 | Sprint 1은 백엔드만 수정 |

### 재사용 자산

| 기존 모듈 | 재활용 내용 |
|----------|------------|
| `core/clients/kis_rest.py` | `place_order()`, `get_order_status()`, `get_current_price()` |
| `core/clients/throttler.py` | REST 폴백 + 매도 주문 시 throttler 공유 |
| `core/redis.py` | `realtime:{code}` 키 읽기, HSET 패턴 |
| `modules/trading/position_manager.py` | `update_prices()`, `check_exit_conditions()`, `close_position()` 기존 구현 활용 |
| `modules/trading/strategy.py` | `TradeSignalData` 직렬화/역직렬화 (signal_json) |

---

## Sprint 2 상세 — P2 리스크 개선

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/trading/risk_manager.py` | `check_daily_loss()`: 분모를 "당일 시작 잔고" 기반으로 변경. Redis `risk:daily_capital` 키에 장 시작 시 잔고 캐시 |
| `backend/modules/trading/risk_manager.py` | `reset_daily_counters()`: 장 시작 시 `risk:daily_capital` 캐시 설정 |
| `backend/modules/trading/position_manager.py` | `close_position()`: `realized_pnl < 0`이면 `record_loss()` 호출 (exit_reason 무관) |
| `backend/modules/trading/position_manager.py` | `_trailing_highs`: dict → Redis HSET (`trailing_highs`) 이관 |
| `backend/modules/trading/position_manager.py` | `__init__`: 시작 시 Redis에서 trailing_highs 로드 |
| `backend/modules/trading/position_manager.py` | `update_prices()`: trailing_highs 갱신 시 Redis 동기화 |
| `backend/modules/trading/position_manager.py` | `close_position()`: trailing_highs 삭제 시 Redis hdel |
| `backend/modules/trading/eod_liquidator.py` | `liquidate_all()`: Redis `trailing_highs` 키 전체 삭제 추가 |
| `backend/tests/` | daily_loss 분모 테스트, record_loss 확장 테스트, trailing Redis 테스트 |

---

## Sprint 3 상세 — E2E 검증 + LIVE 전환 게이트

### E2E 검증 체크리스트 (Paper 모드)

| # | 검증 항목 | 성공 기준 | 상태 |
|---|----------|----------|------|
| 1 | 1차 스크리닝 → 후보 생성 | 1건 이상 후보 | ⬜ |
| 2 | 2차 스크리닝 → 신호 생성 | generate_signals 1건+ 반환 | ⬜ |
| 3 | 주문 제출 → KIS API 주문 | order_no 수신 | ⬜ |
| 4 | 체결 확인 → 포지션 생성 | positions 테이블 1건+ | ⬜ |
| 5 | 가격 갱신 | current_price != avg_price (변화 확인) | ⬜ |
| 6 | 손절 발동 → 매도 주문 → 포지션 삭제 | trade_history 기록 + positions 0건 | ⬜ |
| 7 | 트레일링 스탑 → 매도 | trailing_activated=True → 1% 후퇴 시 청산 | ⬜ |
| 8 | EOD 청산 (14:50) | 미청산 전부 강제 매도 | ⬜ |
| 9 | 일일 손실 한도 | daily_loss 초과 시 신규 진입 차단 | ⬜ |
| 10 | 연속 손절 쿨다운 | 3연속 손절 → 60분 쿨다운 | ⬜ |

### LIVE 전환 게이트 기준

| # | 조건 | 기준 | 상태 |
|---|------|------|------|
| 1 | Paper 핫픽스 0건 | 5거래일 연속 | ⬜ |
| 2 | 신호 발생 | 3거래일 연속 (generate_signals 1건+) | ⬜ |
| 3 | 포지션 생명주기 완전 | 주문→체결→포지션→가격갱신→청산 1회+ 성공 | ⬜ |
| 4 | Sprint 1+2 전부 머지 | develop 브랜치 반영 확인 | ⬜ |
| 5 | LIVE 초기 파라미터 적용 | 확정 파라미터 #15~#22 settings 테이블 반영 | ⬜ |

### LIVE 전환 절차

1. LIVE 게이트 전 조건 충족 확인
2. `TRADING_ENV=live` 환경변수 변경 (Railway)
3. KIS 실전 APP_KEY/SECRET 확인
4. settings 테이블에 LIVE 초기 파라미터 반영 (max_position_count=2, position_size_pct=5 등)
5. 거래 모드 `semi-auto` 확인
6. 첫 거래일 실시간 모니터링 (텔레그램 알림 수신 확인)

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 담당 | 배치 |
|---|------|--------|------|------|
| 1 | 모의/실전 체결가 차이 | ⚠️ | 윤에이피 | Sprint 1에서 역산 구현, 실전 전환 시 검증 |
| 2 | REST 폴백 시 Rate Limit 증가 | ⚠️ | 윤에이피 | throttler 공유 인스턴스로 관리 |
| 3 | 부분 체결 reconciliation | ⚠️ | 윤에이피 | cancel 실패 시 return 채택으로 리스크 완화, 별도 Phase에서 고도화 |
| 4 | LIVE 전환 시 tr_id 접두사 전환 | ⚠️ | 윤에이피 | 기존 settings.TRADING_ENV 기반 자동 전환 확인 |
| 5 | LIVE 첫 주 슬리피지 | ⚠️ | 김단타 | semi-auto 모드로 수동 관찰 |
| 6 | trade_strength_min 100 → 110 상향 시점 | 정보 | 김단타+최리스크 | LIVE 1주 관찰 후 결정 |
| 7 | _execute_exit 체결 폴링 6초 내 중복 매도 가능성 | ✅ 해결 | Sprint 2 | Sprint 2에서 Redis `exit:inflight:{stock_code}` TTL 30s 플래그로 중복 매도 방지 구현 완료 |
| 8 | `/screening/secondary` API 날짜 필터 누락 | 정보 | — | 오늘 통과 종목 없으면 어제 마지막 레코드 반환. 거래 로직 무관, 운영 가시성 혼란 유발. Sprint 3 이후 수정 (발견: 2026-04-17 LIVE 모니터링) |
| 9 | `secondary_last_run` Redis 미저장 | 정보 | — | 2차 스크리닝 실행 시각을 Redis에 저장하지 않아 collector/status API에서 null 표시. 거래 로직 무관. Sprint 3 이후 수정 (발견: 2026-04-17 LIVE 모니터링) |
| 10 | 2차 스크리닝 상대 백분위 스코어 — N=1 시 무의미 | 정보 | — | 필터 통과 종목이 1개이면 비교 대상 없어 모든 팩터 100점 자동 부여 → is_passed 항상 True, 스코어가 절대 품질 미반영. 거래 신호 발생 자체는 정상이나 신호 품질 구분 불가. Sprint 3 이후 절대값 기반 스코어링 혼합 검토 (발견: 2026-04-17 LIVE 모니터링) |

---

## 기존 Phase 7 (5분봉 가속도) 넘버링 조정

- 기존 Phase 7 (5분봉 거래량 가속도 지표) → **Phase 7.1**로 리넘버링
- 데이터 축적(vol5m Redis 키)은 Phase 6.1 배포(2026-04-13) 이후 계속 진행 중
- Phase 7.1 착수 가능 시점: 2026-05-12 이후 (20거래일 축적 완료)
- Phase 7.0은 데이터 축적과 무관하므로 즉시 착수 가능

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| P0 결함 3건 수정 | 가격 갱신 + 포지션 생성 + 청산 실행 동작 확인 | ✅ 완료 (Sprint 1) |
| P1 이중 주문 방지 | cancel 실패 시 return 동작 확인 | ✅ 완료 (Sprint 1) |
| P1 파라미터 조정 | trade_strength_min=100.0, max_candidates=20 반영 | ✅ 완료 (Sprint 1) |
| P2 daily_loss 분모 수정 | 당일 시작 잔고 기반 체크 동작 확인 | ✅ 완료 (Sprint 2) |
| P2 record_loss 확장 | trailing/eod 손실 시 카운터 증가 확인 | ✅ 완료 (Sprint 2) |
| P2 트레일링 Redis 이관 | 서버 재시작 후 trailing_highs 유지 확인 | ✅ 완료 (Sprint 2) |
| E2E 1사이클 성공 | 주문→체결→포지션→가격갱신→청산 완전 성공 | ⬜ |
| Paper 5거래일 안정 | 핫픽스 0건 + 신호 발생 3거래일 연속 | ⬜ |
| LIVE 전환 게이트 통과 | 전 조건 충족 | ⬜ |
| pytest 전체 통과 | 기존 + 신규 테스트 전체 통과 | ✅ 완료 (837 passed, 5 failed 기존 무관) |
