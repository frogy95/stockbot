# Hotfix: 2차 스크리닝 → 매매 엔진 연결 누락 수정

**브랜치:** `hotfix/secondary-screen-engine-link`
**담당자:** frogy95
**리뷰어:** hotfix-close agent
**상태:** ⬜ 배포 대기
**배포일:** 2026-03-31

---

## 문제 분석

### 증상

장중 전체 구간에서 자동 매매 신호가 전혀 생성되지 않음. 2차 스크리닝이 30초 주기로 정상 실행되어 통과 종목이 DB에 저장되지만, 매매 주문이 발생하지 않음.

### 원인

`CollectorScheduler._secondary_screen()`이 실시간 스크리닝 결과를 DB에 저장하지만 `TradingEngine.process_screening_results()`를 호출하지 않아 통과 종목이 매매 엔진에 전달되지 않았음. 스케줄러와 매매 엔진이 독립적으로 초기화되어 있었으나 두 컴포넌트를 연결하는 코드가 누락.

### 영향 범위

- 장중 전체(09:00~15:30) 자동 매매 신호 미생성
- 반자동/완전자동 모드 모두 영향
- 2차 스크리닝 결과가 엔진에 도달하지 않으므로 매매 주문 0건

---

## 수정 내용

### 변경 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/scheduler.py` | `_trading_engine` 속성 + `set_trading_engine()` setter 추가, `_secondary_screen()` 내 통과 종목을 엔진에 전달 |
| `backend/main.py` | 매매 엔진 초기화 후 `collector_scheduler.set_trading_engine(trading_engine)` 주입 |

### 커밋 이력

| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `1956e55` | fix: 2차 스크리닝 결과를 매매 엔진에 전달하는 연결 누락 수정 | 2026-03-31 |

---

## 검증

### 자동 검증

- pytest 전체: 539 passed, 0 failed
- 관련 테스트(test_scheduler.py, test_trading_engine.py, test_engine_approval.py): 23 passed
- 코드 리뷰: Critical/High 이슈 없음
  - `if passed and self._trading_engine:` 조건부 호출로 엔진 미주입 시 안전한 동작 보장
  - 기존 `set_telegram_bot()` 패턴과 일관된 setter 방식 사용

### 수동 검증

- ⬜ docker compose up --build (코드 반영)
- ⬜ Railway 배포 후 장중 2차 스크리닝 실행 시 로그에서 `TradingEngine.process_screening_results` 호출 확인
- ⬜ Railway 배포 후 매매 신호 생성 확인 (스크리닝 통과 종목 존재 시)

---

## PR

- **URL:** https://github.com/frogy95/stockbot/pull/50
- **대상:** main
- **역머지:** ⬜ develop에 역머지 필요
