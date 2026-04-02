# Phase 4.7: 1차 스크리닝 스코어링 구조 수정 — 실행 계획

> **Status**: Sprint 1 완료 (2026-04-02)
> **ROADMAP 참조**: `ROADMAP.md` Phase 4.7
> **검토 리포트**:
>
> - `phase4.7-po-review.md` (정프로, PO)
> - `phase4.7-risk-review.md` (최리스크, 리스크관리)
> - `phase4.7-quant-review.md` (박퀀트, 퀀트)
> - `phase4.7-trader-review.md` (김단타, 단타 전문가)

---

## 개요

프로덕션 배포 첫날(2026-04-02)부터 **1차 스크리닝(primary_screen)이 단 한 건도 후보를 통과시키지 못하는 치명적 설계 버그**를 발견했다. 1차 스크리닝에서 실시간 데이터가 필요한 팩터 2개(체결강도, 호가잔량)에 고정 중립값을 넣은 결과, 동률 처리 로직에 의해 해당 팩터의 백분위가 ~2%로 고정되어 **이론적 최대 스코어 60.91점 < 임계값 80.0점**인 구조적 결함이다.

### 버그 파이프라인 영향도

```
[1차 스크리닝] ─ is_passed 항상 0건 ─┐
                                      ├─> WS 구독 0건
                                      ├─> 2차 스크리닝 후보 0건
                                      ├─> 매매 신호 생성 불가
                                      └─> DART/센티멘트 수집 대상 0건
```

### 버그 수치 증명 (44개 필터 통과 후보 기준)

```
팩터               값       rank    percentile (N=44)
---------------------------------------------------------
volume_factor      각기 다름  1~44    2.27% ~ 100%        가중 0.2
volatility_factor  각기 다름  1~44    2.27% ~ 100%        가중 0.2
momentum_factor    각기 다름  1~44    2.27% ~ 100%        가중 0.2
trade_strength     전부 50.0  1       2.27% (고정)         가중 0.2
orderbook_ratio    전부 1.0   1       2.27% (고정)         가중 0.2

최대 스코어 = (100*0.2)*3 + (2.27*0.2)*2 = 60 + 0.91 = 60.91 < 80.0(임계값)
```

### 해결 방향: A안 채택 (전문가 전원 합의)

| 방안 | 설명 | 판정 | 근거 |
|------|------|------|------|
| **A안** | 1차 스크리닝에서 실시간 팩터 제외, 3팩터(volume/volatility/momentum)만 사용 | **채택** | 가용 데이터만 사용, 역할 분리 명확, 통계적으로 올바름 |
| B안 | 중립 팩터에 고정 percentile=50 부여 | 기각 | 정보 없음을 "평균"으로 가장, 편향 주입, 경계값 문제(최대=80) |

---

## 검토팀 확정 파라미터 (2026-04-02)

> **검토 참여**: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 김단타(단타 전문가) — 4명

### 스코어링 구조 파라미터

| #   | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|-----|------|----------|--------|------|------|
| 1   | 1차 주식 팩터 | STOCK_FACTORS (5개) | **PRIMARY_STOCK_FACTORS = [volume, volatility, momentum]** | 실시간 데이터 없는 팩터 제외 (전원 합의) | 박퀀트 |
| 2   | 1차 ETF 팩터 | ETF_FACTORS (5개) | **PRIMARY_ETF_FACTORS = [volume, volatility, momentum]** | 동일 논리. tracking_error도 1차에서 NAV 없음 (전원 합의) | 박퀀트 |
| 3   | 1차 가중치 | 각 0.2 (5등분) | **각 ~0.333 (3등분, 균등)** | 단순성 원칙 + 과적합 방지 (박퀀트). 초기 균등, 2주 운영 후 IC 기반 조정 | 박퀀트 |
| 4   | 1차 pass_threshold | 80.0 | **60.0** | 3팩터 상위 40% 통과. max_candidates=30이 실질 상한 (최리스크 + 김단타 합의) | 최리스크 |
| 5   | 2차 pass_threshold | 80.0 | **75.0** | 5팩터 실시간 기반. 초기 운영 데이터 확보를 위해 소폭 하향 (최리스크 + 김단타 합의) | 최리스크 |
| 6   | 2차 주식 팩터 | STOCK_FACTORS (5개) | **유지 (5개)** | 실시간 체결강도/호가잔량 가용 (전원 합의) | 김단타 |
| 7   | 2차 ETF 팩터 | ETF_FACTORS (5개) | **유지 (5개)** | 실시간 데이터 가용 (전원 합의) | 김단타 |
| 8   | max_candidates | 30 | **30 유지** | WS 40종목 제한 대비 여유. 1차 상한 역할 (김단타) | 김단타 |

