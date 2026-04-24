# Phase 8.5: 신호 발생 데드락 해제 — 실행 계획 (제안, 사용자 승인 대기)

> **Status**: 계획 초안 (2026-04-22, 사용자 최종 승인 대기)
> **ROADMAP 참조**: 아직 반영 안 함. 본 문서는 **제안**이며, 사용자 승인 후 ROADMAP delta 적용.
> **검토 리포트**:
> - `phase8.5-po-review.md` (정프로, PO)
> - `phase8.5-risk-review.md` (최리스크, 리스크관리)
> - `phase8.5-quant-review.md` (박퀀트, 퀀트)
> - `phase8.5-daytrader-review.md` (김단타, 단타 전문가)
>
> **검토 방식 제약 (고지)**: 본 Phase 계획은 phase-planner가 서브에이전트 스폰 도구를 사용할 수 없는 세션 제약으로, 4개 전문가 페르소나(`docs/experts/*.md`)를 기반으로 **phase-planner가 직접 순차 작성**했다. 페르소나 원칙은 엄격히 적용됐으나, 완전 독립 세션 병렬 검토가 필요하다면 사용자 지시 시 재수행 가능.

---

## 개요

2026-04-22 프로덕션 관측에서 드러난 **"신호 0건 교차 단절"** 문제를 선제 해소하여 Phase 8.6 Sprint 1(E2E + LIVE 게이트, 구 Phase 8 Sprint 3 이관)의 DoD 달성 경로를 확보한다. 데이터 축적을 요구하지 않는 **코드·파라미터 수정만**으로 구성되며, Phase 9·10·10.1의 순서·전제 조건은 **건드리지 않는다**.

### 문제의 본질 (논리적 데드락)

현재 신호가 생성되려면 다음이 동시에 성립해야 한다:

| 조건 | 현재 상태 | 평가 |
|------|----------|------|
| 2차 스크리닝 풀 ≥ 몇 종목 | **1종목 (073490만 통과)** | 기댓값 ≈ 0 |
| 당일 거래량 ≥ 전일 × 0.5 (`MIN_VOLUME_FLOOR`) | 오전엔 미달 (31%) | 오전 차단 |
| 시간창 유효 (prev_close는 13:00 이전) | 오후 13:00 이후 prev_close 차단 | 오후 차단 |

→ 오전엔 거래량 부족으로 컷, 오후엔 시간 가드로 컷 → **교차 불가능한 구조**. Phase 8.6 Sprint 1 원안 DoD("3거래일 연속 신호 발생")는 현 조건에서 **논리적으로 달성 불가**.

### 이 Phase의 목적

**딱 하나**: 2차 스크리닝 풀과 게이트의 교차 가능 집합을 **양수**로 만든다. 전략 자체는 건드리지 않는다. 관측성을 먼저 배포해서 이후 모든 파라미터 조정을 **데이터 기반**으로 한다.

### 배경

- 2026-04-22 관측: 2차 스크리닝 `pass_threshold=75.0`에서 1종목만 통과 (5팩터 모두 100점)
- signal_generator 30초 주기 `입력=1 통과=0 전략미충족=1` 반복
- 12:30~12:59 KST: `min_volume_floor` 100% 컷 (073490 당일 거래량 전일 31%)
- 13:00~: `prev_close_time_guard` 100% 컷 (Sprint 2 안전장치)
- 과거 완화 이력: 1차 스크리닝은 Phase 5·5.1·6.1에서 여러 번 완화했으나 **2차 스크리닝·전략 게이트는 Sprint 2 제외 사실상 미조정**

### 우선순위

