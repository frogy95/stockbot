# Hotfix: ETF/일봉 수집기 UTC 날짜 불일치 수정 (KST 기준으로 변경)

**브랜치:** `hotfix/collector-timezone-kst`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-07

---

## 문제 분석

### 증상
ETF DB 검증 실패: `etf 수집 199건이나 DB 오늘자 시세 0 < 140 (db_validation.passed = false)`

### 원인
`kis_collector.py`의 `_save_etf_price()`와 `kis_daily_collector.py`의 `collect_all()`에서 `date.today()`를 사용하여 날짜를 결정. Railway 서버는 UTC로 동작하기 때문에 KST 기준 날짜(+9시간)와 불일치 발생. UTC 00:00~09:00 구간(KST 09:00~18:00, 즉 장중~장후)에 데이터 저장 시 UTC 날짜(전날)로 기록되어 당일 DB 검증 실패.

### 영향 범위
- ETF 수집기(`kis_collector.py`): `_save_etf_price()` — ETF 시세를 market_data에 저장 시 날짜 오기록
- 일봉 보조 수집기(`kis_daily_collector.py`): `collect_all()` — 전일(T-1) 날짜 계산 오류
- DB 검증: `etf.db_validation.passed = false` 발생 → pipeline_healthy 위협 가능성

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/sources/kis_collector.py` | `_save_etf_price()`의 `date.today()` → `datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()` |
| `backend/modules/collector/sources/kis_daily_collector.py` | `collect_all()`의 `date.today()` → `datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()` |
| `.claude/rules/backend.md` | 타임존 규칙 추가: `date.today()` 사용 금지 명시 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| (PR 머지 후 기록) | fix(collector): ETF/일봉 수집기 date.today() → KST 기준 datetime.now() 수정 | 2026-04-07 |

---

## 검증

### 자동 검증
- ✅ `test_kis_collector.py`: 7 passed
- ✅ `test_kis_daily_collector.py`: 5 passed
- ✅ 전체 pytest: 690 passed, 4 failed (기존 실패 1건 포함 — test_screening_readiness_pass_t1)

### 수동 검증
- ⬜ `docker compose up --build` (코드 반영)
- ⬜ ETF 수집 수동 트리거: `curl -X POST https://api.stockbot.choiji.kr/api/v1/collector/trigger/etf`
- ⬜ `pipeline-status`에서 `etf.db_validation.passed = true` 확인

---

## PR
- **URL:** (생성 중)
- **대상:** main
- **역머지:** ⬜ develop에 역머지 필요
