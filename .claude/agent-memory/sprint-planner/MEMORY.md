# Sprint Planner 메모리

이 파일은 sprint-planner 에이전트의 영구 메모리입니다.
프로젝트 진행 상황, 기술 스택, 패턴 등을 기록합니다.

## 스프린트 현황 (2026-03-31 업데이트)

- [Phase 0.5 Sprint 1](phase0.5-sprint1-status.md) — 외부 API 5종 탐색/검증, ✅ 완료 (2026-03-29)
- [Phase 1 Sprint 1](phase1-sprint1-status.md) — Docker Compose + DB/Redis + 백엔드 스켈레톤, ✅ 완료 (2026-03-29) / PR: https://github.com/frogy95/stockbot/pull/2
- [Phase 1 Sprint 2](phase1-sprint2-status.md) — 한투 API 연동 + 토큰 관리 + 모의/실전 전환, ✅ 완료 (2026-03-29) / PR: https://github.com/frogy95/stockbot/pull/3
- [Phase 2 Sprint 1](phase2-sprint1-status.md) — 핵심 데이터 수집 (공공데이터포털 + 한투 WS/REST + 체결강도), ✅ 완료 (2026-03-29) / PR: https://github.com/frogy95/stockbot/pull/5
- [Phase 2 Sprint 2](phase2-sprint2-status.md) — 종목 스크리닝 엔진 (1차/2차 스크리닝 + 팩터 스코어링), ✅ 완료 (2026-03-29) / PR: https://github.com/frogy95/stockbot/pull/6
- Phase 2 Sprint 3 — 보조 데이터 + 통합 테스트 (DART 재무 + 네이버 센티멘트), ✅ 완료 (2026-03-30) / PR: https://github.com/frogy95/stockbot/pull/7
- Phase 2.5 Sprint 1 — ETF 마스터 수집 + 스케줄러 통합, ✅ 완료 (2026-03-30) / PR: https://github.com/frogy95/stockbot/pull/26

- Phase 2.6 Sprint 1 — mst 파서 재작성 + 검증, ✅ 완료 (2026-03-30) / PR: https://github.com/frogy95/stockbot/pull/27

- Phase 3 Sprint 1 — 리스크/자금 관리 모듈, ✅ 완료 (2026-03-30) / PR: https://github.com/frogy95/stockbot/pull/32
- Phase 3 Sprint 2 — 매매 전략 + 주문 실행, ✅ 완료 (2026-03-30) / PR: https://github.com/frogy95/stockbot/pull/33

- Phase 3 Sprint 3 — 텔레그램 봇 + 반자동 승인, ✅ 완료 (2026-03-31)
- [Phase 4 Sprint 1](phase4-sprint1-status.md) — 대시보드 기본 구조 + 핵심 페이지, 🔄 계획 수립 완료 (2026-03-31)

## 다음 사용 가능한 스프린트

- Phase 4 Sprint 1 — 대시보드 기본 구조 + 핵심 페이지 (즉시 착수 가능)

## 핵심 주의사항