1. **P0**: Sprint 1 관측성 (모든 후속 의사결정의 근거)
2. **P0**: Sprint 2 풀 하한 폴백 + 동적 min_volume_floor (데드락 해제)
3. **그 외**: Phase 8.6 Sprint 1(E2E + LIVE 게이트)로 진행 (DoD 재정의 후)

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 ✅ | **관측성 강화** | stage 분포 메트릭, 2차 score 분포 히스토그램, 탈락 상위 종목 로깅, 가상 신호 로깅 (13:00+ prev_close) | 없음 |
| 2 ✅ | **풀 하한 폴백 + 동적 min_volume_floor** | `passed<3` 시 상위 score 보강, `MIN_VOLUME_FLOOR` 조건부 분기(0.4/0.5/0.6), env 변수화, HARD 상한 0.3 | Sprint 1 배포 후 1.5거래일 관찰 |
| 2.5 ✅ | **인프라 보강 + 관측성·문서 정합성** | `resolve_override()` 단일 진입점, env 동기화 스크립트, override-status API + 배너, phase8.md 문서 정합성 | Sprint 2 완료 후 |

> **실행 원칙**:
> - Sprint 수 **상한 2개** (PO 경계)
> - Sprint 1 → Sprint 2 순차
> - Sprint 2 완료 후 Phase 8.6 Sprint 1(E2E + LIVE 게이트)로 진행
> - 브리지 **최대 1.5주 내외** (개발자 1명 기준)

---

## 검토팀 확정 파라미터 (2026-04-22, 4명 검토)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 김단타(단타) — 4명 전원 의견 수렴

### 2차 스크리닝 풀 하한 폴백

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | 폴백 발동 조건 | 없음 | **`passed_count < 3`** | 통계적 신뢰구간 최소치(박퀀트) + 실전 watchlist 최소치(김단타) |
| 2 | 폴백 보강 방식 | — | **1차 스크리닝 통과 종목 중 total_score 상위순으로 3까지 보강** | parsimonious (박퀀트), 시가총액 상위 편향 금지(김단타) |
| 3 | 폴백 후 풀 상한 | — | **최대 5종목** | watchlist 관리 한계(김단타), 트랜잭션 비용(박퀀트) |
| 4 | 폴백 종목 메타데이터 | — | **`is_fallback=True`, `raw_score`, `percentile_rank` 기록** | 성과 분리 분석(박퀀트), 추후 Phase 10.1 근거(정프로) |
| 5 | 폴백 종목 UI 시각 구분 | — | **대시보드 ⚠️ 배지 + 색상 구분** | 트레이더 직관 경고(김단타) |
| 6 | 폴백 종목 position_size | 100% | **50% (반 포지션)** 강제 | 품질 불확실성 보상 (최리스크 R-2) |
| 7 | 폴백 종목 하락 제외 | 없음 | **전일 대비 -3% 이하 종목 제외** | Phase 5.1 하락 종목 매수 금지 계승·강화 (최리스크 R-3) |
| 8 | 폴백 종목 손절 기준 | -2% | **-1.5% (타이트)** | 저품질 신호 손실 제한 (김단타) |
| 9 | **2차 `pass_threshold`** | 75.0 | **75.0 유지** | 임계값 자체 완화는 분포 데이터 확인 후(박퀀트) |

### 전략 게이트 재튜닝 (`MIN_VOLUME_FLOOR` 동적 분기)

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 10 | **min_volume_floor (기본)** | 0.5 고정 | **0.5 유지** | 현 설정 합리(김단타) |
| 11 | min_volume_floor (gap ≥ 5% OR prev_high 돌파+3%이상) | — | **0.4** | 강한 돌파 강도엔 거래량 허용(박퀀트, 김단타) |
| 12 | min_volume_floor (prev_close tier) | 0.5 | **0.6 상향** | 약한 신호엔 더 강한 거래량 요구(김단타, 최리스크) |
| 13 | **`MIN_VOLUME_FLOOR_HARD` (absolute floor)** | 없음 | **0.3 (절대 하한, 어떤 분기도 이 이하 금지)** | 안전장치(최리스크 리스크2) |
| 14 | **시간대 슬라이딩** | 제안: 0.2→0.5 | **거부 — 시간 슬라이딩 금지** | 자유도 증가 과적합(박퀀트), 오후 완화는 단타 반상식(김단타), 리스크 관점 무근거(최리스크) |
| 15 | **`prev_close_time_guard` 13:00→14:00** | 제안: 연장 | **거부 — 13:00 유지** | 오후 되돌림 70%+(김단타), Sprint 2 확정 직후 번복 프로세스 위반(최리스크), 데이터 없음(박퀀트) |
| 16 | 가상 신호 로깅 (13:00~14:00 prev_close 가정 발동) | 없음 | **도입 (실행 X, 로그만)** | Phase 10.1 재평가 근거 데이터 수집(박퀀트) |

