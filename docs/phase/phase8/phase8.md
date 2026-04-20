# Phase 8: 즉시 착수 가능 개선 사항 통합 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-20)
> **ROADMAP 참조**: `ROADMAP.md` Phase 8
> **검토 리포트**:
>
> - `phase8-po-review.md` (정프로, PO)
> - `phase8-risk-review.md` (최리스크, 리스크관리)
> - `phase8-daytrader-review.md` (김단타, 단타 전문가)
> - `phase8-quant-review.md` (박퀀트, 퀀트 전문가)

---

## 개요

데이터 축적 대기 없이 즉시 착수 가능한 개선 사항들을 **단일 Phase로 통합**한다. 사용자 지시(2026-04-20)에 따라 기존 Phase 7.1 초안(5분봉 가속도), Phase 7.2 확정 계획(매매 신호 0건 근본 원인), Phase 4.5 Sprint 2(시스템 관리 UI), Phase 5 Sprint 3 등을 재편성하여 실행한다.

### 배경

- 2026-04-17 매매 신호 0건 문제 → Phase 7.2 확정 계획 수립 완료 (OHLC 파싱 + 다층 진입)
- Phase 4.5 Sprint 2 (시스템 관리 UI): 백엔드 완료, UI만 남음
- Phase 5 Sprint 3: 독립 작업 (성과 분석)
- 5분봉 가속도 지표: **박퀀트 권고로 Phase 9 Sprint 0으로 이관** — 지표 상관관계 + 통합 설계 이익

### 우선순위

1. **P0 (최우선)**: Sprint 1~2 — 매매 신호 0건 해결, LIVE 게이트 선행 조건
2. **P1 (순차)**: Sprint 3·4 — Sprint 1 배포 후 순차 실행 (1명 개발자 컨텍스트 분산 방지)

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 | 장중 OHLC 파싱 + 갭 분기 수정 | H0STCNT0 OHLC 파싱, Redis 캐싱 확장, snapshot 조립 수정, 갭 분기 `breakout_ref = open_price` | 없음 |
| 2 | 다층 진입 조건 + 리스크 안전장치 | prev_close/prev_high/gap_open 3단계 분기, confidence 상한, 반 포지션, 일일 10건 한도, 13:00 시간 가드 | Sprint 1 + 2거래일 관찰 |
| 3 | 시스템 관리 UI | 스케줄러 상태/수동 제어/파이프라인 헬스 + 보유 포지션/청산 카운트다운/장 단계 | Sprint 1 배포 후 순차 |
| 4 | 성과 분석 보강 | 일간/주간 PnL/승률/MDD/보유시간/시간대 분포 대시보드 | Sprint 3 완료 후 |

> **실행 원칙**: Sprint 1·2는 순차 P0. Sprint 3·4는 Sprint 1 배포 + Phase 7.0 Sprint 3 E2E 검증 재개 후 순차 진행. 전문가 리뷰 수용(정프로 P1, 김단타 D2).

---

## 검토팀 확정 파라미터 (2026-04-20)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 김단타(단타), 박퀀트(퀀트) — 4명. Sprint 1·2는 기존 Phase 7.2 확정(2026-04-17) 승계.

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
| 16 | **LIVE 초기(Sprint 2 전) 한도** | 10건/일 | **3건/일, 포지션 1건 상한** | 최리스크 (R2) |

### Sprint 3: 시스템 관리 UI

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 17 | UI 기본 범위 | 스케줄러 상태/수동 제어/pipeline_healthy | 유지 | 한유엑(검토 생략, 이미 합의) |
| 18 | 수동 트리거 가드 | 1단계 | **2단계 확인 + LIVE/PAPER 명시 + 이력 로깅** | 최리스크 (R1) |
| 19 | LIVE 중 수동 트리거 | 허용 | **장중 비활성화** (주문 중복 위험) | 최리스크 |
| 20 | 추가 UI 요청 | 없음 | **보유 포지션 카드 + 청산 카운트다운 + 장 단계** | 김단타 (D1) |

### Sprint 4: 성과 분석 보강

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 21 | 기본 지표 | PnL, 승률 | 유지 | 전원 동의 |
| 22 | MDD 계산 | 미명시 | **고점 대비 (peak-to-trough)** | 박퀀트 (Q2) |
| 23 | Sharpe 비율 | 미명시 | **무위험 수익률 KOFR 3.5% 기준** | 박퀀트 (Q3) |
| 24 | 표본 경고 | 없음 | **표본 < 30거래일 시 "참고용" 표시** | 박퀀트 (Q4) |
| 25 | 단타 특화 지표 | 없음 | **평균 보유 시간 + 시간대 진입 분포** | 김단타 (D2) |

