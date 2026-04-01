# Phase 4.6 API 개발자 검토 리포트 — 윤에이피

> **검토일**: 2026-04-02 (수정안 검토)
> **대상**: 데이터 수집 파이프라인 근본 수리 계획 — KIS 조회/매매 도메인 분리 반영 수정안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| tr_id 패턴 분석 정확성 | ✅ 통과 — 조회 tr_id는 환경 무관 고정값 |
| 도메인 분리 구현 방안 | ✅ 통과 — inquiry_client/trading_client 분리 합리적 |
| TokenManager 이중 인스턴스 | ✅ 통과 — 기존 구조가 env별 독립이므로 자연스러운 확장 |
| KISRestClient 수정 범위 | ✅ 통과 — 클래스 내부 변경 없음, 인스턴스만 2개 |
| main.py 초기화 변경 | ✅ 통과 — 파급 범위 관리 가능 |
| Dockerfile --reload | ❌ 재검토 — 즉시 제거 필수 (기존 판정 유지) |

## 2. 항목별 검증 결과

### tr_id 패턴 분석 — ✅ 정확

한투 API tr_id 규칙:
- **조회** (시세/호가/종목정보): `FHKST01010100`, `FHKST01010200` 등 -> 환경 prefix 없음, 고정값
- **매매** (주문/취소): `{V/T}TTC0802U`, `{V/T}TTC0801U` -> V=모의, T=실전
- **잔고/체결**: `{V/T}TTS3320R`, `{V/T}TTC8001R` -> V=모의, T=실전

실전 도메인으로 조회 tr_id를 보내면 정상 동작한다. 모의 도메인이 일부 조회(ETF 포함)에서 HTTP 500을 반환하는 것은 문서에 없는 실전 이슈.

### 구현 방안 — ✅ 합리적

```python
# 현재 구조 (단일 환경)
env = get_current_environment()  # paper or live
token_manager = KISTokenManager(env=env, redis=redis_client)
rest_client = KISRestClient(env=env, token_manager=token_manager, throttler=throttler)

# 수정 구조 (이중 환경)
inquiry_env = get_environment("live")  # 조회는 항상 LIVE
trading_env = get_current_environment()  # 매매는 TRADING_ENV 따름

inquiry_token = KISTokenManager(env=inquiry_env, redis=redis_client)
trading_token = KISTokenManager(env=trading_env, redis=redis_client)

inquiry_throttler = TokenBucketThrottler(interval=inquiry_env.rate_limit_interval)
trading_throttler = TokenBucketThrottler(interval=trading_env.rate_limit_interval)

inquiry_client = KISRestClient(env=inquiry_env, token_manager=inquiry_token, throttler=inquiry_throttler)
trading_client = KISRestClient(env=trading_env, token_manager=trading_token, throttler=trading_throttler)
```

**장점**: KISRestClient 내부 코드 변경 없음. 인스턴스만 2개.
**참고**: `TRADING_ENV=live`일 때 inquiry_env == trading_env -> 동일 환경 2개 인스턴스. 토큰은 Redis 키가 같아서 (`kis:live:access_token`) 공유됨. 문제없음.

### TokenManager 이중 인스턴스 — ✅ 자연스러운 확장

기존 `KISTokenManager`는 `_token_key()`를 `kis:{env.name}:access_token`으로 생성:
- inquiry용: `kis:live:access_token`
- trading용 (paper): `kis:paper:access_token`

Redis 키가 자연스럽게 분리. 코드 수정 불필요.

### 파급 범위 분석

| 파일 | 변경 | 설명 |
|------|------|------|
| `kis_config.py` | 수정 | `get_inquiry_environment()` 헬퍼 추가 |
| `main.py` | 수정 | lifespan에서 inquiry/trading 이중 초기화, app.state 분리 |
| `scheduler.py` | 수정 | `__init__`에 `inquiry_client` 파라미터 추가, ETF 수집에 inquiry_client 사용 |
| `kis_collector.py` | 변경 없음 | 이미 `rest_client`를 외부에서 받으므로 inquiry_client 넘기면 됨 |
| `kis_rest.py` | 변경 없음 | 인스턴스 2개, 클래스 자체 수정 불필요 |
| `token_manager.py` | 변경 없음 | 이미 env별 독립 |

**app.state 권고**: 기존 `app.state.kis_rest`를 매매용으로 유지하고 `app.state.kis_inquiry` 추가 -> 기존 코드 파급 최소화.

### Shutdown 순서

inquiry_client `.close()` + trading_client `.close()` 각각 호출 필요. inquiry_token_manager도 `.close()` 필요.

### WS 클라이언트 — 변경 없음

WS(웹소켓)는 실시간 체결/호가 수신용. WS 연결 URL은 모의/실전이 다르므로 현재 구조 유지.

## 3. 파라미터 조정 권고

| # | 항목 | 기존 확정값 | 권고 수정값 | 근거 |
|---|------|-----------|-----------|------|
| 5 | ETF 시세 (모의) | optional | **required** | LIVE 도메인 조회로 정상 수집 |
| 신규 | inquiry Rate Limit | 미정 | **LIVE 기준 0.07초** | 실전 도메인 Rate Limit |
| 신규 | Throttler 분리 | 미정 | **inquiry/trading 각각 독립 Throttler** | Rate Limit 간섭 방지 |
| 기존 | Dockerfile, 에러 전파, 날짜 폴백 등 | 유지 | 유지 | 기존 분석 정확 |

## 4. 리스크 및 대안

### TRADING_ENV=live 시 Rate Limit 공유
inquiry와 trading이 동일 LIVE 환경 -> 서버 측에서 앱키 기준 Rate Limit. 두 Throttler 합산이 실제 한도를 초과할 수 있다. -> 단, 조회는 장전 08:00 집중, 매매는 장중 09:00~15:30이므로 시간대 분리. 리스크 수용 가능. Phase 5 범위에서 Throttler 공유/분할 검토.

### CI 환경
실전 앱키가 없는 CI에서 서버 시작 실패 -> 테스트 시 mock 필수. 기존 테스트가 mock 기반이므로 문제없음.

## 최종 판단

**수정안 승인**. KISRestClient를 인스턴스 2개로 분리하는 방식은 기존 코드 변경이 최소화되면서 문제를 근본적으로 해결한다. 클래스 내부 수정 없이 초기화 시점에서만 분리하는 것이 핵심.
