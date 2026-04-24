# Phase 8: 즉시 착수 가능 개선 사항 통합 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-20, Sprint 재편성 2026-04-20)
> **ROADMAP 참조**: `ROADMAP.md` Phase 8
> **검토 리포트**:
>
> - `phase8-po-review.md` (정프로, PO)
> - `phase8-risk-review.md` (최리스크, 리스크관리)
> - `phase8-daytrader-review.md` (김단타, 단타 전문가)
> - `phase8-quant-review.md` (박퀀트, 퀀트 전문가)
> - **E2E + LIVE 게이트 (Sprint 3)**: Phase 7.0 검토 리포트 승계 — `../phase7.0/phase7.0-po-review.md`, `../phase7.0/phase7.0-risk-review.md`, `../phase7.0/phase7.0-daytrader-review.md`, `../phase7.0/phase7.0-api-review.md`

---

## 개요

데이터 축적 대기 없이 즉시 착수 가능한 개선 사항들을 **단일 Phase로 통합**한다. 사용자 지시(2026-04-20)에 따라 기존 Phase 7.1 초안(5분봉 가속도), Phase 7.2 확정 계획(매매 신호 0건 근본 원인), Phase 4.5 Sprint 2(시스템 관리 UI), Phase 5 Sprint 3 등을 재편성하여 실행한다.

2026-04-20 재정렬에서 **기존 Phase 7.0 Sprint 3 (E2E 검증 + LIVE 전환 게이트)를 Phase 8 Sprint 3으로 이관**하여, 다층 진입 로직이 반영된 최종 전략으로 E2E를 검증하도록 순서를 재구성했다. 이로써 **Sprint 번호 = 실행 순서**가 된다.

### 배경

- 2026-04-17 매매 신호 0건 문제 → Phase 7.2 확정 계획 수립 완료 (OHLC 파싱 + 다층 진입)
- Phase 4.5 Sprint 2 (시스템 관리 UI): 백엔드 완료, UI만 남음
- Phase 5 Sprint 3: 독립 작업 (성과 분석)
- 5분봉 가속도 지표: **박퀀트 권고로 Phase 9 Sprint 0으로 이관** — 지표 상관관계 + 통합 설계 이익
- Phase 7.0 Sprint 3 (E2E + LIVE 게이트): **본 Phase Sprint 3으로 이관** (2026-04-20) — Phase 7.0은 Sprint 1·2 완료로 종결

### 우선순위

1. **P0 (최우선)**: Sprint 1~3 — 매매 신호 복구 → 다층 진입 → E2E + LIVE 전환 게이트
2. **P1 (순차)**: Sprint 4·5 — LIVE 전환 후 운영 품질 개선 (관리 UI, 성과 분석)

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 ✅ | 장중 OHLC 파싱 + 갭 분기 수정 | H0STCNT0 OHLC 파싱, Redis 캐싱 확장, snapshot 조립 수정, 갭 분기 `breakout_ref = open_price` | 없음 |
| 2 ✅ | 다층 진입 조건 + 리스크 안전장치 | prev_close/prev_high/gap_open 3단계 분기, confidence 상한, 반 포지션, 일일 10건 한도, 13:00 시간 가드 | Sprint 1 + 2거래일 관찰 |
| 3 | **E2E 검증 + LIVE 전환 게이트** (Phase 7.0 Sprint 3 이관) | Paper E2E 1사이클, 5거래일 관찰, LIVE 초기 파라미터 적용 | Sprint 2 |
| 4 | 시스템 관리 UI | 스케줄러 상태/수동 제어/파이프라인 헬스 + 보유 포지션/청산 카운트다운/장 단계 | Sprint 3 (LIVE 전환 후 운영 가시성 확보) |
| 5 | 성과 분석 보강 | 일간/주간 PnL/승률/MDD/보유시간/시간대 분포 대시보드 | Sprint 4 완료 후 |

> **실행 원칙**: Sprint 번호 = 실행 순서. Sprint 1~3은 P0 순차 (매매 신호 복구 → LIVE 게이트). Sprint 4·5는 LIVE 전환 이후 운영 품질 개선. 전문가 리뷰 수용(정프로 P1, 김단타 D2).

---