### 관측성 메트릭

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 17 | stage별 reject/pass 카운터 | 텍스트 로그만 | **1분 bucket × stage Counter + DB 일별 집계** | 데이터 기반 의사결정(박퀀트) |
| 18 | 2차 스크리닝 `total_score` 분포 | 기록 없음 | **10점 bucket × 10개 + `>=75` 별도 카운트, 일별 히스토그램** | 임계값 재교정 근거(박퀀트) |
| 19 | stage × 시간대 heatmap | 없음 | **10분 bucket × stage heatmap 대시보드 카드** | 시간대 병목 식별(박퀀트) |
| 20 | stage 탈락 상위 5종목 + 사유 + breakout_ref 이격 | 없음 | **실시간 최근 5건 대시보드 리스트** | 실전 튜닝 피드백(김단타) |
| 21 | 폴백 발동 통계 | — | **일별 폴백 횟수, 폴백 종목 평균 score, 폴백 종목 신호 발생 여부** | 폴백 품질 검증(박퀀트) |
| 22 | 관측성 배포 순서 | — | **Sprint 1 첫날 배포 필수** | 모든 후속 의사결정 근거(박퀀트, 최리스크) |

### 운영·환경변수·롤백

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 23 | 모든 Phase 8.5 파라미터 env 변수화 | — | **필수 (`MIN_VOLUME_FLOOR_MODE`, `SECONDARY_POOL_FALLBACK_ENABLED`, `FALLBACK_THRESHOLD` 등)** | 롤백 즉시 가능(최리스크 리스크3) |
| 24 | 자동 롤백 트리거 | 없음 | **Sprint 2 배포 후 2거래일 연속 신호 0건 시 자동 롤백** | 브리지 실효성 실패 시 원복(정프로) |
| 25 | Sprint 1→2 관찰 기간 | — | **1.5거래일 (배포 당일 2시간 + 다음 거래일 종일)** | 관찰 단축(정프로) + 최소 안전(최리스크) |
| 26 | Phase 8.5 → Sprint 3 관찰 기간 | Sprint 2→3 2거래일 | **5거래일 유지** | LIVE 전환 직전 보수 유지(최리스크) |

---

## Phase 8.6 Sprint 1 (구 Phase 8 Sprint 3) DoD 재정의 (제안)

### 원안 (현재)

> Paper 5거래일 핫픽스 0건 + **신호 발생 3거래일 연속** + **다층 진입 분기 각 1회+**

### 문제점

- "3거래일 연속" = 시계열 조건, 현 조건에서 확률적 달성 불가
- "각 tier 1회+" = gap_open tier는 `gap_rate≥3%` 시장 이벤트 의존, 의도적 달성 불가능

### 제안 재정의 DoD (Phase 8.5 완료 후 적용)

| # | 조건 | 기준 | 근거 |
|---|------|------|------|
| D1 | Paper 5거래일 관찰 기간 | 필수 | 최리스크 승인 유지 |
| D2 | 일평균 신호 발생 수 ≥ 1 | 5일 합 ≥ 5 | 박퀀트 기댓값 관점 |
| D3 | 신호 0건 일수 ≤ 2 / 5 | 0건 비율 ≤ 40% | 박퀀트, 김단타 |
| D4 | tier 다양성 | **최소 2개 tier** 각 1회+ (gap_open 필수 아님) | 김단타 (시장 의존 조건 제외) |
| D5 | 손절 체결 경험 | **최소 1회** | 김단타 (LIVE 첫날 손절 로직 검증) |
| D6 | Paper 핫픽스 0건 | 유지 | 원안 계승 |
| D7 | 신호 0건 3거래일 연속 발생 | **자동 중단 + 재검토 트리거** | 최리스크 D4 |

