# Phase 8.6: 신호 생성 로직 구조 재설계 — 실행 계획

> **Status**: Sprint 1~4 ✅ 완료. **Sprint 5 신설 (계획 수립, 사용자 승인 대기, 2026-05-14)** — 2026-05-13~14 모니터링 결과 14개 결함 처리. Phase 8.7 entry gate 재정의 동반.
> **ROADMAP 참조**: ROADMAP.md `Phase 8.6` 절 — 본 문서 승인 시 "누적 백로그 통합" → "신호 생성 로직 구조 재설계 (분기 D 트리거 선제 착수)"로 재정의되며, 기존 백로그(피라미딩 / 2차 하이브리드)는 Phase 10.1로 분리한다.
> **트리거**: Phase 8.5 v2.6.1 5거래일 관찰 결과 분기 D 확정 (2026-04-28 16:10 `auto_rollback_2d_zero_signals` 발동, 4거래일 본 신호 1건 / 폴백 605회).
> **검토 리포트** (분기 D 4명 재리뷰가 1차 입력 — 본 Phase 결정 추적성 확보):
> - `docs/phase/phase8.5/phase8.5-branch-d-po-review.md` (정프로, PO)
> - `docs/phase/phase8.5/phase8.5-branch-d-risk-review.md` (최리스크, 리스크관리)
> - `docs/phase/phase8.5/phase8.5-branch-d-quant-review.md` (박퀀트, 퀀트)
> - `docs/phase/phase8.5/phase8.5-branch-d-daytrader-review.md` (김단타, 단타 전문가)
>
> **Sprint 5 신설 검토 리포트** (2026-05-14, 모니터링 결과 14개 결함 기반):
> - `docs/phase/phase8.6/phase8.6-sprint5-api-review.md` (윤에이피, Open API/WS)
> - `docs/phase/phase8.6/phase8.6-sprint5-quant-review.md` (박퀀트, 퀀트)
> - `docs/phase/phase8.6/phase8.6-sprint5-risk-review.md` (최리스크, 리스크)
> - `docs/phase/phase8.6/phase8.6-sprint5-po-review.md` (정프로, PO — 최종 의사결정)
> **모니터링 근거**: `docs/phase/phase8.6/sprint4/2026-05-13-monitoring-result.md` + `docs/phase/phase8.6/sprint4/2026-05-14-monitoring-result.md`

---

## 1. 개요

### 1.1 분기 D 사후 진단 (4명 합의)

분기 D는 "Phase 8.5 폴백이 실패했다"가 아니라 **"폴백은 작동했으나, 폴백으로 끌어올린 종목조차 직렬 AND 게이트를 통과하지 못했다"**는 구조적 결론이다.

- **퀀트(박퀀트) 진단** — `phase8.5-branch-d-quant-review.md` §1·§2:
  > "tier가 직렬 AND 형태인 한, 종류를 늘려도 통과율이 곱셈으로 줄어든다 ··· 본 신호 풀이 비어 있다고 거의 매 tick 외쳤지만, 폴백이 보강해도 신호는 1건만 나왔다."
  - 시뮬 2nd-screening pass 38.9% vs 실측 ~3% → **10배 이상 괴리**
  - 실측 일별 신호 발생확률 p ≈ 1/605 ≈ 0.0017 (사전 가정 5%의 1/30)
- **단타(김단타) 진단** — `phase8.5-branch-d-daytrader-review.md` §2:
  > "시스템이 잡아야 할 진짜 단타 패턴(거래량 급증·VI·테마 강세)을 구조적으로 못 본다."
  - 가격 기준 돌파(prev_high·prev_close)만 보는 단일 시각의 한계
- **PO(정프로) 진단** — `phase8.5-branch-d-po-review.md` §1:
  > "(a) 시장 레짐 가정 미스, (b) 게이트 다층 차단, (c) 자동 롤백 임계값과 단계 배포 일정의 불일치"
- **리스크(최리스크) 진단** — `phase8.5-branch-d-risk-review.md` §2:
  > "🚨 시스템 신뢰도 적색 — LIVE 전환 절대 금지 신호 ··· 시스템이 무엇을 매매할지 예측 불가능한 상태."

### 1.2 본 Phase의 사명

직렬 AND → **병렬 OR 다중 진입 경로**로 신호 생성 로직을 구조 재설계하고, 단타 실전 패턴 1순위(거래량 급증)를 신규 tier로 도입하며, ATR 임계를 분포 기반 동적 캘리브레이션으로 전환한다. 동시에 분기 D 같은 사고가 다시 발생하더라도 LIVE 자금이 보호되도록 **리스크 P0 가드레일(G1~G3)을 Definition of Ready로 강제**한다.

### 1.3 사용자 의사결정 (2026-04-28)

PO는 Sprint 2.6(파라미터 미세조정 + M-F2 + 시뮬 재검증)을 1주 내 재배포로 권고했으나, 사용자는 **"구조 재설계 노선(퀀트/단타)"**을 선택. 이에 따라 PO의 Sprint 2.6 안은 본 Phase의 **Sprint 1(선행 패치)** 으로 흡수하여 중간 손실을 막고, Sprint 2 이후 본 구조 재설계를 진행한다.

### 1.4 데이터 의존성 / Phase 9·10과의 관계

- 본 Phase의 핵심 변경(병렬 OR, ATR 분위수 캘리브레이션, volume_surge tier)은 **추가 데이터 축적이 필수가 아니다**. 분기 D는 데이터 부족이 아니라 구조 결함이며, 60일 walk-forward는 KIS 분봉 백필(Phase 9 Sprint 0의 백필 메커니즘과 동일 인프라)로 즉시 시작 가능.
- 본 Phase는 **Phase 8.6 Sprint 1(E2E + LIVE 게이트)의 선행**이 된다. Phase 8.5 → Phase 8.6의 의존이 본 Phase로 우회된다 (Phase 8.5 완료 기준 "일평균 신호 ≥1"이 분기 D로 미충족이므로).
- Phase 9·10 순서 자체는 변경하지 않는다. Phase 10(U자형 비선형)은 여전히 Phase 9 Sprint 3 + 2~6개월 축적이 전제.
- **단, Phase 8.6 → Phase 10.1 (구 백로그) 분리 정책 신규**: 본 Phase가 "누적 백로그 통합"이 아닌 **"분기 D 구조 재설계 선제 착수"**로 재정의되므로, 피라미딩·2차 스크리닝 하이브리드는 Phase 10.1로 별도 분리한다. (사용자 승인 시 ROADMAP·index.json 동시 반영)

---

## 2. 목표 / 성공 기준 (정량)

### 2.1 시스템 행동 변경 목표 (Phase 8.6 완료 시점)

| # | 항목 | 현재(분기 D) | 목표 | 측정 |
|---|------|-------------|------|------|
| G-A | 일평균 본 신호 수 | 0.25 (4일 1건) | **≥ 1.5건/일** (5거래일 평균) | M-S1 일별 합산 |
| G-B | 0건 일수 비율 | 75% (3/4) | **≤ 30%** (5거래일 중 ≤1건) | observation-daily API |
| G-C | tier 다양성 | 1종(prev_high) | **≥ 3종 활성** (각 5일 누적 ≥ 1건) | tier별 카운터 |
| G-D | tier 간 신호 발생 상관 | 미측정 | **≤ 0.3** (병렬 OR 독립성 검증) | tier 발생일 페어와이즈 상관 |
| G-E | 시뮬-실측 pass율 괴리 | 35.9%p (38.9% vs 3%) | **≤ 5%p** | Walk-forward backtest vs 5거래일 실측 KS 검정 p ≥ 0.05 |
| G-F | 폴백 신호율(M-F2) | 측정 불가 | **0~100% 명시 산출** + 일별 대시보드 카드 | `signal.fallback=true` 메타데이터 신호·체결 로그 전파 |
| G-G | LIVE 전환 차단 신호 자동 감지 | 단일(2일 0건) | **다중 트리거 OR** (R1: 0건 3일 연속 / R2: 폴백 발동률 ≥50% 3일 연속 / R3: tier 다양성 1종 5일 연속 / R4: 폴백 신호 비중 ≥70% 1일) | 16:10 스케줄러 |

### 2.2 비기능 목표

- **회귀 0건 보장**: Phase 7.0 LIVE 파라미터(max_position=2, position_size=5%, daily_max_loss=-2%, emergency_stop=-3%)는 코드 레벨 상수 잠금. 본 Phase 어떤 변경에서도 수정 금지 (리스크 G9).
- **모든 신규 파라미터 env 토글**: 1줄 변경으로 즉시 원복 가능 (리스크 G6).
- **dry_run 우선 배포**: 신규 신호 로직(volume_surge 등)은 기본 `dry_run=true`로 배포되어 Paper 5거래일 + 백테스트 KS 검정 통과 후 LIVE 토글 (리스크 G5).

### 2.3 비목표 (이번 Phase에서 하지 않음)

- 피라미딩(당일 고가 갱신 진입) → Phase 10.1로 분리
- 2차 스크리닝 절대 점수 ↔ 백분위 하이브리드 → Phase 10.1로 분리
- VI 재개 tier (`vi_resume`) → Phase 10.1 또는 별도 후속 (단타 3순위, 변동성 리스크가 커서 1·2순위 정착 후 도입)
- 테마 모멘텀 가중치 (`theme_momentum`) → Phase 10.1로 분리 (섹터 메타데이터 인프라 별도 필요)
- **Phase 10 U자형 비선형 보정 (절대 가속 금지 — 사용자 2026-04-20 "완화 불가" 확정 유지)**

---

## 3. Definition of Ready (DoR) — Sprint 2 착수 전 선결조건