## 검토팀 확정 파라미터 (2026-04-20)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 김단타(단타), 박퀀트(퀀트), 윤에이피(API) — 5명. Sprint 1·2는 기존 Phase 7.2 확정(2026-04-17) 승계. Sprint 3은 Phase 7.0 확정(2026-04-15) 승계.

### Sprint 1: 데이터 인프라 수정 (기존 Phase 7.2 Sprint 1 승계)

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | H0STCNT0 파싱 필드 | price/volume/CTTR 등 8필드 | + STCK_OPRC(idx 7), STCK_HGPR(idx 8), STCK_LWPR(idx 9) | 전원 동의 |
| 2 | Redis 캐싱 키 | `realtime:{code}:execution` | 기존 JSON에 `open_price`, `high`, `low` 추가 | 윤에이피 패턴 유지 |
| 3 | snapshot 조립 | open_price=prev_close 폴백 | Redis 실시간 값 우선, 미수신 시 폴백 | 전원 동의 |
| 4 | 갭 3%+ 분기 | `breakout_ref = snapshot.high` (자기돌파 버그) | `breakout_ref = snapshot.open_price` | 김단타+최리스크 |
| 5 | Sprint 1 배포 당일 검증 | 없음 | **Redis idx 매핑 오류 가능성, 1~2시간 모니터링 필수** | 김단타 |

### Sprint 2: 다층 진입 조건 (기존 Phase 7.2 Sprint 2 승계 + 리스크 보강)

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 6 | 진입 기준 | prev_high 단일 | prev_close(1단계) + prev_high(2단계) 다층 | 전원 합의 |
| 7 | prev_close confidence 상한 | 없음 | 0.75 | 최리스크 |
| 8 | prev_close momentum_score 스케일 | min(pct/5.0, 1.0) | min(pct/7.0, 1.0) * 0.7 | 박퀀트 |
| 9 | prev_close volume_threshold | breakout_pct 연동 (1.5~2.0) | 고정 2.5 | 박퀀트+김단타 |
| 10 | prev_close position_size | 100% | 50% (반 포지션) | 최리스크 |
| 11 | 갭 돌파 momentum_score 상한 | 1.0 | 0.85 | 박퀀트 |
| 12 | 일일 최대 거래 횟수 | 없음 | 10건/일 | 최리스크 |
| 13 | 13:00 이후 prev_close 돌파 | 허용 | 비활성화 | 김단타 |
| 14 | 당일 고가 갱신 진입 | — | Phase 10.1로 이관 | 김단타+최리스크 |
| 15 | Sprint 1→2 관찰 기간 | 없음 | 최소 2거래일 | 정프로+김단타 |
| 16 | **LIVE 초기(Sprint 3 전) 한도** | 10건/일 | **3건/일, 포지션 1건 상한** | 최리스크 (R2) |

### Sprint 3: E2E 검증 + LIVE 전환 게이트 (기존 Phase 7.0 Sprint 3 승계)

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 17 | LIVE 초기 max_position | 3~5 | **2** | 최리스크+김단타 |
| 18 | LIVE 초기 position_size | 10% | **5%** | 최리스크+김단타 |
| 19 | LIVE 초기 daily_max_loss | -3% | **-2%** | 최리스크 |
| 20 | LIVE 초기 emergency_stop | -5% | **-3%** | 최리스크 |
| 21 | LIVE 초기 거래 모드 | auto | **semi-auto** | 전원 동의 |
| 22 | LIVE 초기 자본금 | 미지정 | **50만원 이하** | 최리스크 |
| 23 | Paper 관찰 기간 | 없음 | **5거래일 핫픽스 0건 + 일평균 신호 ≥ 1 + 0건 일수 ≤ 2/5** (Phase 8.5 재정의 D1~D7, Sprint 3 상세 표 참조) | 정프로+최리스크 |
| 24 | trade_strength_min 상향 시점 | 미지정 | LIVE 1주 관찰 후 결정 (100 → 110 검토) | 김단타+최리스크 |

### Sprint 4: 시스템 관리 UI

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 25 | UI 기본 범위 | 스케줄러 상태/수동 제어/pipeline_healthy | 유지 | 한유엑(검토 생략, 이미 합의) |
| 26 | 수동 트리거 가드 | 1단계 | **2단계 확인 + LIVE/PAPER 명시 + 이력 로깅** | 최리스크 (R1) |
| 27 | LIVE 중 수동 트리거 | 허용 | **장중 비활성화** (주문 중복 위험) | 최리스크 |
| 28 | 추가 UI 요청 | 없음 | **보유 포지션 카드 + 청산 카운트다운 + 장 단계** | 김단타 (D1) |

