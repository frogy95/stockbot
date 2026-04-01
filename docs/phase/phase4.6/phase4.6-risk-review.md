# Phase 4.6 리스크관리 검토 리포트 — 최리스크

> **검토일**: 2026-04-02 (수정안 검토)
> **대상**: 데이터 수집 파이프라인 근본 수리 계획 — KIS 조회/매매 도메인 분리 반영 수정안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| 도메인 분리 아키텍처 | ✅ 통과 — 조회/매매 분리는 보안상으로도 올바르다 |
| "모의 ETF optional" 제거 | ✅ 통과 — optional은 리스크를 숨기는 안티패턴이었다 |
| 실전 앱키로 조회 | ⚠️ 주의 — 실전 앱키 존재 검증 필요 |
| pipeline_healthy 판정 | ✅ 통과 — ETF 시세도 항상 required로 통일 |
| 에러 전파/수집 건수 검증 | ✅ 유지 — 기존 확정 파라미터 그대로 적용 |

## 2. 항목별 검증 결과

### 도메인 분리 — ✅ 통과 (강력 지지)

**기존 설계의 리스크**: `TRADING_ENV=paper`이면 모든 API 호출이 모의 도메인으로 간다.
- 조회 데이터의 정확성을 보장할 수 없다 (모의 서버는 시세가 다를 수 있음)
- ETF 시세 전량 실패 -> pipeline_healthy 판정 왜곡 -> 잘못된 데이터로 매매 결정

**수정안**: 조회는 항상 LIVE 도메인 -> 실제 시장 데이터 수집 보장. 매매만 TRADING_ENV에 따라 분기. 리스크 관리 관점에서 올바른 구조.

### "모의 ETF optional" 제거 — ✅ (이전 설계는 위험했다)

기존 "모의 환경이면 ETF 실패해도 healthy" 로직은 **위험 요소를 숨기는 안티패턴**이었다. 실전 전환 시 이 분기를 잊으면 ETF 데이터 없이 매매하게 된다. 도메인 분리로 예외 분기 자체가 없어지는 것이 좋다.

### 실전 앱키로 조회 — ⚠️ 주의

- 모의 환경에서도 실전 앱키(KIS_APP_KEY/SECRET)가 .env에 반드시 있어야 한다
- 실전 앱키의 Rate Limit을 조회가 소비한다 (초당 ~20건이므로 문제없음)
- CI 등 실전 앱키가 없는 환경에서는 조회 불가 -> `.env.example`에 명시 + 테스트 시 mock 처리

**권고**: 서버 시작 시 KIS_APP_KEY 존재 여부 검증 추가

### pipeline_healthy 판정 — ✅ 통일

ETF 시세가 항상 LIVE 도메인 조회이므로 모의/실전 무관 동일 판정 기준:
- ETF 수집률 < 10% -> failed
- premarket < 100건 -> failed
- pipeline_healthy = CORE_STEPS success + 최소 건수 충족

## 3. 파라미터 조정 권고

| # | 항목 | 기존 확정값 | 권고 수정값 | 근거 |
|---|------|-----------|-----------|------|
| 1 | Dockerfile CMD | --reload 제거 | 유지 | 변경 없음 |
| 2 | docker-compose 개발 | command override | 유지 | 변경 없음 |
| 3 | premarket 최소 건수 | 100건 미만 시 failed | 유지 | 변경 없음 |
| 4 | ETF 시세 최소 수집률 | 10% 미만 시 failed | 유지 | 변경 없음 |
| 5 | ETF 시세 (모의) | **optional** | **required** | 도메인 분리로 모의에서도 정상 수집 |
| 6 | ETF 시세 (실전) | required | 유지 | 변경 없음 |
| 7 | data_go_kr 0건 처리 | warning + 날짜 폴백 | 유지 | 변경 없음 |
| 8 | pipeline_healthy 판정 | status + 건수 동시 확인 | 유지 | 변경 없음 |
| 신규 | 실전 앱키 필수 검증 | 없음 | **서버 시작 시 KIS_APP_KEY 존재 검증** | 조회에 실전 앱키 필수 |

## 4. 리스크 및 대안

### 이중 토큰 관리
inquiry + trading 토큰 2개 -> Redis 키 `kis:live:access_token`, `kis:paper:access_token` 자연 분리. 기존 구조 활용이므로 리스크 낮음.

### Rate Limit 공유 (TRADING_ENV=live 시)
실전 전환 시 inquiry와 trading이 같은 앱키 -> Rate Limit 공유. 단, 조회는 장전 08:00 집중, 매매는 장중 09:00~15:30이므로 시간대 분리됨. 리스크 수용 가능. Phase 5 범위에서 Throttler 공유/분할 검토.

### 절대 원칙 (유지)
- 데이터 품질 미검증 상태에서 매매 엔진 활성화 금지
- 0건 수집 success는 수용 불가
- Dockerfile --reload은 Sprint 1 첫 번째 커밋에서 제거

## 최종 판단

**수정안 승인**. 기존 "모의 optional"은 리스크를 숨기는 위험한 구조였다. 도메인 분리가 올바른 근본 해결이다.