> 리스크 G1~G3은 **Sprint 2 착수의 차단 해제 조건**이다. Sprint 1에서 우선 구현한다. 이게 없으면 본 Phase의 어떤 구조 변경도 LIVE 안전성 검증이 불가능하다 (리스크 페르소나 §3 P0).

### G1. 폴백 신호율(M-F2) 산출 가능화

- `signal.fallback=true` 메타데이터를 **신호 → 주문 → 체결 → 일별 집계** 전 경로에 전파
- 일별 폴백 신호 비율 = `폴백 종목 신호 수 / 폴백 발동 종목 수` 산출
- 대시보드 카드: 폴백 종목 PnL 별도 집계
- **이게 없으면 Sprint 2 착수 차단**

### G2. 자동 롤백 사유 다변화

기존 `auto_rollback_2d_zero_signals` 단일 트리거 → 다음을 **OR 조건**으로 추가:

| 트리거 ID | 조건 | 근거 |
|----------|------|------|
| R1 (기존 강화) | 신호 0건 **3거래일 연속** | PO §2 권고 — 휴장 인접 단기 0건 조기 롤백 방지 |
| R2 | 폴백 발동률 ≥ 50% 일수 **3거래일 연속** | 리스크 §3 G2 — 스크리닝 단절 조기 감지 |
| R3 | tier 다양성 1종 **5거래일 연속** | 리스크 §3 G2 — 게이트 협소화 감지 |
| R4 | 폴백 신호 비중 ≥ 70% **1거래일** | 리스크 §3 G2 — 폴백 우회 경로화 감지 |

- 모든 트리거는 env 토글로 즉시 비활성화 가능 (`AUTO_ROLLBACK_R{1..4}_ENABLED`)
- 트리거 발동 시 **Phase 8.6 신규 변경분만 비활성화**, Phase 8.5 폴백은 별도 결정

### G3. 1차→2차 통과율 회로차단기

- 일별 2차 통과율(폴백 제외) **< 10% 3거래일 연속** 시 본 Phase 변경분 자동 비활성화 + Phase 8.5 폴백 차단
- 실측 데이터로는 분기 D 시점 4일 평균 ~3% (5종 폴백 / 평균 1차 풀 ~150종 가정 시) — 이 임계 10%는 "분기 D 같은 사태 즉시 감지" 기준

### DoR 체크리스트

- ✅ G1 구현 완료 — is_fallback 신호→주문→DB 전파 + M-F2 API (Sprint 1 Task 3, 2026-04-29)
- ✅ G2 R1~R4 4종 트리거 단위 테스트 통과 + env 토글 검증 (Sprint 1 Task 4, 13 tests PASS, 2026-04-29)
- ✅ G3 회로차단기 단위 테스트 통과 + 임계 10% env 변수화 (Sprint 1 Task 5, 9 tests PASS, 2026-04-29)
- ✅ Phase 7.0 LIVE 파라미터 코드 레벨 잠금 (`Final[int]` 상수 + 변경 시 빌드 실패 테스트, Sprint 1 Task 1, 5 tests PASS, 2026-04-29)

위 4개 모두 ✅ 후에만 Sprint 2 착수 가능. — **Sprint 1 완료로 DoR 4종 충족 (2026-04-29)**

> Paper 1거래일 메타데이터 전파 확인 (`signals.fallback=true` 1건 이상)은 수동 검증 필요 (deploy.md ⬜)

---

