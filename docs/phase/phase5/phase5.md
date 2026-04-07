# Phase 5: 1차 스크리닝 안정화 + 완전 자동 모드 + 성과 분석 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-07)
> **ROADMAP 참조**: `ROADMAP.md` Phase 5
> **검토 리포트**:
>
> - `phase5-po-review.md` (정프로, PO)
> - `phase5-risk-review.md` (최리스크, 리스크관리)
> - `phase5-quant-review.md` (박퀀트, 퀀트)
> - `phase5-trader-review.md` (김단타, 단타 전문가)

---

## 개요

2026-04-07 프로덕션 모니터링에서 **1차 스크리닝 통과 0건** 문제가 발견되었다. `volume_ratio >= 2.0` 필터에 88%(2,717/3,084건)가 탈락하고, `prev_volume=0`으로 319건이 추가 탈락하여 매매 전체 불능 상태가 발생하였다.

기존 Phase 5(완전 자동 모드 + 성과 분석)에 스크리닝 안정화를 Sprint 1로 선행 배치하여, 매매 파이프라인의 근본 안정성을 확보한 후 완전 자동 모드와 성과 분석을 진행한다.

### 문제 분석

```
[2026-04-07 프로덕션 데이터]
1차 필터 입력: 3,084건
  ├─ prev_volume_zero 탈락: 319건 (T-2 데이터 부재)
  ├─ volume_ratio 탈락: 2,717건 (88% — volume_ratio >= 2.0 기준 미달)
  ├─ volume_min 탈락: 9건
  ├─ market_cap 탈락: 34건
  └─ change_rate 탈락: 5건
  
  => 통과: 0건 => 2차 스크리닝 입력 부재 => 매매 전체 불능

[근본 원인]
1. volume_ratio 2.0(200%)은 극단적으로 높은 기준 — 평시 장에서 충족 불가
2. prev_volume=0일 때 무조건 탈락 — 초기 배포/데이터 갭에 취약
3. 1차 0건 시 2차 스크리닝 독립 경로 없음 — SPOF
```

### 해결 아키텍처

```
[Sprint 1: 스크리닝 안정화]

1. volume_ratio 임계값 완화 (2.0 → 1.5)
2. 적응형 필터 — 0건 시 단계적 완화 [1.5, 1.2]
3. prev_volume=0 폴백 — 최근 5일 평균 (유효 3일+ 조건)
4. 0건 시 기본 후보 — 거래량 상위 15개 (시총 500억+), 2차 직접 투입
5. date.today() → KST 전환 (risk_manager 최우선)

[Sprint 2: 완전 자동 모드 + 텔레그램 고도화]
(Sprint 1 배포 후 5거래일 관찰 후 착수)

6. 완전 자동 모드 (신호 → 즉시 주문)
7. 반자동/자동 모드 전환 안전장치
8. 일일 마감 리포트 텔레그램 발송
9. 시스템 오류/경고 알림 강화

[Sprint 3: 성과 분석 대시보드]

10. 수익률 차트 (기간별)
11. 전략별 성과 비교
12. 매매 이력 상세 분석
13. 스크리닝 페이지 데이터 신선도 표시
```

---

## 검토팀 확정 파라미터 (2026-04-07)

