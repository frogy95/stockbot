# Phase 4.6 리스크관리 검토 리포트 — 최리스크

> **rev.3** (2026-04-02) — 수집 유효성 검증 임계값 확정 + 실패 유형 분류
> **rev.2** (2026-04-02) — KIS 조회/매매 도메인 분리 반영
> **rev.1** (2026-04-02) — 최초 검토

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| 도메인 분리 아키텍처 | ✅ 통과 — 조회/매매 분리는 보안상으로도 올바르다 (rev.2 유지) |
| 수집 유효성 검증 체계 (rev.3) | ✅ 통과 — 필수. 없으면 매매 엔진에 쓰레기 데이터 공급 |
| 검증 실패 시 매매 차단 (rev.3) | ✅ 통과 — pipeline_healthy=false면 매매 불가 |
| 재시도 가능/불가 분류 (rev.3) | ✅ 통과 — 장애 유형별 대응 필수 |
| 구체적 임계값 설정 (rev.3) | ✅ 통과 — 코드베이스 기반 수치 확정 |

## 2. 항목별 검증 결과

### 2.1 수집 유효성 검증 -- 단계별 성공 조건 (rev.3 신규)

**핵심 원칙: 검증 실패 = 매매 차단. 예외 없음.**

#### premarket (data_go_kr)

| 검증 항목 | 임계값 | 근거 |
|----------|--------|------|
| 수집 건수 | >= 1,500 | KOSPI ~2,000 + KOSDAQ ~1,700 = ~3,700. 40% 이상 필수 |
| data_date 유효성 | T-1 또는 T-2 거래일 | 공공데이터포털 T+1 지연 고려. T-3 이전이면 실패 |
| close_price null 비율 | < 5% | 핵심 시세 필드, 5% 이상이면 데이터 소스 문제 |
| volume null 비율 | < 5% | 거래량 비율 계산의 기반 필드 |
| DB 후검증 (Sprint 2) | SELECT COUNT(*) ... WHERE close_price IS NOT NULL | 실제 DB 적재 확인 |

#### etf_master (kis_master)

| 검증 항목 | 임계값 | 근거 |
|----------|--------|------|
| ETF 종목 수 | >= 200 | 기존 sanity check 유지 (코드에 이미 존재) |
| spot-check | 069500 등 5종목 존재 | 기존 sanity check 유지 |
| 전일 대비 변동 | +- 30% 이내 | 기존 sanity check 유지 |

#### etf_collect (kis_collector)

| 검증 항목 | 임계값 | 근거 |
|----------|--------|------|
| 수집 건수 | >= ETF 전체의 50% | LIVE 도메인 사용하므로 50% 미달은 심각한 API 장애 |
| close_price > 0 비율 | 수집된 건 전량 | close_price가 0이면 해당 건 무효 처리 |
| 전량 실패 (0건) | 즉시 failed + 알림 | 0건 수집은 무조건 실패 |

#### primary_screen

| 검증 항목 | 임계값 | 근거 |
|----------|--------|------|
| 스크리닝 통과 종목 수 | >= 0 (0건 허용) | 시장 상황에 따라 0건 가능 |
| 0건 시 처리 | **warning** (failed 아님) | 매매 안 하는 것이 올바른 행동 |
| 0건 시 알림 | 텔레그램 "오늘 매매 대상 없음" | 사용자 인지 필요 |

#### dart

| 검증 항목 | 임계값 | 근거 |
|----------|--------|------|
| corp_code 매핑 성공률 | >= 50% | 대상 종목 중 절반 이상 매핑 안되면 데이터 문제 |
| 재무 데이터 수집 건수 | 정보만 | DART API 특성상 전년도 보고서 미제출 종목 존재 |
| 0건 시 처리 | **warning** (failed 아님) | 보조 데이터, 파이프라인 차단 불필요 |

#### sentiment (naver)

| 검증 항목 | 임계값 | 근거 |
|----------|--------|------|
| 뉴스 수집 성공률 | >= 70% | 대상 종목 중 70% 이상에서 뉴스 1건 이상 |
| 0건 시 처리 | **warning** (failed 아님) | 보조 데이터, 파이프라인 차단 불필요 |

### 2.2 pipeline_healthy 판정 강화 (rev.3 신규)

**기존**: `status == "success"` 만 확인
**확정**: `status == "success"` AND `collected_count >= 임계값` AND `validation_passed == true`

```
pipeline_healthy = true 조건:
  premarket: status=success AND collected >= 1500 AND null_ratio < 5% AND date_valid
  primary_screen: status=success (0건도 OK — 시장 상황)
  
  => CORE_STEPS 모두 통과해야 pipeline_healthy = true
```

