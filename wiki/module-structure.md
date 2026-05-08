# 모듈 구조

[[system-overview|백엔드]]는 `backend/` 하위에 명확한 책임 경계로 구성된다.

## 디렉토리 레이아웃

```
backend/
├── main.py              # FastAPI 앱 진입점
├── core/
│   ├── config.py        # 환경변수 (Settings)
│   ├── database.py      # SQLAlchemy async 세션
│   ├── redis.py         # Redis 클라이언트
│   ├── trading_calendar.py  # 한국 거래소 캘린더
│   ├── clients/         # 외부 API 클라이언트
│   └── models/          # DB 모델 (SQLAlchemy)
├── modules/
│   ├── collector/       # 데이터 수집 — [[data-collection-flow]]
│   ├── screening/       # 종목 스크리닝 — [[screening-pipeline]]
│   ├── trading/         # 매매 실행 — [[signal-generation]]
│   ├── analyzer/        # 성과 분석
│   └── notifier/        # 텔레그램 알림 — [[telegram-integration]]
└── api/
    └── routes/          # REST API 엔드포인트
```

## 모듈별 책임

### collector
외부 API에서 데이터를 수집하고 DB/Redis에 저장.
- `scheduler.py`: APScheduler 기반 장전/장중/장후 스케줄
- `sources/`: 공공데이터포털, DART, 네이버, KIS REST 수집기
- `ws_manager.py`: KIS WebSocket 실시간 연결 — [[websocket-management]]
- `trade_strength.py`: 체결강도 계산기
- `volume_aggregator.py`: 5분봉 거래량 집계

### screening
수집된 데이터에서 거래 후보 종목을 선별.
- `screener.py`: 1차 스크리닝 (장전, DB 기반 정적 필터)
- `realtime_screener.py`: 2차 스크리닝 (장중, 실시간 동적 필터, 폴백 보강 5종)
- `factors.py`: 5팩터 계산 — [[screening-factors]]
- `scorer.py`: 다팩터 스코어링 — [[scoring-system]]
- `filters.py`: 필터 조건 체크
- `atr_calibration.py`: 08:35 KOSPI200 ATR 분위수 동적 상한 산출 (Phase 8.6 Sprint 2) — [[tier-architecture]]
- `tier_correlation.py`: tier 페어와이즈 phi + 조건부 P(B|A) (Phase 8.6 Sprint 2)
- `sim_vs_real_diff.py`: shadow vs 실제 통과율 절대차 메트릭 (Phase 8.6 Sprint 2)

### safety
LIVE 자금 보호 가드레일 (Phase 8.6 Sprint 1).
- `auto_rollback.py`: R1~R4 다중 트리거 OR 평가 (16:10 잡)
- `circuit_breaker.py`: 1차→2차 통과율 회로차단기 (G3)

### trading
신호 생성부터 주문 실행, 포지션 관리까지.
- `signal_generator.py`: 2차 스크리닝 결과에 전략 적용 — [[signal-generation]]
- `strategies/momentum_breakout.py`: 모멘텀 돌파 전략 — [[momentum-breakout-strategy]]
- `engine.py`: 매매 엔진 (신호 처리 루프)
- `order_manager.py`: 주문 실행/취소 — [[order-execution]]
- `position_manager.py`: 포지션 생명주기 — [[position-management]]
- `position_sizer.py`: 건당 투자금 계산 — [[position-sizing]]
- `risk_manager.py`: 매매 전 리스크 체크 — [[risk-management]]
- `eod_liquidator.py`: 장 마감 전 전량 청산

### analyzer
체결 내역 정산 및 성과 기록.

### notifier
텔레그램 알림 발송 및 반자동 모드 승인 처리 — [[telegram-integration]].

## 의존성 규칙

- `core/` ← 모든 모듈이 의존
- 모듈 간 직접 import 금지 — API 라우터나 서비스 레이어를 통해 조합
- 외부 API 클라이언트는 `core/clients/`에서 초기화, 모듈에 주입
