# Hotfix: KIS 일봉 수동 수집 API 추가

**브랜치:** `hotfix/manual-kis-daily-trigger`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-07

---

## 문제 분석

### 증상
초기 프로덕션 배포 후 DB에 T-1 데이터만 존재하여 1차 스크리닝이 전 종목 탈락 (prev_volume=0).

### 원인
스크리닝 로직이 전일 거래량(prev_volume)을 참조하는데, DB에 T-1 단 하루 데이터만 수집된 상태에서 T-2 이전 데이터가 없어 prev_volume이 0으로 계산됨. 특정 날짜의 KIS 일봉 데이터를 수동 수집할 API 엔드포인트가 없어 T-2 데이터 보충 불가.

### 영향 범위
- 1차 스크리닝 전 종목 탈락 → 매매 신호 생성 불가
- 프로덕션 초기 기동 직후 및 DB 재초기화 후 발생 가능

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/api/routes/collector.py` | `POST /api/v1/collector/trigger/kis-daily/{YYYYMMDD}` 엔드포인트 추가 |
| `backend/modules/collector/scheduler.py` | `trigger_kis_daily(target_date)` 메서드 추가 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `952bb7a` | feat: KIS 일봉 수동 수집 API 추가 (target_date 지정) | 2026-04-07 |

---

## 검증

### 자동 검증
- pytest test_scheduler.py + test_kis_daily_collector.py: 22 passed

### 수동 검증
- ⬜ docker compose up --build (코드 반영)
- ⬜ T-2 데이터 보충: `curl -X POST https://api.stockbot.choiji.kr/api/v1/collector/trigger/kis-daily/20260402`
- ⬜ pipeline-status에서 premarket.db_validation 날짜 분포 확인
- ⬜ 1차 스크리닝 재트리거: `curl -X POST https://api.stockbot.choiji.kr/api/v1/screening/trigger/primary`

---

## PR
- **URL:** (PR 생성 후 업데이트)
- **대상:** main
- **역머지:** ⬜ develop에 역머지 필요
