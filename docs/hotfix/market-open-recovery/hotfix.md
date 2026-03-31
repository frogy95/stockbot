# Hotfix: market_open 미실행 장애 복구

**브랜치:** `hotfix/market-open-recovery`
**담당자:** frogy95
**리뷰어:** —
**상태:** ✅ 배포 완료 + 실서버 검증 완료
**배포일:** 2026-03-31

---

## 문제 분석

### 증상

2026-03-31 09:00 KST, `market_open` 잡이 실행되지 않아 장중 2차 스크리닝이 전일 내내 무력화됨.

### 원인

APScheduler의 `MISFIRE_GRACE_TIME`이 60초로 설정되어 있었음. Railway 컨테이너 재시작 지연(수십 초~수분)이 발생하면 스케줄러가 `market_open`을 "이미 지난 잡"으로 판단하고 스킵.

### 영향 범위

- `market_open` 미실행 → WebSocket 미연결
- `secondary_screen` 잡이 pause 상태 유지 → 장중 30초 주기 2차 스크리닝 완전 무력화
- 실시간 종목 선정 불가 (실제 매매 신호 생성 없음)

**상세**: `docs/phase/phase3/sprint3/sprint3.md` 하단 "프로덕션 장애 기록" 섹션 참조.

---

## 수정 내용

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/scheduler.py` | MISFIRE_GRACE_TIME 60→300초, 09:05 _market_open_recovery 잡 추가, set_telegram_bot 메서드 추가 |
| `backend/modules/trading/eod_liquidator.py` | MISFIRE_GRACE_TIME 60→300초 |
| `backend/main.py` | collector_scheduler.set_telegram_bot(telegram_bot) 호출 추가 |
| `backend/tests/test_scheduler.py` | job_count 7→8, market_open_recovery 잡 검증 추가 |
| `docs/phase/phase4/phase4.md` | P2 운영 개선 백로그 추가 |

### 커밋 이력

| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `ba7f86a` | fix(hotfix): market_open 미실행 장애 복구 (misfire_grace_time + 09:05 자동 복구) | 2026-03-31 |

---

## 검증

### 자동 검증

- ✅ pytest: 522 passed, 0 failed
- ✅ test_scheduler.py: 8 passed (market_open_recovery 잡 포함)
- ✅ GET /api/v1/collector/status: market_open_recovery 잡 09:05 KST 정상 등록 확인
- ✅ MISFIRE_GRACE_TIME 300초 반영 확인

### 수동 검증

- ✅ docker compose up --build (코드 반영)
- ✅ Railway 배포 후 POST /collector/trigger/market-open → ws_connected: true 확인 (2026-03-31 14:02 KST)
- ✅ secondary_screen 30초 주기 활성화 확인 (secondary_last_run: 14:04:18 KST)
- ⬜ 내일(04/01) 09:00 market_open 자동 실행 확인 (스케줄 등록 완료)
- ⬜ 내일(04/01) ws_subscriptions > 0 확인 (1차 스크리닝 후 구독 종목 필요)

---

## PR

- **URL:** https://github.com/frogy95/stockbot/pull/40
- **대상:** main
- **역머지:** ✅ PR #41 (hotfix 역머지) + PR #43 (수동 트리거 API 역머지) 완료
- **추가 PR:** https://github.com/frogy95/stockbot/pull/42 (market_open 수동 트리거 API)
