# Hotfix: Railway 장중 재시작 시 market_open 누락 버그 수정

**브랜치:** `hotfix/lifespan-market-open-detection`
**담당자:** frogy95
**리뷰어:** hotfix-close agent
**상태:** ⬜ 배포 대기 (PR #47 main 머지 후 완료)
**배포일:** 2026-03-31

---

## 문제 분석

### 증상

Railway 서버가 09:00~15:30(장중) 사이에 재시작되면 WebSocket 연결이 수립되지 않고 2차 스크리닝이 비활성화 상태로 유지됩니다.

### 원인

FastAPI lifespan에서 `collector_scheduler.start()`를 호출하면 APScheduler가 `market_open` CronTrigger(09:00 KST)를 등록합니다. 그러나 서버가 이미 09:00 이후에 시작되면 해당 시각이 지나쳐 job이 실행되지 않습니다. `misfire_grace_time=300`이 설정되어 있어도 재시작이 5분 이상 걸리면 미스파이어로 처리되고, 다음 날 09:00까지 `_market_open()`이 호출되지 않습니다.

### 영향 범위

- Railway 장중 재시작 시 WS 연결 미수립 → 실시간 시세 수신 불가
- `secondary_screen` job이 pause 상태로 유지 → 2차 스크리닝 완전 비활성화
- 이전 hotfix(`market-open-recovery`)가 09:05 자동 복구 잡을 추가했으나, lifespan 재시작 시점에 스케줄러가 새로 생성되므로 09:05 잡도 이미 지난 경우 같은 문제 발생

### 배경

- Phase 3 Sprint 3 market_open 미실행 장애(P2 백로그)에서 도출
- Phase 4 미해결 사항으로 이관되어 있던 항목

---

## 수정 내용

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/scheduler.py` | `check_and_recover_market_open()` 메서드 추가 — 서버 시작 시 09:00~15:30이면 `_market_open()` 자동 호출 |
| `backend/main.py` | lifespan에서 `collector_scheduler.start()` 직후 `check_and_recover_market_open()` 호출 |
| `backend/tests/test_scheduler.py` | 장중/장전/장후 3케이스 테스트 추가 |
| `.env.example` | JWT_SECRET 최소 32자 주석 추가 |

### 커밋 이력

| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `8ccef64` | fix(scheduler): 장중 서버 재시작 시 market_open 자동 복구 | 2026-03-31 |

---

## 검증

### 자동 검증

- pytest: 539 passed, 38 warnings, 0 failed
- 신규 테스트 3건 통과:
  - `test_check_and_recover_market_open_during_market_hours` — 장중 10:30 재시작 시 `_market_open()` 호출 확인
  - `test_check_and_recover_market_open_before_market` — 장전 08:00 재시작 시 `_market_open()` 미호출 확인
  - `test_check_and_recover_market_open_after_market` — 장후 16:00 재시작 시 `_market_open()` 미호출 확인

### 코드 리뷰

- Critical/High 이슈: 없음
- Medium 이슈: `check_and_recover_market_open()` 내부 `from datetime import time as dtime` — 함수 내 import. alias 충돌 회피를 위한 의도적 배치로 기능 문제 없음. 배포 차단 사유 아님.

### 수동 검증

- ⬜ docker compose up --build (코드 반영)
- ⬜ Railway 배포 후 장중 재시작 시 로그에서 "장중 재시작 감지" 메시지 확인
- ⬜ Railway 배포 후 ws_subscriptions > 0 확인 (WS 연결 성공)

---

## PR

- **URL:** https://github.com/frogy95/stockbot/pull/47
- **대상:** main
- **역머지:** ⬜ develop에 역머지 필요
