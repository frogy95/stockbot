# Phase 4.6 API 개발자 검토 리포트 — 윤에이피

> **rev.3** (2026-04-02) — 수집 유효성 검증 구현 설계 + 수집 범위 이원화 검토
> **rev.2** (2026-04-02) — KIS 조회/매매 도메인 분리 반영
> **rev.1** (2026-04-02) — 최초 검토

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| tr_id 패턴 분석 정확성 | ✅ 통과 — 조회 tr_id는 환경 무관 고정값 (rev.2 유지) |
| 도메인 분리 구현 방안 | ✅ 통과 — inquiry_client/trading_client 분리 (rev.2 유지) |
| 유효성 검증 구현 아키텍처 (rev.3) | ✅ 통과 — CollectionValidator 클래스 분리 권고 |
| 수집기 반환값 변경 (rev.3) | ✅ 통과 — CollectionResult dataclass 도입 |
| 수집 범위 이원화 문서화 (rev.3) | ✅ 통과 — 현황 기록 필수, 해소는 Phase 5 |
| ETN 시세 수집 경로 (rev.3) | ⚠️ 주의 — KIS REST로 가능하나 Phase 4.6 범위 밖 |
| 실패 정보 구조화 (rev.3) | ✅ 통과 — pipeline_status JSON 확장 |

## 2. 항목별 검증 결과

### 2.1 유효성 검증 구현 아키텍처 (rev.3 신규)

**권고: `CollectionValidator` 클래스 분리**

scheduler.py에 검증 로직을 인라인으로 넣으면 코드가 복잡해진다. 별도 클래스로 분리:

```
backend/modules/collector/validator.py (신규)
  CollectionValidator
    validate_premarket(result: CollectionResult) -> ValidationResult
    validate_etf_master(result: dict) -> ValidationResult  # 기존 sanity_check 위임
    validate_etf_collect(result: CollectionResult) -> ValidationResult
    validate_primary_screen(candidates_count: int) -> ValidationResult
    validate_dart(result: CollectionResult) -> ValidationResult
    validate_sentiment(result: CollectionResult) -> ValidationResult

  ValidationResult (dataclass)
    passed: bool
    failure_type: "retryable" | "permanent" | None
    failure_reason: str | None
    details: dict
    severity: "error" | "warning" | "info"
```

장점:
- 각 수집기는 결과만 반환, 검증은 validator가 담당
- scheduler.py는 validator 결과에 따라 status 업데이트
- 테스트가 쉬워짐 (validator 단독 unit test 가능)

### 2.2 수집기 반환값 변경 (rev.3 신규)

현재 수집기들이 `int` (건수만) 반환하는데, 검증에 필요한 정보가 부족하다.

| 수집기 | 현재 반환 | 변경 후 |
|--------|----------|--------|
| `data_go_kr.collect_all()` | `int` | `CollectionResult(collected, skipped, data_date, null_counts)` |
| `kis_collector.collect_etf_prices()` | `int` | `CollectionResult(collected, failed, total_target)` |
| `kis_master.collect()` | `dict` | 유지 (이미 충분한 정보 포함) |
| `screener.screen()` | `list[dict]` | 유지 (candidates 수 = len(results)) |
| `dart.collect_financials()` | `int` | `CollectionResult(collected, mapped_count, target_count)` |
| `naver.collect_sentiments()` | `int` | `CollectionResult(collected, target_count)` |

**CollectionResult** dataclass:
```python
@dataclass
class CollectionResult:
    collected: int
    failed: int = 0
    skipped: int = 0
    total_target: int = 0
    data_date: str | None = None
    null_counts: dict[str, int] | None = None  # {"close_price": 5, "volume": 2}
```

### 2.3 data_go_kr null 비율 계산 (rev.3 신규)

현재 `_save_market_data`에서 null 필드를 그대로 저장한다. null 비율 검증을 위해 `collect_all` 내부에서 null 카운팅 추가:

