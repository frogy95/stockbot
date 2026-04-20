# Hotfix: 2차 스크리닝 ETF 후보 tracking_error_factor 누락 KeyError

**브랜치:** `hotfix/realtime-screener-tracking-error-missing`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**발생/배포일:** 2026-04-20

---

## 문제 분석

### 증상
프로덕션 Railway 백엔드 로그에 `KeyError: 'tracking_error_factor'` 가 30초마다 반복 발생. 2차 스크리닝 파이프라인이 ETF 포함 후보를 처리하는 순간 예외로 중단되어 신호 생성 단계에 도달하지 못함. v2.2.0 머지(02:26:33Z) 이전 02:25부터 이미 발생 중이던 회귀 버그.

### 원인
`backend/modules/screening/realtime_screener.py`의 `screen()` 메서드가 `factor_candidates`를 조립할 때 stock 5팩터(volume/momentum/volatility/trade_strength/orderbook_ratio)만 포함하고 **ETF용 `tracking_error_factor` 필드를 넣지 않음**. 이후 `FactorScorer.score_candidates`가 ETF 후보에 대해 `ETF_FACTORS = [..., "tracking_error_factor"]` 기준으로 `_calc_percentiles`를 호출하면 `c[factor]` 접근에서 `KeyError` 발생.

과거 1차 스크리닝(`screener.py`)에도 동일 버그가 있어 커밋 `ade1d9d`에서 중립값 0.0 스텁으로 고친 이력이 있으나, Phase 4.7에 추가된 2차 스크리닝(`realtime_screener.py`)에는 동일 패치가 적용되지 않아 회귀.

### 영향 범위
- 2차 스크리닝 ETF 경로 전면 중단 (30초 주기 실패)
- ETF 종목 매수 신호 생성 불가
- v2.2.0 전략 거부 관측성 개선 로그 역시 신호 생성 단계 미도달로 샘플링 불가
- 주식 종목 신호 생성 역시 동일 배치에 ETF가 포함되면 전체 실패 → 광범위 영향

### 근본 해결 일정
Phase 4.10 "ETF 2차 스크리닝 근본 해결"에서 NAV 실시간 수집 및 `tracking_error_factor` 정식 계산 예정. 본 핫픽스는 그 전까지 파이프라인 전면 중단을 막기 위한 스텁 패치.

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/screening/realtime_screener.py` | `factor_candidates.append({...})` 에 `"tracking_error_factor": 0.0` 한 줄 추가 (주석 포함 2줄) |
| `backend/tests/test_realtime_screener.py` | ETF 후보 단독 파이프라인 통과 회귀 테스트 `test_etf_candidate_has_tracking_error_factor` 추가 |

### 근거
- `screener.py` 1차 스크리닝에서도 같은 문제를 동일한 방식으로 해결(`ade1d9d`). 최소 변경 원칙 준수.
- NAV 데이터가 현재 Redis/DB에 수집되지 않으므로 값 계산 불가 → 중립값 0.0으로 모든 ETF가 동률 → 순위 왜곡 최소.

---

## 검증

### 자동 검증
- `pytest tests/test_realtime_screener.py tests/test_scorer.py tests/test_screener.py` → **62 passed**
- 신규 회귀 테스트 `test_etf_candidate_has_tracking_error_factor` 포함 → 단일 ETF 후보가 파이프라인을 통과하고 `factors["tracking_error_factor"]`가 생성됨을 확인

### 수동 검증
- ⬜ Railway 배포 후 백엔드 로그에서 `KeyError: 'tracking_error_factor'` 재발하지 않음 확인 (10분 이상 관찰)
- ⬜ 장중 2차 스크리닝 통과 로그(`2차 스크리닝 필터 통과: N종목`) 정상 출력 확인
- ⬜ v2.2.0 신규 구조화 로그(`전략 거부 [stage]` / `전략 통과 [strategy]`) 샘플링 재시도

---

## PR
- **URL:** https://github.com/frogy95/stockbot/pull/146
- **대상:** main
- **역머지:** develop 역머지 완료 예정
