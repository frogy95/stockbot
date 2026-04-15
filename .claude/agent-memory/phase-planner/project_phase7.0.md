---
name: Phase 7.0 계획
description: 매매 엔진 치명적 결함 수정 + LIVE 전환 준비, 전문가 4명 검토, 3 Sprint, P0 3건(가격갱신+포지션생성+청산실행) + P1 2건 + P2 3건 + E2E 검증 + LIVE 게이트
type: project
---

Phase 7.0: 매매 엔진 치명적 결함 수정 + LIVE 전환 준비 (2026-04-15 계획 수립)

**Why:** 2026-04-15 평가에서 LIVE 전환 불가 판정. 치명적 결함 3건: (1) engine._monitor_positions_loop에서 update_prices() 미호출 → 손절/익절 영구 불능, (2) order_manager._execute_order에서 on_order_filled() 미호출 → 포지션 미생성, (3) check_exit_conditions 결과로 실제 매도 미수행 → 청산 불능. 추가: trade_strength_min=70 과도, max_candidates=30 WS 초과, daily_loss 분모 왜곡, trailing 인메모리 소실.

**How to apply:**
- Sprint 1: P0 결함 3건 + P1 2건 (가격 갱신 WS+REST, 콜백 패턴, 청산 매도 실행, cancel return, 파라미터 60/20)
- Sprint 2: P2 리스크 3건 (daily_loss 분모, record_loss 확장, trailing Redis)
- Sprint 3: E2E 검증 + LIVE 전환 게이트 (Paper 5거래일 + 신호 3거래일 + 생명주기 1회)
- 기존 Phase 7(5분봉 가속도)은 Phase 7.1로 리넘버링. 데이터 축적은 계속 진행 중.
- LIVE 초기: semi-auto, max_position=2, position_size=5%, daily_max_loss=-2%, 자본금 50만원 이하

**전문가 검토 주의사항:**
- 최리스크: P0 없이 LIVE = 무한 손실 가능. P2 없이도 위험(-10%+ 일일 손실). LIVE 초기 파라미터 보수적 설정 필수.
- 김단타: 가격 갱신 09:00~15:30만. 청산 시장가 고정. LIVE 첫 주 semi-auto.
- 윤에이피: 콜백 패턴(순환 참조 방지). Order.signal_json 컬럼 추가(Alembic). 체결가=tot_ccld_amt/tot_ccld_qty.
- 정프로: _monitor_positions_loop에서 청산 미실행 추가 발견(P0 #3). Sprint 3분할 적절.
- 추가 발견: check_exit_conditions 결과를 로깅만 하고 매도 주문+close_position 미호출 (P0급)