### Sprint 5: 성과 분석 보강

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 29 | 기본 지표 | PnL, 승률 | 유지 | 전원 동의 |
| 30 | MDD 계산 | 미명시 | **고점 대비 (peak-to-trough)** | 박퀀트 (Q2) |
| 31 | Sharpe 비율 | 미명시 | **무위험 수익률 KOFR 3.5% 기준** | 박퀀트 (Q3) |
| 32 | 표본 경고 | 없음 | **표본 < 30거래일 시 "참고용" 표시** | 박퀀트 (Q4) |
| 33 | 단타 특화 지표 | 없음 | **평균 보유 시간 + 시간대 진입 분포** | 김단타 (D2) |

---

## Sprint 1 상세 ✅ 완료 (PR #149, 2026-04-20) — 장중 OHLC 데이터 파싱 수정

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/collector/sources/kis_realtime.py` | `EXECUTION_FIELD_MAP`에 `open_price: 7`, `high: 8`, `low: 9` 추가. `ExecutionData` dataclass 필드 추가. `parse_execution()` 로직 확장 |
| `backend/modules/collector/scheduler.py` | WS 메시지 Redis 캐싱 시 3필드 추가 저장 |
| `backend/modules/screening/realtime_screener.py` | `_get_realtime_data()` 반환 dict에 3필드 포함 |
| `backend/modules/trading/signal_generator.py` | `_build_snapshot()`: Redis 실시간 값 우선 사용, 폴백 유지 |
| `backend/modules/trading/strategies/momentum_breakout.py` | 갭 3%+ 분기: `breakout_ref = snapshot.open_price` |
| `backend/tests/` | 파서/snapshot/갭 분기 테스트 |

### 재사용 자산

| 기존 모듈 | 재활용 내용 |
|----------|------------|
| `kis_realtime.py` | 기존 EXECUTION_FIELD_MAP 패턴 그대로 확장 |
| `scheduler.py` | 기존 Redis JSON 구조에 필드만 추가 |
| `kis_rest.py` | StockPrice.open_price/high/low 이미 REST에서 파싱 — 동일 필드명 통일 |

---

## Sprint 2 상세 — 다층 진입 조건 + 리스크 안전장치 ✅ 완료 (PR #157, 2026-04-22)

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/trading/strategies/momentum_breakout.py` | 3단계 기준점 로직: 갭 3%+ → open_price, 비갭 prev_close → 탐색적, 비갭 prev_high → 확신. breakout_tier 변수 도입. prev_close 시 momentum_score `min(pct/7.0,1.0)*0.7`, confidence 상한 0.75, volume_threshold 고정 2.5. reason에 `breakout_tier` 추가. 13:00 이후 prev_close 비활성화 |
| `backend/modules/trading/position_sizer.py` | `breakout_tier == "prev_close"` 시 position_size 50% |
| `backend/modules/trading/risk_manager.py` | `daily_trade_count` 카운터, 10건/일 초과 시 차단. Sprint 3(LIVE 게이트) 전 임시 3건/일 환경변수 가드 |
| `backend/modules/trading/engine.py` | 주문 제출 전 `check_daily_trade_limit()` 호출 |
| `backend/tests/` | 분기 테스트, confidence 상한, 반 포지션, 거래 한도, 13:00 가드 |

### 재사용 자산

| 기존 모듈 | 재활용 내용 |
|----------|------------|
| `momentum_breakout.py` | 기존 4팩터 confidence 프레임워크 유지, momentum_score 스케일만 변경 |
| `position_sizer.py` | 기존 `calc_quantity()`에 tier 기반 size 조정만 추가 |
| `risk_manager.py` | 기존 `daily_loss_count`, `consecutive_losses` 패턴과 동일 |

---

## Sprint 3 상세 — E2E 검증 + LIVE 전환 게이트 (Phase 7.0 Sprint 3 이관)

### 목적