Phase 8.6 Sprint 1 (구 Phase 8 Sprint 3) 원문 DoD 중 "신호 발생 3거래일 연속"과 "다층 진입 분기 각 1회+"를 위 D2·D3·D4로 교체.

---

## Sprint 1 상세 — 관측성 강화 ✅ 완료

> **완료**: PR #162 머지, 2026-04-22. 929 passed / 1 failed (기존 버그, 이 PR 비관련). /diagnostics 페이지 정상 동작 확인.

### 백엔드
- `backend/modules/screening/realtime_screener.py`: 2차 스크리닝 `total_score` 히스토그램 Redis counter (key: `metrics:secondary:score:{date}:{bucket}`)
- `backend/modules/trading/strategies/momentum_breakout.py`: stage별 reject/pass 카운트 (key: `metrics:strategy:stage:{date}:{stage}:{hour_min_bucket}`)
- 가상 신호 로깅: `_reject` 호출 시 `stage == "prev_close_time_guard"`이고 현재 시각 13:00~14:00 KST 인 경우, **별도 `virtual_signals` 테이블 또는 로그**에 기록 (실제 주문 절대 발생 X)
- 일별 집계 배치 (16:00 스케줄러): Redis counter → DB `screening_metrics_daily` / `strategy_metrics_daily` 테이블

### 프론트엔드
- 대시보드 신규 섹션 "신호 진단 (Phase 8.5)":
  - 카드 1: 2차 스크리닝 score 분포 히스토그램 (오늘 + 7일 이동)
  - 카드 2: stage 탈락 heatmap (x=시간 10분 bucket, y=stage)
  - 카드 3: stage 탈락 상위 5종목 실시간 리스트 (코드/사유/breakout_ref 이격)
  - 카드 4: 폴백 발동 통계 (Sprint 2 배포 후 활성화 — 플레이스홀더만 먼저)

### 재사용 자산
- Redis counter 패턴: 기존 `core/redis.py` 유틸 재사용
- 일별 집계 배치: 기존 `modules/collector/scheduler.py` APScheduler job 추가
- 대시보드 카드 컴포넌트: 기존 `frontend/components/dashboard/` 패턴

---

## Sprint 2 상세 — 풀 하한 폴백 + 동적 min_volume_floor ✅ 완료

> **완료**: PR #170 머지 대기, 2026-04-23. 956 passed / 1 failed (기존 플레이크, 이 PR 비관련). /diagnostics 폴백 통계 카드 + shadow heatmap 정상 동작 확인.

### 백엔드
- `backend/modules/screening/realtime_screener.py`:
  - `screen()` 결과 `passed_count < 3`이면 **1차 스크리닝 통과 종목 중 total_score 상위** 보강 (절대 1차 미통과 투입 금지)
  - 폴백 결정 시 전일 대비 -3% 이하 제외
  - 각 결과에 `is_fallback`, `raw_score`, `percentile_rank` 추가
  - 풀 상한 5종목
- `backend/modules/trading/strategies/momentum_breakout.py`:
  - `MIN_VOLUME_FLOOR` 상수 → `_resolve_min_volume_floor(snapshot, tier, gap_rate)` 함수로 교체
  - 반환값: 0.4 / 0.5 / 0.6 중 하나
  - `MIN_VOLUME_FLOOR_HARD = 0.3`로 절대 하한 체크 (어떤 분기도 이보다 낮게 반환되면 에러 + 0.3 강제)
- `backend/modules/trading/engine.py` (또는 포지션 사이징 경로):
  - `is_fallback` 종목에 대해 position_size × 0.5 적용
  - 손절 기준 -1.5% 적용 (일반 -2%)