> 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 김단타(단타) — 4명 검토 완료

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | volume_ratio 기본 임계값 | 2.0 | **1.5** | 전원 합의. 2.0은 88% 탈락으로 과도. 1.5는 1.5σ 수준으로 통계적 적정 (박퀀트) |
| 2 | 적응형 필터 완화 단계 | 없음 | **[1.5, 1.2]** | 최리스크+박퀀트+김단타: 1.0은 필터 무력화. 최저 1.2(20% 증가)가 최소 신호 |
| 3 | 적응형 최소 후보 수 | 없음 | **10개** | 전원 합의. 백분위 최소 유의 표본 크기 |
| 4 | prev_volume 폴백 방식 | 0 (탈락) | **최근 5일 평균 (유효 3일+ 조건)** | 최리스크+박퀀트: 2일 이하 데이터는 통계적 의미 없음 |
| 5 | 0건 시 기본 후보 선정 | 없음 | **거래량 상위 15개 (시총 500억+)** | 김단타: 시총 상위 대형주는 단타 비효율, 거래량 상위가 기회 많음 |
| 6 | 기본 후보 1차 스코어링 | - | **skip (2차 직접 투입)** | 박퀀트: 기본 후보는 volume_ratio 신호 없어 1차 스코어 무의미 |
| 7 | 기본 후보 완전 자동 매매 | - | **금지 (반자동만)** | 최리스크+정프로+김단타 전원: 미검증 종목 자동 주문 불가 |
| 8 | 기본 후보 포지션 사이징 | - | **정상의 50%** | 최리스크: 리스크 완화 목적 |
| 9 | 적응형 결과 표시 | - | **'완화됨' 플래그 + 알림 표시** | 정프로: 텔레그램/대시보드에서 구분 필수 |
| 10 | Sprint 2 착수 조건 | - | **Sprint 1 배포 후 5거래일 관찰** | 최리스크: 안정성 확인 필수 |
| 11 | date.today() 수정 우선순위 | - | **risk_manager.py 최우선** | 최리스크: 손실 한도 계산 오류 가능 |
| 12 | 장세 판별 모듈 | - | **Phase 6 이관** | 정프로: 복잡도 대비 긴급성 낮음, 전원 동의 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 | 1차 스크리닝 안정화 | volume_ratio 완화, 적응형 필터, prev_volume 폴백, 기본 후보, date.today() 정리 | 없음 |
| 2 | 완전 자동 모드 + 텔레그램 고도화 | 자동 모드 구현, 모드 전환, 마감 리포트, 경고 알림 | Sprint 1 + 5거래일 관찰 |
| 3 | 성과 분석 대시보드 | 수익률 차트, 전략 비교, 매매 이력 분석, 데이터 신선도 | Sprint 2 |

---

## Sprint 1 상세 — 1차 스크리닝 안정화

### 백엔드

| 파일 | 작업 내용 |
|------|----------|
| `backend/modules/screening/filters.py` | volume_ratio 기본값 2.0 → 1.5 변경, AdaptiveFilter 클래스 추가 |
| `backend/modules/screening/screener.py` | 적응형 필터 로직 (_apply_adaptive_filters), prev_volume 폴백 (_get_fallback_prev_volume), 기본 후보 선정 (_get_fallback_candidates) |
| `backend/modules/screening/scorer.py` | 기본 후보 스코어링 skip 처리 |
| `backend/modules/trading/risk_manager.py` | date.today() → KST 변환 (line 180, 311) |
| `backend/modules/notifier/manager.py` | date.today() → KST 변환 (line 105) |
| `backend/modules/notifier/commands.py` | date.today() → KST 변환 (line 47) |
| `backend/api/routes/dashboard.py` | date.today() → KST 변환 (line 33) |
| `backend/api/routes/trading.py` | date.today() → KST 변환 (line 57) |
| `backend/tests/test_screener.py` | 적응형 필터, 폴백, 기본 후보 테스트 추가 |
| `backend/tests/test_filters.py` | volume_ratio 1.5 기준 테스트 업데이트 |

### 프론트엔드

| 파일 | 작업 내용 |
|------|----------|
| 해당 없음 | Sprint 1은 백엔드 전용 |

### 재사용 자산

| 기존 모듈 | 재활용 방법 |
|----------|-----------|
| `core/config.py` settings.MARKET_TIMEZONE | KST 타임존 설정 (기존) |
| `modules/collector/validator.py` validate_screening_readiness | DB 데이터 충분성 검증 (Phase 4.9에서 구현) |
| `modules/screening/scorer.py` FactorScorer | 기존 스코어링 엔진 재사용 |
| `modules/screening/filters.py` PrimaryFilters | 기존 필터 구조 확장 |

---

## Sprint 2 상세 — 완전 자동 모드 + 텔레그램 고도화

### 백엔드

