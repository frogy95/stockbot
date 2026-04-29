# Wiki 운영 로그

## 2026-04-29

- Phase 8.6 Sprint 2 완료(v2.8.0 prod) 반영: [[tier-architecture]] 신설(병렬 OR + ATR 동적 캘리브레이션), [[momentum-breakout-strategy]] 대규모 갱신(직렬 AND → 병렬 OR + ATR `[0.025, min(0.08, P80×1.2)]` + prev_close 5분봉 거래량 컨펌 + gap_open 시초가 컷 + ATR HARD 절대상한 + 안전모드)
- [[signal-generation]] 갱신: `signals.matched_tiers` JSON 컬럼, `signals.fallback`, 안전모드 가드, 일일 신호 한도/동시 보유 회로 단계 추가, M-F2 메트릭 노출
- [[screening-pipeline]] 갱신: 폴백 임계 5종 + `min_volume_floor` 시간대 슬라이딩(0.3 09~11시) + ATR 캘리브레이션 모듈 링크
- [[risk-management]] 대규모 갱신: Phase 7.0 LIVE 파라미터 `Final` 잠금 + 런타임 assert, DoR 가드레일 G1(M-F2)/G2(자동 롤백 R1~R4)/G3(회로차단기), `/api/v1/metrics/phase86-status`, 안전모드 상세
- [[redis-usage]] 갱신: `metrics:atr:*`, `safe_mode:active`, `shadow:tier:*`, `metrics:quant:sim_vs_real_diff`, `auto_rollback:R*:streak`, `circuit_breaker:active`, `quota_cap_blocked` 키 추가
- [[database-schema]] 갱신: `signals.matched_tiers`, `signals.fallback`, `orders.fallback`, `stocks.is_kospi200`, `daily_screening_metrics.fallback_signal_rate / tier_pass_rates` 컬럼 추가
- [[module-structure]] 갱신: `screening/atr_calibration.py`, `tier_correlation.py`, `sim_vs_real_diff.py` + 신규 `safety/` 모듈(`auto_rollback.py`, `circuit_breaker.py`)
- [[system-overview]] / [[index]] / [[screening-factors]] 보강
- 환경변수 정리: Sprint 2 신규 10종(`PARALLEL_OR_TIER_ENABLED`, `ATR_CALIBRATION_ENABLED`, `ATR_CALIBRATION_METHOD`, `ATR_FLOOR`, `ATR_CEIL_HARD`, `ATR_CEIL_FALLBACK`, `ATR_CEIL_MULT`, `ATR_CALIBRATION_WINDOW_DAYS`, `TEMP_TIME_GUARD_SPRINT2`, `SAFE_MODE_TIMEOUT_MIN`) + Sprint 1(`SECONDARY_POOL_FALLBACK_THRESHOLD=5`, `SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP=5`, `AUTO_ROLLBACK_R{1..4}_ENABLED`, `CIRCUIT_BREAKER_*`)

## 2026-04-28

- Phase 8.5 5거래일 관찰 종결 — 분기 D 확정(`auto_rollback_2d_zero_signals` 발동, 4거래일 본 신호 1건 / 폴백 605회). 후속 작업 Phase 8.6(신호 생성 로직 구조 재설계)로 이관

## 2026-04-29 (Sprint 1)

- Phase 8.6 Sprint 1 완료(PR #181, develop 머지) 반영: 선행 패치 + DoR 가드레일 G1·G2·G3 + Phase 7.0 LIVE 파라미터 `Final` 코드 잠금. 폴백 임계 5종, `min_volume_floor` 09~11시 0.3 슬라이딩, `is_fallback` 메타데이터 신호→주문→체결 전파, 자동 롤백 R1~R4 OR 트리거(13 tests), 회로차단기(9 tests), `/api/v1/metrics/fallback-signal-rate`, `/api/v1/metrics/phase86-status`, 프론트엔드 fallback-signal-rate-card / auto-rollback-multi-trigger 카드 추가

## 2026-04-17

- 초기 wiki 생성: [[system-overview]], [[tech-stack]], [[module-structure]] 추가
- 데이터 수집 문서화: [[data-collection-flow]], [[kis-api]], [[websocket-management]], [[public-data-sources]]
- 스크리닝 문서화: [[screening-pipeline]], [[screening-factors]], [[scoring-system]]
- 매매 실행 문서화: [[trading-modes]], [[signal-generation]], [[momentum-breakout-strategy]], [[order-execution]], [[position-management]]
- 리스크 관리 문서화: [[risk-management]], [[position-sizing]]
- 인프라 문서화: [[deployment]], [[database-schema]], [[redis-usage]]
- API 연동 문서화: [[telegram-integration]], [[external-apis]]
- 개발 프로세스 문서화: [[development-workflow]], [[paper-vs-live]], [[trading-calendar]]
- Phase 7.2 Sprint 1 진행 중 — 장중 OHLC 파싱 수정 + 갭 분기 버그 수정