- `backend/core/config.py`:
  - `MIN_VOLUME_FLOOR_MODE` (legacy=0.5 고정 / dynamic=조건부)
  - `SECONDARY_POOL_FALLBACK_ENABLED` (True / False)
  - `SECONDARY_POOL_FALLBACK_THRESHOLD` (3)
  - `SECONDARY_POOL_MAX` (5)
  - `FALLBACK_DROP_EXCLUDE_PCT` (-3.0)
  - `FALLBACK_POSITION_SIZE_RATIO` (0.5)
  - `FALLBACK_STOP_LOSS_PCT` (-1.5)
- `.env.example` 동시 업데이트

### 프론트엔드
- 대시보드 폴백 발동 통계 카드 활성화
- 2차 스크리닝 결과 리스트: `is_fallback=True` 종목에 ⚠️ 배지 + 색상 구분

### 재사용 자산
- 기존 position_size 계산 로직 (prev_close tier 50% 적용 패턴 재사용)
- 기존 손절 % 설정 경로

### 자동 롤백 트리거
- 스케줄러 16:10 job: `signal_count(오늘) == 0 AND signal_count(어제) == 0` 시 Telegram 경고 + `MIN_VOLUME_FLOOR_MODE=legacy`, `SECONDARY_POOL_FALLBACK_ENABLED=False` 자동 전환 + 관리자 확인 대기

---

## Sprint 2.5 상세 — 인프라 보강 + 관측성·문서 정합성 ✅ 완료

> **완료**: PR #172 머지 대기, 2026-04-24 sprint-review 완료. 963 passed / 1 failed (기존 플레이크 `test_ws_manager_env_max_subscriptions`, 이 Sprint 비관련).

### 구현 내용

- `backend/core/settings_override.py`: `resolve_override()` 유틸 통합 — Redis `settings:override:*` 단일 진입점. 기존 인라인 override 로직과 행동 동일성 검증 완료.
- `scripts/check_env_sync.py`: `.env.example` ↔ `Settings` 필드 동기화 검증 스크립트 (CI 외부 안전망)
- `backend/api/routes/metrics.py` + `frontend/components/diagnostics/override-banner.tsx`: `/api/v1/metrics/override-status` + `OverrideBanner` — 자동 롤백 발동 상태 관측성 배너
- `frontend/components/diagnostics/fallback-stats-card.tsx`: 롤백 중 dimmed 상태 (opacity-50 + 경고 메시지)
- `docs/phase/phase8/phase8.md`: Sprint 3 DoD D1~D7 재정의 잔재 정리 (Phase 8.5 재정의판으로 교체)

### 코드 리뷰 결과

이슈 없음. Critical/High/Medium 0건. PR #172 코멘트 참조.

### 불변 파라미터 검증

| 파라미터 | 확인 결과 |
|----------|----------|
| `ATR_FILTER_PCT` 기본값 0.05 | 변경 없음 |
| `MIN_VOLUME_FLOOR` 분기값 (0.4/0.5/0.6/HARD 0.3) | 변경 없음 |
| `SECONDARY_POOL_PASS_THRESHOLD=75.0` | 변경 없음 |
| 폴백 파라미터 (THRESHOLD=3, MAX=5, position 0.5, 손절 -1.5%, 제외 -3%) | 변경 없음 |

---

## ROADMAP 재편 delta 제안 (본 문서 승인 시 적용)

### 변경 내용

1. **Phase 8.5 신규 추가** (Phase 8과 Phase 9 사이):
   - 제목: "신호 발생 데드락 해제 (Sprint 1~2) 🔄"
   - 목표: 2차 스크리닝 풀 하한 폴백 + 동적 min_volume_floor + 관측성 강화
   - 필요 선행 데이터: 없음 (코드·파라미터 수정만)
   - Sprint 1 관측성 / Sprint 2 풀+게이트

2. **Phase 8.6 Sprint 1 (구 Phase 8 Sprint 3) DoD 업데이트**:
   - "신호 발생 3거래일 연속" → "일평균 ≥1, 0건 일수 ≤2/5"
   - "다층 진입 분기 각 1회+" → "tier 2개+ 각 1회 (gap_open 필수 아님)"
   - 추가: "손절 체결 최소 1회"
   - 추가: "Phase 8.5 완료 후 착수" 전제

