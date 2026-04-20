# Phase 4.10 검토 리포트 — 윤에이피 (API 개발자)

> **검토일**: 2026-04-20
> **검토 대상**: ETF 2차 스크리닝 KeyError 장애 근본 해결 Phase 계획 초안
> **페르소나**: 윤에이피 (금융 API 연동 10년)

---

## 1. 요약

**판정**: ✅ 통과 (단, NAV 소스 선정을 **김단타 안(KIS inquire-price 응답 필드 직접 활용)**으로 확정하면). 초안에 열거된 대안 중 크롤링/pykrx는 운영 비용 측면에서 배제. KIS API가 이미 `nav` 필드를 제공하므로 별도 데이터 소스 추가는 **불필요한 복잡도 증가**다.

---

## 2. 항목별 검증 결과

### 2.1 NAV 데이터 소스 후보 비교 (API 개발자 관점)

초안에서 네 가지 후보를 제시했다. 각각에 대한 실전 평가:

| 후보 | 평가 | 판정 |
|------|------|------|
| **KIS ETF 현재가 API (`inquire-price` for ETF)** | 이미 호출 중인 KIS API로 해결. `nav`, `etf_dspr`(괴리율), `etf_ntas_aset_tval`(순자산총액) 필드 제공 | ✅ **채택** |
| KIS 전용 ETF NAV API | 별도 엔드포인트 불필요. 위 API가 모두 제공 | ❌ 중복 |
| pykrx | 일 단위 EOD만 제공, 실시간 iNAV 불가. Python 의존성 추가, 운영비용 상승 | ❌ 배제 |
| KRX Open API | 등록/승인 필요, 갱신 주기 긴 편, Rate Limit 엄격 | ❌ 배제 |
| 네이버 금융 크롤링 | HTML 구조 변경 리스크, 운영 자동복구 어려움 | ❌ 절대 배제 |

**확정**: KIS `inquire-price` (ETF 전용 TR) 응답 필드를 그대로 사용한다. 새 API 연동 없음.

### 2.2 KIS API 상세 스펙 (실전 경험 기반)

#### 엔드포인트
- **실전**: `https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price`
- **모의**: `https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-price`
- **TR ID**: `FHKST01010100` (주식/ETF 공용) — ETF 종목코드 입력 시 ETF 응답 포맷 반환
  - 단, **ETF 전용 TR `FHPST02400000`**이 별도 존재할 수 있음 (KIS 문서 재확인 필요)

#### ETF 응답의 NAV 관련 필드 (실전 관찰)
| 필드명 (KIS) | 의미 | 타입 |
|-------------|------|------|
| `nav` | 현재 NAV (장중 iNAV) | string, 원 단위 |
| `etf_dspr` | 괴리율 % | string |
| `etf_ntas_aset_tval` | 순자산총액 | string |
| `stck_prpr` | 현재가 | string |

주의: **모든 필드가 string으로 내려온다**. Decimal/float 변환 시 빈 문자열 처리 주의 (`""` → 0.0 또는 None 결정 필요).

#### Rate Limit
- 실전: 초당 20건
- 모의: 초당 1건
- 2차 스크리닝 후보(최대 20~30개) × ETF 비율(~30%) = **6~9개 ETF만 조회**. Rate Limit 여유 충분.

#### 모의거래 지원 여부
- ETF 조회는 모의거래에서 **지원됨**. 단, nav 필드가 **최신이 아닐 수** 있다 (Phase 4.8에서 KIS 일봉 모의 이슈와 유사).
- **Sprint 2 착수 전 모의거래에서 샘플 종목(069500 KODEX 200, 122630 KODEX 레버리지, 114800 KODEX 인버스) 조회하여 nav 필드 실제 값/타입 확인 필수**.

### 2.3 호출 타이밍 설계

초안에서 "장 마감 후(16:30~17:00) EOD 수집" 언급이 있었으나, **김단타 권고대로 장중 실시간 호출이 맞다**. 두 가지 방식 중 선택:

#### 방식 A: WS 구독 시 동반 호출
```
2차 스크리닝 진입 시 ETF 종목에 대해 inquire-price 호출
→ nav 값을 Redis `realtime:{code}:etf_nav`에 저장 (TTL 30초)
→ RealtimeScreener._build_candidates에서 Redis에서 조회
```
- 장점: 타임슬라이스 동기화
- 단점: 2차 스크리닝 실행 시마다 API 호출 (스크리닝 주기 30초~1분 × ETF 6~9개 = 초당 0.1~0.3건)

