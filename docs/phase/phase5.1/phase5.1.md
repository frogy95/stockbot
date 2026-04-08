# Phase 5.1: 1차 스크리닝 change_rate 필터 수정 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-08)
> **ROADMAP 참조**: `ROADMAP.md` Phase 5.1
> **검토 리포트**:
>
> - `phase5.1-po-review.md` (정프로, PO)
> - `phase5.1-risk-review.md` (최리스크, 리스크관리)
> - `phase5.1-quant-review.md` (박퀀트, 퀀트)
> - `phase5.1-trader-review.md` (김단타, 단타 전문가)

---

## 개요

2026-04-08 프로덕션에서 **1차 스크리닝 통과 0건** 문제가 재발견되었다. Phase 5 Sprint 1에서 volume_ratio 완화(2.0->1.5) + 적응형 필터 + 기본 후보를 도입했으나, **change_rate 필터(+1%~+7%)가 여전히 과도하게 엄격**하여 평시 장에서 대다수 종목이 탈락한다.

### 문제 분석

```
[2026-04-08 프로덕션 데이터 — 추정 분석]
1차 필터 입력: ~3,000건
  ├─ volume_ratio 탈락: 적응형 [1.5, 1.2]로 대부분 통과
  ├─ change_rate 탈락: 대량 (change_rate_min=1.0 기준)
  │   ├─ 전일 하락 종목 (change_rate < 0): ~50% 즉시 탈락
  │   ├─ 전일 횡보 종목 (0 <= change_rate < 1.0): ~20% 탈락
  │   └─ 합계: ~70% 종목이 change_rate 단일 조건으로 탈락
  └─ volume_min + market_cap 탈락: 소수

  => 적응형 필터가 volume_ratio만 완화하므로 change_rate 병목 미해소
  => 기본 후보(거래량 상위 15개) 투입되지만, 정상 스크리닝 경로 마비
```

### 근본 원인

1. **change_rate_min=1.0은 전체 종목의 ~70-75%를 즉시 탈락시킴** (KOSPI/KOSDAQ 일평균 등락률 표준편차 ~2.0%, 평균 ~0%)
2. **적응형 필터가 change_rate를 미포함**: volume_ratio만 단계적 완화, change_rate는 항상 고정 적용
3. **단타 전략 절반 누락**: 전일 하락 후 반등(갭하락 반등, 과매도 반등) 패턴이 change_rate_min=1.0에 의해 차단

### 해결 아키텍처

```
[Sprint 1: change_rate 필터 수정 + 적응형 확장]

1. change_rate_min 완화 (1.0 → -2.0)
2. 적응형 필터에 change_rate 포함 (volume_ratio → change_rate 순차 완화)
3. 하락 종목(change_rate < 0) 안전장치
   - auto_trade_blocked: true (반자동만)
   - change_rate < -2%: 포지션 사이징 50%
4. 진단 로깅 강화 (필터별 탈락 통계)
5. 테스트 업데이트
```

---

## 검토팀 확정 파라미터 (2026-04-08)

> 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 김단타(단타) — 4명 검토 완료

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | change_rate_min | 1.0 | **-2.0** | 퀀트: 1 sigma 기준 85% 종목 포함. PO/단타는 -3.0 권고했으나 보수적 채택. 적응형으로 -3.0 확대 가능 |
| 2 | change_rate_max | 7.0 | **7.0 유지** | 전원 합의. 과열 종목 제외는 리스크 관리 핵심 |
| 3 | 적응형 change_rate 단계 | 미포함 | **[-2.0, -3.0]** | 퀀트+리스크: volume_ratio 적응형과 독립 운영. 최저 하한 -5.0 |
| 4 | 적응형 완화 순서 | volume_ratio만 | **volume_ratio 먼저 → change_rate 후순위** | 김단타: 거래량이 단타 최우선 신호, 거래량 필터 먼저 완화 |
| 5 | 하락 종목(change_rate < 0) 자동매매 | - | **금지 (auto_trade_blocked: true)** | 최리스크+김단타+정프로: 하락 추세 자동 진입 불가 |
| 6 | 하락 종목(-2% 이하) 포지션 사이징 | - | **정상의 50%** | 최리스크: 추가 하락 리스크 완화 |
| 7 | change_rate 적응형 최저 하한 | - | **-5.0** | 최리스크: -5% 이하는 구조적 악재(상폐, 유증 등) 가능성 |
| 8 | 필터별 탈락 통계 로깅 | 없음 | **필수** | 정프로+박퀀트: 향후 파라미터 튜닝의 데이터 기반 |
| 9 | 절대값 필터 도입 | - | **Phase 6 이관** | 박퀀트: 효과 검증(백테스팅) 후 도입. 현 Phase에서 과도 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 | change_rate 필터 수정 + 적응형 확장 | filters.py 수정, screener.py 적응형 확장, 하락 종목 안전장치, 진단 로깅, 테스트 | 없음 |