### 운영 안전장치

| #   | 항목 | 원래 설계 | 확정값 | 근거 | 담당 |
|-----|------|----------|--------|------|------|
| 9   | 1차 최소 후보 경고 | 없음 | **5개 미만 시 warning 로깅** | 소수 후보 시 백분위 왜곡 경고 (최리스크 + 박퀀트) | 최리스크 |
| 10  | 0건 팩터 동률 방지 | 없음 (현재 버그) | **1차에서 실시간 팩터 자체를 제외** | 근본 해결 (전원 합의) | 박퀀트 |
| 11  | FactorScorer 팩터 지정 | 없음 (하드코딩) | **생성자에 factors 파라미터 추가** | 1차/2차 재사용. 기본값은 기존 STOCK_FACTORS (하위 호환) | 박퀀트 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| ✅ 1 | 스코어링 구조 수정 + 임계값 조정 | scorer.py 팩터 분리, screener.py 3팩터 빌드, 임계값 조정, 테스트 전면 수정, 2차 임계값 하향 | 없음 |

---

## Sprint 1 상세 — 스코어링 구조 수정 + 임계값 조정 ✅ 완료

> 완료: 2026-04-02, PR #72, pytest 638 passed

### 작업 순서

1. **scorer.py: 팩터 리스트 분리 + FactorScorer 확장** — PRIMARY_STOCK_FACTORS, PRIMARY_ETF_FACTORS 정의. FactorScorer에 factors 파라미터 추가
2. **scorer.py: 1차 전용 가중치 + 임계값** — PRIMARY_WEIGHTS (각 1/3), pass_threshold 60.0
3. **screener.py: _build_candidates 수정** — 3팩터만 빌드, 중립값 제거
4. **screener.py: PrimaryScreener 생성자 수정** — PRIMARY_STOCK_FACTORS + PRIMARY_WEIGHTS로 FactorScorer 생성
5. **screener.py: 최소 후보 경고 로깅** — 필터 통과 5개 미만 시 warning
6. **scheduler.py: 2차 스크리닝 임계값 조정** — 기존 FactorScorer(pass_threshold=75.0) 적용 확인
7. **테스트 업데이트** — test_scorer.py, test_screener.py 전면 수정. 1차/2차 분리 테스트 추가
8. **통합 검증** — 전체 테스트 통과 확인

### 백엔드

| 파일 | 변경 | 설명 |
|------|------|------|
| `backend/modules/screening/scorer.py` | **수정** | `PRIMARY_STOCK_FACTORS`, `PRIMARY_ETF_FACTORS` 추가. `PRIMARY_WEIGHTS` (각 ~0.333). `FactorScorer.__init__`에 `factors` 파라미터 추가 (기본값: STOCK_FACTORS — 하위 호환). `score_candidates`에서 주입된 factors 사용 |
| `backend/modules/screening/screener.py` | **수정** | `_build_candidates()`: trade_strength_factor, orderbook_ratio_factor, tracking_error_factor 제거. `PrimaryScreener.__init__`: FactorScorer를 PRIMARY 팩터/가중치/임계값=60.0으로 생성. 최소 후보 warning 로깅 추가 |
| `backend/modules/collector/scheduler.py` | **확인/수정** | `_secondary_screen`에서 사용하는 realtime_screener의 FactorScorer가 기존 5팩터 + pass_threshold=75.0 사용하는지 확인. 필요 시 명시적 설정 |
| `backend/tests/test_scorer.py` | **수정** | 1차(3팩터) / 2차(5팩터) 분리 테스트. 기존 5팩터 테스트는 2차용으로 유지. PRIMARY_STOCK_FACTORS 테스트 추가. 동률 시나리오 보완 |
| `backend/tests/test_screener.py` | **수정** | _build_candidates가 3팩터만 반환하는지 검증. 통합 테스트에서 is_passed=True 종목이 실제로 나오는지 검증 (버그 재현 방지 회귀 테스트) |

