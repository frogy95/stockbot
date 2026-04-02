# Hotfix: ETF 시세 수집 실패 시 DB 트랜잭션 롤백 누락 수정

**브랜치:** `hotfix/etf-transaction-rollback`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-02

---

## 문제 분석

### 증상

ETF 시세 수집 중 특정 종목 저장에 실패하면, 이후 모든 종목이
`InFailedSQLTransactionError`(실패한 트랜잭션에서의 연쇄 에러)로 연속 실패하는 현상.

### 원인

`kis_collector.py`의 `collect_etf_prices` 메서드 except 블록에서
`await self._db.rollback()`을 호출하지 않아 세션이 실패 상태로 남아 있었음.
SQLAlchemy asyncpg 드라이버는 트랜잭션 오류 후 rollback 없이 추가 쿼리를 실행하면
`InFailedSQLTransactionError`를 발생시킨다.

### 영향 범위

- ETF 시세 수집 전체 (KODEX ~280종목)
- 수집 실패 시 1종목 오류 → 나머지 279종목도 연쇄 실패
- premarket 수집 결과 DB에 ETF 시세 전혀 미기록

---

## 수정 내용

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/sources/kis_collector.py` | except 블록에 `await self._db.rollback()` 1줄 추가 |

### 커밋 이력

| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `cf9fa6f` | fix(etf-collector): ETF 시세 수집 실패 시 DB 트랜잭션 롤백 추가 | 2026-04-02 |

---

## 검증

### 자동 검증

- pytest ETF 관련 테스트 54개 통과 (전체 pytest 결과 포함)
- 도커 서버 미실행 환경으로 curl/Playwright 타겟 검증 생략

### 수동 검증

- ⬜ Railway 배포 후 ETF 시세 수집 시 InFailedSQLTransactionError 미발생 확인
- ⬜ 수집 로그에서 롤백 후 다음 종목 정상 수집 이어짐 확인

---

## PR

- **URL:** https://github.com/frogy95/stockbot/pull/64
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료 (PR #65)
