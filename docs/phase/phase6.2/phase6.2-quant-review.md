# Phase 6.2 퀀트 검토 리포트 — 박퀀트

> **검토일**: 2026-04-14
> **검토 대상**: 포털 수집 타이밍 불일치 해결 아키텍처 초안

---

## 요약

| 항목 | 판정 |
|------|------|
| 스크리닝 품질 영향 분석 | ✅ 완료 |
| market_cap 보정 로직 | ⚠️ 주의 — 보정 커버리지 확인 필요 |
| 포털 부재 시 팩터 영향 | ✅ 경미 (3팩터 중 직접 의존 없음) |
| 백필 후 재스크리닝 | ⚠️ 주의 — 과거 데이터 재계산 불필요 |

---

## 항목별 검증 결과

### 1. 1차 스크리닝 포털 필드 의존도 분석

현재 screener.py의 `_fetch_today_and_prev` 쿼리가 사용하는 필드:

| 필드 | 소스별 가용성 | 스크리닝 역할 | 포털 부재 시 영향 |
|------|-------------|-------------|-----------------|
| close_price | data_go_kr ✅ / kis_daily ✅ | 모멘텀 팩터, ATR 계산 | 없음 |
| volume | data_go_kr ✅ / kis_daily ✅ | 거래량 비율 필터 + 팩터 | 없음 |
| high_price | data_go_kr ✅ / kis_daily ✅ | ATR 계산 | 없음 |
| low_price | data_go_kr ✅ / kis_daily ✅ | ATR 계산 | 없음 |
| change_rate | data_go_kr ✅ / kis_daily ✅ | 등락률 필터 | 없음 |
| **market_cap** | data_go_kr ✅ / kis_daily **None** | **시총 필터 (500억)** | **치명적** |
| **listed_shares** | data_go_kr → stocks ✅ / kis_daily 미갱신 | market_cap 보정 | **간접 영향** |

**결론**: 포털 부재 시 **시총 필터가 핵심 취약점**. 나머지 OHLCV + change_rate는 KIS로 완전 대체 가능.

### 2. market_cap=0 영향 정량 분석

screener.py L406-408 보정 로직:
```python
market_cap = int(today_row["market_cap"] or 0)
if market_cap == 0 and today_row["listed_shares"] and today_row["close_price"]:
    market_cap = int(today_row["listed_shares"]) * int(today_row["close_price"])
```

- stocks.listed_shares는 포털 수집 시 `_upsert_stock`에서 갱신 (data_go_kr.py L176)
- 한 번이라도 포털 수집 성공한 종목은 listed_shares 보유 → 보정 가능
- **신규 상장 종목** (IPO 후 첫 포털 수집 전): listed_shares=None → 보정 불가 → market_cap=0 → 탈락
- **주식분할/병합 종목**: 이전 listed_shares 오래됨 → 시총 계산 부정확 (과대/과소 평가)

### 3. 3팩터 스코어링 영향

| 팩터 | 포털 의존 | 영향 |
|------|----------|------|
| 거래량 팩터 (volume/prev_volume) | 없음 (KIS 제공) | 없음 |
| 모멘텀 팩터 (3일 수익률) | 없음 (close_price) | 없음 |
| 변동성 팩터 (ATR) | 없음 (high/low/close) | 없음 |

**스코어링 자체는 포털 부재에 무관.** 문제는 오직 필터 단계(시총)에서 후보 모수가 줄어드는 것.

### 4. 실제 영향 추정

- KOSPI+KOSDAQ 활성 종목 약 2,500개
- 시총 500억+ 종목 약 1,200~1,500개 (시장 상황에 따라)
- KIS 폴백 시 market_cap=0이지만 listed_shares 보정 가능 종목: 대부분 (최소 1회 포털 수집 경험)
- 보정 불가 종목: 최근 IPO + 포털 미수집 = 극소수 (일 0~2개)
- **즉, stocks.listed_shares 갱신 이력이 있는 한 영향은 미미**

### 5. 장기 부재 시 열화 시나리오

- 포털 5거래일 이상 부재 시:
  - 주식분할/병합 반영 안 됨 → 시총 계산 오차 누적
  - 신규 상장 종목 완전 누락
  - 하지만 이 기간 동안 listed_shares가 바뀌는 종목은 극소수 (일 0~1건)
- **10거래일 이상**: 오차 누적 무시 불가 → 포털 복구 또는 수동 백필 필수

---

## 파라미터 조정 권고

| 항목 | 원래값 | 권고값 | 근거 |
|------|--------|--------|------|
| KIS 폴백 시 스크리닝 품질 등급 | 없음 | KIS 1~2일: 정상, 3일+: 경고 | 시총 데이터 열화 한계 |
| market_cap=0 처리 | 시총 필터에서 탈락 | 경고 로그 + 탈락 유지 | 부정확한 0값으로 통과시키는 것이 더 위험 |
| 백필 후 재스크리닝 | 미정 | 불필요 | 과거 스크리닝 결과는 이미 소비됨 |

---

## 리스크 및 대안

- **리스크**: stocks.listed_shares가 NULL인 종목 비율이 예상보다 높을 수 있음
- **대안**: Sprint 1에서 DB 조회로 listed_shares=NULL 종목 수 확인하는 진단 쿼리 포함
- **리스크**: 14:00 포털 수집 성공 시 market_cap이 갱신되지만, 이미 08:00~09:00에 1차 스크리닝 완료 → 당일 스크리닝에는 반영 안 됨
- **대안**: 14:00 수집은 "다음 거래일" 스크리닝 품질 보장이 목적으로 명확히 정의 (당일 재스크리닝 불필요)
