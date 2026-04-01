# Phase 4.6 리스크관리 검토 리포트 — 최리스크

> **검토일**: 2026-04-02
> **대상**: 데이터 수집 파이프라인 근본 수리 계획 초안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| 매매 엔진 안전성 | ❌ 재검토 — 데이터 없이 pipeline_healthy=true가 될 수 있는 구조적 결함 |
| 에러 전파 | ❌ 재검토 — 전량 실패도 success로 기록되는 심각한 문제 |
| Dockerfile --reload | ❌ 재검토 — 프로덕션에서 WatchFiles는 즉시 제거 필수 |
| 데이터 품질 검증 | ⚠️ 주의 — 수집 건수 0건 success는 매매 기반 데이터 부재를 의미 |

## 2. 항목별 검증 결과

### 치명적 리스크: pipeline_healthy 거짓 양성

현재 구조에서 `_premarket_collect`가 0건을 수집해도 예외가 발생하지 않으면 `success`로 기록된다. `_are_core_steps_healthy`는 `premarket`과 `primary_screen`의 status만 확인한다. **데이터 0건 수집도 healthy로 판단되어 매매 엔진이 활성화될 수 있다.**

이는 Phase 4.5에서 설계한 pipeline_healthy 플래그의 근본 의도를 무력화한다. "데이터 없이 매매"는 최악의 시나리오.

### 치명적 리스크: ETF 수집 거짓 성공

`collect_etf_prices`에서 881개 전부 HTTP 500이 나도 `collected=0`만 반환하고 예외를 던지지 않는다. scheduler의 `_etf_collect`는 이를 `success`로 기록한다. Redis에 "etf: success"가 찍혔는데 실제 데이터 0건.

### Dockerfile --reload 즉시 제거

프로덕션에서 `--reload`는 **절대 사용 불가**. WatchFiles가 파일 시스템 이벤트마다 프로세스를 재시작하면:
1. APScheduler job이 실행 중 강제 종료 → DB 트랜잭션 미완료
2. 재시작 루프 → 스케줄 window를 모두 놓침
3. 토큰 갱신 중 중단 → 인증 실패

## 3. 파라미터 조정 권고

| 항목 | 원래 설계 | 권고값 | 근거 |
|------|----------|--------|------|
| premarket 최소 수집 건수 | 0 (검증 없음) | **100건 미만 시 failed** | 전체 시장 3,700+ 종목, 100건 미만은 API 장애 |
| ETF 시세 최소 수집률 | 0% (검증 없음) | **10% 미만 시 failed** | 881개 중 88개 미만이면 데이터 무의미 |
| Dockerfile CMD | --reload 포함 | **--reload 제거 필수** | 프로덕션 안정성 최우선 |
| uvicorn workers | 1 (암묵) | **1 유지** (APScheduler 단일 프로세스) | 멀티워커 시 스케줄 중복 실행 |
| data_go_kr 수집 0건 시 | success | **warning + 전일 재시도** | 0건 success는 pipeline_healthy 거짓 양성 유발 |
| pipeline_healthy 판정 | status만 확인 | **status + 최소 수집 건수 동시 확인** | 0건 success 방지 |

## 4. 리스크 및 대안

### 최우선 (Sprint 1 Day 1)
1. **Dockerfile --reload 제거** — 한 줄 수정이지만 영향이 가장 크다
2. **에러 전파 수정** — 수집 결과가 최소 임계값 미달이면 failed로 처리
3. **pipeline_healthy 판정 강화** — 건수 검증 추가

### 주요 리스크
- 공공데이터포털 API가 당일 데이터를 제공하지 않는 것은 API 설계의 한계. 이를 "장애"와 구분하는 로직 필요.
- 모의투자 KIS API의 ETF 시세 미지원은 코드로 해결 불가. **실전 전환 전까지 ETF 시세 수집을 비필수(optional)로 분류**하되, 수집 실패 시 정직하게 failed를 기록해야 한다.

### 절대 원칙
- **데이터 품질이 검증되지 않은 상태에서 매매 엔진 활성화 금지**
- 0건 수집 success는 수용 불가
- Dockerfile --reload은 Sprint 1의 첫 번째 커밋에서 제거