Sprint 1·2로 복구된 다층 진입 로직이 실제 매매 파이프라인에서 **주문→체결→포지션→가격갱신→청산** 전체 사이클을 완주하는지 Paper 모드에서 검증하고, LIVE 전환 게이트를 통과한다. 구 Phase 7.0 Sprint 3의 E2E 체크리스트와 LIVE 초기 파라미터를 그대로 승계한다.

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
| 11 | **다층 진입 분기 동작 (Sprint 2)** | prev_close/prev_high/gap_open 세 경로 각 1회+ | ⬜ |
| 12 | **일일 10건 한도 (Sprint 2)** | 10건 초과 차단 확인 | ⬜ |

### LIVE 전환 게이트 기준 (Phase 8.5 재정의 — 2026-04-22)

> 원안 DoD("신호 발생 3거래일 연속" + "다층 진입 분기 각 1회+")는 2차 스크리닝 교차 단절 구조에서 논리적 달성 불가로 폐기. Phase 8.5 `phase8.5.md` Line 131~141 전문가 4명(PO/리스크/퀀트/단타) 합의로 D1~D7 재정의.

| # | 조건 | 기준 | 상태 |
|---|------|------|------|
| D1 | Paper 5거래일 관찰 기간 | 필수 | ⬜ |
| D2 | 일평균 신호 발생 수 ≥ 1 | 5일 합 ≥ 5 | ⬜ |
| D3 | 신호 0건 일수 ≤ 2/5 | 0건 비율 ≤ 40% | ⬜ |
| D4 | tier 다양성 | 최소 2개 tier 각 1회+ (gap_open 필수 아님) | ⬜ |
| D5 | 손절 체결 경험 | 최소 1회 (LIVE 첫날 손절 로직 검증) | ⬜ |
| D6 | Paper 핫픽스 0건 | 5거래일 연속 (원안 계승) | ⬜ |
| D7 | 신호 0건 3거래일 연속 | 자동 중단 + 재검토 트리거 (최리스크 D4) | ⬜ |
| D8 | 포지션 생명주기 완전 | 주문→체결→포지션→가격갱신→청산 1회+ 성공 | ⬜ |
| D9 | Sprint 1·2 전부 머지 | main 브랜치 반영 확인 | ⬜ |
| D10 | LIVE 초기 파라미터 적용 | 확정 파라미터 #17~#22 settings 테이블 반영 | ⬜ |

### LIVE 전환 절차

1. LIVE 게이트 전 조건 충족 확인
2. `TRADING_ENV=live` 환경변수 변경 (Railway)
3. KIS 실전 APP_KEY/SECRET 확인
4. settings 테이블에 LIVE 초기 파라미터 반영 (max_position_count=2, position_size_pct=5, daily_max_loss=-2%, emergency_stop=-3%)
5. 거래 모드 `semi-auto` 확인
6. 첫 거래일 실시간 모니터링 (텔레그램 알림 수신 확인)

### 재사용 자산

| 기존 모듈 | 재활용 내용 |
|----------|------------|
| Phase 7.0 Sprint 1·2 구현 | 가격 갱신, 체결 콜백, 청산 실행, 이중 주문 방지, trailing Redis 이관 모두 완료 |
| `diagnose_ws.py` | Phase 7.0.1 완료로 LIVE WS 연결 검증 이미 확보 |
| Phase 8 Sprint 1·2 구현 | OHLC 파싱 + 다층 진입 로직 |

---

## Sprint 4 상세 — 시스템 관리 UI

### 목적

Phase 4.5 Sprint 1에서 구축한 pipeline_healthy 플래그, 스케줄러 헬스 API, 수동 트리거 엔드포인트에 대응하는 **관리 UI**를 제공. LIVE 전환(Sprint 3) 이후 운영 가시성 확보.

### 범위 (김단타 D1 + 최리스크 R1 반영)

1. 스케줄러 상태 대시보드 (`/admin/scheduler`)
2. pipeline_healthy 플래그 + 사유 조회
3. 수동 트리거 버튼 (2단계 확인 + LIVE/PAPER 명시 + 이력 로깅)
4. 최근 파이프라인 실행 이력
5. **보유 포지션 실시간 현황 카드** (시가/현재가/PnL%/경과시간)
6. **청산 카운트다운** (14:50 기준)
7. **장 단계 배지** (장전/시초30분/장중/마감30분 전/마감 임박)

### 프론트엔드

