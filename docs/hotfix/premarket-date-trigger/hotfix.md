# Hotfix: 공공데이터포털 특정 날짜 수동 수집 API 추가

**브랜치:** `hotfix/premarket-date-trigger`
**담당자:** ChoiJiSeon
**리뷰어:** ChoiJiSeon
**상태:** ✅ 배포 완료
**배포일:** 2026-04-07

---

## 문제 분석

### 증상
KIS REST API 불안정으로 인해 일봉 수동 수집(`trigger/kis-daily`)이 사실상 불가 상태.
과거 날짜 데이터를 수동으로 보충할 수 있는 대안 API가 없음.

### 원인
`trigger/kis-daily` 엔드포인트는 한투 KIS REST API에 의존하는데, KIS API 불안정 구간에서는
호출 실패율이 높아 수동 보충 경로가 사실상 막힌 상태.
공공데이터포털은 안정적인 대안이나, 기존 `DataGoKrCollector.collect_all()`에 `target_date` 파라미터가 없어
특정 날짜 수집이 불가능했음.

### 영향 범위
- 장전 데이터 누락 시 수동 보충 불가
- 1차 스크리닝에서 데이터 부족으로 인한 종목 선정 오류 가능성

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/sources/data_go_kr.py` | `collect_all()`에 `target_date: str \| None` 파라미터 추가. None이면 기존 자동 결정 로직 유지 |
| `backend/modules/collector/scheduler.py` | `trigger_premarket_date(target_date)` 메서드 추가. 공공데이터포털을 사용해 특정 날짜 수동 수집 |
| `backend/api/routes/collector.py` | `POST /api/v1/collector/trigger/premarket/{target_date}` 엔드포인트 추가. YYYYMMDD 형식 검증 포함 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `c928a0e` | feat: 공공데이터포털 특정 날짜 수동 수집 API 추가 | 2026-04-07 |

---

## 검증

### 자동 검증
- pytest 타겟(test_data_go_kr.py + test_scheduler.py): 27 passed

### 수동 검증
- ⬜ docker compose up --build (코드 반영)
- ⬜ T-2 데이터 보충: `curl -X POST https://api.stockbot.choiji.kr/api/v1/collector/trigger/premarket/20260402`
- ⬜ DB 데이터 건수 증가 확인 (pipeline-status)
- ⬜ 1차 스크리닝 재트리거: `curl -X POST https://api.stockbot.choiji.kr/api/v1/screening/trigger/primary`
- ⬜ 결과 확인: `curl https://api.stockbot.choiji.kr/api/v1/screening/primary`

---

## PR
- **URL:** (PR 생성 후 업데이트)
- **대상:** main
- **역머지:** ⬜ develop에 역머지 필요