**primary_screen 0건은 왜 failed가 아닌가?**
- 시장이 극도로 침체되면 필터 통과 종목이 0건일 수 있음
- 이 경우 매매를 안 하는 것이 올바른 행동
- 단, premarket 데이터가 유효한 상태에서 0건이어야 함

### 2.3 재시도 가능 vs 불가 분류 (rev.3 신규)

| 실패 유형 | 재시도 | failure_type | 대응 |
|----------|--------|-------------|------|
| API 타임아웃/5xx | 가능 | `retryable` | 기존 재시도 로직 (3회) 활용 |
| API 인증 실패 (401/403) | 조건부 | `retryable` | 토큰 갱신 후 재시도 1회 |
| 데이터 0건 (API 정상 응답) | 불가 | `permanent` | 날짜 폴백 시도, 그래도 0건이면 failed |
| null 비율 초과 | 불가 | `permanent` | 즉시 failed, 데이터 소스 문제 |
| 건수 미달 (1~1499건) | 불가 | `permanent` | 즉시 failed, 부분 수집은 위험 |
| DB 적재 실패 | 가능 | `retryable` | DB 커넥션 재시도 |
| 네트워크 장애 | 가능 | `retryable` | 지수 백오프 재시도 |

### 2.4 실패 정보 Redis 저장 (rev.3 신규)

pipeline_status JSON 확장:

```json
{
  "premarket": {
    "status": "failed",
    "timestamp": "2026-04-02T08:05:00+09:00",
    "collected_count": 50,
    "validation": {
      "passed": false,
      "failure_type": "permanent",
      "failure_reason": "collected_count_below_threshold",
      "details": {
        "collected": 50,
        "threshold": 1500,
        "null_ratio": 0.02,
        "data_date": "20260401"
      }
    }
  }
}
```

## 3. 파라미터 조정 권고 (rev.3)

| 항목 | 기존 확정값 | 권고 수정값 (rev.3) | 근거 |
|------|-----------|-------------------|------|
| premarket 최소 건수 | 100 | **1,500** | 전체 3,700+ 중 100은 사실상 검증 없음. 최소 40% |
| ETF 시세 최소 수집률 | 10% | **50%** | LIVE 도메인 전환 후 50% 미달은 심각한 API 장애 |
| close_price null 허용 비율 | 없음 (신규) | **< 5%** | 핵심 시세 필드, 5% 이상이면 데이터 소스 문제 |
| volume null 허용 비율 | 없음 (신규) | **< 5%** | 거래량 비율 계산의 기반 필드 |
| data_date 유효 범위 | 없음 (신규) | **T-2 거래일 이내** | T-3 이전 데이터로 매매하면 위험 |
| primary_screen 0건 | 없음 (신규) | **warning (failed 아님)** | 시장 침체 시 정상 동작 |
| dart/sentiment 0건 | 없음 (신규) | **warning (failed 아님)** | 보조 데이터, 파이프라인 차단 불필요 |
| dart corp_code 매핑률 | 없음 (신규) | **>= 50%** | 절반 미만이면 데이터 매핑 문제 |
| sentiment 수집 성공률 | 없음 (신규) | **>= 70%** | 대부분 종목에서 뉴스 존재 |
| 실전 앱키 필수 검증 | 없음 -> 서버 시작 검증 (rev.2) | 유지 | 변경 없음 |

## 4. 리스크 및 대안

- **임계값 과도 설정**: 처음에는 보수적(높은 임계값)으로 시작. 거짓 양성이 많으면 단계적 하향. 1주일 운영 데이터 후 조정
- **ETN 시세 공백**: 매매 대상이 아니므로 당장 리스크 없음. Phase 5에서 검토
- **data_go_kr T+1 지연 + 공휴일**: 날짜 폴백이 실패하면 premarket 전체 실패. 최대 7일 폴백이면 연휴도 커버
- **LIVE 앱키 Rate Limit 공유**: 장전(조회)과 장중(매매) 시간대가 다르므로 수용 가능

### 절대 원칙 (유지 + 강화)
- 데이터 품질 미검증 상태에서 매매 엔진 활성화 금지
- 0건 수집 success는 수용 불가
- **건수 미달 수집도 success 수용 불가** (rev.3 추가)
- Dockerfile --reload은 Sprint 1 첫 번째 커밋에서 제거

## 최종 판단

**rev.3 수정안 승인**. 유효성 검증 체계는 매매 안전의 마지막 방어선이다. 임계값은 보수적으로 시작하고 운영 데이터로 보정한다.