| 파일 | 수정 내용 |
|------|----------|
| `frontend/app/admin/scheduler/page.tsx` | 스케줄러 상태 대시보드 신규 |
| `frontend/components/admin/PipelineHealthCard.tsx` | pipeline_healthy 카드 |
| `frontend/components/admin/ManualTriggerPanel.tsx` | 수동 트리거 + 2단계 확인 모달 |
| `frontend/components/trading/PositionMonitorCard.tsx` | 보유 포지션 실시간 카드 |
| `frontend/components/trading/SessionCountdown.tsx` | 청산/장 단계 표시 |
| `frontend/hooks/useSchedulerHealth.ts` | 헬스 API SWR 훅 |
| `frontend/hooks/usePositions.ts` | 보유 포지션 SWR 훅 (폴링 10초) |

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/api/v1/admin/scheduler.py` | 수동 트리거에 `confirmation_token` + `mode` 검증 + 이력 로깅 |
| `backend/api/v1/admin/scheduler.py` | 장중(09:00~15:30) 수동 트리거 비활성화 가드 |
| `backend/modules/audit/admin_log.py` | 관리 액션 이력 기록 (신규) |

---

## Sprint 5 상세 — 성과 분석 보강

### 목적

LIVE 전환 후 매매 결과 검증이 가능하도록 일간/주간 성과 리포트를 구축한다.

### 범위 (박퀀트 Q2~Q4 + 김단타 D2 반영)

1. 일간/주간 PnL 집계 배치 (EOD)
2. 모드별(PAPER/LIVE) 분리 리포트
3. 대시보드 성과 페이지 (`/dashboard/performance`)
4. 지표: 승률, 평균 수익률, **MDD(peak-to-trough)**, **Sharpe(KOFR 3.5%)**, **평균 보유 시간**, **시간대별 진입 분포**
5. **표본 < 30거래일 시 "참고용" 경고 표시**

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/analytics/performance_aggregator.py` | PnL/승률/MDD/Sharpe/보유시간 일간 집계 (신규) |
| `backend/modules/analytics/scheduler.py` | EOD 15:40 집계 배치 등록 |
| `backend/api/v1/performance.py` | 성과 조회 API (일간/주간/모드별) |
| `backend/tests/analytics/` | 집계 로직 단위 테스트 |

### 프론트엔드

| 파일 | 수정 내용 |
|------|----------|
| `frontend/app/dashboard/performance/page.tsx` | 성과 대시보드 페이지 |
| `frontend/components/performance/PnLChart.tsx` | 일간 누적 PnL 차트 |
| `frontend/components/performance/MetricsCards.tsx` | 승률/평균/MDD/Sharpe 카드 |
| `frontend/components/performance/EntryTimeHeatmap.tsx` | 시간대별 진입 분포 히트맵 |
| `frontend/components/performance/SampleSizeWarning.tsx` | 30거래일 미만 경고 배너 |

### 재사용 자산