| 파일 | 작업 내용 |
|------|----------|
| `backend/modules/trading/auto_executor.py` | (신규) 자동 실행 엔진 — 신호 → 즉시 주문, 리스크 체크 내장 |
| `backend/modules/trading/strategy.py` | 자동/반자동 모드 분기 처리 |
| `backend/core/models/settings.py` | trading_mode 설정 (manual/semi-auto/auto) |
| `backend/modules/notifier/manager.py` | 일일 마감 리포트 생성/발송, 시스템 경고 알림 |
| `backend/api/routes/settings.py` | 모드 전환 API + 보호 로직 (확인 절차) |
| `backend/modules/trading/risk_manager.py` | 기본 후보/적응형 후보 자동 매매 차단 로직 |

### 프론트엔드

| 파일 | 작업 내용 |
|------|----------|
| `frontend/app/settings/page.tsx` | 매매 모드 전환 UI (확인 모달) |
| `frontend/components/mode-indicator.tsx` | (신규) 현재 모드 표시 컴포넌트 |

---

## Sprint 3 상세 — 성과 분석 대시보드

### 백엔드

| 파일 | 작업 내용 |
|------|----------|
| `backend/modules/analyzer/performance.py` | (신규) 수익률/샤프비율/MDD 계산 |
| `backend/api/routes/analyzer.py` | (신규) 성과 분석 API (기간별 수익률, 전략별 비교) |

### 프론트엔드

| 파일 | 작업 내용 |
|------|----------|
| `frontend/app/analysis/page.tsx` | (신규) 성과 분석 페이지 |
| `frontend/components/charts/` | (신규) 수익률 차트, 전략 비교 차트 컴포넌트 |
| `frontend/app/screening/page.tsx` | 데이터 신선도 표시 추가 |

---

## 미해결 사항 / 리스크

| 항목 | 상태 | Sprint | 비고 |
|------|------|--------|------|
| 적응형 필터 후 후보 5개 미만 시 백분위 왜곡 | ⚠️ 알려진 제약 | 1 | 5개 미만은 전원 통과 허용 (박퀀트) |
| 장세 판별 모듈 (동적 임계값) | Phase 6 이관 | - | 전원 동의 |
| rolling z-score 기반 volume 임계값 | Phase 6 이관 | - | 데이터 축적 필요 (박퀀트) |
| IC 기반 팩터 가중치 조정 | Phase 6 이관 | - | 운영 데이터 축적 후 (박퀀트) |
| 완전 자동 모드 + 적응형/기본 후보 조합 | 금지 확정 | 2 | 최리스크 원칙: 미검증 종목 자동 주문 불가 |
| Sprint 2 착수 시점 | Sprint 1 배포 후 5거래일 | 2 | 최리스크+김단타 권고 |
| ETN 시세 수집 공백 | Phase 6 | - | 매매 대상 아님 (Phase 4.6에서 확인) |
| 수집 범위 이원화 (주식T+1/ETF당일) | Phase 6 | - | Phase 4.6에서 확인 |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| 1차 스크리닝 0건 방지 | 적응형 필터 + 기본 후보로 최소 10건 통과 보장 | ⬜ |
| volume_ratio 필터 정상화 | 1.5 기준 적용, 평시 장에서 후보 10건+ | ⬜ |
| prev_volume 폴백 동작 | T-2 부재 시 5일 평균 대체, 유효 3일+ 조건 | ⬜ |
| date.today() 잔존 제거 | 프로덕션 코드 전체 KST 변환 완료 (5개 파일) | ⬜ |
| 완전 자동 모드 동작 | 신호 → 자동 주문, 리스크 한도 적용 | ⬜ |
| 모드 전환 안전장치 | 확인 절차 + 기존 대기 주문 처리 | ⬜ |
| 일일 마감 리포트 | 텔레그램 자동 발송 (손익 요약) | ⬜ |
| 수익률 차트 렌더링 | 일/주/월 기간별 정상 표시 | ⬜ |
| 전략별 성과 비교 | 데이터 정상 표시 | ⬜ |
| 스크리닝 데이터 신선도 | "오늘 결과 없음" 상태 표시 | ⬜ |
| 기본 후보 안전장치 | 반자동만, 50% 사이징, 플래그 표시 | ⬜ |
| 단위 테스트 | 적응형 필터, 폴백, 기본 후보 테스트 | ⬜ |