---

## Sprint 1 상세 — 장중 OHLC 데이터 파싱 수정

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

## Sprint 2 상세 — 다층 진입 조건 + 리스크 안전장치

### 백엔드

| 파일 | 수정 내용 |
|------|----------|
| `backend/modules/trading/strategies/momentum_breakout.py` | 3단계 기준점 로직: 갭 3%+ → open_price, 비갭 prev_close → 탐색적, 비갭 prev_high → 확신. breakout_tier 변수 도입. prev_close 시 momentum_score `min(pct/7.0,1.0)*0.7`, confidence 상한 0.75, volume_threshold 고정 2.5. reason에 `breakout_tier` 추가. 13:00 이후 prev_close 비활성화 |
| `backend/modules/trading/position_sizer.py` | `breakout_tier == "prev_close"` 시 position_size 50% |
| `backend/modules/trading/risk_manager.py` | `daily_trade_count` 카운터, 10건/일 초과 시 차단. Sprint 2 완료 전 임시 3건/일 환경변수 가드 |
| `backend/modules/trading/engine.py` | 주문 제출 전 `check_daily_trade_limit()` 호출 |
| `backend/tests/` | 분기 테스트, confidence 상한, 반 포지션, 거래 한도, 13:00 가드 |

### 재사용 자산

| 기존 모듈 | 재활용 내용 |
|----------|------------|
| `momentum_breakout.py` | 기존 4팩터 confidence 프레임워크 유지, momentum_score 스케일만 변경 |
| `position_sizer.py` | 기존 `calc_quantity()`에 tier 기반 size 조정만 추가 |
| `risk_manager.py` | 기존 `daily_loss_count`, `consecutive_losses` 패턴과 동일 |

---

## Sprint 3 상세 — 시스템 관리 UI

### 목적

Phase 4.5 Sprint 1에서 구축한 pipeline_healthy 플래그, 스케줄러 헬스 API, 수동 트리거 엔드포인트에 대응하는 **관리 UI**를 제공.

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

## Sprint 4 상세 — 성과 분석 보강

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
| 5 | Phase 7.0 Sprint 3 선후관계 | ⚠️ | 정프로 | Sprint 1 완료 후 Phase 7.0 Sprint 3 재개 |
| 6 | Sprint 2 생략 시 LIVE 한도 축소 | ⚠️ | 최리스크 | 3건/일, 포지션 1건 상한 환경변수 |
| 7 | 5분봉 가속도 지표 Phase 이관 | 정보 | 박퀀트 | Phase 9 Sprint 0으로 이관 완료 (본 문서에서 제외) |

---

## Phase 7.0 Sprint 3과의 관계

```
실행 순서:
Phase 8 Sprint 1 (OHLC 수정) → 2거래일 관찰
  → 신호 발생 OK → Phase 7.0 Sprint 3 (E2E) 재개 → LIVE 초기(3건/일)
  → Phase 8 Sprint 2 (다층 진입) 완료 → LIVE 정상 한도(10건/일)
  → Phase 8 Sprint 3 (관리 UI) → Sprint 4 (성과 분석)
```

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| H0STCNT0 OHLC 파싱 | Redis 시가/고가/저가 저장 확인 | ⬜ |
| snapshot 정합성 | open_price/high/low 실시간 값 조립 | ⬜ |
| 갭 분기 정상 동작 | 갭 3%+ open_price 기준 판정 | ⬜ |
| 매매 신호 생성 | 2거래일 연속 1건+ (노이즈 필터 후) | ⬜ |
| 다층 진입 구현 | prev_close/prev_high 2단계 + gap | ⬜ |
| confidence 계층화 | prev_close 돌파 ≤ 0.75 | ⬜ |
| 반 포지션 적용 | prev_close 돌파 50% | ⬜ |
| 일일 거래 한도 | 10건 초과 차단 (Sprint 2 전 3건) | ⬜ |
| 13:00 시간 가드 | prev_close 비활성화 | ⬜ |
| 시스템 관리 UI | 스케줄러 + 2단계 가드 + 포지션/카운트다운/장 단계 | ⬜ |
| 성과 분석 | PnL/승률/MDD/Sharpe/보유시간/시간대 분포 | ⬜ |
| pytest 전체 통과 | 기존 + 신규 테스트 | ⬜ |
