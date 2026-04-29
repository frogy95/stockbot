# Sprint Planner 메모리

이 파일은 sprint-planner 에이전트의 영구 메모리입니다.
프로젝트 진행 상황, 기술 스택, 패턴 등을 기록합니다.

## 스프린트 현황 (2026-04-23 업데이트)

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
- [Phase 4 Sprint 1](phase4-sprint1-status.md) — 대시보드 기본 구조 + 핵심 페이지, ✅ 완료 (2026-03-31) / PR: https://github.com/frogy95/stockbot/pull/36

- Phase 4 Sprint 2 — 신호/스크리닝/설정 + 웹 매매 승인 (MVP 완성), ✅ 완료 (2026-03-31) / PR: https://github.com/frogy95/stockbot/pull/44

- Phase 4.5 Sprint 1 — 백엔드 안정화 (Redis 영속화, 스케줄 의존성, 수동 파이프라인), ✅ 완료 (2026-04-01) / PR: https://github.com/frogy95/stockbot/pull/55

- [Phase 4.6 Sprint 1](phase4.6-sprint1-status.md) — 근본 수리 + KIS 도메인 분리 + 유효성 검증, ✅ 완료 (2026-04-02) / PR: https://github.com/frogy95/stockbot/pull/58
- Phase 4.6 Sprint 2 — 데이터 품질 + KODEX 필터 + 통합 검증, 🔄 계획 수립 완료 (2026-04-02)

- Phase 4.6 Sprint 2 — 데이터 품질 + KODEX 필터 + 통합 검증, ✅ 완료 (2026-04-02) / PR: https://github.com/frogy95/stockbot/pull/62
- Phase 4.7 Sprint 1 — 1차 스크리닝 3팩터 분리 + 임계값 조정, ✅ 완료 (2026-04-02) / PR: https://github.com/frogy95/stockbot/pull/72

- [Phase 4.8 Sprint 1](phase4.8-sprint1-status.md) — KIS 일봉 보조 수집기 + 스케줄러 폴백, ✅ 완료 (2026-04-03) / PR: https://github.com/frogy95/stockbot/pull/77
- Phase 4.8 Sprint 2 — 재시도 스케줄 + 알림 + 모니터링, ✅ 완료 (2026-04-05) / PR: https://github.com/frogy95/stockbot/pull/78
- Phase 4.8 Sprint 3 — 장전 파이프라인 체인 구조 전환, ✅ 완료 (2026-04-05) / PR: https://github.com/frogy95/stockbot/pull/80

- Phase 4.9 Sprint 1 — DB 기반 스크리닝 의존성 + 재시도 후 재실행, ✅ 완료 (2026-04-06) / PR: https://github.com/frogy95/stockbot/pull/90

- Phase 5 Sprint 1 — 1차 스크리닝 안정화 (volume_ratio 완화 + 적응형 필터 + 폴백 + date.today() KST), ✅ 완료 (2026-04-07) / PR: https://github.com/frogy95/stockbot/pull/101

- Phase 5 Sprint 2 — 완전 자동 모드 + 텔레그램 고도화, ✅ 완료 (2026-04-07) / PR: https://github.com/frogy95/stockbot/pull/102

- Phase 5.1 Sprint 1 — change_rate 필터 수정 + 적응형 확장, ✅ 완료 (2026-04-08)

- Phase 5.2 Sprint 1 — WS 재연결 안정화 + 구독 제한, ✅ 완료 (2026-04-08) / PR: https://github.com/frogy95/stockbot/pull/106

- Phase 6 Sprint 1 — 치명적 버그 수정 + 최소 방어, ✅ 완료 (2026-04-12) / PR: https://github.com/frogy95/stockbot/pull/108
- Phase 6 Sprint 2 — 복원력 강화 + 불필요 실행 방지, ✅ 완료 (2026-04-12) / PR: https://github.com/frogy95/stockbot/pull/108

- Phase 6.1 Sprint 1 — 시간가중 거래량 보정 + 5분봉 수집 선행 구축, ✅ 완료 (2026-04-13) / PR: (생성 후 기입)

- Phase 6.2 Sprint 1 — 장전 수집 단순화 (KIS 직접 + 16:00 포털 보조), ✅ 완료 (2026-04-14)