#### 방식 B: 별도 배경 작업 주기적 갱신
```
백그라운드 태스크가 활성 ETF 목록을 30초마다 inquire-price 호출
→ Redis `realtime:{code}:etf_nav`에 저장
```
- 장점: 스크리닝과 독립, 호출 빈도 예측 가능
- 단점: ETF가 2차 필터 통과하지 않아도 호출 낭비

**권고**: **방식 A**. 이유:
- 2차 스크리닝은 이미 WS 기반 실시간 데이터를 기다리는 구조다. ETF 판정 시점에서 NAV도 함께 조회하는 것이 자연스럽다
- 호출 빈도가 낮아 Rate Limit 문제 없음
- Redis 캐시 TTL 30초로 동일 종목 반복 조회는 억제됨

### 2.4 EOD NAV 수집은 필요한가

김단타 의견대로 **Sprint 2 범위에서 제외**한다. 이유:
- 장중 iNAV만으로 2차 스크리닝 완결
- EOD NAV는 Phase 9(백테스트) 시점에 별도 수집 가능
- Sprint 2 범위를 "장중 실시간 NAV 연동"으로 축소하면 1~2일 작업으로 완료 가능

### 2.5 스키마 변경 판단

PO는 `market_data.nav` 컬럼을 제안했다. API 관점 의견:

- **장중 NAV는 Redis에만 저장** (시계열 DB 불필요)
- **EOD NAV는 Phase 9에서 필요 시 market_data.nav 컬럼 추가** (Phase 4.10에서는 보류)

즉 **Phase 4.10에서는 DB 스키마 변경 불필요**. Alembic 마이그레이션 없음. 이는 PO 초안과 다른 권고이나, 범위 축소 이득이 크다.

**단, Sprint 3에서 `Stock.etf_leverage_type` 컬럼 추가는 필요** (김단타 권고). 이건 1회 Alembic 마이그레이션.

### 2.6 에러 핸들링 체크리스트

KIS inquire-price ETF 조회 시 다음 에러 케이스가 실전에서 확인됨:

| 에러 | 빈도 | 대응 |
|------|-----|------|
| 거래정지 ETF | 드물지만 발생 | `nav=""` 또는 404. Redis 캐시하지 않고 폴백 진입 |
| 신규 상장 ETF (1개월 이내) | 월 1~2회 | `nav` 값은 있으나 iNAV 신뢰도 낮음. 신규 상장 ETF는 별도 필터 고려 |
| 네트워크 타임아웃 | 월 5~10회 | 3회 재시도 후 폴백 진입. Phase 6 Sprint 2에서 구현된 재시도 로직 재사용 |
| Rate Limit 초과 | 드물지만 발생 | 500ms 대기 후 재시도. inquire_client(LIVE 고정) 사용 |
| 토큰 만료 (401) | 일 1회 | 자동 갱신 (기존 토큰 매니저 로직) |

**Sprint 2 구현 시 위 5개 케이스를 모두 커버하는 래퍼 함수 작성 권고**: `backend/modules/collector/sources/kis_collector.py`에 `get_etf_nav(code)` 메서드 추가.

---

## 3. 파라미터 조정 권고

| # | 항목 | 초안 | 확정 권고 | 근거 |
|---|------|------|----------|------|
| 1 | NAV 데이터 소스 | 4개 후보 나열 | **KIS inquire-price 단일 소스** | 기존 API 재활용 |
| 2 | NAV 캐싱 | DB | **Redis만 (TTL 30초)** | 장중 실시간만 필요 |
| 3 | market_data 스키마 변경 | nav 컬럼 추가 | **Phase 4.10에서는 변경 없음** | EOD NAV 불필요 |
| 4 | EOD NAV 수집 스케줄 | 16:30~17:00 | **Phase 4.10 범위 제외**, Phase 9에서 결정 | 장중 iNAV로 충분 |
| 5 | ETF 타입 분류 (Stock.etf_leverage_type) | 초안 없음 | **Sprint 3에서 추가** | 김단타 권고 반영 |
| 6 | Sprint 2 착수 전 선행 작업 | 없음 | **모의거래에서 KODEX 200/레버리지/인버스 3종 샘플 조회하여 nav 필드 타입/값 검증** | KIS 문서 vs 실제 동작 불일치 방지 |
| 7 | KIS inquire-price 재시도 정책 | 명시 없음 | **3회 재시도 + 500ms 백오프 + Phase 6 Sprint 2 로직 재사용** | 기존 패턴 준수 |
| 8 | Redis 키 규약 | 명시 없음 | **`realtime:{code}:etf_nav` (JSON: {"nav": float, "etf_dspr": float, "updated_at": iso})** | 기존 `realtime:{code}:execution` 패턴 |
| 9 | KIS inquire_client 환경 | 명시 없음 | **LIVE 고정** (Phase 4.6에서 확정된 원칙) | 시세 조회는 LIVE 도메인 사용 |

