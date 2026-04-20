# Phase 9 검토 리포트 — 윤에이피 (API 개발자)

> **검토일**: 2026-04-20
> **검토 대상**: `docs/phase/phase9/phase9.md`
> **검토 관점**: KIS API 연동 / Rate Limit / 실전 구현 이슈

---

## 요약

⚠️ **주의** — 대안 A(KIS 과거 분봉 백필)는 기술적으로 가능하지만 **KIS API Rate Limit / 데이터 range 제약 / 토큰 관리** 세 가지 이슈가 구현 전에 반드시 확인되어야 함.

---

## KIS 과거 분봉 API 실전 검증

### 1. 사용 엔드포인트 확인

**국내주식 분봉조회**: `/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice`

- tr_id: `FHKST03010200` (주식 분봉)
- 1회 호출 시 최대 **30건** (약 2.5시간 분량, 5분봉 기준)
- 즉, **하루치(78개 5분봉)를 받으려면 3회 호출** 필요

### 2. Rate Limit 실전 제약 ⚠️

- 한투 API 기본: **초당 20건**
- 50종목 × 30거래일 × 3회 = **4,500건** → 약 4분 소요 (최대 전력 사용 시)
- 하지만 80% 여유 원칙(16/초) 적용 → **약 5분**
- **실전 경험**: 장중 시간대(09:00~15:30)에는 서버 부하로 간헐적 429 에러 발생. 장후(18:00+) 실행 권고.

### 3. 데이터 Range 제약 ⚠️

- KIS API는 과거 30거래일(1.5개월) 수준까지만 안정적 조회 가능
- 더 먼 과거 데이터는 비어있거나 누락 (KIS 내부 정책)
- 즉, **1.5개월 이상의 깊은 시계열은 백필 불가** → 박퀀트 "3개월+ 데이터 필요" 판단 시 실시간 축적 불가피

### 4. 수정주가 이슈 ⚠️ (박퀀트 지적 연장)

- KIS 과거 분봉은 **수정주가 기준** 제공 (액면분할 시 과거 가격·거래량이 수정됨)
- 실시간 수집 데이터는 **원가격 기준** (체결 그대로)
- 두 데이터를 혼용하면 분할 이후 시점 종목에서 거래량 왜곡
- **대응**: 박퀀트 권고(30일 내 분할·증자 종목 제외)에 동의 + KIS 응답에 `adjusted_flag` 플래그가 있다면 확인

### 5. 백필 배치 설계 권고

```python
# backend/modules/collector/kis_minute_backfill.py
class KisMinuteBackfillService:
    async def backfill_stock(self, code: str, days: int = 30):
        """종목별 과거 N일 5분봉 백필.
        - 장후(18:00 이후) 실행 권고
        - 80% Rate Limit 준수 (16req/s)
        - 토큰 만료 30분 전 자동 재발급
        - 응답 검증: buy_vol 필드 미제공 시 total_vol만 저장
        """
```

---

## VWAP 실시간 계산 설계

### 1. Redis 키 구조

```
vwap:{code}:{YYYYMMDD}:pv  → 누적 price*vol (정수 또는 float)
vwap:{code}:{YYYYMMDD}:v   → 누적 vol
TTL: 2일 (장마감 후 1일 유지, 이후 EOD 이관 후 삭제)
```

### 2. WebSocket 체결 수신 시 누적

```python
# kis_realtime.py 또는 scheduler.py 확장
async def on_execution(data: ExecutionData):
    pv = data.price * data.volume_tick  # 체결량 * 가격
    await redis.incrbyfloat(f"vwap:{code}:{today}:pv", pv)
    await redis.incrbyfloat(f"vwap:{code}:{today}:v", data.volume_tick)
```

### 3. 조회 시 계산

```python
async def get_vwap(code: str) -> float:
    pv = await redis.get(f"vwap:{code}:{today}:pv") or 0
    v = await redis.get(f"vwap:{code}:{today}:v") or 0
    return pv / v if v > 0 else None
```

**권고**: 계산 자체는 O(1). 조회 캐시(TTL 1초)로 API 부하 낮추기.

---

## REST API 엔드포인트 설계

Sprint 3에서 구현할 API:

| 엔드포인트 | 메소드 | 응답 |
|----------|--------|------|
| `/api/v1/indicators/vwap/{code}` | GET | `{code, vwap, price, position: "above"/"below"}` |
| `/api/v1/indicators/zscore/{code}?slot={slot}` | GET | `{code, slot, zscore, weight, samples}` |

- JWT 인증 필수
- Rate Limit: 초당 10req (UI 용이므로 충분)

---

## 파라미터 조정 권고

| # | 항목 | 원안 | 권고 | 근거 |
|---|------|------|------|------|
| A1 | 백필 실행 시간대 | 미명시 | **18:00~23:00 한정** | 장중 429 회피 |
| A2 | 백필 Rate Limit | 미명시 | **16req/s (80%)** | 공식 20 대비 여유 |
| A3 | 백필 range | 30거래일 | **최대 30거래일 (KIS 제약)** | 심층 시계열 불가 |
| A4 | VWAP Redis TTL | 미명시 | **2일** | 장마감 후 EOD 이관 여유 |
| A5 | API Rate Limit | 미명시 | **10req/s** | UI 용 적정 |
| A6 | 토큰 갱신 가드 | 미명시 | **만료 30분 전 자동 갱신** | 배치 중간 만료 방지 |

---

## 리스크 및 대안

1. **KIS API 스펙 변경 가능성**: MCP `search_domestic_stock_api`로 Sprint 0 초반 재확인 필수.
2. **백필 중 토큰 만료**: 장시간 배치이므로 자동 재발급 경로 필수 (기존 `KisAuthService` 재사용).
3. **수정주가 플래그가 없는 경우**: `corporate_actions` 이력 테이블로 별도 관리.

---

## 결론

재검토 방향은 기술적으로 가능. 단, **KIS 제약(30거래일, 18:00+ 실행, 수정주가)**를 Sprint 0 초반에 MCP로 재확인하여 Sprint 1 설계에 반영 필요.