## 4. Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 | 예상 소요 |
|--------|------|----------|--------|----------|
| **1** ✅ | **선행 패치 + 가드레일** (PO Sprint 2.6 안 흡수 + 리스크 G1~G3) | M-F2 산출, 자동 롤백 사유 다변화(R1~R4), 회로차단기, 폴백 5종 확장, min_volume_floor 시간대 슬라이딩(0.3 09~11시 / 0.5 그 외), Phase 7.0 LIVE 파라미터 잠금 | 없음 (분기 D 직후 즉시) | ~~4~6일~~ **완료 (2026-04-29, PR #181)** |
| **2** ✅ | **병렬 OR tier 분리 + ATR 분위수 캘리브레이션** | tier별 sub-게이트 분리(gap_open=ATR우회+gap≥3%, prev_high=ATR+breakout, prev_close=시간가드만), ATR 하한 0.025 + 상한 동적(`min(0.08, 80퍼센타일×1.2)`), 09:00 KOSPI 200 분위수 잡 | Sprint 1 완료 + DoR 통과 | ~~5~7일~~ **완료 (2026-04-22, PR #186)** |
| **3** ✅ | **`volume_surge` tier 신설 + 시간대 필터** | 5분봉 거래량 ≥ 직전 20분 평균 ×5 + 호가창 매수/매도 잔량 ≥ 2배, 가격 조건 약하게(전일 종가 +0.5%↑), 09:00~09:10 진입 금지·14:30+ 신규 진입 금지·점심 floor 0.7, dry_run=True 기본값 | Sprint 2 + KIS WS 호가 스트림(Phase 6 인프라 재사용) | ~~6~9일~~ **완료 (2026-05-08, PR #200)** |
| **4** ✅ | **Walk-forward 백테스트 + 시뮬↔실측 자동 감지** | 60거래일+ 백테스트(박스권/추세장 각 20일+), TimeSeriesSplit(40일 학습 / 20일 검증 슬라이딩), 매주 KS 검정 자동 트리거(p<0.05 시 시뮬 재구축 알림), Bootstrap CI 하한 ≥1 통과 시 LIVE 토글 허용 | Sprint 2~3 코드 + KIS 분봉 백필(Phase 9 Sprint 0과 동일 메커니즘) | ~~5~8일~~ **완료 (2026-05-08, PR #208)** |

> **순서**: Sprint 1 → 2 → 3 → **5거래일 Paper 관찰** → Sprint 4 (병렬 불가)
> - Sprint 1·2·3은 코드 변경 후 즉시 다음 Sprint 착수 가능
> - **Sprint 3 → 4 사이에 Paper 5거래일 관찰 강제** (§10 DoD #9~#11 충족 측정 = LIVE 토글 게이트 §7.5 G-Bt3 입력)
> - Sprint 4의 Walk-forward 백테스트는 위 5거래일 관찰과 **병행** (Sprint 4 코드 작업 자체는 Paper 관찰과 시간축 분리)
>
> **예외 조항 (2026-05-08 사용자 의사결정)**: Sprint 3 배포 후 Paper 2거래일 이내(5/7+5/8) **G2 신호 0건** 누적 + 신호 부재 원인이 Sprint 3 변경(volume_surge / 시간 필터 / 우선순위 큐) **외**의 임계(2차 스크리닝 / volume_threshold 2.0)로 명확히 진단 (`observation_2026-05-08.md`). 이 경우 5거래일 관찰은 G-Bt3 입력값을 만들어내지 못함이 자명하므로 강제 조건을 우회하여 **Sprint 4 즉시 착수**한다. Sprint 4 walk-forward 결과로 임계 재조정 → hotfix 적용 → 의미 있는 시점에 Paper 관찰 재시작. R1 자동 롤백은 발동 시 그대로 수용 (가드레일 정상 작동의 증거).
> **총 예상 소요**: 3~4주 (관찰 5거래일 = ~1주 포함)
> **각 Sprint 종료 시 Paper 1거래일 회귀 통합 검증** (이는 §10 DoD 5거래일 관찰과 별개)

---

## 5. 검토팀 확정 파라미터

> **검토 참여**: 정프로(PO), 최리스크(리스크), 박퀀트(퀀트), 김단타(단타) — 분기 D 4명 재리뷰 1차 입력
> **충돌 해소 원칙**: 보수적 방향 + 리스크 의견 우선 (Phase 표준)

### 5.1 신호 게이트 구조

| # | 항목 | 원래 설계 (분기 D 시점) | 확정값 | 근거 (출처) |
|---|------|----------------------|--------|------------|
| 1 | tier 게이트 결합 방식 | **직렬 AND** (모든 tier가 ATR 5% + 2차 pass 75 공유) | **병렬 OR** (각 tier 독립 sub-게이트) | 박퀀트 §3.2 — "직렬 AND인 한 종류 늘려도 곱셈 0" |
| 2 | gap_open tier sub-게이트 | ATR + 2차pass + breakout | **gap_rate ≥ 3% 단독, ATR 우회 허용** | 박퀀트 §3.2 — gap 자체가 변동성 조건 |
| 3 | prev_high tier sub-게이트 | ATR + 2차pass + breakout | **ATR(2.5~동적) + breakout** | 박퀀트 §3.2 — 기존 본질 유지 |
| 4 | prev_close tier sub-게이트 | ATR + 2차pass + 13:00 가드 | **시간 가드(13:00) 단독** | 박퀀트 §3.2 — 약한 신호일수록 단순화 |
| 5 | tier 간 신호 발생 상관 목표 | 미측정 | **≤ 0.3** (페어와이즈) | 박퀀트 §3.2 — 독립 진입 경로 확보 |

### 5.2 ATR 임계

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 6 | ATR_FLOOR (하한) | 없음 | **0.025** | 박퀀트 §3.1 — 너무 낮은 변동성은 단타 부적합 / 김단타 동일 |
| 7 | ATR_CEIL (상한) | 0.05 고정 | **`min(0.08, KOSPI200 80퍼센타일×1.2)` 동적** | 박퀀트 §3.1 — 분위수 기반은 자유도 증가 아님 |
| 8 | ATR 캘리브레이션 주기 | 없음 | **매일 09:00 KOSPI 200 ATR 분위수 산출 잡** | 박퀀트 §3.1 |
| 9 | ATR 상한 완화 패키지 | — | **gap_open tier는 ATR 우회**, 기타 tier는 동적 상한 적용 | 리스크 §3.2 — "5%→8% 직접 변경 거부, 패키지로만" 부분 수용 |
| 10 | 폴백 종목 ATR 상한 추가 제한 | 없음 | **0.05 고정 (동적 미적용)** | 리스크 §3 G4 패키지 — 폴백 종목 변동성 추가 제한 |

### 5.3 `volume_surge` tier (신규, Sprint 3)

| # | 항목 | 확정값 | 근거 |
|---|------|--------|------|
| 11 | 진입 조건 거래량 | **5분봉 거래량 ≥ 직전 20분 평균 × 5배** | 김단타 §2 패턴 1 / §3 1순위 |
| 12 | 호가창 잔량 | **매수/매도 잔량 비율 ≥ 2.0** | 김단타 §2 패턴 1 |
| 13 | 가격 조건 | **전일 종가 +0.5% 이상** (약하게) | 김단타 §2 패턴 1 — 가격 돌파 전 진입 골든타임 |
| 14 | 활성 시간대 | **09:30~14:00 한정** | 김단타 §3 1순위 (장 초반/마감 제외) |
| 15 | 손절 | **5분봉 저가 또는 -1.5%** (타이트) | 김단타 §3 1순위 |
| 16 | position_size | **30%** (반의 60% — 신규 tier 보수 적용) | 리스크 G4 + 단타 신규 tier 패키지 |
| 17 | 초기 배포 모드 | **dry_run=True 기본값** | 리스크 G5 — Paper 5일 + 백테스트 KS 통과 후 LIVE |

### 5.4 시간대 필터

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 18 | 09:00~09:10 진입 금지 | 없음 (09:30 게이트) | **신규 tier 09:00~09:10 금지, gap_open만 09:05까지 허용** | 박퀀트 §3.3 / 김단타 §2 패턴 3 |
| 19 | 점심 11:30~13:00 floor | 0.5 | **0.7로 시간 분기 (구조적 거래량 -40% 정정)** | 박퀀트 §3.3 — "분포 정정"이지 자유도 아님 |
| 20 | 14:30~15:00 신규 진입 | 허용 | **신규 진입 금지, 청산만 허용** | 박퀀트 §3.3 — 마감 갭 리스크 회피 |
| 21 | min_volume_floor 시간대 슬라이딩 (Sprint 1만) | 0.5 고정 | **0.3 (09:00~11:00) / 0.5 (그 외)** | PO 분기 D §2 — 사전 SHOULD를 MUST 승격, tier 다양성 직접 해소 |

### 5.5 폴백 / 자동 롤백 (Sprint 1)

| # | 항목 | v2.6.1 | 확정값 | 근거 |
|---|------|--------|--------|------|
| 22 | 풀 하한 폴백 보강 종목 수 | 3 | **5** | PO §2 — 04월 4째주 실측 풀 협소 |
| 23 | 자동 롤백 R1 (0건 연속) | 2일 | **3일** | PO §2 — 단계 배포 윈도우와 일치 |
| 24 | 자동 롤백 R2 (폴백 발동률 ≥50%) | 없음 | **3일 연속** OR 추가 | 리스크 §3 G2 |
| 25 | 자동 롤백 R3 (tier 다양성 1종) | 없음 | **5일 연속** OR 추가 | 리스크 §3 G2 |
| 26 | 자동 롤백 R4 (폴백 신호 비중 ≥70%) | 없음 | **1일** OR 추가 | 리스크 §3 G2 |
| 27 | M-F2 측정 로직 | 미구현 | **G1 일환으로 Sprint 1 첫 Task 필수 구현** | PO §2 / 리스크 §3 G1 / 퀀트 §2 — "표본 부족으로 검증 불가" |

### 5.6 일일 손실 한도 / 포지션

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 28 | 일일 손실 한도 (전체) | -2% | **-2% 유지 (Phase 7.0 잠금)** | 리스크 G9 |
| 29 | 일일 손실 한도 (폴백 종목 한정 별도) | 없음 | **-1% 별도 적용** | 리스크 §3 G4 — 폴백 손실 격리 |
| 30 | volume_surge tier position_size | — | **30%** | §5.3 #16 |
| 31 | 폴백 종목 position_size | 50% (Phase 8.5) | **50% 유지** | Phase 8.5 계승 |
| 32 | LIVE 신호 로직 토글 | — | **모든 신규 tier env 토글 + dry_run 기본값** | 리스크 G5·G6 |

### 5.7 백테스트 (Sprint 4)

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 33 | 백테스트 기간 | Phase 8.5 시뮬 (수일분) | **최소 60거래일 (3개월)** | 박퀀트 §3.4 |
| 34 | 시장 환경 분포 강제 | 없음 | **박스권 ≥20일 + 추세장 ≥20일 보장** | 박퀀트 §3.4 |
| 35 | 검증 방법 | 단일 in-sample | **Walk-forward (40일 학습 / 20일 검증 슬라이딩)** | 박퀀트 §3.4 |
| 36 | 시뮬-실측 일치도 검정 | 없음 | **매주 카이제곱 / KS 검정 p<0.05 시 시뮬 재구축 자동 알림** | 박퀀트 §3.4 |
| 37 | DoD 통계 기준 | 점추정 | **Bootstrap 95% CI 하한 ≥ 1** 일 때만 통과 | 박퀀트 §3.4 |
| 38 | LIVE 토글 게이트 | 없음 | **백테스트 KS p≥0.05 + Paper 5거래일 G-A·G-B 충족 동시** | 리스크 G5 + 박퀀트 §3.4 + PO §2 |

---

## 6. Sprint별 상세

### Sprint 1 — 선행 패치 + 가드레일 (PO Sprint 2.6 흡수)

> **의도**: PO가 "Phase 8.6 점프 대신 1주 내 재배포"로 권고한 안을 본 Phase의 첫 Sprint로 흡수. 분기 D 손실을 빠르게 막고, Sprint 2~4의 전제조건(DoR G1~G3)을 동시에 깐다.

#### 백엔드

- `backend/modules/screening/realtime_screener.py`:
  - 풀 하한 폴백 보강 3종 → **5종**으로 상향 (`SECONDARY_POOL_FALLBACK_BACKFILL=5`)
  - `signal_metadata.fallback=true` 키 추가, 신호 객체 직렬화에 포함
- `backend/modules/trading/strategies/momentum_breakout.py`:
  - `_resolve_min_volume_floor()`에 **시간대 슬라이딩** 분기 추가 (09:00~11:00 → 0.3, 그 외 → 기존 0.5/0.4/0.6 유지). HARD 0.3 유지.
- `backend/modules/trading/engine.py` + `backend/modules/orders/executor.py`:
  - `signal_metadata.fallback` 메타데이터를 주문 생성 → 체결 → DB `orders.fallback` 컬럼까지 전파 (Alembic 마이그레이션)
- `backend/modules/scheduler/auto_rollback.py` (신규 또는 기존 16:10 잡 확장):
  - R1~R4 트리거 4종 OR 평가
  - 각 트리거 env 토글 (`AUTO_ROLLBACK_R{1..4}_ENABLED`)
  - 발동 시 본 Phase 변경분만 비활성화 (`PHASE10_1_*_ENABLED=False`로 일괄 전환)
- `backend/modules/screening/circuit_breaker.py` (신규):
  - 일별 2차 통과율(폴백 제외) < 10% 3일 연속 시 본 Phase 변경분 자동 비활성화 + Phase 8.5 폴백 차단
- `backend/core/constants.py` (신규 또는 `core/config.py`):
  - Phase 7.0 LIVE 파라미터를 `Final[int]`/`Final[float]` 상수로 잠금 + 변경 시 빌드 실패 테스트
- `backend/api/routes/metrics.py`:
  - `GET /api/v1/metrics/fallback-signal-rate` (M-F2) 추가 — 일별 폴백 신호 비율
- Alembic 마이그레이션:
  - `orders.fallback BOOLEAN NULL`
  - `signals.fallback BOOLEAN NULL`
  - `daily_screening_metrics.fallback_signal_rate FLOAT NULL`

#### 프론트엔드

- `frontend/components/diagnostics/fallback-signal-rate-card.tsx` (신규):
  - 일별 폴백 신호 비율 + 7일 이동평균 차트
  - 폴백 종목 PnL 별도 집계 카드
- `frontend/components/diagnostics/auto-rollback-multi-trigger.tsx` (신규):
  - R1~R4 4종 트리거 발동 상태 시각화 (어떤 트리거가 임박했는지)

#### 재사용 자산

- Phase 8.5 Sprint 2.5의 `OverrideBanner` 패턴 (env 자동 롤백 시각화)
- Phase 8.5 Sprint 1의 Redis counter + 일별 집계 배치 패턴 (일별 폴백 신호율 집계에 동일 패턴)
- Phase 8.5 Sprint 2의 `_resolve_min_volume_floor` 함수 (시간대 슬라이딩 분기 추가)

#### 통합 검증

- pytest 전체 통과 + 신규 단위 테스트(R1~R4 4종 트리거 + 회로차단기 + 메타데이터 전파)
- Paper 1거래일에서 `signals.fallback=true` 종목 1건 이상 체결 → DB 전파 확인
- `/api/v1/metrics/fallback-signal-rate` 응답 정상

#### 종료 조건 (DoR 체크)

- ✅ G1 (M-F2 산출) — is_fallback 전파 + fallback-signal-rate API (2026-04-29, PR #181)
- ✅ G2 (R1~R4 트리거) — AutoRollbackEvaluator 13 tests PASS (2026-04-29, PR #181)
- ✅ G3 (회로차단기) — CircuitBreaker 9 tests PASS (2026-04-29, PR #181)
- ✅ Phase 7.0 LIVE 파라미터 잠금 — Final 상수 + assert + 5 regression tests (2026-04-29, PR #181)

위 4개 모두 충족 — **Sprint 2 착수 게이트 해제 (2026-04-29)**
> 단, Paper 1거래일 메타데이터 전파 확인은 수동 검증 필요 (deploy.md ⬜)

---

### Sprint 2 — 병렬 OR tier 분리 + ATR 분위수 캘리브레이션

#### 백엔드

- `backend/modules/trading/strategies/momentum_breakout.py`:
  - tier별 `_evaluate_gap_open()`, `_evaluate_prev_high()`, `_evaluate_prev_close()` 분리
  - 각 tier 독립 sub-게이트:
    - **gap_open**: gap_rate ≥ 3%, ATR 우회, 09:00~09:05 허용 + 09:05~09:30 일반 허용
    - **prev_high**: ATR(하한 0.025 + 동적 상한) + breakout(close > prev_high × 1.001)
    - **prev_close**: 13:00 시간 가드만 + min_volume_floor 분기 (Sprint 1 슬라이딩 그대로)
  - tier 1개라도 OR 조건 충족 시 신호 발행 (병렬 OR)
- `backend/modules/screening/atr_calibration.py` (신규):
  - 매일 09:00 KOSPI 200 ATR 20일 평균의 분위수 산출 (numpy.percentile)
  - `ATR_CEIL_DYNAMIC = min(0.08, P80 × 1.2)` 결과를 Redis `metrics:atr:ceil:{date}`에 저장
  - 폴백 종목은 `ATR_CEIL_FALLBACK = 0.05` 고정 적용
- `backend/modules/scheduler/scheduler.py`:
  - 09:00 ATR 캘리브레이션 잡 신규 등록
- `backend/core/config.py`:
  - `ATR_FLOOR=0.025`, `ATR_CEIL_HARD=0.08`, `ATR_CALIBRATION_ENABLED=True`, `PARALLEL_OR_TIER_ENABLED=True` 등 env 추가

#### 프론트엔드

- `frontend/components/diagnostics/tier-correlation-card.tsx` (신규):
  - tier 페어와이즈 신호 발생 상관 7일 이동
  - 목표선 0.3 표시
- `frontend/components/diagnostics/atr-distribution-card.tsx` (신규):
  - KOSPI 200 ATR 분위수 + 동적 CEIL 표시

#### 재사용 자산

- Phase 6.1 5분봉 vol5m Redis 축적 패턴 (ATR 계산에 일봉 데이터 사용)
- Phase 4.7의 3팩터 분리 패턴 (tier sub-게이트 분리에 유사 구조)

#### 통합 검증

- 단위 테스트: tier 3종 각각 독립 평가 + OR 결합 검증
- Paper 1거래일: 최소 1 tier 활성, 다른 tier 0건이어도 신호 발행 확인 (병렬 OR 동작 증명)
- ATR 캘리브레이션 09:00 잡 성공 + 동적 CEIL Redis 저장 확인

---

### Sprint 3 ✅ 완료 — `volume_surge` tier 신설 + 시간대 필터
> 완료: 2026-05-08, PR #200 (phase8.6-sprint3 → develop 머지 대기)
> pytest 1116 passed / GroupingError(metrics GROUP BY) sprint-review 발견 후 fix 커밋 aca388a

#### 백엔드

- `backend/modules/trading/strategies/volume_surge.py` (신규):
  - 진입 조건: `vol_5m / mean(vol_5m, last 4) >= 5.0` AND `bid_total / ask_total >= 2.0` AND `price >= prev_close × 1.005`
  - 활성 시간대: 09:30~14:00 KST
  - 손절: 5분봉 저가 -1.5% 또는 absolute -1.5% (보수)
  - position_size: 30% (LIVE 진입 시점)
  - 기본 `VOLUME_SURGE_DRY_RUN=True`
- `backend/modules/realtime/quote_aggregator.py` (또는 기존 KIS WS handler 확장):
  - 호가창(bid/ask 5호가 잔량) 1초 스냅샷 → Redis `quote:depth:{code}` (TTL 5초)
  - 5분봉 거래량 누적 (Phase 6.1 vol5m 인프라 재사용)
- 시간대 필터 게이트 (`backend/modules/trading/strategies/_time_filter.py` 신규):
  - 09:00~09:10 신규 진입 금지 (gap_open만 09:05까지 예외)
  - 11:30~13:00 min_volume_floor 0.7
  - 14:30~15:00 신규 진입 금지 (청산만 허용)
- `backend/core/config.py`:
  - `VOLUME_SURGE_ENABLED`, `VOLUME_SURGE_DRY_RUN`, `VOLUME_SURGE_VOL_RATIO=5.0`, `VOLUME_SURGE_BID_ASK_RATIO=2.0`, `VOLUME_SURGE_PRICE_THRESHOLD=0.005`, `VOLUME_SURGE_POSITION_SIZE=0.3`

#### 프론트엔드

- `frontend/components/diagnostics/volume-surge-card.tsx`:
  - dry_run 신호 발생 횟수 (실제 주문 없음)
  - 호가창 깊이 시계열
- `frontend/components/diagnostics/time-filter-card.tsx`:
  - 시간대별 신규 진입 차단 횟수

#### 재사용 자산

- Phase 6 KIS WS 안정화 (재연결 백오프, 캐시 TTL 10초) — 호가 스트림에 동일 적용
- Phase 6.1 vol5m Redis 축적 인프라
- Phase 7.0 다층 진입 패턴 (gap 분기) — volume_surge에서 동일 진입 분기 구조

#### 통합 검증

- Paper 1거래일: dry_run 신호 1건 이상 발생 (실제 주문 0건 확인)
- 호가창 스냅샷 정상 수집 (Redis TTL 동작)
- 시간대 필터 09:05 이전·14:30 이후 신규 진입 차단 로그

---

### Sprint 4 ✅ 완료 — Walk-forward 백테스트 + 시뮬↔실측 자동 감지 (PR #208, 2026-05-08)

#### 백엔드

- `backend/modules/backtest/walkforward.py` (신규):
  - 60거래일 데이터셋 로드 (KIS 분봉 백필 — Phase 9 Sprint 0과 동일 메커니즘 차용)
  - TimeSeriesSplit n=2 (40일 학습 / 20일 검증, 슬라이딩)
  - 박스권/추세장 분류기 (KOSPI 60일 변동성 ≤ 1.5σ → 박스권) + 각 ≥20일 보장 검증
  - tier별 시뮬 pass율 산출
- `backend/modules/backtest/distribution_check.py` (신규):
  - 매주 (월요일 00:00) KS 검정 + 카이제곱 적합도 검정
  - 시뮬 pass율 vs 직전 5거래일 실측 pass율
  - p<0.05 시 Telegram 알림 + `BACKTEST_REBUILD_REQUIRED=True` 전환
- `backend/modules/backtest/bootstrap_ci.py` (신규):
  - 일평균 신호 수 95% CI 하한 산출 (n_resamples=1000)
  - CI 하한 ≥ 1 + Paper 5거래일 G-A·G-B 동시 충족 시 `volume_surge`/`prev_high`/`gap_open` LIVE 토글 허용
- `backend/api/routes/backtest.py` (신규):
  - `POST /api/v1/backtest/run` (관리자 토큰 필수)
  - `GET /api/v1/backtest/distribution-check`

#### 프론트엔드

- `frontend/app/admin/backtest/page.tsx`:
  - Walk-forward 실행 버튼 + 결과 테이블 (tier별 pass율 / Bootstrap CI)
  - 시뮬-실측 KS 검정 결과 7주 이동
  - LIVE 토글 게이트 상태 (충족/미충족 시각화)

#### 재사용 자산

- Phase 9 Sprint 0 KIS 분봉 백필 메커니즘 (착수 시점에 일부만 차용)
- Phase 4 대시보드 admin 페이지 패턴 (`/admin/backtest`)

#### 통합 검증

- 60일 백테스트 1회 실행 성공 + 결과 DB 저장
- KS 검정 정상 동작 (인위적 분포 차이 데이터로 p<0.05 유도 확인)
- LIVE 토글 게이트 미충족 시 dry_run 강제 유지 확인

---

## 7. Walk-forward 백테스트 설계 (별도 섹션)

> 박퀀트 §3.4 권고를 본 Phase의 핵심 검증 인프라로 승격. 분기 D 같은 시뮬-실측 괴리(시뮬 38.9% vs 실측 ~3%)를 **자동 감지**하는 것이 목적.

### 7.1 데이터셋 요건

- **기간**: 최소 60거래일 (~3개월)
- **시장 환경 분포**:
  - 박스권 (KOSPI 60일 변동성 σ ≤ 1.5σ_long_term): ≥ 20일
  - 추세장 (그 외): ≥ 20일
  - 둘 다 충족하지 못하면 **데이터셋 부족** 판정 + 백테스트 강행 금지
- **데이터 소스**: KIS REST 분봉 백필 (Phase 9 Sprint 0의 백필 메커니즘 일부 사전 활용)

### 7.2 검증 방법

```
[Day 1 ── Day 40]    학습   (in-sample fitting)
                  [Day 41 ── Day 60]    검증 (out-of-sample)

다음 슬라이드:
[Day 21 ── Day 60]    학습
                  [Day 61 ── Day 80]    검증

... (n=3 슬라이딩, 60일 데이터에서 최소 1 슬라이드, 80일에서 2 슬라이드)
```

- 슬라이드별 검증 R² (또는 tier 활성률)을 보고
- 검증 R² 학습 R² 대비 -10%p 이내일 때만 합격

### 7.3 Bootstrap CI 보고 강제

- 점추정만으로 LIVE 토글 금지
- 일평균 신호 수의 95% CI 하한을 1000회 리샘플링으로 산출
- **하한 ≥ 1**일 때만 "통과" — 분기 D 처럼 "1주 1건"이 우연인지 구조인지 식별

### 7.4 시뮬 ↔ 실측 자동 감지

- **트리거**: 매주 월요일 00:00 KST 자동 잡
- **대상**: 시뮬 tier별 pass율 vs 직전 5거래일 실측 tier별 pass율
- **방법**: KS 2-sample 검정 + 카이제곱 적합도 검정
- **임계**: p < 0.05 시 시뮬 데이터셋 재구축 트리거 + Telegram 알림 + `BACKTEST_REBUILD_REQUIRED=True` 전환
- **목표**: 분기 D(시뮬 38.9% vs 실측 ~3%, KS p ≪ 0.001)를 **다음 사이클에서는 1주 안에 자동 감지**

### 7.5 LIVE 토글 게이트 (3중 직렬 AND — 보수적)

LIVE 활성화는 다음 모두 충족 시에만:

- ✅ **G-Bt1**: Walk-forward 검증 R² 학습 대비 -10%p 이내
- ✅ **G-Bt2**: Bootstrap 95% CI 하한 ≥ 1
- ✅ **G-Bt3**: ~~Paper 5거래일 G-A(일평균 ≥1.5) + G-B(0건 일수 ≤30%) 동시 충족~~ **(Sprint 5 신설 시 갱신, 2026-05-14)** → **§11.5 Phase 8.7 entry gate 10개 지표 모두 통과** 로 교체. (G-Bt1/G-Bt2 walk-forward 통계 검증은 유지하되 §11.5 표 안에 E9/E10 위치로 통합 표기.)

3개 중 1개라도 미충족 시 dry_run 강제 유지.

---

## 8. 전문가 리뷰 인용 매핑 (결정 추적)

| 본 Phase 결정 | 출처 리뷰 / 인용 위치 |
|--------------|---------------------|
| 직렬 AND → 병렬 OR (#1~#5) | 박퀀트 §3.2 |
| ATR 하한 0.025 + 상한 동적 (#6~#10) | 박퀀트 §3.1 + 리스크 §3.2 (패키지 수용) |
| `volume_surge` tier 신설 (#11~#17) | 김단타 §2 패턴 1 + §3 1순위 |
| 09:00~09:10 진입 금지 (#18) | 박퀀트 §3.3 + 김단타 §2 패턴 3 |
| 점심 floor 0.7 (#19) | 박퀀트 §3.3 (구조적 거래량 정정) |
| 14:30+ 신규 진입 금지 (#20) | 박퀀트 §3.3 |
| min_volume_floor 슬라이딩 0.3 09~11시 (#21) | PO 분기 D §2 (사전 SHOULD 승격) |
| 폴백 5종 확장 (#22) | PO 분기 D §2 |
| 자동 롤백 R1~R4 다변화 (#23~#26) | PO §2 (R1) + 리스크 §3 G2 (R2~R4) |
| M-F2 측정 (#27) | PO §2 + 리스크 §3 G1 + 퀀트 §2 |
| 폴백 종목 일일 -1% 별도 한도 (#29) | 리스크 §3 G4 |
| volume_surge position 30% (#30) | 리스크 G4 + 단타 신규 tier 보수 적용 |
| dry_run 우선 + LIVE 토글 (#32, §7.5) | 리스크 §3 G5 |
| 60일 walk-forward + Bootstrap CI (#33~#37) | 박퀀트 §3.4 |
| KS 자동 감지 (#36) | 박퀀트 §3.4 |
| LIVE 토글 게이트 3중 (#38) | 리스크 G5 + 박퀀트 §3.4 + PO §2 |
| Phase 8.6 점프 vs 즉시 재배포 — Sprint 1 흡수 결정 | PO §3 (Sprint 2.6 안) — 사용자 구조 재설계 선택 후 흡수 |
| LIVE 자금 보호 가드레일 (DoR) | 리스크 §3 P0 (G1~G3) |
| Phase 7.0 LIVE 파라미터 잠금 | 리스크 §3 G9 |

---

## 9. 미해결 사항 / 리스크

### ⚠️ 알려진 리스크 (전문가 지적 + 미완화)

1. ~~**Sprint 3 호가창 스트림 인프라 의존성** (Sprint 3 신규 부담)~~
   - ~~KIS WS 호가창 5호가 잔량 데이터를 안정적으로 받을 수 있는지 Sprint 3 착수 전 spike 필요~~
   - ~~완화: Phase 6 WS 안정화 인프라 재사용 + Sprint 3 첫 Task에 KIS WS 호가 데이터 수신 검증 1일 spike~~
   - ✅ 해결 (Sprint 3, 2026-05-08): Phase 6 인프라 재사용으로 호가창 스트림 정상 통합

2. ~~**Walk-forward 60일 데이터 백필 시간** (Sprint 4)~~
   - ~~KIS REST 분봉 백필은 Phase 9 Sprint 0에서 처음 본격 시도 예정 — 본 Phase 4에서 차용 시 일정 압박~~
   - ~~완화: Phase 9 Sprint 0의 백필 메커니즘 일부를 Sprint 2 시점부터 점진 활용 (별도 트랙 병행)~~
   - ✅ 해결 (Sprint 4, 2026-05-08): kis_daily_collector 인프라 재사용 (배치 50건 + 지수 백오프), 일봉 60일만 사용 (분봉은 Phase 9 Sprint 0 유지)

3. ~~**시간대 필터 + 09:00~09:10 진입 금지의 신호 추가 차단 위험** (Sprint 3)~~
   - ~~Sprint 1의 min_volume_floor 슬라이딩(0.3 09~11시)과 시간대 필터가 충돌 시 09~09:10은 어차피 차단되므로 슬라이딩 효과가 약화~~
   - ~~완화: gap_open tier만 09:05까지 예외로 두어 갭 단타는 보존 (단타 §2 패턴 3)~~
   - ✅ 해결 (Sprint 3, 2026-05-08): `_time_filter.py` should_block_entry gap_open 예외 구현 완료 + 43종 단위 테스트 통과

4. **병렬 OR로 신호 수가 너무 많이 늘어날 위험** (Sprint 2)
   - 현재 일일 10건 한도(Phase 7.2)가 있지만, 1주에 70건+ 발생 시 LIVE 자금 분산
   - 완화: 일일 신호 한도 10건 유지 + 신호 우선순위 (volume_surge > prev_high > gap_open > prev_close) 큐 적용

5. **dry_run → LIVE 토글 인적 오류 위험** (Sprint 4)
   - 게이트 G-Bt1~3 충족이 자동 평가지만 실제 토글은 사용자 수동
   - 완화: 토글 시 텔레그램 2단계 확인 + 24시간 후 자동 dry_run 복귀 옵션

### ❌ 거부된 제안 (분기 D 재리뷰에서)

- **Phase 10 (U자형 비선형) 동시 착수** — 사용자 2026-04-20 "완화 불가" 확정 유지, 분기 D는 U자형과 무관
- **2차 pass_threshold 75 추가 완화** — PO §2 + Sprint 2.5 검증 결과 임계 자체는 무결, 직렬 AND 구조 변경이 우선
- **Phase 8.5 폴백 전면 폐기** — PO §2 거부, 폴백 자체는 정상 작동했음
- **prev_close 13:00 → 14:00 연장** — 분기 D 원인 분석 우선순위 낮음 (Phase 8.5 사전 거부 결정 유지)

### Sprint 3 코드 리뷰 발견 이슈 (sprint-review 자동 검증)

| # | 파일 | 내용 | Severity | 조치 |
|---|------|------|----------|------|
| B1 | `api/routes/metrics.py` | `volume-surge-stats` GROUP BY — `func.date_trunc("day", col)` 사용 시 asyncpg GroupingError 발생. `func.cast(..., Date)` 로 fix 완료 (aca388a) | Critical → **수정 완료** | fix 커밋 aca388a 포함됨 |

### Sprint 4 코드 리뷰 발견 Medium 이슈 (Phase 8.7에서 개선 권장)

| # | 파일 | 내용 | Severity | 조치 |
|---|------|------|----------|------|
| S4-M1 | `api/routes/backtest.py` | `POST /backtest/run` trigger_run이 uuid를 직접 생성해 반환하지만 실제 WalkForwardRunner.run()은 내부에서 별도 uuid를 생성함 — 클라이언트가 받은 run_id로 DB를 조회하면 항상 404 반환 | Medium | Phase 8.7에서 run_id를 runner에 주입하거나 반환값 poll 방식으로 교체 권장 |
| S4-M2 | `modules/backtest/live_gate.py` | G-Bt1 "no_completed_backtest_run" 상태에서 passed=True 반환 — 최초 배포 후 백테스트 미실행 시 LIVE 게이트 G-Bt1을 자동 통과함 (underspecified=True 명시, 의도적 설계) | Medium | 첫 배포 후 즉시 백테스트를 실행하거나, 미완료 시 passed=False로 보수 처리하는 옵션 검토 (Phase 8.7) |

### Sprint 1 코드 리뷰 발견 Medium 이슈 (Sprint 2에서 개선 권장)

| # | 파일 | 내용 | Severity | Sprint 2 조치 |
|---|------|------|----------|--------------|
| M1 | `modules/safety/auto_rollback.py` | `_prev_days` 함수 독스트링 "오늘 포함 직전 count일"과 모듈 독스트링 "직전 3거래일" 표현 불일치 (기능은 정상, 문서 혼란 소지) | Medium | 모듈 독스트링을 "오늘 포함 직전 N일" 또는 "N일 (오늘부터 역산)"으로 통일 |
| M2 | `api/routes/metrics.py` | `phase86-status` API rollback_active/circuit_active 판정이 `is not None` (key 존재 확인) — `circuit_breaker.is_active()`는 값 비교("true","1","yes"). 실제 쓰기가 항상 "true"여서 동작 동일하나 일관성 결여 | Medium | `is not None` → 값 비교 방식으로 통일 |

### 🤔 사용자 최종 결정 필요 항목

1. **Sprint 4 walk-forward용 KIS 분봉 백필을 Phase 9 Sprint 0과 분리해 본 Phase에서 부분 진행할지** (일정 압박 vs Phase 9 일정 보존 트레이드오프)
2. **dry_run → LIVE 토글 게이트(G-Bt1~3) 충족 시 자동 토글 vs 사용자 수동 승인** (현 본문은 수동 + 텔레그램 2단계 권고)

> **참고**: Phase 8.6 → Phase 10.1 분리(기존 백로그 이관)는 본 Phase 전제로 **이미 채택**되어 §1.4 / §5 / §6 / §10 전반에 반영됨. 사용자가 명시적으로 거부할 경우에만 본 문서 절반의 재작성이 필요하므로 별도 결정 항목이 아닌 **착수와 동반 적용**으로 처리.

---

## 10. 완료 기준 (Phase 8.6 전체 DoD)

| # | 항목 | 기준 | 상태 |
|---|------|------|------|
| 1 | DoR 통과 (G1·G2·G3 + Phase 7.0 잠금) | Sprint 1 종료 시점 4종 모두 ✅ | ✅ 완료 (2026-04-29, PR #181) |
| 2 | 병렬 OR tier 분리 배포 | Sprint 2 완료 + 단위 테스트 통과 | ✅ 완료 (2026-04-22, PR #186) |
| 3 | ATR 분위수 캘리브레이션 09:00 잡 동작 | Sprint 2 완료 + Redis 저장 확인 | ✅ 완료 (2026-04-22, PR #186) |
| 4 | `volume_surge` tier dry_run 배포 | ~~Sprint 3 완료 + Paper 5거래일 dry_run 신호 ≥ 5건~~ **(2026-05-14: "Paper 5거래일 ≥5건" 기준은 §11.5 entry gate로 대체, 코드 배포만 기준)** | ✅ 완료 (2026-05-08, PR #200) — Paper 5거래일 카운트 기준은 §11.5 10개 지표로 교체됨 |
| 5 | 시간대 필터 동작 (09:00~09:10·14:30+) | Sprint 3 완료 + 단위 테스트 + Paper 1거래일 차단 로그 | ✅ 완료 (2026-05-08, PR #200) — Sprint 5 T2 shadow mode 측정으로 운영 분포 검증 승계 |
| 6 | 60일 Walk-forward 백테스트 1회 성공 | Sprint 4 완료 | ✅ 완료 (2026-05-08, PR #208) |
| 7 | 시뮬-실측 KS 자동 감지 잡 동작 | Sprint 4 완료 + p<0.05 인위 데이터 트리거 검증 | ✅ 완료 (2026-05-08, PR #208) — KS/카이제곱 잡 구현, 1172 passed |
| 8 | LIVE 토글 게이트 G-Bt1~3 미충족 시 dry_run 강제 유지 | Sprint 4 완료 + 통합 테스트 | ✅ 완료 (2026-05-08, PR #208) — 매주 월요일 자동 평가 잡 + Redis dry_run_forced 강제 |
| 9 | ~~G-A: Paper 5거래일 일평균 신호 ≥ 1.5~~ **(Sprint 5 신설 시 deprecated, 2026-05-14)** | Sprint 3 종료 후 5거래일 관찰 | ⚠️ deprecated — §11.5 Phase 8.7 entry gate로 교체. 5/13~14 모니터링에서 표면 카운트 게이트의 한계 입증 (신호 2건이지만 출처 신뢰도 미입증). 모니터링 카드로 강등, gate에서 제외. |
| 10 | ~~G-B: 0건 일수 ≤ 30% (≤1/5)~~ **(deprecated, 2026-05-14)** | Sprint 3 종료 후 5거래일 관찰 | ⚠️ deprecated — 동일 사유 |
| 11 | ~~G-C: tier 다양성 ≥ 3종 활성~~ **(deprecated, 2026-05-14)** | Sprint 3 종료 후 5거래일 관찰 | ⚠️ deprecated — 동일 사유 (단일 stage 점유율 기준으로 §11.5에서 재정의) |
| 12 | G-D: tier 페어와이즈 상관 ≤ 0.3 | Sprint 4 종료 시 60일 데이터 산출 | ⬜ |
| 13 | G-E: 시뮬-실측 pass율 괴리 ≤ 5%p | Sprint 4 KS 검정 p ≥ 0.05 | ⬜ |
| 14 | G-F: 폴백 신호율(M-F2) 일별 산출 + 대시보드 카드 | Sprint 1 완료 + 5거래일 대시보드 정상 | ⬜ |
| 15 | G-G: 자동 롤백 R1~R4 다중 트리거 동작 | Sprint 1 완료 + 4종 단위 테스트 | ⬜ |
| 16 | pytest 전체 통과 | 각 Sprint 종료 시점 | ⬜ |
| 17 | 회귀 0건: Phase 7.0 LIVE 파라미터 코드 잠금 | Sprint 1 완료 + 빌드 실패 테스트 | ⬜ |

위 17개 모두 ✅ 후 Phase 8.6 Sprint 1(E2E + LIVE 게이트)로 진행.

---

## 11. Sprint 5 신설 — 진단 + 측정 인프라 (2026-05-14)

> **Status**: 계획 수립 완료, 사용자 승인 대기
> **트리거**: 2026-05-13~14 Phase 8.6 신호 발생 모니터링에서 14개 결함 발견 (5건 hotfix 처리 / 9건 미해결)
> **모니터링 근거**: `docs/phase/phase8.6/sprint4/2026-05-13-monitoring-result.md` + `docs/phase/phase8.6/sprint4/2026-05-14-monitoring-result.md`
> **검토 4명**: 윤에이피(API) + 박퀀트(퀀트) + 최리스크(리스크) + 정프로(PO) — Sprint 5 신설 리포트 참조
> **메타**: 본 신설 계획의 4명 전문가 검토는 Agent 서브에이전트 도구가 본 환경에서 제공되지 않아 phase-planner 내부에서 각 페르소나(`docs/experts/*.md`) + 모니터링 결과 2건을 입력으로 합성 작성됨. 추적성 확보를 위해 4 리뷰 파일은 동일 디렉토리에 별도 산출물로 보존.

### 11.1 14개 결함 분류 + 처리 경로

> 사용자 명시: "기존 5개 hotfix는 Sprint 5에서 추가 완화/되돌리기 안 함, 단 구조 변경 후 재평가 가능"

#### 이미 처리한 5건 — 모두 유지 (Sprint 5 동안 unchanged)

| # | 결함 | 처리 | PR |
|---|------|------|-----|
| 1 | `change_rate_max 7→30` (A안 1차 모멘텀 차단 해제) | hotfix | PR #233 |
| 2 | `trade_strength_min 100→80` (A안 2차 모멘텀 차단 해제) | hotfix | PR #233 |
| 3 | `ATR_FILTER_PCT 0.05→0.07` | hotfix | PR #231 |
| 4 | `MIN_VOLUME_FLOOR_HARD 0.3→0.25` | hotfix | PR #231 |
| 5 | `/virtual-signals?stock_code=` 필터 추가 | hotfix | PR #236 |

#### 미해결 9건 — Sprint 5/hotfix/Sprint 6 분류

| # | 결함 | 본질도 | 처리 경로 | 의사결정 근거 |
|---|------|--------|----------|--------------|
| 6 | **KIS WS execution 35% 누락** (2차 통과 100% 영향, fallback 강제 발동의 root cause 후보) | 최본질 | **Sprint 5 T1 진단** | 윤에이피 §1 인과 사슬 / 최리스크 §2 P0 / advisor §2 |
| 7 | `SECONDARY_POOL_FALLBACK_ENABLED` unset 분기 누락 | 작음 | **즉시 hotfix (Sprint 5 외)** + SettingsOverrideKey Enum 단일 진실 소스 묶음 | 윤에이피/최리스크/PO 만장일치 |
| 8 | R1 자동 발동 원인 의문 (signals=2 임에도 active) | 본질 | **Sprint 5 T3 진단** | plan-code 일치 검증 |
| 9 | G3 임계 부등호 (`≤10%` vs `≥10% 미발동`) | 단발 | **Sprint 5 T4 진단 후 hotfix 여부 결정** | advisor §4 — 코드 의도 확인 없이 hotfix 위험 |
| 10 | breakout 72.2% 단일 stage 편중 | 본질 | **Sprint 5 T2 shadow mode 측정 → Sprint 6 결정** | #6 종속 가능성 + baseline 부재 |
| 11 | **임계 게임 패턴 (#11 사용자 최본질 지목)** — 진짜 본체는 stage 직렬 AND 결합 (Sprint 2의 tier 병렬 OR가 한 층 아래 stage에는 미적용) | 최본질 | **Sprint 5 T2 shadow mode → Sprint 6 stage 결합 정책 변경** | 박퀀트 §1 / advisor §2 |
| 12 | `/screening/primary` 응답 스키마에 `change_rate` 필드 없음 (운영 진단 불가) | 작음 | **즉시 hotfix (Sprint 5 외)** | response_model 단순 확장 |
| 13 | fallback 폭증 (오늘 456건) — 신호 신뢰도 미입증 | 본질 | **Sprint 5 T5 M-F2 정량화** | #6 종속 |
| 14 | secondary 통과 종목 4h 100% 교체 | 본질 | **Sprint 5 T1/T5 (#6 종속 진단)** | #6 root cause면 자연 해소 |

**미검증 trace 3건** (Sprint 5 T7 sub-체크리스트):
- momentum_breakout 평가 경로에 +7% 종목 도달 여부
- `_get_realtime_data` 폴백 로직 (execution null 시 처리)
- R3 자동 SET 로직 (정확한 발동 시각/조건 미관찰)

### 11.2 Sprint 5 핵심 원칙 (전문가 4명 합의)

1. **진단 + 측정 인프라 Sprint** — 임계 변경 0건, dry_run 변경 0건, LIVE_TRADING_ENABLED false 잠금
2. **기존 5개 hotfix 유지** (사용자 명시) — Sprint 5 동안 측정 노이즈 회피
3. **shadow mode 도입** — `momentum_breakout` 4 stage 모두 평가 (reject 차단 X, 평가 결과만 로깅) — 박퀀트 권고
4. **#6 root cause 진단 1순위** — 윤에이피/최리스크 P0
5. **#11 (임계 게임) 진짜 본체는 stage 직렬 AND 결합** — 박퀀트 진단 (tier는 Sprint 2에서 이미 OR)
6. **hotfix 2건 즉시 분리** (#7, #12), #9는 Sprint 5 T4 진단 후 결정
7. **Phase 7.0 LIVE 파라미터 영구 잠금 유지** (최리스크 G9)

### 11.3 Sprint 5 Task 구성 (8 Task, 1.5~2주)

| Task | 내용 | 산출물 | 기간 | 담당 영역 |
|------|------|--------|------|----------|
| **T1** | **#6 KIS WS execution 35% 누락 root cause trace** — A(KIS 한도) / B(subscribe 레이스) / C(MST sync) 3개 후보 trace. `WS_TRACE_ENABLED=true` env 토글 + 1~2 거래일 KIS 응답 코드 캡처 | 진단 보고서 + root cause 후보 채택 | 3~5일 | 윤에이피 |
| **T2** | **stage shadow mode 도입** — `momentum_breakout` 4 stage 모두 평가 (reject 없이 점수만 기록, Redis stream + 일별 stage 통과 패턴 집계 API) | shadow mode 모듈 + `/metrics/stage-shadow` API + dashboard 카드 | 5~7일 | 박퀀트 |
| **T3** | **#8 R1 자동 발동 원인 진단** — `AutoRollbackEvaluator` 코드 vs phase8.6 §5.5 1:1 대조 + 05-15 자동 해제 분기 관찰 + R1~R4 trigger snapshot Telegram 알림 | 진단 보고 + plan-code 불일치 리스트 + Telegram payload 확장 | 2~3일 | 최리스크 |
| **T4** | **#9 G3 부등호 코드 의도 확인** — `pass_rate < 0.10` vs `≤ 0.10` 확인 + 안전망 임계 부등호 전수 검사 (R1~R4 + G3 + 기타) + 의도 어긋남 시 hotfix 분리 | 부등호 audit 결과 + (필요 시) hotfix PR | 1일 | 박퀀트 |
| **T5** | **fallback 신호 비중 (M-F2) 정량화 + 신호 신뢰도 분리** — fallback 발동 종목 신호 vs 정상 종목 신호 일별 분리 집계 + Phase 8.7 entry gate "fallback 신호 비중 ≤ 20%" 측정 인프라 | M-F2 신호 비중 API + 일별 분리 대시보드 카드 | 3~4일 | 박퀀트/윤에이피 |
| **T6** | **R3 자동 SET/UNSET audit log + 자가치유 전수 회귀** — `SettingsOverrideKey` Enum (단일 진실 소스) + 모든 키 unset 분기 자동 포함 + audit log (시점/조건/trigger value 적재) + 전수 회귀 테스트 | enum + audit log + 회귀 테스트 ≥10 PASS | 2~3일 | 최리스크 |
| **T7** | **미검증 trace 3건 완료** — `_get_realtime_data` 폴백 trace + momentum_breakout +7% 종목 평가 경로 trace + R3 자동 SET 시점 관측 (T1/T6의 sub-체크리스트로 통합 가능) | trace 보고서 + Sprint 5 통합 보고에 부록 | 1일 | 윤에이피/박퀀트 |
| **T8** | **Phase 8.7 entry gate 재정의 문서화 + 측정 dashboard** — §11.5의 10개 지표 dashboard 카드 + 일일 측정 + 통과/미통과 판정 자동화 | gate 문서 + `/admin/phase87-gate` dashboard | 2~3일 | PO/UX |

**병렬 가능 조합**: T1 + T2 + T6 (인프라 영역 분리). T3 + T4 (안전망 영역). T5 + T8 (지표 영역). T7은 T1/T6 sub로 흡수 가능.

### 11.4 Sprint 5 Definition of Done

| # | 항목 | 기준 | 상태 |
|---|------|------|------|
| S5-1 | #6 root cause 후보 1개 이상 채택 + 재현 방법 문서화 | T1 진단 보고서 | ⬜ |
| S5-2 | stage shadow mode 1차 풀 20종 × 4 stage = 80건 평가/분당 정상 로깅 | Paper 1거래일 검증 | ⬜ |
| S5-3 | R1~R4 plan-code 1:1 대조 결과 + 불일치 fix or 문서 갱신 | T3 보고서 | ⬜ |
| S5-4 | G3 부등호 audit 결과 + (필요 시) hotfix 머지 | T4 audit | ⬜ |
| S5-5 | M-F2 신호 비중 일별 산출 정상 + 대시보드 카드 노출 | Paper 1거래일 검증 | ⬜ |
| S5-6 | `SettingsOverrideKey` Enum + R3 자가치유 전수 회귀 테스트 ≥10 PASS | T6 테스트 | ⬜ |
| S5-7 | 미검증 trace 3건 결론 도출 (T1/T6 흡수 가능) | T7 보고서 | ⬜ |
| S5-8 | Phase 8.7 entry gate 10개 지표 dashboard + 일일 자동 판정 | T8 dashboard | ⬜ |
| S5-9 | pytest 전체 통과 | 각 Task 종료 시점 | ⬜ |
| S5-10 | Phase 7.0 LIVE 파라미터 잠금 회귀 0건 | 빌드 실패 테스트 | ⬜ |

### 11.5 Phase 8.7 entry gate 재정의 (사용자 요청 직접 응답)

> 사용자 명시: "5거래일 일평균 ≥1 게이트는 무의미하다 — 표면 통과형 게이트 X. 신호 신뢰도 입증 (fallback 비중 / WS 누락률 / stage 다양성 등) 기반으로."

**기존 §10 DoD #9~#11 (5거래일 관찰 G-A/G-B/G-C) 폐기 → 다음 10개 지표로 교체.** §7.5 G-Bt3 정의도 본 §11.5로 갱신. G-Bt1(walk-forward KS p≥0.05), G-Bt2(Bootstrap CI 하한 ≥1) 는 유지.

| 카테고리 | # | 지표 | 임계 | 측정 출처 | 근거 |
|---------|---|------|------|----------|------|
| **데이터 인프라** | E1 | WS execution 누락률 (1차 풀 대비) | **≤ 5%** | Sprint 5 T1 + T8 일별 | 최리스크 §3 (윤에이피 ≤10% 강화) |
| **신호 신뢰도** | E2 | fallback 신호 비중 (M-F2) | **≤ 20%** | Sprint 5 T5 일별 | 최리스크 §3 |
| **신호 신뢰도** | E3 | 단일 stage 점유율 | **≤ 50%** | Sprint 5 T2 shadow mode 일별 | 박퀀트 §2 #10 |
| **신호 신뢰도** | E4 | Secondary 통과 종목 4h 교체율 | **≤ 30%** | Sprint 5 T8 일중 측정 | 최리스크 §2 #14 |
| **신호 성과** | E5 | Paper 신호 PnL 5거래일 누적 | **양(+)** | Phase 8.7 Sprint 1 측정 | 박퀀트 §3 / advisor §5 |
| **안전망 신뢰도** | E6 | 손절 체결 발생 (Paper 5거래일) | **≥ 1** | Phase 8.7 Sprint 1 측정 | 최리스크 §3 / advisor §5 |
| **안전망 신뢰도** | E7 | R1~R4 plan-code 일치 단위 테스트 통과 | **통과** | Sprint 5 T3 | 최리스크 §3 (P0 신규) |
| **안전망 신뢰도** | E8 | R3 자가치유 settings:override:* 전수 회귀 통과 | **통과** | Sprint 5 T6 | 최리스크 §3 (P0 신규) |
| **통계 검증 (승계)** | G-Bt1 | walk-forward KS 검정 p | **≥ 0.05** | Phase 8.6 §7.5 승계 | 박퀀트 §3 |
| **통계 검증 (승계)** | G-Bt2 | Bootstrap 95% CI 하한 | **≥ 1** | Phase 8.6 §7.5 승계 | 박퀀트 §3 |
| (참고 트래픽) | — | Paper 일평균 신호 수 | (gate 아님, 모니터링만) | 모니터링 카드 | advisor §5 — 0건 검출 자체는 필요, gate 부적격 |

**통과 조건**: 위 10개 지표 모두 통과 (직렬 AND). 단 1개라도 미충족 시 Phase 8.7 Sprint 1 LIVE 토글 차단.

> **E5/E6의 "5거래일" 윈도우는 측정창이지 카운트 게이트가 아님**: 사용자가 거부한 것은 "5거래일 일평균 ≥1" 식의 *카운트* 게이트이지 5거래일 측정창 자체가 아니다. E5(Paper PnL 누적)·E6(손절 체결 ≥1)는 *품질* 지표로 5거래일이 합리적 측정창. 사용자가 5거래일 윈도우 자체도 거부할 경우 7~10거래일로 확장하거나 누적 종목 수 기반 측정으로 전환 가능 (§14 사용자 다음 단계에서 옵션 제시).

### 11.6 Sprint 5 Sprint planner 호출 시 입력

- 본 §11.1~§11.5 + 4 reviewer 리포트 (`phase8.6-sprint5-{api,quant,risk,po}-review.md`)
- 모니터링 결과 2건 (`sprint4/2026-05-13-monitoring-result.md` + `sprint4/2026-05-14-monitoring-result.md`)
- 브랜치명 후보: `phase8.6-sprint5`

### 11.7 hotfix 분리 처리 (Sprint 5 외 트랙)

> Sprint 5 본 작업 전에 또는 병행으로 처리. Sprint 5 브랜치는 hotfix 머지 후 rebase.

#### Hotfix A: #7 SECONDARY_POOL_FALLBACK_ENABLED unset + SettingsOverrideKey Enum

- **변경 파일** (예상): `backend/modules/safety/auto_rollback.py`, `backend/core/constants.py` (or `settings.py`), tests
- **내용**: `SettingsOverrideKey` Enum 도입 + R3 자가치유 분기에서 enum.iter 기반 unset + 회귀 테스트
- **브랜치**: `hotfix/phase86-r3-unset-enum`

#### Hotfix B: #12 `/screening/primary` change_rate 노출

- **변경 파일** (예상): `backend/api/routes/screening.py`, response_model, tests
- **내용**: `PrimaryCandidateResponse` 스키마에 `change_rate: float` 필드 추가
- **브랜치**: `hotfix/phase86-primary-change-rate`

#### #9 (G3 부등호) — Sprint 5 T4 진단 후 결정 (즉시 hotfix 후보 아님)

---

## 12. Sprint 6 — placeholder (Sprint 5 결과 의존)

> **Status**: placeholder, 풀 스펙 미작성 (advisor §3 권고)
> **착수 시점**: Sprint 5 완료 (예상 2026-05-30 전후) 후 별도 sprint-planner 호출
> **이유**: Sprint 5 진단 결과에 따라 Sprint 6 작업 범위가 완전히 달라짐

### 12.1 Sprint 5 진단 결과별 Sprint 6 방향 분기

| Sprint 5 진단 결과 | Sprint 6 방향 |
|------------------|-------------|
| #6 root cause = **KIS 구독 한도 초과** | 1차 풀 축소 (20→18) + 우선순위 큐 (score 기준) + 잔여 슬롯 polling. `PRIMARY_POOL_SIZE` env. |
| #6 root cause = **subscribe 레이스** | subscribe 응답 코드 0 미확인 시 재시도 + 누락 종목 분리 재구독 + Telegram 알림 (Phase 6 WS 안정화 인프라 재사용) |
| #6 root cause = **MST sync 타이밍** | MST sync 강제 동기화 + `KOSPI200_MST_SYNC` kill-switch 활용 |
| #6 fix 불가 (KIS 한계) | LIVE 전환 무기한 보류 + execution 정상 종목만 신호 발행 대상으로 제한 (fallback 종목은 dry_run 평가) |
| stage shadow mode = 다수결 ≥3/4 유효 | stage 결합 정책 변경 (직렬 AND → 다수결): shadow → dry_run → 본 도입 단계적 |
| stage shadow mode = 가중치 학습 가능 | stage 가중치 학습 + OOS R² > 0 검증 후 도입 |
| R1~R4 plan-code 불일치 발견 | 안전망 plan-code 통일 + Telegram alert payload 강화 + 회귀 테스트 |
| fallback 신호 비중 (M-F2) ≤ 20% 달성 | Phase 8.7 entry gate E2 자동 통과 → 다른 지표 집중 |
| fallback 신호 비중 (M-F2) > 50% | fallback 경로 자체 재설계 (Phase 8.5 폴백 일부 폐기 검토) |

### 12.2 Sprint 6 일단 예측 가능한 공통 Task

- 기존 5개 hotfix 임계 재평가 (Sprint 5 측정 결과 기반) — 사용자 명시 "구조 변경 후 재평가 가능"
- Phase 8.7 entry gate 10개 지표 통과 여부 일일 측정 + 미통과 지표 fix
- Sprint 6 자체 회귀 테스트 + Paper 1거래일 통합 검증

### 12.3 Sprint 7 — 작성 X

Sprint 6 완료 후 Phase 8.7 entry gate 10개 지표 전수 통과 시 Sprint 7 미필요 → Phase 8.7 Sprint 1 (LIVE 게이트) 직접 진입. 미통과 시 Sprint 7 신설 후 잔여 결함 대응.

---

## 13. 14개 결함 추적 표 (Sprint 5/6 처리 경로 종합)

| # | 결함 | 상태 | 처리 | 산출물 |
|---|------|------|------|--------|
| 1 | change_rate_max 7→30 | ✅ 완료 | PR #233 hotfix | hotfix/phase86-real-momentum-strategy |
| 2 | trade_strength_min 100→80 | ✅ 완료 | PR #233 hotfix | (동일) |
| 3 | ATR_FILTER_PCT 0.05→0.07 | ✅ 완료 | PR #231 hotfix | hotfix/phase86-atr-volume-floor-relax |
| 4 | MIN_VOLUME_FLOOR_HARD 0.3→0.25 | ✅ 완료 | PR #231 hotfix | (동일) |
| 5 | /virtual-signals?stock_code= 필터 | ✅ 완료 | PR #236 hotfix | hotfix/virtual-signals-stock-code-filter |
| 6 | **KIS WS execution 35% 누락** | ⬜ | Sprint 5 T1 진단 → Sprint 6 fix | 진단 보고서 + Sprint 6 PR |
| 7 | SECONDARY_POOL_FALLBACK_ENABLED unset | ⬜ | **Hotfix A** (Sprint 5 외) | hotfix/phase86-r3-unset-enum |
| 8 | R1 자동 발동 원인 의문 | ⬜ | Sprint 5 T3 진단 | T3 보고서 + 알림 payload 확장 |
| 9 | G3 임계 부등호 불일치 | ⬜ | Sprint 5 T4 진단 → 필요 시 hotfix | T4 audit |
| 10 | breakout 72.2% 단일 stage | ⬜ | Sprint 5 T2 shadow mode 측정 → Sprint 6 결정 | shadow mode 측정 데이터 |
| 11 | **임계 게임 = stage 직렬 AND** | ⬜ | Sprint 5 T2 shadow → Sprint 6 결합 정책 변경 | Sprint 6 stage 결합 정책 |
| 12 | /screening/primary change_rate 노출 | ⬜ | **Hotfix B** (Sprint 5 외) | hotfix/phase86-primary-change-rate |
| 13 | fallback 폭증 (456건) | ⬜ | Sprint 5 T5 정량화 → #6 종속 fix | M-F2 신호 비중 API |
| 14 | secondary 4h 100% 교체 | ⬜ | Sprint 5 T1 (#6 종속) | T1 진단 보고서 |
| trace-1 | momentum_breakout +7% 종목 도달 | ⬜ | Sprint 5 T7 | trace 보고서 |
| trace-2 | `_get_realtime_data` 폴백 로직 | ⬜ | Sprint 5 T7 (#6 종속) | trace 보고서 |
| trace-3 | R3 자동 SET 로직 | ⬜ | Sprint 5 T6 audit log | audit log + 회귀 테스트 |

---

## 14. 사용자 다음 단계 (Sprint 5 진입)

본 문서는 **Sprint 5 신설 계획 수립 완료 (사용자 승인 대기)** 상태이다.

### 선택지

1. **승인 → Hotfix A/B 즉시 분리 + Sprint 5 sprint-planner 호출** (권고)
2. **§11.5 entry gate 10개 지표 임계 수정 후 승인** — 예: WS execution 누락률 ≤5%를 ≤10%로 완화 등 (단 최리스크 권고 강화값을 임의 완화 시 LIVE 안전성 손실)
3. **Sprint 5 Task 우선순위 변경** — 예: T1(#6 진단) 대신 T2(shadow mode) 우선
4. **거부 / 재검토** — Sprint 5 신설 보류, 다른 방향

선택 후 다음 자동 진행:
- Sprint 5 승인 시: `hotfix/phase86-r3-unset-enum` + `hotfix/phase86-primary-change-rate` 즉시 분리 처리 → `phase8.6-sprint5` 브랜치에서 sprint-planner 호출
- ROADMAP.md Phase 8.6 절 갱신 (Sprint 5 신설 표시 + 다음 마일스톤을 "Phase 8.6 Sprint 5" 로 갱신)
- index.json phase8.6 sprints 배열 갱신

### 먼저 검토 권장 섹션

- §11.1 14개 결함 분류 (의사결정 기록)
- §11.2 Sprint 5 핵심 원칙 7개 (특히 "임계 변경 0건, dry_run 변경 0건" 강제)
- §11.5 Phase 8.7 entry gate 10개 지표 (사용자 요청 직접 응답)
- §12 Sprint 6 placeholder (advisor §3 권고 — 미리 풀 스펙 X)
- §13 14개 결함 추적 표 (전수 처리 경로 확인)

### Sprint 5 신설 결정 추적

| 결정 | 근거 | 출처 |
|------|------|------|
| Sprint 1~4 본문 unchanged | 사용자 명시 + 추적성 | 사용자 메시지 |
| §10 DoD #9~#11 deprecated (삭제 X) | 추적성 | advisor §9 |
| §7.5 G-Bt3을 §11.5 10개 지표로 교체 (G-Bt1/G-Bt2 유지) | phase8.6 내부 모순 방지 | advisor §6 |
| Sprint 5 = 진단 + 측정 Sprint, 임계 변경 0건 | 4명 전문가 합의 | 윤/박/최/PO 리뷰 |
| Sprint 6은 placeholder만 | Sprint 5 결과 의존 | advisor §3 |
| #9 hotfix 즉시 분리 X | 코드 의도 미확인 | advisor §4 |
| Phase 8.7 entry gate = 10개 지표 (표면 카운트 폐기) | 사용자 요청 + 4명 합의 | 사용자 메시지 + advisor §5 |
| Phase 7.0 LIVE 파라미터 영구 잠금 유지 | Phase 표준 (최리스크 G9) | 분기 D 4명 재리뷰 승계 |