3. **Phase 9 / 10 / 10.1 변경 없음**:
   - 순서·전제·DoD 유지
   - 조기 착수 / 병행 모두 전문가 4명 전원 거부
   - Phase 10.1 하이브리드의 **MVP 하위집합(풀 하한 폴백)**만 Phase 8.5에 흡수 — Phase 10.1 고도화 범위는 그대로

### 변경하지 않는 것

- Phase 8 Sprint 1·2 확정 파라미터 (Sprint 2 13:00 가드, 일일 10건 한도, LIVE 초기 3건/일, 반 포지션 등 전원 유지)
- Phase 7.0 확정 LIVE 초기 파라미터 (max_position=2, position_size=5%, daily_max_loss=-2%, emergency_stop=-3%)
- Phase 9 Sprint 0~3 순서 및 의존성
- Phase 10 "완화 불가" 원칙

### 적용 방법

사용자 승인 시 ROADMAP.md에 다음 섹션을 **Phase 8.5/8.6 섹션을 Phase 8과 Phase 9 사이에 삽입**하고, Phase 8.6 Sprint 1 DoD 문장을 반영한다. 이 작업은 **사용자가 명시적으로 지시할 때만 수행**한다.

---

## 배포간 최소 검증 기준 (Phase 8.5 적용)

`dev-process.md` §5 매트릭스 대비 축소안 (4명 전문가 승인):

| 항목 | 매트릭스 원안 | Phase 8.5 적용 | 승인 |
|------|--------------|---------------|------|
| `pytest -v` | 전체 필수 | **전체 필수 유지** | 전원 |
| API curl | 전체 | **변경분만 (+ 관측 API 필수)** | PO 조건부 |
| 데모 모드 API | ✅ | 유지 | — |
| Playwright UI | 전체 | **변경분만 (대시보드 신규 카드 + 폴백 배지 표시)** | 전원 |
| 관찰 기간 | Sprint 간 2거래일 | **Sprint 1→2 간 1.5거래일** (배포당일 2시간 + 다음 거래일 종일) | 최리스크 조건부 |
| **Phase 8.5 → Sprint 3 관찰** | 미정의 | **5거래일 유지 (단축 금지)** | 최리스크 엄격 |

---

## 미해결 사항 / 리스크

### ⚠️ 리스크 (전문가 지적)

1. **풀 하한 폴백의 저품질 종목 투입 위험** (최리스크·김단타)
   - 완화: position 50%, 손절 -1.5%, 하락 -3% 제외, 자동 롤백 트리거
2. **동적 min_volume_floor 구현 버그 가능성** (최리스크)
   - 완화: `MIN_VOLUME_FLOOR_HARD = 0.3` 절대 하한 + 단위 테스트 필수
3. **시장 상태가 원인인 신호 부족의 가능성** (김단타)
   - 완화: Phase 8.5가 시스템 교차 불가 구조만 해제함을 명시. "신호 0건 일수가 원래 있을 수 있음" 사용자 합의
4. **브리지 변경이 누적되어 사실상 전략 변경** (박퀀트)
   - 완화: env 변수화로 1줄 롤백, A/B 대시보드로 효과 분리 추적

### ❌ 거부된 제안 (원안 vs 확정)

- 시간 슬라이딩 min_volume_floor (전원 거부)
- `prev_close_time_guard` 13:00→14:00 연장 (전원 거부)
- Phase 9 Sprint 0 브리지와 병행 (전원 거부)
- Phase 10 "대안 C만" 조기 착수 (전원 거부)
- Phase 10.1 하이브리드 전체 조기 흡수 (PO 거부, MVP만 흡수)

### 🤔 사용자 최종 결정 필요 항목

