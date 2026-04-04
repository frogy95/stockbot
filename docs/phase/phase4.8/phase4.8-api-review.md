# Phase 4.8 API 개발자 검토 리포트 — 윤에이피

> **검토일**: 2026-04-02
> **검토 대상**: EOD 데이터 수집 내결함성 강화 아키텍처 초안

---

## 1. 요약

| 구분 | 판정 | 비고 |
|------|------|------|
| KIS 일봉 API 사용 가능성 | ✅ 통과 | `FHKST03010100` (주식일별가격조회) 사용 가능 |
| Rate Limit 대응 | ⚠️ 주의 | 모의거래 초당 1건 → 전 종목 수집 시 시간 초과 위험 |
| 기존 KISRestClient 확장 | ✅ 통과 | `get_daily_prices()` 메서드 추가로 충분 |
| 스케줄러 통합 | ✅ 통과 | 기존 파이프라인 구조에 자연스럽게 통합 가능 |

## 2. 항목별 검증 결과

### KIS 주식일별가격조회 API 스펙

```
엔드포인트: /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
tr_id: FHKST03010100 (실전/모의 동일)
주요 파라미터:
  - FID_COND_MRKT_DIV_CODE: "J" (주식)
  - FID_INPUT_ISCD: 종목코드
  - FID_INPUT_DATE_1: 시작일 (YYYYMMDD)
  - FID_INPUT_DATE_2: 종료일 (YYYYMMDD)
  - FID_PERIOD_DIV_CODE: "D" (일봉)
  - FID_ORG_ADJ_PRC: "0" (수정주가 미반영) / "1" (수정주가 반영)

응답 필드 (output2 배열):
  - stck_bsop_date: 영업일자
  - stck_oprc: 시가
  - stck_hgpr: 고가
  - stck_lwpr: 저가
  - stck_clpr: 종가
  - acml_vol: 누적거래량
  - acml_tr_pbmn: 누적거래대금
```

### Rate Limit 분석

| 환경 | 초당 한도 | 2,500종목 소요 시간 | 500종목 소요 시간 |
|------|----------|-------------------|------------------|
| 모의거래 | ~1건 | ~42분 | ~8.3분 |
| 실전 | ~20건 | ~2.1분 | ~25초 |

**권고**: 
- 실전 환경에서는 전 종목 수집 가능 (2분 내)
- 모의거래에서는 시총 상위 500종목만 수집 (8분 내, 08:00 시작 → 08:10 완료)
- `inquiry_client` (조회 전용 클라이언트)가 이미 존재하므로 이를 활용

### 기존 코드 재사용

| 모듈 | 재사용 방식 |
|------|-----------|
| `KISRestClient._request()` | 공통 인증/Rate Limit/재시도 로직 그대로 사용 |
| `TokenBucketThrottler` | 배치 간 딜레이 자동 적용 |
| `CollectionResult` | 수집 결과 표준 형식 |
| `CollectionValidator` | 보조 수집용 검증 메서드 추가 |
| `market_data` 테이블 | source="kis_daily"로 구분 저장 |

### 구현 권고

1. `KISRestClient`에 `get_daily_price(stock_code, start_date, end_date)` 메서드 추가
2. `KISDailyCollector` 신규 클래스: stocks 테이블에서 활성 주식 목록 조회 → 배치 수집
3. `scheduler._premarket_collect()`에서 포털 수집 후 검증 실패 시 KIS 보조 수집 자동 호출
4. 배치 크기: 50종목 단위로 commit하여 중간 실패 시에도 부분 데이터 보존

## 3. 파라미터 조정 권고

| 항목 | 원래값 | 권고값 | 근거 |
|------|--------|--------|------|
| KIS 일봉 배치 크기 | — | 50종목 | 중간 commit + 로깅 단위 |
| KIS 일봉 조회 기간 | — | 전일 1일만 (T-1) | OHLCV 1일치면 충분 |
| 수정주가 옵션 | — | "0" (미반영) | 공공데이터포털과 일관성. 수정주가는 과거 비교 시에만 필요 |
| 배치 간 딜레이 | — | throttler 자동 (추가 딜레이 불필요) | TokenBucketThrottler가 Rate Limit 관리 |
| 타임아웃 | 30초 (기존) | **30초 유지** | 단일 종목 조회이므로 충분 |

## 4. 리스크 및 대안

- **리스크**: KIS API 장전 시간대(08:00) 서버 부하로 응답 지연 가능
- **경감**: 타임아웃 + 재시도 로직이 이미 `_request()`에 구현됨
- **리스크**: 모의거래 환경에서 일봉 API `FHKST03010100`이 지원되지 않을 가능성 (일부 tr_id는 모의거래 미지원)
- **경감**: 사전 테스트 필수. 미지원 시 `inquiry_client`(실전 조회 전용)를 사용
- **리스크**: KIS 일봉 응답에 시가총액/상장주식수 미포함
- **경감**: stocks 테이블에 이미 listed_shares 저장 중 (포털 수집 시 upsert). 보조 수집 시에는 stocks 갱신 불필요, market_data만 저장