```python
null_counts = {"close_price": 0, "volume": 0, "market_cap": 0}
for item in items:
    if self._parse_int(item.get("clpr")) is None:
        null_counts["close_price"] += 1
    if self._parse_int(item.get("trqu")) is None:
        null_counts["volume"] += 1
    if self._parse_int(item.get("mrktTotAmt")) is None:
        null_counts["market_cap"] += 1
```

DB 후검증은 Sprint 2에서 추가 (Sprint 1은 수집 시점 검증만).

### 2.4 수집 범위 이원화 현황 (rev.3 신규)

```
일반주식 시세:  data_go_kr (T+1 일별) -- 당일 시세 없음
ETF 시세:      kis_collector (당일, LIVE) -- 당일 시세 있음
ETN 시세:      없음 -- 수집 코드 자체 없음
```

**ETF 시세 수집 경로**: inquiry_client(LIVE 도메인) 전환으로 해결 완료 (rev.2)
**ETN 시세 수집 경로**: KIS REST `FHKST01010100` (주식현재가) API로 ETN도 조회 가능. 하지만:
- ETN은 ~200종목 추가 호출 필요 (Rate Limit 0.07초 기준 약 14초 추가)
- 현재 매매 대상 아님
- Phase 5에서 kis_collector에 ETN 추가하는 것이 자연스러움

**공공데이터포털 ETF API**: `GetStockSecuritiesInfoService`는 코드에 명시적으로 "일반 주식만 (ETF 미포함)" 주석. 별도 ETF/ETN API 존재 여부 미확인.

### 2.5 _update_step_status 시그니처 확장 (rev.3 신규)

```python
async def _update_step_status(
    self, step: str, status: str, 
    error: str | None = None,
    collected_count: int | None = None,
    validation: dict | None = None,
) -> None:
```

pipeline_status JSON에 validation 정보를 포함하여 장애 원인 진단 용이.

### 2.6 도메인 분리 구현 (rev.2 유지)

```python
# 수정 구조 (이중 환경)
inquiry_env = get_environment("live")      # 조회는 항상 LIVE
trading_env = get_current_environment()    # 매매는 TRADING_ENV 따름

inquiry_client = KISRestClient(env=inquiry_env, ...)
trading_client = KISRestClient(env=trading_env, ...)
```

KISRestClient 내부 코드 변경 없음. 인스턴스만 2개.

## 3. 파라미터 조정 권고 (rev.3)

| 항목 | 기존 확정값 | 권고 수정값 (rev.3) | 근거 |
|------|-----------|-------------------|------|
| premarket 최소 건수 | 100 | **1,500** | PO/리스크 의견 동의. 3,700+ 중 100은 검증 없음 |
| ETF 시세 최소 수집률 | 10% | **50%** | LIVE 도메인 전환 후 정상이면 90%+ 예상. 50%는 보수적 |
| validator 분리 | 없음 (신규) | **CollectionValidator 별도 클래스** | scheduler.py 비대화 방지, 테스트 용이성 |
| 수집기 반환값 | int (신규) | **CollectionResult dataclass** | 검증에 필요한 메타데이터 포함 |
| _update_step_status | status+error만 (기존) | **+ collected_count + validation** | 장애 원인 진단 정보 포함 |
| 기존 도메인 분리 파라미터 | rev.2 확정 | 유지 | 변경 없음 |

## 4. 리스크 및 대안

- **CollectionResult 도입 시 기존 코드 영향**: scheduler.py의 각 `_xxx_collect` 메서드에서 반환값 처리 변경 필요. 내부 인터페이스이므로 문제없음
- **null 카운팅 성능**: 3,700+ 종목에 대해 필드별 null 체크는 O(n) -- 무시할 수준
- **Redis pipeline_status JSON 크기 증가**: validation 정보 추가로 JSON이 커지지만 KB 단위이므로 문제없음
- **ETN 시세 API 호출**: Phase 5에서 ~200건 추가 호출 시 약 14초 추가. Rate Limit 내
- **CI 환경 (기존)**: 실전 앱키 없는 CI에서 서버 시작 실패 -> 테스트 시 mock 필수

## 최종 판단

**rev.3 수정안 승인**. CollectionValidator 분리 + CollectionResult dataclass 도입으로 검증 로직이 깔끔하게 분리된다.