- Phase 1 Sprint 1에서 확인: SQLAlchemy async 모델에서 UniqueConstraint는 `__table_args__`로 명시 필요
- redis[hiredis] 패키지명으로 설치 시 redis.asyncio 임포트 정상 동작 확인
- pytest-asyncio는 `asyncio_mode = "auto"` 설정 필수 (pytest.ini 또는 pyproject.toml)
- conftest.py에서 DB 엔진 글로벌 상태 리셋 (이벤트 루프 충돌 방지)
- exploration/kis/ 참조용 코드 있음 — 코드 복사 금지, 패턴만 참조
- Phase 2 Sprint 1에서 확인: DB 세션은 의존성 주입(get_db) 대신 독립 생성하여 테스트 격리 확보
- Phase 2 Sprint 1에서 확인: screening_results 테이블에 created_at/updated_at 추가 필요 (리뷰에서 지적)
- Phase 2 Sprint 3: DART corp_code XML은 93MB ZIP — lxml 파싱 필요, zipfile로 압축 해제 후 처리
- Phase 2 Sprint 3: DART 재무 조회 대상은 1차 스크리닝 통과 종목만 (최대 30건, 일 10,000건 한도 절약)
- Phase 2 Sprint 3: 네이버 센티멘트는 ML 모델 없이 키워드 사전 기반 간이 점수만 (보조 팩터용)
- Phase 2 Sprint 3: 보조 데이터는 팩터 스코어링에 통합하지 않음 — 별도 조회 API만 (Phase 5에서 통합 예정)
- Phase 2.5: mst URL(https://new.real.download.dws.co.kr/common/master/)은 SLA 미보장 — Sprint 착수 전 curl -I 수동 검증 필수
- Phase 2.5: KOSPI/KOSDAQ mst 파일은 필드 구조가 다름 — 파서 분리 구현 필수 (단일 파서 금지)
- Phase 2.5: Stock 모델 변경 없음 — 기존 stock_type/extra_data 필드 활용, Alembic 마이그레이션 불필요
- Phase 2.5: 기존 스케줄러의 ETF 시세 수집 시간을 08:05 -> 08:15로 변경해야 함 (확정 파라미터)
- Phase 2.5 Sprint 1: bash-guard 정규식이 소수점 브랜치명(phase2.5-*)을 차단 — .claude/hooks/pretooluse-bash-guard.sh 수정 완료
- Phase 2.5 Sprint 1: asyncio.gather 병렬 다운로드로 KOSPI+KOSDAQ mst 동시 처리 — httpx.AsyncClient 사용
- Phase 2.5 Sprint 1: func.count()로 DB ETF 종목 수 조회 후 prev_count 전달하여 sanity check ±10% 변동 감지
- Phase 2.6: mst 파서 버그 — 고정길이 200바이트 offset이 아닌 줄바꿈(\n) split 방식이 정답. ETF 판별: offset 61:63 = 'EF', ETN = 'EN'(추정)
- Phase 2.6: 수정 대상 파일 2개만: kis_master.py + test_kis_master.py. 외부 인터페이스(collect, sanity_check 등) 변경 없음
- Phase 2.6: KOSPI/KOSDAQ mst 필드 구조 동일 확인 필요 (Phase 2.5에서는 "다름"이라 했으나, Phase 2.6 검토에서 동일 offset으로 확정)
- Phase 2.6 Sprint 1 완료: 바이트 슬라이싱이 핵심 — CP949 한글 2바이트로 decode 후 문자 슬라이싱 시 offset 불일치. 반드시 `data[start:end].decode("cp949").strip()` 방식 사용
- Phase 2.6 Sprint 1 완료: KOSDAQ mst에는 ETF 없음 확인, ETN은 해당 URL mst 미포함(별도 URL 가능성)
- Phase 2.6 Sprint 1 완료: sanity_passed=True, ETF=878종목 (KOSPI mst 기준)
- Phase 3 Sprint 1: 사용자 확정 — 레버리지 손절 -1.5%, 익절 +3%, 트레일링 활성화 +2% (phase3.md와 일치)
- Phase 3 Sprint 1: 기존 seed_settings.py에 leverage_etf_size_pct=7.0 → 확정 5.0으로 변경 필요
- Phase 3 Sprint 1: 기존 seed_settings.py에 force_close_start=15:00 → 확정 14:50으로 변경 필요
- Phase 3 Sprint 1: modules/trading/ 디렉토리에 __init__.py만 존재 (빈 파일) — 새 모듈 생성 가능
- Phase 3 Sprint 1: KISRestClient에 place_order/cancel_order/get_balance/get_positions 이미 구현 — eod_liquidator에서 직접 사용 가능
- Phase 3 Sprint 1: main.py lifespan에 모듈 초기화 패턴 정립 — app.state에 인스턴스 저장, shutdown에서 정리
- Phase 3 Sprint 1: PositionRecord의 UniqueConstraint(stock_code)는 __table_args__ 방식 필수 (Phase 1 학습)
- Phase 3 Sprint 2: DB 모델(trade_signals, orders, positions, trade_history) 이미 Sprint 1에서 생성 완료 — Alembic 마이그레이션 불필요
- Phase 3 Sprint 2: KISRestClient에 place_order, cancel_order, get_order_status, get_balance, get_positions 모두 구현 완료
- Phase 3 Sprint 2: TokenBucketThrottler에 bypass 옵션 없음 — 주문 시 bypass 필요하면 throttler 확장 필요
- Phase 3 Sprint 2: RealtimeScreener.screen()이 반환하는 dict 구조 — stock_code, stock_name, stock_type, trade_strength, orderbook_ratio, volume, prev_volume, current_price, change_rate, total_bid/ask_volume
- Phase 3 Sprint 2: factors.py의 calc_volatility_factor(highs, lows, closes) -> ATR 값 반환, 이미 구현되어 있어 전략에서 재사용
- Phase 3 Sprint 2: main.py lifespan에 session_factory, rest_client, redis_client, throttler 이미 생성됨 — 추가 모듈은 이후에 초기화
- Phase 3 Sprint 2: 모의거래(TRADING_ENV=paper)에서는 시장가만 사용, 최우선 지정가 건너뜀 (미해결 사항 #1)
- Phase 4 Sprint 1: 기존 frontend/app/layout.tsx에 `dark` 클래스 + zinc-950 배경 이미 적용 — shadcn/ui 다크모드와 호환
- Phase 4 Sprint 1: frontend/package.json에 Next.js 16.2.1, React 19, Tailwind 4 설치됨 — swr, shadcn/ui 추가 필요
- Phase 4 Sprint 1: 기존 trading API 6개 재활용 — positions, orders, history, signals, risk-status, engine-status
- Phase 4 Sprint 1: main.py CORS origins 하드코딩 ["http://localhost:3000"] -> 환경변수 ALLOWED_ORIGINS 전환 필요
- Phase 4 Sprint 1: JWT_SECRET은 core/config.py에 이미 존재 — PyJWT로 HS256 서명에 재활용
- Phase 4 Sprint 1: api/deps.py에 get_db, get_redis만 존재 — get_current_user 추가 필요
- Phase 4 Sprint 1: 인증은 Depends(get_current_user) 방식 (글로벌 미들웨어 아님) — health, auth/login, telegram/webhook 제외 용이
- Phase 4 Sprint 1: Next.js 16 미들웨어 파일명 변경 가능성 확인 필요 (middleware.ts vs proxy.ts)
