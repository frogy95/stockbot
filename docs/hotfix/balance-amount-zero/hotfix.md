# Hotfix: 포지션 사이징 balance_amount=0 하드코딩 결함 수정

**브랜치:** `hotfix/balance-amount-zero`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-15

---

## 문제 분석

### 증상
매매 신호가 발생해도 실제 주문이 전혀 실행되지 않음. 모든 종목에서 `주문 수량 0 — 스킵` 로그 발생.

### 원인
`TradingEngine.process_screening_results()`에서 `PositionSizer.calculate(..., balance_amount=0, ...)`를 고정값 0으로 호출하고 있었음. 잔고를 조회하는 코드가 누락된 채로 배포됨. `PositionSizer`는 `balance_amount=0`이면 항상 `quantity=0`을 반환하므로 모든 매매 신호가 무시됨.

### 영향 범위
- **심각도**: Critical — 매매 엔진 전체 무력화
- **영향 기능**: 장중 2차 스크리닝 후 매매 신호 처리, 반자동/완전자동 주문 실행 전체
- **영향 기간**: Phase 6.2 Sprint 1 배포(v1.9.0, 2026-04-14) 이후 전 구간

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/core/clients/kis_rest.py` | `Balance` 모델에 `available_cash: int = 0` 필드 추가 및 `dnca_tot_amt` 파싱 |
| `backend/modules/trading/engine.py` | `rest_client` 의존성 주입, `get_balance()` 호출로 실잔고 조회 후 포지션 사이징에 전달 |
| `backend/main.py` | `TradingEngine()` 생성자에 `rest_client=rest_client` 인수 추가 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `c222bc3` | fix: 포지션 사이징 balance_amount=0 하드코딩 결함 수정 | 2026-04-15 |

---

## 검증

### 자동 검증
- ✅ pytest: 경량 코드 리뷰 통과 (Critical/High 이슈 없음)

### 수동 검증
- ⬜ docker compose up --build (코드 반영)
- ⬜ 장중 매매 신호 발생 시 주문 수량 > 0 확인 (Railway 로그)
- ⬜ `get_balance()` 호출 로그 확인 (`주문가능 예수금: NNNNN원`)

---

## PR
- **URL:** (생성 후 기재)
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