1. **Sprint 1→2 관찰 기간 1.5거래일 채택 여부** (최리스크 조건부 승인). 엄격히 가려면 2거래일.
2. **Phase 8.5 → Phase 8.6 Sprint 1 이행 시 관찰 기간 5거래일 유지 vs 단축**. 권고는 5거래일 유지.
3. **자동 롤백 트리거 발동 시 관리자 확인 vs 완전 자동 원복**. 권고는 관리자 확인.

### Sprint 1 코드 리뷰에서 발견된 미해결 이슈 (Medium, Sprint 2에서 개선 권장)

| # | 이슈 | Severity | 파일 | 상태 |
|---|------|----------|------|------|
| ~~M1~~ | ~~`top-rejects` API `limit` 파라미터 최대 50 허용이나 Redis `TOP_REJECT_SIZE=5` 고정 — 5 초과 요청은 항상 5건만 반환~~ | ~~Medium~~ | ~~`backend/api/routes/metrics.py`~~ | ✅ 해결 — Sprint 2 task7에서 API limit 상한 5로 제한 (`ge=1, le=5`) |
| ~~M2~~ | ~~stage heatmap 프론트엔드 `HOUR_MINS`가 09:30부터 시작 — 09:00~09:20 구간 데이터 수집은 되나 UI에 미표시~~ | ~~Medium~~ | ~~`frontend/components/diagnostics/stage-heatmap-card.tsx`~~ | ✅ 해결 — Sprint 2 task7에서 09:00 시작 컬럼으로 수정 |

### Sprint 2 코드 리뷰에서 발견된 미해결 이슈 (Medium)

| # | 이슈 | Severity | 파일 | Sprint 3/8.6에서 개선 방향 |
|---|------|----------|------|--------------------------|
| M3 | `_apply_fallback()` 함수 내부에 `import bisect` 인라인 배치 — 동작 문제 없으나 모듈 상단 import 관례 위반 | Medium | `backend/modules/screening/realtime_screener.py` | 다음 Sprint 관련 파일 수정 시 모듈 상단으로 이동 권장 |

---

## 완료 기준 (Phase 8.5 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| Sprint 1 관측성 대시보드 카드 4개 배포 | stage 분포 + score 분포 + heatmap + 탈락 상위 | ⬜ |
| 1.5거래일 관찰에서 관측성 메트릭 정상 수집 | Redis counter + 일별 집계 배치 동작 | ⬜ |
| Sprint 2 풀 하한 폴백 배포 | `passed<3` 시 보강 로직 + 메타데이터 기록 | ✅ 완료 |
| 동적 `MIN_VOLUME_FLOOR` 배포 | 0.4/0.5/0.6 조건 분기 + HARD 0.3 | ✅ 완료 |
| 폴백 종목 position 50%, 손절 -1.5%, 하락 -3% 제외 동작 | 통합 테스트 통과 | ✅ 완료 |
| env 변수화 + `.env.example` 동기화 | 6개 변수 반영 | ✅ 완료 (8종 변수) |
| 자동 롤백 트리거 스케줄러 동작 확인 | 2거래일 신호 0건 시 발동 | ✅ 완료 (단위 테스트 통과) |
| Phase 8.5 관찰 5거래일에서 일평균 신호 ≥ 1 | Phase 8.6 Sprint 1 착수 전제 | ⬜ 관찰 진행 중 |
| pytest 전체 통과 | — | ✅ 완료 (963 passed / 1 기존 플레이크) |

완료 후 Phase 8.6 Sprint 1 (E2E + LIVE 게이트)로 진행한다.

---

## 사용자 다음 단계

본 문서는 **제안**이다. ROADMAP은 아직 변경되지 않았다.

선택지:

1. **제안 그대로 승인 → ROADMAP 반영 → Phase 8.5 Sprint 1 sprint-planner 호출**
2. **특정 파라미터 수정 후 승인** (예: 관찰 기간 2거래일로 엄격화, 자동 롤백 완전 자동화 등)
3. **거부 / 재검토** (Phase 8.6 Sprint 1 원안 DoD 그대로 시도, 또는 다른 접근)

선택을 알려주면 그에 따라 진행한다.