- Phase 7.0 Sprint 1 — P0 치명적 결함 + P1 수정 (가격 갱신/포지션 생성/청산 실행/파라미터), ✅ 완료 (2026-04-15) / PR: https://github.com/frogy95/stockbot/pull/132
- Phase 7.0 Sprint 2 — P2 리스크 개선 (daily_loss 분모, record_loss 확장, trailing Redis, in-flight 중복 매도 방지), ✅ 완료 (2026-04-16) / PR: https://github.com/frogy95/stockbot/pull/135

- Phase 7.0.1 Sprint 1 — LIVE WS 연결 복구 (ws_url /tryitout 경로 추가, Task4 KIS IP등록 불필요 확인), ✅ 완료 (2026-04-16) / PR: https://github.com/frogy95/stockbot/pull/137

- Phase 8 Sprint 1 — 장중 OHLC 파싱 + 갭 분기 수정 (H0STCNT0 파서 OHLC 3필드, Redis 캐싱, snapshot 실시간 우선, breakout_ref=open_price), ✅ 완료 (2026-04-20) / PR: https://github.com/frogy95/stockbot/pull/149
- Phase 8 Sprint 2 — 다층 진입 조건 + 리스크 안전장치 + 이관 버그 수정 (breakout_tier 3단계, daily_trade_count 10건/일, 동시호가 가드, 재연결/일일리포트 dedup, 프론트 리셋 버튼), ✅ 완료 (2026-04-22) / PR: https://github.com/frogy95/stockbot/pull/157
- [Phase 8.5 Sprint 1](phase8.5-sprint1-status.md) — 관측성 강화 (score 히스토그램 + stage heatmap + 탈락 상위 + 가상 신호 로깅), ✅ 완료 (2026-04-22) / PR: https://github.com/frogy95/stockbot/pull/162
- Phase 8.5 Sprint 1.5 — 전략 필터 shadow evaluation (각 stage 독립 pass/fail 카운터, 주문 경로 불변 TDD), ✅ 완료 (2026-04-23) / PR: https://github.com/frogy95/stockbot/pull/168
- Phase 8.5 Sprint 2 — 풀 하한 폴백 + 동적 MIN_VOLUME_FLOOR (0.4/0.5/0.6 + HARD 0.3) + 자동 롤백 + Sprint 1 M1/M2, ✅ 완료 (2026-04-23) / PR: (develop)
- Phase 8.5 Sprint 2.5 — 인프라 보강 + 관측성·문서 정합성 (resolve_override 통합 + 경고 배너 + env 동기화 스크립트 + DoD 재정의), ✅ 완료 (2026-04-23) / PR: https://github.com/frogy95/stockbot/pull/172
- **Phase 8.6 Sprint 1** — 선행 패치 + DoR 가드레일 G1~G3 (PO Sprint 2.6 흡수, M-F2/자동롤백 R1~R4/회로차단기/Phase 7.0 코드 잠금/폴백 5종/min_volume_floor 0.3 09~11시), 🔄 계획 수립 완료 (2026-04-29), `docs/phase/phase8.6/sprint1/sprint1.md` (7 Task)

## 다음 사용 가능한 스프린트