---

## 4. 리스크 및 대안

### 4.1 "inquire-price가 ETF에 대해 nav 필드를 반환하지 않으면?"

샘플 조회(Sprint 2 착수 전) 결과 nav 필드가 없거나 비어있다면 **ETF 전용 TR을 찾아야** 한다. KIS 문서에는 `FHPST02400000` 또는 유사 ETF 전용 TR이 있을 가능성이 높다. 확정은 **Sprint 2 Task 1에서 수행** — 그 결과에 따라 Sprint 2 범위가 미세 변동.

이 불확실성이 Sprint 2 일정의 최대 리스크다. 모의거래 사전 검증 없이 Sprint 2 착수는 금지.

### 4.2 WebSocket ETF 추가 구독 가능성

KIS WebSocket에는 **ETF 전용 실시간 체결/NAV 스트림**이 존재할 수 있다(`H0STCNT0` 외 ETF 전용 TR). 만약 WS로 NAV 실시간 스트리밍이 가능하면 REST 호출조차 불필요해진다.

**Sprint 2 Task 1 선행 조사에 포함**: KIS WS에 ETF NAV 실시간 TR이 있는지 확인. 있으면 REST 대신 WS 채택 (구독 한도 Phase 5.2 PAPER=25/LIVE=35 내 여유 확인).

### 4.3 Phase 4.9의 pipeline_healthy 플래그와의 통합

Sprint 2에서 NAV 호출이 반복 실패할 경우 **pipeline_healthy=false로 플래그 설정**하는 것은 Phase 4.9 패턴과 일관된다. 단, **주식 2차 스크리닝은 NAV 장애와 무관하게 정상 진행**되어야 하므로 `pipeline_healthy` 플래그 범위를 ETF 전용으로 한정:

- `pipeline_healthy`: 전체 시스템 (기존)
- `etf_pipeline_healthy`: ETF NAV 수집 상태 (신규)

이 구분이 없으면 ETF NAV 장애 하나로 주식 매매까지 막히는 SPOF 재발.

### 4.4 Sprint 1 폴백과의 운영 호환성

Sprint 1에서 `tracking_error_factor=0.0` 폴백을 넣는다. Sprint 2 배포 시점에 **이 폴백 경로를 그대로 두고 NAV 데이터가 Redis에 있으면 실제 값, 없으면 폴백**으로 전환하는 점진적 구조 권고. 즉:

```python
# 의사코드 (Sprint 2 이후)
nav_data = await redis.get(f"realtime:{code}:etf_nav")
if nav_data:
    tracking_error_factor = parse_and_calc(nav_data, current_price)
else:
    tracking_error_factor = 0.0  # Sprint 1 폴백 유지
    logger.warning(f"ETF {code} NAV 결측 — 폴백 사용")
```

Sprint 2 배포 직후 NAV 수집이 안정화되는 데 시간이 걸릴 수 있으므로 폴백 즉시 제거는 위험. **Sprint 3 마무리 시점에 로그에서 "폴백 사용" 경고 빈도가 일간 <1%로 떨어지는 것을 확인한 후** 폴백 제거 (Sprint 3 완료 기준).

### 4.5 실전 디버깅 포인트

Sprint 2 배포 직후 관찰할 것:
1. `realtime:{code}:etf_nav` 키 갱신 주기 (의도: 30초 이내)
2. KIS inquire-price 평균 응답 시간 (의도: <300ms)
3. KIS 응답의 `etf_dspr` 값 분포 (의도: -3% ~ +3% 내 95% 이상)
4. nav=0 또는 null 응답 비율 (의도: <1%)

위 지표가 무너지면 Sprint 3 착수 중단하고 원인 분석 우선.

---

## 5. 최종 판정

**통과**. PO/리스크/단타 4명의 권고를 종합하면 다음 구조가 수렴한다:

- **Sprint 1**: 긴급 폴백 + scorer 격리 + 레버리지 ETF 완전 제외
- **Sprint 2**: KIS inquire-price ETF 응답 필드를 Redis 캐시 → 스코어링 연동. DB 스키마 변경 없음
- **Sprint 3**: 괴리율 절대 컷오프(2%/1.5%) + Stock.etf_leverage_type 추가(Alembic 1회) + ETF 회귀 테스트 보강

KIS API가 이미 NAV/괴리율을 제공한다는 점 때문에 **당초 예상보다 파이프라인 복잡도가 훨씬 낮다**. 이는 프로젝트 일정 관점에서 호재다. 다만 모의거래 사전 검증은 **절대 생략 금지**. 문서와 실제 동작이 다른 경우가 많다는 점, 이 프로젝트에서 수차례 입증되었다.
