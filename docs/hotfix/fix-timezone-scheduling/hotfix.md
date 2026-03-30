# Hotfix: APScheduler 타임존 스케줄링 버그

**브랜치:** `hotfix/fix-timezone-scheduling`
**담당자:** frogy95
**리뷰어:** hotfix-close agent
**상태:** ⬜ 진행 중
**배포일:** 2026-03-30

---

## 문제 분석

### 증상

Railway 프로덕션 서버에서 모든 스케줄 job이 KST 기준 +9시간 늦게 실행됨.
예: 장전 수집(08:00 KST)이 실제로는 17:00 KST에 실행.

### 원인

Railway 서버가 UTC 타임존으로 동작하는데, APScheduler CronTrigger에 `timezone` 파라미터가 없어 UTC 기준으로 스케줄이 설정됨.
또한 `datetime.now()` / `date.today()` 호출이 서버 로컬 타임(UTC)을 반환하여 거래일 계산 오류 발생.

### 영향 범위

- 모든 스케줄 job 실행 시각 (장전 수집, ETF 수집, 장 개시/마감, 1차 스크리닝, DART 수집, 센티멘트 수집)
- 직전 거래일 계산 (`_latest_trading_date`)
- 시초가 구간 판단 (`_is_no_signal_period`)
- 공공데이터포털 진단 엔드포인트 날짜 계산

---

## 수정 내용

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/core/config.py` | `MARKET_TIMEZONE` 설정 추가 (기본값: `Asia/Seoul`) |
| `backend/modules/collector/scheduler.py` | `CronTrigger` 7개에 `timezone=tz` 추가, `datetime.now()` 6곳을 timezone-aware로 수정 |
| `backend/modules/screening/realtime_screener.py` | `_is_no_signal_period()`의 `datetime.now()`를 KST-aware로 수정 |
| `backend/modules/collector/sources/data_go_kr.py` | `_latest_trading_date()`의 `date.today()`를 KST 기준으로 수정 |
| `backend/api/routes/collector.py` | `probe_data_go_kr()`의 `date.today()`를 KST 기준으로 수정 |

### 커밋 이력

| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `fbab51c` | fix(scheduler): APScheduler CronTrigger에 KST timezone 설정 + datetime.now() timezone-aware 수정 | 2026-03-30 |

---

## 검증

### 자동 검증

- pytest: 303 passed, 3 warnings (기존과 동일, 회귀 없음)
- 타겟 API 검증: 서버 미가동 상태로 로컬 자동 검증 생략
- Playwright: 서버 미가동 상태로 생략

### 수동 검증

- ⬜ Railway 배포 후 scheduler 로그에서 CronTrigger timezone=Asia/Seoul 확인
- ⬜ 장전(08:00 KST) premarket_collect job 정상 실행 확인

---

## PR

- **URL:** (PR 생성 후 기입)
- **대상:** main
- **역머지:** ⬜ develop에 역머지 필요
