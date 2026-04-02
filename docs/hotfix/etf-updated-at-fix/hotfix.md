# Hotfix: ETF 시세 저장 updated_at 컬럼 오참조 수정

**브랜치:** `hotfix/etf-updated-at-fix`
**담당자:** frogy95
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-02

---

## 문제 분석

### 증상
ETF 시세 수집 스케줄이 실행될 때마다 모든 ETF 시세 저장이 실패하여 DB에 당일 데이터가 전혀 기록되지 않음.

### 원인
`backend/modules/collector/sources/kis_collector.py`의 `_save_etf_price` 메서드 내 `on_conflict_do_update`의 `set_` 절에서 `market_data` 테이블에 존재하지 않는 `updated_at` 컬럼을 참조. `market_data` 테이블은 `updated_at` 대신 `collected_at` 컬럼을 사용함.

### 영향 범위
- ETF 시세 수집 전체 실패 (`UndefinedColumnError`)
- 장전(08:00) 및 장중 ETF 시세 DB 미적재
- 1차 스크리닝에서 ETF 후보군 데이터 없음 → 스크리닝 결과 공백 가능성

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/sources/kis_collector.py` | `_save_etf_price` 메서드 upsert `set_` 절 `"updated_at"` → `"collected_at"` 1줄 수정 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `b2c70f2` | fix(etf-collector): market_data upsert에서 updated_at → collected_at 수정 | 2026-04-02 |

---

## 검증

### 자동 검증
- pytest ETF 관련 테스트 54개 통과

### 수동 검증
- ⬜ Railway 배포 후 다음 장전(08:00) ETF 시세 수집 로그 확인 — `UndefinedColumnError` 미발생 확인
- ⬜ `market_data` 테이블에 당일 ETF 시세 데이터 적재 확인

---

## PR
- **URL:** (PR 생성 후 업데이트)
- **대상:** main
- **역머지:** ⬜ develop에 역머지 필요
