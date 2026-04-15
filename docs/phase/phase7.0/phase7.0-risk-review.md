# Phase 7.0 — 최리스크 (리스크관리) 검토 리포트

> **검토일**: 2026-04-15
> **검토 대상**: 매매 엔진 치명적 결함 수정 + LIVE 전환 준비

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| P0 결함 #1 (가격 갱신 미연결) | ❌ 재검토 — 치명적. 손절이 불능이면 무한 손실 가능 |
| P0 결함 #2 (포지션 미생성) | ❌ 재검토 — 치명적. 유령 주문(주문은 체결됐으나 추적 불가) |
| P0 추가 (청산 미실행) | ❌ 재검토 — check_exit_conditions 결과로 실제 매도 미수행 |
| P1 이중 주문 | ⚠️ 주의 — 실전에서 이중 체결 시 포지션 초과 |
| P2 daily_loss_pct 분모 | ⚠️ 주의 — 전액 청산 후 재진입 시 체크 무효화 |
| P2 연속 손절 미집계 | ⚠️ 주의 — trailing/eod 손실이 카운터에 미반영 |
| P2 트레일링 고점 Redis | ⚠️ 주의 — 서버 재시작 시 트레일링 스탑 무효화 |
| LIVE 전환 게이트 | ✅ 통과 — 5거래일 관찰 기준 적절 |

## 2. 항목별 검증 결과

### P0 — 치명적 리스크

**결함 #1: update_prices() 미호출**
- `_monitor_positions_loop`가 5초마다 `check_exit_conditions()`를 호출하지만, `update_prices()`가 선행되지 않으면 `current_price`는 진입 시점 가격으로 영구 고정.
- **실전 시나리오**: 10,000원에 매수 → 주가 8,000원 하락 → stop_loss=9,800원이지만 current_price=10,000원으로 고정 → 손절 미발동 → -20% 이상 손실 가능.
- **수정 방향**: WS 실시간 데이터 또는 Redis `realtime:{code}` 캐시에서 현재가를 읽어 `update_prices()` 호출. WS가 불안정할 경우 REST 폴백 필수.

**결함 #2: on_order_filled() 미호출**
- `_execute_order()`에서 status="filled" DB 업데이트만 수행. `engine.on_order_filled()` 호출 없음.
- **실전 시나리오**: 주문 체결 → 포지션 미생성 → 모니터링 불가 → 손절/익절 미작동 → EOD 청산도 미작동(포지션 없음) → 잔고에 종목은 남지만 시스템에서 추적 불가.
- **수정 방향**: OrderManager에 engine 참조 주입 또는 콜백 함수 주입. 순환 참조 방지 위해 콜백 패턴 권장.

**추가 결함: 청산 미실행**
- `_monitor_positions_loop`에서 `check_exit_conditions()` 결과를 로깅만 하고 실제 청산 주문(매도) + `close_position()` 호출이 없음.
- **수정 방향**: 청산 대상 각각에 대해 매도 주문 발송 + 체결 확인 후 `close_position()` 호출.

### P1 — 이중 주문 위험

- `order_manager.py` L218-223: cancel 실패 시 `logger.warning` 후 continue 없이 시장가 발송.
- **실전 시나리오**: 지정가 부분 체결(50주 중 30주) → 취소 실패 → 시장가 50주 추가 발송 → 총 80주 체결.
- **수정 방향**: cancel 실패 시 `get_order_status`로 잔량 확인 → 잔량만 시장가 주문 또는 안전하게 return.
- **권고**: cancel 실패 시 return이 가장 안전. 미체결분은 reconciliation에서 처리.

### P2 — 리스크 개선

**daily_loss_pct 분모 왜곡**
- `total_capital = sum(avg_price * quantity)` — 포지션 0건이면 total_capital=0 → `return False` (체크 패스).
- **실전 시나리오**: 5건 포지션 전부 손절 청산(-3% 실현) → 포지션 0건 → daily_loss 체크 패스 → 재진입 허용 → 추가 손실 가능.
- **수정 방향**: 분모를 "당일 시작 잔고" 또는 "투자 원금 합계 + 당일 실현 손익의 절대값 기반"으로 변경. 최소값으로 settings에서 `initial_capital` 참조.

**연속 손절 카운터 미집계**
- `record_loss()`는 `exit_reason == "stop_loss"`에서만 호출됨.
- trailing(-1% 후퇴)과 eod(손실 상태 강제 청산) 손실이 누락.
- **수정 방향**: `close_position()`에서 `realized_pnl < 0`이면 `record_loss()` 호출 (exit_reason 무관).

**트레일링 고점 인메모리**
- `_trailing_highs: dict` — Railway 재시작 시 소실.
- **수정 방향**: Redis `trailing_high:{stock_code}` 키로 이관. TTL은 장 마감(16:00) 자동 만료.

## 3. 파라미터 조정 권고

| 항목 | 원래값 | 권고값 | 근거 |
|------|--------|--------|------|
| trade_strength_min | 70 | 60 | 동의. 단, 실전 전환 시 65로 상향 검토 (1주 관찰 후) |
| max_candidates | 30 | 20 | 동의. WS 구독 한도 내 유지 필수 |
| daily_loss_pct 분모 | 활성 포지션 원금 | 당일 시작 잔고 기반 | 전액 청산 후 재진입 차단 |
| record_loss 트리거 | stop_loss만 | realized_pnl < 0 전체 | trailing/eod 손실 누락 방지 |
| trailing_highs 저장 | 인메모리 dict | Redis 키 | 서버 재시작 시 소실 방지 |

## 4. LIVE 전환 게이트 — 필수 조건

| # | 조건 | 기준 |
|---|------|------|
| 1 | Paper 모드 핫픽스 0건 | 5거래일 연속 |
| 2 | 신호 발생 | 3거래일 연속 (generate_signals 1건+) |
| 3 | 포지션 생명주기 완전 | 주문→체결→포지션→가격갱신→청산 1회 이상 성공 |
| 4 | P0+P1+P2 전부 수정 완료 | Sprint 1+2 머지 확인 |
| 5 | 초기 자본금 | 50만원 이하 (최리스크 강력 권고) |
| 6 | 최대 포지션 | 2건 (LIVE 첫 주는 max_position_count=2) |
| 7 | 일일 손실 한도 | -2% (LIVE 초기는 보수적) |

## 5. 리스크 및 대안

- **최대 리스크**: P0 수정 없이 LIVE 전환 시 "무한 손실 + 유령 포지션" → 절대 불가.
- **P2 없이 LIVE 전환**: 가능하나 **위험**. daily_loss 분모 왜곡 + 연속 손절 미집계 조합 시 -10% 이상 일일 손실 가능.
- **권고**: P0+P1+P2 전부 수정 후 LIVE 전환. Sprint 3에서 5거래일 관찰.
