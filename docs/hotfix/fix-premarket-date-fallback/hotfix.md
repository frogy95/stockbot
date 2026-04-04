# Hotfix: 포털 수집기 날짜 폴백 제거 — 최신 거래일 0건 시 KIS 폴백 발동

**브랜치:** `hotfix/fix-premarket-date-fallback`
**담당자:** frogy95
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-05

---

## 문제 분석

### 증상
장전 premarket 파이프라인에서 공공데이터포털 수집기가 최신 거래일 데이터 0건을 반환해도
KIS 폴백이 발동되지 않고 이전 날짜의 stale 데이터를 성공으로 반환.

### 원인
`collect_all()`에 날짜 폴백 for 루프가 존재하여, 최신 거래일(오늘)에 데이터가 없으면
자동으로 하루 전, 이틀 전 날짜를 시도해 구(舊) 데이터를 성공으로 반환.
결과적으로 상위 레이어에서 `collected > 0`으로 판단하여 KIS 폴백 발동 조건이 충족되지 않음.

### 영향 범위
- 공공데이터포털 API에 당일 데이터가 아직 없는 시간대(장 전 이른 시간) 수집 시
  stale 전일 데이터로 스크리닝이 진행되어 부정확한 종목 선정 가능성
- KIS 폴백 미발동으로 인해 당일 기준 시가총액/상장주식수 데이터 미갱신

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/sources/data_go_kr.py` | `collect_all()` 날짜 폴백 for 루프 제거, 최신 거래일 1개만 시도. 0건 시 `collected=0` 반환 |
| `backend/tests/test_data_go_kr.py` | 날짜 폴백 관련 테스트 케이스 제거 및 신규 동작 검증 테스트 추가 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `1aa42c9` | fix: 포털 수집기 날짜 폴백 제거 — 최신 거래일 0건 시 KIS 폴백 발동 | 2026-04-05 |

---

## 검증

### 자동 검증
- pytest: 678 passed, 0 failed

### 수동 검증
- ⬜ 다음 거래일 08:00 premarket_pipeline 실행 시 포털 0건 → KIS 폴백 발동 확인 (Railway 로그)

---

## PR
- **URL:** https://github.com/frogy95/stockbot/pull/82
- **대상:** main
- **역머지:** ✅ develop 역머지 완료