---

## Sprint 1 상세 — change_rate 필터 수정 + 적응형 확장

### 백엔드

#### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/screening/filters.py` | change_rate_min: 1.0 -> -2.0, change_rate_adaptive_steps 추가 |
| `backend/modules/screening/screener.py` | _apply_filters_with_adaptive 확장 (change_rate 적응형 추가), 하락 종목 안전장치, 필터별 탈락 통계 로깅 |
| `backend/tests/test_filters.py` | change_rate_min=-2.0 기본값 테스트, 음수 change_rate 통과 테스트 |
| `backend/tests/test_screener.py` | 적응형 change_rate 테스트, 하락 종목 안전장치 테스트 |

#### 변경 상세

**1. `filters.py` — PrimaryFilters 수정**
```python
@dataclass
class PrimaryFilters:
    volume_ratio: float = 1.5
    volume_min_stock: int = 50_000
    volume_min_etf: int = 10_000
    market_cap_min: int = 50_000_000_000
    change_rate_min: float = -2.0          # 1.0 -> -2.0
    change_rate_max: float = 7.0           # 유지
    max_candidates: int = 30
```

**2. `screener.py` — 적응형 필터 확장**
- `__init__`에 `change_rate_adaptive_steps: list[float]` 파라미터 추가 (기본값: `[-2.0, -3.0]`)
- `_apply_filters_with_adaptive` 로직 변경:
  1. 기본 필터로 시도
  2. 부족하면 volume_ratio 단계적 완화 (기존 로직)
  3. 여전히 부족하면 change_rate_min 단계적 완화 (신규)
  4. 최저 하한: change_rate_min >= -5.0

**3. `screener.py` — 하락 종목 안전장치**
- `_build_candidates` 또는 `_truncate_and_rank` 이후:
  - `change_rate < 0`: `auto_trade_blocked: true` 플래그 추가
  - `change_rate < -2.0`: `position_size_ratio: 0.5` 추가

**4. `screener.py` — 필터별 탈락 통계 로깅**
- `_apply_filters`에서 탈락 사유별 카운트 수집
- 로그 출력: `"1차 필터 통계: 입력 %d, volume_ratio탈락 %d, change_rate탈락 %d, ..."`

### 프론트엔드

해당 없음 (백엔드 필터 조건 수정만)

### 재사용 자산

| 기존 모듈 | 재사용 방식 |
|----------|------------|
| `screener.py` 적응형 필터 패턴 | volume_ratio 적응형 로직을 change_rate에도 동일 패턴 적용 |
| Phase 5 `is_relaxed` 플래그 | 적응형으로 통과한 종목에 동일 플래그 재활용 |
| Phase 5 `auto_trade_blocked` 플래그 | 기본 후보에 사용한 동일 플래그를 하락 종목에도 적용 |
| Phase 5 `position_size_ratio` 필드 | 기본 후보 50% 사이징 로직을 하락 종목에도 적용 |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 대응 |
|---|------|--------|------|
| 1 | 하락 종목의 익일 수익률 미검증 | ⚠️ | Phase 6 백테스팅에서 검증. 현재는 반자동 + 포지션 축소로 리스크 제한 |
| 2 | 적응형 완화 시 저품질 종목 유입 | ⚠️ | 2차 스크리닝(체결강도+호가잔량)이 품질 필터 역할. 기존 안전망 활용 |
| 3 | change_rate 절대값 필터 미도입 | ⚠️ | Phase 6 이관 합의. 횡보 종목(|change_rate| < 0.3%) 제외 효과 검증 필요 |
| 4 | 코스피/코스닥 지수 기반 동적 임계값 | ⚠️ | Phase 6 이관 합의 (Phase 5에서도 이관 결정) |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| change_rate_min = -2.0 적용 | filters.py 수정 + 테스트 통과 | ⬜ |
| 적응형 필터 change_rate 포함 | volume_ratio -> change_rate 순차 완화 동작 확인 | ⬜ |
| 하락 종목 안전장치 | auto_trade_blocked + position_size_ratio 플래그 정상 설정 | ⬜ |
| 필터별 탈락 통계 로깅 | 로그에 탈락 사유별 카운트 출력 | ⬜ |
| 기존 테스트 통과 | pytest 전체 통과 | ⬜ |
| 프로덕션 배포 후 1차 스크리닝 통과 > 0건 | 평시 장 기준 10개 이상 통과 목표 | ⬜ |