### 프론트엔드

Sprint 1에서 프론트엔드 변경 없음.

### 재사용 자산

| 기존 모듈 | 활용 |
|----------|------|
| `FactorScorer` 클래스 | 확장 (factors 파라미터 추가). 1차/2차 모두 동일 클래스 사용 |
| `_calc_percentiles()` 함수 | 변경 없음 — 주입된 factors 리스트만 변경 |
| `PrimaryFilters` | 변경 없음 — 필터 로직은 정상 동작 중 |
| `calc_volume_factor`, `calc_volatility_factor`, `calc_momentum_factor` | 변경 없음 — 팩터 계산 자체는 정상 |
| `CollectionValidator.validate_primary_screen()` | 변경 없음 — 0건도 warning으로 처리하는 기존 로직 유지 |

---

## 미해결 사항 / 리스크

| # | 항목 | 상태 | 대응 |
|---|------|------|------|
| 1 | 임계값(60.0/75.0) 운영 보정 | ⚠️ 1주일 운영 후 | 초기 보수적 값. 실제 스코어 분포 관찰 후 조정. Phase 4.6 미해결 #11과 연계 |
| 2 | 소수 후보(3~5개) 시 백분위 왜곡 | ⚠️ 모니터링 | warning 로깅으로 감지. 향후 top-K 방식 전환 검토 |
| 3 | momentum_factor 0.0 동률 (데이터 부족 시) | ⚠️ 낮은 확률 | closes < 4일(신규 상장 등)이면 0.0. 3팩터 중 1개이므로 나머지로 차별화 가능 |
| 4 | 1차/2차 팩터 불일치로 인한 순위 역전 | 정보 정상 동작 | 1차 통과 후 2차에서 5팩터 재스코어링. 1차 순위가 2차에서 뒤바뀌는 것은 의도된 동작 |
| 5 | 가중치 비대칭 (volume 우선) 미적용 | 📋 Phase 5 범위 | 김단타: volume 0.4 권장. 박퀀트: 초기 균등 후 IC 기반 조정. 2주 운영 후 검토 |
| 6 | ~~2차 스크리닝 realtime_screener 임계값 확인~~ | ✅ 해결 (Sprint 1) | realtime_screener.py에서 FactorScorer(pass_threshold=75.0)으로 명시 확인 완료 |
| 7 | FactorScorer factors 파라미터 부분 키 KeyError | ⚠️ Medium — Sprint 2에서 개선 권장 | scorer.py 99-100: factors 파라미터에 "STOCK"/"ETF" 중 한 키만 전달 시 KeyError 발생 가능. .get() 방식으로 변경 권장. 현재 호출부는 모두 두 키 제공하므로 즉각 장애 없음 |

---

## 완료 기준 (Phase 전체)

| # | 항목 | 기준 | 상태 |
|---|------|------|------|
| 1 | 1차 스크리닝 3팩터 분리 | PRIMARY_STOCK_FACTORS, PRIMARY_ETF_FACTORS 정의 및 사용 | ✅ 완료 |
| 2 | 1차 pass_threshold 60.0 | FactorScorer(pass_threshold=60.0) 적용 | ✅ 완료 |
| 3 | 2차 pass_threshold 75.0 | 2차 스크리닝에서 75.0 사용 확인 | ✅ 완료 |
| 4 | _build_candidates 3팩터만 | trade_strength/orderbook_ratio/tracking_error 미포함 | ✅ 완료 |
| 5 | FactorScorer factors 파라미터 | 생성자에서 팩터 리스트 지정 가능, 기본값 하위 호환 | ✅ 완료 |
| 6 | 버그 재현 방지 회귀 테스트 | 44개+ 후보에서 is_passed=True 종목 존재 확인 테스트 | ✅ 완료 |
| 7 | 기존 테스트 통과 | pytest 전체 pass | ✅ 완료 (638 passed) |
| 8 | 최소 후보 경고 | 5개 미만 시 warning 로깅 | ✅ 완료 |
| 9 | 프로덕션 배포 후 검증 | 다음 거래일 primary_screen passed > 0 확인 | ⬜ 수동 필요 |