- Phase 8.6 Sprint 2 — 병렬 OR tier 분리 + ATR 분위수 캘리브레이션 (Sprint 1 DoR 4종 통과 후)
- Phase 8.6 Sprint 3 — `volume_surge` tier 신설 + 시간대 필터 (Sprint 2 후)
- Phase 8.6 Sprint 4 — Walk-forward 60일 백테스트 + 시뮬↔실측 KS 자동 감지 (Sprint 3 + Paper 5거래일 관찰 후)
- Phase 8.7 Sprint 1 — E2E 검증 + LIVE 전환 게이트 (구 Phase 8 Sprint 3, Phase 8.6 완료 후)

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
- Phase 4 Sprint 2: settings.py 라우터에 인증 미적용 상태 — dependencies=[Depends(get_current_user)] 추가 필요
- Phase 4 Sprint 2: ApprovalManager.validate_approval()은 일회용(조회 후 삭제) — 대기 목록 조회는 Redis scan_keys로 별도 구현 필요 (validate 호출하면 토큰 소멸)
- Phase 4 Sprint 2: TradingEngine.approve_signal/reject_signal은 NotifierManager.handle_approval 경유 — app.state.trading_engine에서 직접 호출
- Phase 4 Sprint 2: seed_settings.py에 trading_env 키 존재 (category=system) — 모드 전환 시 이 키의 value를 paper/live로 업데이트
- Phase 4 Sprint 2: approval 토큰 TTL은 승인 타임아웃과 동일 (기본 30초/15초/60초) — expires_in_sec는 Redis TTL 명령으로 조회
- Phase 4 Sprint 2: frontend/lib/api.ts에 apiPut 미존재 — 추가 필요 (apiPost 패턴 복사, method="PUT")
- Phase 4 Sprint 2: 프론트엔드 use-polling.ts의 refreshInterval은 정수만 지원 — 동적 전환은 상태값으로 interval 변경하여 usePolling에 전달
- Phase 4.5 Sprint 1: scheduler.py의 _last_* 필드 7개 (premarket, etf, primary_screen, secondary_screen, dart, sentiment, etf_master) — Redis 영속화 대상
- Phase 4.5 Sprint 1: RedisClient에 get/set/delete/scan_keys/ttl 메서드 존재 — 추가 메서드 불필요
- Phase 4.5 Sprint 1: TelegramBot.send_notification(text: str) -> int (message_id 반환) — HTML parse_mode
- Phase 4.5 Sprint 1: scheduler._telegram_bot은 main.py에서 set_telegram_bot()으로 후속 주입 — None일 수 있음
- Phase 4.5 Sprint 1: engine.py의 process_screening_results 진입부에 eod_liquidator.is_entry_blocked() 체크 이미 존재 — pipeline_healthy 가드는 그 직전에 추가
- Phase 4.5 Sprint 1: 기존 test_scheduler.py에서 _make_scheduler() 패턴 — AsyncMock session_factory, redis, ws_client 등 재사용
- Phase 4.6 Sprint 1: inquiry_client는 항상 LIVE 환경 — KIS_APP_KEY 미설정 시 warning만 (서버 차단 안 함, CI 대응)
- Phase 4.6 Sprint 1: CollectionValidator의 T-2 거래일 판정은 주말만 건너뜀 — 공휴일은 Sprint 2 trading_calendar.py에서 추가
- Phase 4.6 Sprint 1: naver collect_sentiments의 CollectionResult.collected는 뉴스 건수가 아닌 종목 수 기준
- Phase 4.6 Sprint 1: dart MAX_FINANCIAL_QUERIES=30 상한 제거 -> corp_code 매핑된 전체 종목 수집
- Phase 4.6 Sprint 1: pg_insert upsert에서 ORM onupdate=func.now() 미작동 -> set_에 명시적 func.now() 추가 필요 (data_go_kr + kis_collector)
- Phase 4.6 Sprint 1: _make_scheduler()에 inquiry_client 파라미터 추가 필요 (기존 테스트 전체 수정 대상)
- Phase 4.6 Sprint 1: scheduler._update_step_status 시그니처 변경 (collected_count, validation 추가) -> 기존 호출부 전체 수정
- Phase 4.6 Sprint 2: ETF 시세 수집 대상 KODEX만으로 제한 — kis_collector._get_etf_codes()에 Stock.stock_name.startswith("KODEX") 조건 추가 (마스터 전체 유지, 시세 수집만 축소)
- Phase 4.6 Sprint 2: KODEX ETF ~280종목 → API 호출 시간 ~30초 (기존 878종목 대비 약 1/3)
- Phase 4.6 Sprint 2: trading_calendar.py는 2026년 공휴일 하드코딩 — 대체공휴일 정확성 확인 필요 (주석 표기)
- Phase 4.6 Sprint 2: validator._is_within_t2()에서 기존 주말만 건너뜀 -> trading_calendar 사용으로 교체
- Phase 4.6 Sprint 2: DB 후검증(validate_premarket_db/validate_etf_db)은 참고 정보 — pipeline_healthy에 직접 영향 없음
- Phase 4.7 Sprint 1: FactorScorer.__init__에 factors 파라미터 없음 — score_candidates에서 STOCK_FACTORS/ETF_FACTORS 하드코딩. factors dict 파라미터 추가 필요
- Phase 4.7 Sprint 1: PrimaryScreener는 FactorScorer()를 기본값으로 생성 (pass_threshold=80.0) — 60.0으로 변경 + 3팩터 지정
- Phase 4.7 Sprint 1: RealtimeScreener도 FactorScorer()를 기본값으로 생성 (pass_threshold=80.0) — 75.0으로 변경
- Phase 4.7 Sprint 1: main.py에서 PrimaryScreener()와 RealtimeScreener() 모두 파라미터 없이 생성 — __init__ 기본값 변경으로 충분, main.py 수정 불필요
- Phase 4.7 Sprint 1: screener.py의 _build_candidates에서 trade_strength_factor=50.0, orderbook_ratio_factor=1.0, tracking_error_factor=0.0 하드코딩 — 이 3개 제거 대상
- Phase 4.8 Sprint 1: KIS 일봉 API(FHKST03010100) — 모의거래 미지원 가능성, inquiry_client(실전 조회 전용) 사용
- Phase 4.8 Sprint 1: market_data.source="kis_daily"로 태깅, "kis_rest"(ETF)와 구분
- Phase 4.8 Sprint 1: KIS 일봉에 시총 미포함 — stocks.listed_shares * close_price로 market_cap 추정
- Phase 4.8 Sprint 1: 배치 50종목 단위 commit (부분 실패 복구), 보조 수집 최소 성공률 80%
- Phase 4.8 Sprint 1: screener._fetch_today_and_prev() date_subq source 필터 확장: "data_go_kr" OR "kis_daily"
- Phase 4.8 Sprint 1: 동일 종목/날짜에 두 소스 있으면 data_go_kr 우선 (확정 파라미터 #11)
- Phase 4.8 Sprint 3: 변경 대상 scheduler.py만 — start()에서 장전 CronTrigger 6개 제거, premarket_pipeline 1개 추가
- Phase 4.8 Sprint 3: test_scheduler.py의 test_scheduler_registers_jobs()에서 job_count=9 → job 구조 변경 필요 (screener 미설정 시 5개)
- Phase 4.8 Sprint 3: run_premarket_pipeline()의 finally에서 PIPELINE_RUNNING_KEY 삭제 — 래퍼에서 중복 삭제 금지
- Phase 4.8 Sprint 3: _check_dependency()는 "대기하지 않고 즉시 스킵" — 체인 방식에서는 순차 실행이므로 이 문제 자동 해소
- Phase 4.9 Sprint 1: validate_screening_readiness 소스 필터 ["data_go_kr", "kis_daily"]는 screener._fetch_today_and_prev() date_subq와 반드시 일치 필요
- Phase 4.9 Sprint 1: pipeline_healthy=false 유지 원칙 — _are_core_steps_healthy()가 premarket "success" 요구하므로 자연 차단, 코드 리뷰 확인 필수
- Phase 4.9 Sprint 1: _premarket_retry 후 재실행 시 PIPELINE_RUNNING_KEY 락 확인 필수 (수동 트리거 충돌 방지)
- Phase 4.9 Sprint 1: DB 폴백 검증 실패 시 기존 의존성 체크 따름 (안전한 실패 패턴)
- Phase 4.9 Sprint 1: 수정 대상 2파일 (validator.py, scheduler.py) + 신규 테스트 2파일
- Phase 5 Sprint 1: date.today() 프로덕션 5개 파일 + datetime.now() 2개소 — risk_manager.py(180,268,311,377), manager.py(105), commands.py(47), dashboard.py(33), trading.py(57)
- Phase 5 Sprint 1: risk_manager.py의 check_time_restriction()과 assert_settings_unlocked()에 datetime.now() 미보호 사용 — KST 전환 필수
- Phase 5 Sprint 1: PrimaryFilters.volume_ratio 기본값 2.0 -> 1.5 변경 시 test_filters.py::TestPrimaryFilters 업데이트 필요
- Phase 5 Sprint 1: screener._fetch_today_and_prev()에서 prev_volume=0 처리 — session 파라미터 이미 전달받고 있어 폴백 쿼리 추가 가능
- Phase 5 Sprint 1: 적응형 필터 반환값 tuple[list[dict], bool]로 is_relaxed 전달 — screen() 결과에 플래그 전파
- Phase 5 Sprint 1: 기본 후보 is_fallback/auto_trade_blocked/position_size_ratio 플래그는 factors JSON에 저장 — Sprint 2에서 engine이 소비
- Phase 5 Sprint 1: dart.py의 datetime.now().year는 연도만 사용하므로 UTC/KST 무관 — 수정 불필요
- Phase 5 Sprint 2: engine.py process_screening_results()에서 notifier 존재 여부로 반자동/직접 주문 분기 (line 109) — trading_mode 기반 분기로 변경 필요
- Phase 5 Sprint 2: seed_settings.py에 trading_mode 미존재 — 추가 필요 (key=trading_mode, value=semi-auto, category=trading)
- Phase 5 Sprint 2: settings.py에 switch_trading_mode(ModeSwitchRequest) 이미 존재 — trading_env 전환용. trading_mode 전환은 별도 엔드포인트 필요
- Phase 5 Sprint 2: screener.py의 기본 후보 플래그 (is_fallback, auto_trade_blocked, position_size_ratio) — engine에서 stock_code 기준으로 매핑 필요
- Phase 5 Sprint 2: NotifierManager.send_daily_report() 이미 구현 (manager.py:102) — 스케줄러 연결만 필요
- Phase 5 Sprint 2: scheduler._market_close()는 WS 종료만 수행 — send_daily_report 호출 추가 필요
- Phase 5 Sprint 2: CollectorScheduler에 notifier_manager 참조 없음 — set_notifier_manager() 메서드 추가 필요 (set_telegram_bot 패턴)
- Phase 5 Sprint 2: RiskManager.__init__에 notifier 파라미터 없음 — 비상 정지 알림 위해 set_notifier() 추가 필요
- Phase 5 Sprint 2: PositionSizer.calculate(stock_code, current_price, balance_amount)에 size_ratio 파라미터 없음 — 추가 필요
- Phase 5 Sprint 2: main.py lifespan에서 notifier_manager 생성 후 collector_scheduler/risk_manager에 주입 순서 중요
- Phase 5 Sprint 2: frontend/(dashboard)/settings/page.tsx에 ModeSwitch 컴포넌트 사용 중 — trading_mode 전환 UI는 별도 섹션으로 추가
- Phase 5 Sprint 2: frontend/components/settings/mode-switch.tsx는 모의/실전(paper/live) 전환 전용 — TradingModeSwitch는 별도로 추가
- Phase 5.1 Sprint 1: PrimaryFilters.change_rate_min 현재값 1.0 -> -2.0 변경, change_rate_max=7.0 유지
- Phase 5.1 Sprint 1: 적응형 필터 확장 — volume_ratio [1.5, 1.2] 다음에 change_rate [-2.0, -3.0] 순차 완화, 최저 하한 -5.0
- Phase 5.1 Sprint 1: 하락 종목 안전장치 — change_rate < 0: auto_trade_blocked=True, change_rate <= -2.0: position_size_ratio=0.5
- Phase 5.1 Sprint 1: 필터별 탈락 통계 로깅 — _log_filter_stats 헬퍼 메서드로 구현, passes_primary_filter 시그니처 변경 없음
- Phase 5.1 Sprint 1: test_filters.py의 test_fail_change_rate_too_low (change_rate=0.5) 수정 필요 — 0.5 >= -2.0이므로 이제 통과
- Phase 5.1 Sprint 1: 수정 대상 2파일 (filters.py, screener.py) + 테스트 2파일 (test_filters.py, test_screener.py)
- Phase 5.2 Sprint 1: KISEnvironment는 frozen=True dataclass — 새 필드 추가 시 PAPER/LIVE 인스턴스에 값 명시 필수
- Phase 5.2 Sprint 1: kis_ws.py _reconnect() 174~175줄이 핵심 수정 대상 — 딜레이 없이 60건 버스트 전송이 근본 원인
- Phase 5.2 Sprint 1: WSSubscriptionManager.__init__에 max_subscriptions=35 기본값 — 환경 기반 주입으로 변경 필요 (main.py에서)
- Phase 5.2 Sprint 1: TradeStrengthCalculator에 reset() 메서드 이미 존재 — warmup 메커니즘만 추가
- Phase 5.2 Sprint 1: scheduler._secondary_screen()에 WS 연결 상태 가드 없음 — 추가 필요 (연속 3회 스킵 시 텔레그램 경고)
- Phase 5.2 Sprint 1: scheduler._send_failure_alert(step, error) 기존 메서드 재사용 가능 — WS 재연결 실패 알림에 활용
- Phase 5.2 Sprint 1: test_kis_ws.py의 test_reconnect_exponential_backoff에서 sleep_calls==[1,2,4,8,16] 검증 — BACKOFF_BASE 변경 후 [2,4,8,16,32,64,128]으로 수정 필요
- Phase 5.2 Sprint 1: on_reconnect_success 콜백을 kis_ws.py에 추가하여 scheduler에서 체결강도 웜업 연결
- Phase 6 Sprint 1: _reconnect()에 disconnect() 패턴(cancel+await) 그대로 적용 — 82~87줄 참조
- Phase 6 Sprint 1: 구독 복원을 try/except로 감싸되, _receive_task 생성은 except 바깥에서 항상 실행
- Phase 6 Sprint 1: ws_manager.py 45줄/74줄 가드 `and` -> `or` — 한쪽만 비정상이어도 차단
- Phase 6 Sprint 1: _market_open() except에 _send_failure_alert("market_open", str(e)) 한 줄 추가
- Phase 8.5 Sprint 1.5: `generate_signal()` 순차 short-circuit 한계로 뒤 stage 표본이 부족 — shadow evaluation으로 각 stage 독립 평가. 기존 `STRATEGY_STAGE_PREFIX` 절대 불변, shadow는 신규 `metrics:shadow:stage` 네임스페이스
- Phase 8.5 Sprint 1.5: `_metrics.py` 순수성 원칙(TradeSignalData import 금지, 예외 전파 금지) 계승. `_shadow_evaluate` 전체를 try/except로 감싸 Logger.warning으로 흡수
- Phase 8.5 Sprint 1.5: `_resolve_tier`/`calc_volatility_factor`는 순수 함수라 shadow/real에서 중복 호출 허용 (성능 영향 미미). `_now_kst()`는 shadow에 공유
- Phase 8.5 Sprint 1.5: prev_volume=0 또는 breakout_ref<=0일 때 관련 stage는 기록 skip(pass/fail 둘 다 아님) — 표본 오염 방지
- Phase 8.5 Sprint 1.5: TDD 필수 — Task 1에서 RED 테스트 선작성으로 "shadow 추가 후 기존 반환값 바이트 동일" + "shadow 예외가 상위로 전파되지 않음" 증명
- Phase 6 Sprint 1: _market_open_recovery() 판단: ws_manager.count -> _ws_client.connected로 변경
- Phase 6 Sprint 1: is_trading_day() import 추가 필요 (from core.trading_calendar import is_trading_day)
- Phase 6 Sprint 1: is_trading_day() 가드 대상 2개: _run_scheduled_pipeline, _market_open (Sprint 2에서 나머지)
- Phase 6 Sprint 1: test_connect_websocket_url 기존 테스트가 open_timeout=10 추가로 assert 수정 필요
- Phase 6 Sprint 1: test_scheduler_phase6.py 신규 생성 — _make_scheduler 패턴 재사용 (tests/test_scheduler.py의 conftest.FakeRedis)
- Phase 8 Sprint 1: EXECUTION_FIELD_MAP idx 7/8/9 = STCK_OPRC/STCK_HGPR/STCK_LWPR (KIS H0STCNT0) — 확정 (Phase 7.2 승계). 배포 후 1~2시간 샘플 5종목 KIS 공식 시세 대조 필수 (김단타 권고)
- Phase 8 Sprint 1: scheduler.py ~1141줄 `realtime:{code}:execution` JSON 구조에 open_price/high/low 3키 추가. set_json 호출 위치 1곳만
- Phase 8 Sprint 1: realtime_screener.py candidate dict 확장 지점 2곳 — passed_candidates.append(~102줄) + factor_candidates.append(~165줄). 누락 시 signal_generator에서 항상 폴백 진입
- Phase 8 Sprint 1: signal_generator._build_snapshot() 137~142줄은 이미 `candidate.get("open_price") or prev_close or current_price` 우선 정책. 코드 변경 없이 주석만 업데이트하면 되고, candidate에 값이 흐르면 자동으로 실시간 우선
- Phase 8 Sprint 1: momentum_breakout.py 86~90줄 1줄 교체 (`snapshot.high` → `snapshot.open_price`). `reason` dict의 breakout_ref 키는 유지 — 값만 바뀌므로 로깅 형식 변경 없음
- Phase 8 Sprint 1: `.get("open_price", 0)` 폴백 + `or prev_close` 체인으로 과거 Redis 캐시 혼재 자동 처리 (0 falsy)
- Phase 8 Sprint 1: 리스크 게이트(daily_trade_count / 반 포지션 / 다층 진입)는 Sprint 1 범위 아님 — Sprint 2로 이월
- Phase 6.1 Sprint 1: momentum_breakout.py에 calc_market_progress() 함수 추가 — now_kst 파라미터로 테스트 주입 가능하게 설계
- Phase 6.1 Sprint 1: RedisClient에 INCRBY/HINCRBY 미노출 — volume_aggregator는 GET-수정-SET 패턴 사용 (단일 프로세스 race condition 없음)
- Phase 6.1 Sprint 1: scheduler._process_realtime_data의 H0STCNT0 분기에 volume_aggregator 호출 추가 — try/except로 감싸서 집계 실패가 실시간 처리 방해 금지
- Phase 6.1 Sprint 1: ExecutionData.time 형식은 "HHMMSS" 문자열 — volume_aggregator에서 hour/minute 파싱 필요
- Phase 6.1 Sprint 1: CollectorScheduler.__init__에 volume_aggregator 파라미터 추가 — 기존 _make_scheduler 테스트 헬퍼에도 추가 필요
- Phase 6.1 Sprint 1: main.py lifespan에서 VolumeAggregator(redis_client) 생성 후 scheduler에 주입 + app.state에 저장
- Phase 6.1 Sprint 1: Phase 문서의 Redis 키 스키마 `vol5m:{stock_code}:{date}:{slot_index}` 확정 (Phase 7 연동 시 동일 키 패턴)
- Phase 6.2 Sprint 1: _premarket_collect 현재 ~80줄 (포털 3중 분기 + 예외 경로 KIS 폴백) -> ~20줄 (KIS 단일 경로)로 단순화
- Phase 6.2 Sprint 1: _run_kis_daily_fallback -> _run_kis_daily_collect 이름 변경 (폴백 -> 주 경로)
- Phase 6.2 Sprint 1: _send_fallback_info_alert, _send_double_failure_alert 메서드 제거 (호출부 모두 _premarket_collect에서 제거)
- Phase 6.2 Sprint 1: validate_premarket_db L226, L242 두 곳에서 source == "data_go_kr" -> source.in_(["data_go_kr", "kis_daily"]) 변경
- Phase 7.0 Sprint 1: engine._monitor_positions_loop가 check_exit_conditions 결과만 로깅 — update_prices 미호출 + 매도 미실행이 핵심 결함
- Phase 7.0 Sprint 1: order_manager._execute_order 체결 후 engine.on_order_filled 미호출 — 콜백 패턴(set_filled_callback)으로 해결
- Phase 7.0 Sprint 1: Order 모델에 signal_json JSONB 컬럼 추가 (Alembic 필수) — 콜백에서 TradeSignalData 복원용
- Phase 7.0 Sprint 1: 실전 cancel 실패 시 시장가 진행 -> return으로 변경 (이중 주문 방지, 확정 파라미터 #6)
- Phase 7.0 Sprint 1: Redis realtime:{code}:execution에 current_price 존재 — _collect_price_updates WS 우선 소스
- Phase 7.0 Sprint 1: trade_strength_min 120.0->100.0 (CTTR 통일), momentum_breakout 70.0->100.0 (확정 파라미터 #8/#8a)
- Phase 7.0 Sprint 1: main.py 순환 참조 — OrderManager 먼저 생성 후 TradingEngine 생성 후 set_filled_callback 주입
- Phase 6.2 Sprint 1: start()에 portal_supplement CronTrigger(hour=16, minute=0) 추가 -> test_scheduler.py job_count 5->6
- Phase 6.2 Sprint 1: test_scheduler_retry.py의 3개 테스트가 DataGoKrCollector mock 사용 — KIS 기반으로 전환 필요
- Phase 6.2 Sprint 1: DataGoKrCollector import는 유지 (_portal_supplement_collect에서 사용)
- Phase 7.0 Sprint 2: RedisClient에 hset/hget/hdel/hgetall 미존재 — Task 1에서 추가 필요
- Phase 7.0 Sprint 2: risk_manager.__init__에 rest_client 미존재 — Task 1에서 추가, main.py 배선도 수정
- Phase 7.0 Sprint 2: position_manager.close_position에서 record_loss 조건이 exit_reason=="stop_loss"만 — realized_pnl<0 전체로 확장
- Phase 7.0 Sprint 2: trailing_highs 인메모리 dict — Redis HSET 이관 시 load_trailing_highs() 메서드 추가 + main.py 호출
- Phase 7.0 Sprint 2: eod_liquidator.liquidate_all에서 trailing_highs Redis 키 삭제 누락 — 추가 필요
- Phase 7.0 Sprint 2: engine._execute_exit 5초 루프 중복 매도 가능성 (미해결 #7) — Redis in-flight 플래그 TTL=30초로 방지
- Phase 8 Sprint 2: momentum_breakout.py 갭 분기 3단계 확장 — gap_open(>=3%) → prev_high(current>prev_high) → prev_close(fallback). reason dict에 `breakout_tier` 키 추가 필수
- Phase 8 Sprint 2: PositionSizer는 수정 불필요 — size_ratio 파라미터 이미 존재. engine.process_screening_results에서 tier 기반 size_ratio 결정 (`tier_ratio=0.5 if prev_close else 1.0`, candidate_ratio와 min)
- Phase 8 Sprint 2: daily_trade_count 증가 지점은 engine.on_order_filled (매수 체결 후) — 주문 제출 시점 아님. 매도/청산은 카운트 안 함 (진입 1회 = 1건)
- Phase 8 Sprint 2: DAILY_MAX_TRADE_COUNT_OVERRIDE 환경변수 — LIVE 초기 3건/일 임시 제한용, Sprint 3 게이트 통과 후 제거
- Phase 8 Sprint 2: seed_settings에 `daily_max_trade_count=10` (category=risk, int) 신규. Alembic 마이그레이션 불필요 (row 추가만)
- Phase 8 Sprint 2: Task 9 재연결 이중 알림, Task 10 일일 리포트 중복 — 근본 원인 미특정 상태로 dedup(Redis TTL) 차단. Sprint 2 배포 후 로그 재수집 필요
- Phase 8 Sprint 2: Task 8 동시호가 구간 스킵 — 15:10~15:30 사이에 `_secondary_no_data_count` 0으로 리셋 + return. `_market_close`는 15:30 실행이므로 영향 없음
- Phase 8 Sprint 2: 브랜치 base는 develop (Hotfix #153이 main→develop 역머지되어 develop에 포함됨, phase8-sprint1 브랜치에는 미포함)
- Phase 8 Sprint 2: Hotfix #153 엔드포인트는 `POST /api/v1/trading/risk/reset` — Task 7 착수 전 `backend/api/routes/trading.py` 실제 경로 재확인 필수
- Phase 8.5 Sprint 2: `MIN_VOLUME_FLOOR=0.5` 상수는 `momentum_breakout.py` 30줄에 있음 — 함수 교체 시 사용처 4곳 (line 215, 377, 384, 385) 전부 동일 함수 사용 필수
- Phase 8.5 Sprint 2: shadow/본체 일관성 보장 — `_shadow_evaluate`의 `min_volume_floor` stage도 반드시 동일 `_resolve_min_volume_floor` 호출 (하드코딩 금지)
- Phase 8.5 Sprint 2: engine.py line 214~217에 이미 `is_fallback or is_relaxed` 분기 존재 — 복합 케이스 정책 명시 필요 (min 배수 선택 권고)
- Phase 8.5 Sprint 2: Redis override (`settings:override:MIN_VOLUME_FLOOR_MODE`)는 `_resolve_min_volume_floor`와 `realtime_screener.screen()` 두 지점만 lookup — 이중 진실 관리 최소화
- Phase 8.5 Sprint 2: 자동 롤백 16:10 job은 `trading_calendar.py` 재사용 (Phase 4.6 Sprint 2) — 주말/공휴일 오인 방지
- Phase 8.5 Sprint 2: M1 처리 방식은 "API limit 상한 5로 제한" 단순 채택 (TOP_REJECT_SIZE env 승격 안 함) — 단일 상수 유지
- Phase 8.5 Sprint 2: 2차 `pass_threshold=75.0` 유지 — 임계값 완화는 Sprint 2 범위 아님 (분포 데이터 별도 확인 후 판단)
- Phase 8.5 Sprint 2: FactorScorer는 `realtime_screener.__init__`에서 `pass_threshold=75.0`으로 고정 생성됨 (line 42) — 건드리지 않음
- Phase 8.5 Sprint 2.5: `resolve_override(key, default, cast=...)` 단일 유틸 — Redis 예외 시 default 반환 (무음 실패). `SETTINGS_OVERRIDE_ENABLED=False`로 override 전체 차단 가능 (긴급 스위치)
- Phase 8.5 Sprint 2.5: `settings:override:triggered_at` / `reason` 키가 존재하면 대시보드 배너 렌더 — Redis에서 수동 삭제 시 배너 사라짐
- Phase 8.5 Sprint 2.5: 5거래일 관찰 종료 의사결정 트리(A~E) 근거: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` § 5거래일 관찰 종료 후 의사결정 트리
