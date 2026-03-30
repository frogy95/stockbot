# Hotfix: 공공데이터포털 ETF 잘못 분류 버그 수정

- **브랜치**: hotfix/fix-etf-stock-type
- **날짜**: 2026-03-30
- **심각도**: High (프로덕션 KIS API 500 에러 다수 발생)
- **담당자**: frogy95
- **리뷰어**: hotfix-close agent

---

## 문제 원인 및 영향 범위

### 원인

`backend/modules/collector/sources/data_go_kr.py`의 `_upsert_stock()` 메서드에서 종목코드(`srtnCd`)가 `'4'`로 시작하면 `stock_type`을 `"ETF"`로 분류하는 잘못된 휴리스틱 로직이 존재했다.

```python
# 버그 코드
stock_type = "ETF" if item.get("srtnCd", "").startswith("4") else "STOCK"
```

그러나 공공데이터포털 `GetStockSecuritiesInfoService`는 **일반 주식만 제공**하며 ETF 데이터를 포함하지 않는다. 따라서 이 조건은 항상 잘못된 분류를 생성한다.

### 영향 범위

- 종목코드가 `'4'`로 시작하는 일반 주식 **266개**가 `stock_type = "ETF"`로 잘못 태깅됨
- 영향 종목 예시: SK스퀘어(402410), 쏘카(403550) 등
- KIS REST API ETF 시세 수집기(`kis_collector.py`)가 이 종목들에 대해 ETF 전용 엔드포인트로 요청 → **500 에러 다수 발생**
- 3/26, 3/27 market_data 누락

---

## 수정 내용

### 코드 변경 (1파일, 2줄)

```python
# 수정 전
stock_type = "ETF" if item.get("srtnCd", "").startswith("4") else "STOCK"

# 수정 후
# 공공데이터포털 GetStockSecuritiesInfoService는 일반 주식만 제공 (ETF 미포함)
stock_type = "STOCK"
```

### DB 데이터 정정 (수동 완료)

- DB에서 잘못 분류된 ETF 266개 → STOCK으로 정정 (수동 UPDATE)
- 3/26, 3/27 market_data 재수집 완료
- 1차 스크리닝 재실행 → 30종목 정상 선정

---

## 커밋

| 해시 | 메시지 | 날짜 |
|------|--------|------|
| 6ffc101 | fix(collector): 공공데이터포털 ETF 잘못 분류 버그 수정 | 2026-03-30 |

---

## 검증 결과

### 자동 검증

- ✅ pytest: 302 passed, 1 failed
  - 실패 항목: `test_stock_crud` — 실제 DB 데이터 충돌 (기존 이슈, 이번 수정과 무관)
  - 회귀 없음 확인

### 수동 완료 항목

- ✅ DB UPDATE: `stock_type = 'STOCK'` where 종목코드 `'4'` 시작 266개
- ✅ 3/26, 3/27 market_data 재수집
- ✅ 1차 스크리닝 재실행 → 30종목 정상 선정

### 수동 검증 필요 항목

- ⬜ Railway 배포 후 수집기 로그에서 ETF 500 에러 미발생 확인
- ⬜ 다음 장전(08:00 KST) premarket_collect 정상 실행 후 종목 분류 확인