- Phase 3 완전 자동 모드의 `trades` 테이블
- Phase 4 대시보드 Recharts 컴포넌트

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 담당 | 배치 |
|---|------|--------|------|------|
| 1 | Sprint 1 OHLC 수정만으로 신호 발생 가능성 | 정보 | 김단타 | Sprint 1 배포 후 2거래일 관찰, Sprint 2 범위 조정 가능 |
| 2 | prev_close 돌파 후 prev_high 저항 반락 | ⚠️ | 최리스크 | 반 포지션(50%) + confidence 상한(0.75) |
| 3 | 10:30~13:00 횡보 구간 false positive | ⚠️ | 김단타 | volume_threshold 2.5 고정, 관찰 후 조정 |
| 4 | 2차 스크리닝 N=1 상대 백분위 | 정보 | 박퀀트 | Phase 10.1에서 하이브리드로 근본 해결 |
| 5 | ~~Sprint 2 생략 시 LIVE 한도 축소~~ | ~~⚠️~~ | ~~최리스크~~ | ✅ 해결 — Sprint 2에서 3건/일 환경변수 오버라이드 구현 완료 (2026-04-22) |
| 6 | 5분봉 가속도 지표 Phase 이관 | 정보 | 박퀀트 | Phase 9 Sprint 0으로 이관 완료 (본 문서에서 제외) |
| 7 | `signal_generator.py` `_build_snapshot()` 독스트링 불일치 (Medium) | ⬜ | sprint-review | Sprint 2에서 개선 권장 — 실제 동작(실시간 OHLC 우선)과 맞게 수정. 기능 버그 없음 |
| 8 | 모의/실전 체결가 차이 | ⚠️ | 윤에이피 | Phase 7.0 Sprint 1에서 역산 구현, Sprint 3 LIVE 전환 시 검증 |
| 9 | REST 폴백 시 Rate Limit 증가 | ⚠️ | 윤에이피 | throttler 공유 인스턴스로 관리 |
| 10 | 부분 체결 reconciliation | ⚠️ | 윤에이피 | cancel 실패 시 return 채택으로 리스크 완화, 별도 Phase에서 고도화 |
| 11 | LIVE 전환 시 tr_id 접두사 전환 | ⚠️ | 윤에이피 | 기존 settings.TRADING_ENV 기반 자동 전환 확인 |
| 12 | LIVE 첫 주 슬리피지 | ⚠️ | 김단타 | semi-auto 모드로 수동 관찰 |
| 13 | trade_strength_min 100 → 110 상향 시점 | 정보 | 김단타+최리스크 | LIVE 1주 관찰 후 결정 (Sprint 3 이후) |
| 14 | `/screening/secondary` API 날짜 필터 누락 | 정보 | — | 오늘 통과 종목 없으면 어제 마지막 레코드 반환. 거래 로직 무관, 운영 가시성 혼란 유발. Sprint 3 이후 수정 |
| 15 | `secondary_last_run` Redis 미저장 | 정보 | — | 2차 스크리닝 실행 시각을 Redis에 저장하지 않아 collector/status API에서 null 표시. 거래 로직 무관. Sprint 3 이후 수정 |
| 16 | 2차 스크리닝 상대 백분위 스코어 — N=1 시 무의미 | 정보 | — | 필터 통과 종목 1개 시 모든 팩터 100점 자동 부여. 거래 신호 자체는 정상이나 품질 구분 불가. Sprint 3 이후 절대값 기반 스코어링 혼합 검토 |

---

## 실행 순서 요약

```
Phase 8 Sprint 1 ✅ (OHLC 수정, PR #149 배포)
  → 2거래일 관찰 (Sprint 1 단독으로 신호 발생 여부)
    → Sprint 2 (다층 진입 + 리스크 안전장치)
      → Sprint 3 (Paper E2E 1사이클 + 5거래일 관찰 → LIVE 전환 게이트)
        → LIVE 초기 한도 운영
          → Sprint 4 (관리 UI, 운영 가시성 확보)
            → Sprint 5 (성과 분석 — LIVE 데이터 기반)
```

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| H0STCNT0 OHLC 파싱 | Redis 시가/고가/저가 저장 확인 | ✅ 완료 (PR #149) |
| snapshot 정합성 | open_price/high/low 실시간 값 조립 | ✅ 완료 (PR #149) |
| 갭 분기 정상 동작 | 갭 3%+ open_price 기준 판정 | ✅ 완료 (PR #149) |
| 매매 신호 생성 | 2거래일 연속 1건+ (노이즈 필터 후) | ⬜ 배포 후 관찰 중 |
| 다층 진입 구현 | prev_close/prev_high 2단계 + gap | ⬜ |
| confidence 계층화 | prev_close 돌파 ≤ 0.75 | ⬜ |
| 반 포지션 적용 | prev_close 돌파 50% | ⬜ |
| 일일 거래 한도 | 10건 초과 차단 (Sprint 2 전 3건) | ⬜ |
| 13:00 시간 가드 | prev_close 비활성화 | ⬜ |
| E2E 1사이클 성공 | 주문→체결→포지션→가격갱신→청산 완전 성공 | ⬜ |
| Paper 5거래일 안정 | 핫픽스 0건 + 일평균 신호 ≥ 1 + 0건 일수 ≤ 2/5 (Phase 8.5 D1~D7 재정의) | ⬜ |
| LIVE 전환 게이트 통과 | 전 조건 충족 | ⬜ |
| 시스템 관리 UI | 스케줄러 + 2단계 가드 + 포지션/카운트다운/장 단계 | ⬜ |
| 성과 분석 | PnL/승률/MDD/Sharpe/보유시간/시간대 분포 | ⬜ |
| pytest 전체 통과 | 기존 + 신규 테스트 | ✅ 완료 (854 passed, 1 pre-existing fail) |
