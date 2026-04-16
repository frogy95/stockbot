# Phase 7.0.1: KIS LIVE WebSocket 연결 복구 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-16)
> **ROADMAP 참조**: `ROADMAP.md` Phase 7.0.1
> **검토 리포트**:
>
> - `phase7.0.1-po-review.md` (정프로, PO)
> - `phase7.0.1-risk-review.md` (최리스크, 리스크관리)
> - `phase7.0.1-api-review.md` (윤에이피, API 개발자)
> - `phase7.0.1-daytrader-review.md` (김단타, 단타 전문가)

---

## 개요

2026-04-16 09:00 KST, KIS LIVE WebSocket 연결이 전면 실패. approval_key 발급(REST)은 성공하나, WS 핸드셰이크에서 `EOFError: stream ends after 0 bytes`로 즉시 종료됨. 3회 recovery 시도 모두 동일 실패.

### 장애 타임라인

```
09:00 KST  _market_open() 실행 → approval_key 발급 성공 → WS connect 실패 (EOF 0 bytes)
09:05 KST  recovery 1/3 → 동일 실패
09:10 KST  recovery 2/3 → 동일 실패
09:15 KST  recovery 3/3 → 최종 실패 → 텔레그램 알림 발송
```

### 추정 원인 (2건, 복합 가능)

```
원인 A — IP 화이트리스트 차단 (유력)
  REST API (openapi:9443) : IP 등록됨 → approval_key 발급 성공
  WS 서버 (ops:21000)    : 다른 서버 → IP 미등록 가능
  증거: TCP 연결 성공 후 HTTP 응답 없이 즉시 EOF = L4/L7 방화벽 차단 패턴
  Railway IP: 동적 → Static IP 미활성화 상태

원인 B — WS URL 경로 누락 (확정)
  현재 코드:   ws://ops.koreainvestment.com:21000         (경로 없음)
  공식 예제:   ws://ops.koreainvestment.com:21000/tryitout (모든 예제 일치)
  KIS kis_auth.py: url = f"{my_url_ws}{api_url}"  (api_url="/tryitout")
  증거: KIS 공식 GitHub 예제 100% /tryitout 경로 사용
```

### 아키텍처 영향

```
WS 미연결 시 파이프라인 중단 범위:

  실시간 체결가 수신 ──X──> 2차 스크리닝 (30초 주기) ──X──> 매매 신호 생성
                                                              ──X──> 주문 실행
  실시간 호가 수신   ──X──> 체결강도 분석

  영향받지 않는 것:
  - 장전 수집 (REST 기반, WS 무관)
  - 1차 스크리닝 (REST 기반)
  - 기존 포지션: 없음 (LIVE 미전환)
```

---

## 검토팀 확정 파라미터 (2026-04-16)

> 정프로(PO), 최리스크(리스크), 윤에이피(API), 김단타(단타) — 4명 검토 완료

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | LIVE ws_url | `ws://ops.koreainvestment.com:21000` | `ws://ops.koreainvestment.com:21000/tryitout` | KIS 공식 예제 100% 일치 (윤에이피 확인) |
| 2 | PAPER ws_url 수정 시점 | LIVE와 동시 수정 | **LIVE 검증 후 별도 수정** | 4명 전원 합의: PAPER는 기존 동작 보호 우선 |
| 3 | Railway Static IP | 원인 A 확인 시 활성화 | **무조건 활성화** | 최리스크: LIVE 운영에 고정 IP 필수, 원인 무관 |
| 4 | diagnose_ws.py 우선 실행 | Task 1 | Task 1 유지 (필수) | 최리스크: 원인 미확정 상태에서 코드 배포 금지 |
| 5 | 복구 확인 시점 | 수동 확인 | 배포 후 즉시 + **내일 08:55 자동 체크** | 김단타: 장 시작 전 5분 여유 필요 |
| 6 | diagnose_ws.py 테스트 경로 | `/tryitout/H0STCNT0` | `/tryitout` | 윤에이피: TR_ID는 구독 메시지에 포함, URL 경로는 `/tryitout`만 |
| 7 | 장중 수동 복구 시도 | 미정 | **오늘 장중은 포기, 장후 수정 집중** | 김단타: 장중 긴급 수정은 2차 장애 위험 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 | WS 연결 진단 + 수정 + 검증 | diagnose 실행, kis_config 수정, Static IP, 검증 | 없음 |

---

## Sprint 1 상세 — WS 연결 진단 + 수정 + 검증

### Task 1: 원인 확정 진단 (diagnose_ws.py 실행)

**실행 환경**: Railway (프로덕션과 동일한 네트워크)

```bash
railway run python3 backend/scripts/diagnose_ws.py
```

**판별 로직**:

| PAPER (31000) | LIVE (21000, /) | LIVE (21000, /tryitout) | 확정 원인 | 조치 |
|---------------|----------------|------------------------|----------|------|
| 101 | EOF | EOF | A (IP 차단) | Static IP + KIS 등록 |
| 101 | EOF | 101 | B (경로 누락) | ws_url 경로 추가 |
| 101 | 101 | 101 | C (라이브러리/키) | approval_key 디버깅 |
| EOF | EOF | EOF | D (전면 차단) | Railway 네트워크 확인 |

**수정 파일**: 없음 (읽기 전용 진단)

### Task 2: kis_config.py 수정 (LIVE ws_url 경로 추가)

**수정 파일**: `backend/core/clients/kis_config.py`

```python
# 변경 전
LIVE = KISEnvironment(
    ...
    ws_url="ws://ops.koreainvestment.com:21000",
    ...
)

# 변경 후
LIVE = KISEnvironment(
    ...
    ws_url="ws://ops.koreainvestment.com:21000/tryitout",
    ...
)
```

**주의**: PAPER ws_url은 변경하지 않음 (확정 파라미터 #2)

**diagnose_ws.py 수정**: LIVE+path 테스트 경로를 `/tryitout`으로 변경 (확정 파라미터 #6)

### Task 3: Railway Static Outbound IP 활성화 + KIS IP 등록 (인프라)

**조건**: 무조건 실행 (확정 파라미터 #3)

1. Railway 대시보드 > Settings > Networking > **Static Outbound IP** 활성화
2. 할당된 고정 IP 확인
3. KIS 개발자 포털 > 실전투자 API > IP 관리 > 할당 IP 등록
4. 등록 반영 확인 (즉시 반영이 아닐 수 있음)

**비상**: KIS IP 등록 반영 지연 시 KIS 고객센터(1544-5000) 긴급 반영 요청

**deploy.md 수동 검증 항목 추가**:
- `Railway Static Outbound IP 활성화 확인`
- `KIS 개발자 포털 LIVE WS IP 등록 확인`

### Task 4: 검증

1. Railway 재배포 (`main` merge 시 자동)
2. 배포 완료 후 즉시:
   ```
   GET /api/v1/kis/status
   → ws_connected: true, subscriptions > 0
   ```
3. 또는 수동 트리거:
   ```
   POST /api/v1/collector/trigger/market-open
   ```
4. 내일 08:55 자동 확인:
   - `GET /api/v1/kis/status` → ws_connected=true

**성공 기준**:
- WS 연결 성공 (ws_connected=True)
- 1개 이상 종목 구독 성공 (subscriptions > 0)
- 실시간 체결가 데이터 수신 확인

### 재사용 자산

| 기존 모듈 | 용도 | 수정 필요 |
|-----------|------|----------|
| `backend/scripts/diagnose_ws.py` | 진단 스크립트 | 테스트 경로 `/tryitout`으로 수정 |
| `backend/core/clients/kis_config.py` | WS URL 설정 | LIVE ws_url 경로 추가 |
| `backend/core/clients/kis_ws.py` | WS 클라이언트 | 수정 없음 (ws_url 자동 반영) |
| `backend/modules/collector/scheduler.py` | 스케줄러 | 수정 없음 |
| `/api/v1/kis/status` | 상태 확인 API | 수정 없음 |
| `/api/v1/collector/trigger/market-open` | 수동 복구 | 수정 없음 |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 담당 검토자 | Sprint 배치 |
|---|------|--------|------------|------------|
| 1 | KIS IP 등록 반영 시간 미확인 (즉시 vs 수 시간) | ⚠️ | 윤에이피 | Sprint 1 Task 3 |
| 2 | PAPER ws_url `/tryitout` 추가 영향 미검증 | ⚠️ | 정프로, 최리스크 | 후속 작업 (Phase 7.0 Sprint 3에서) |
| 3 | Railway Static IP 비용 ($5/month) | ✅ 수용 | 정프로 | Sprint 1 Task 3 |
| 4 | diagnose 결과 원인 D (전면 차단) 시 대응 미정 | ⚠️ | 윤에이피 | Sprint 1 Task 1 결과에 따라 |
| 5 | KIS WS 서버 점검 가능성 (외부 요인) | ⚠️ | 김단타 | KIS 공지사항 확인 |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| diagnose_ws.py Railway 실행 완료 | 원인 A/B/C/D 확정 | ⬜ |
| LIVE ws_url `/tryitout` 경로 추가 | kis_config.py 수정 + 배포 | ⬜ |
| Railway Static IP 활성화 | 고정 IP 할당 확인 | ⬜ |
| KIS IP 등록 (필요 시) | 개발자 포털 등록 완료 | ⬜ |
| WS 연결 성공 확인 | ws_connected=True | ⬜ |
| 종목 구독 성공 확인 | subscriptions > 0 | ⬜ |
| 내일 09:00 자동 연결 성공 | 장 시작 시 정상 동작 | ⬜ |

---

## 후속 작업

- **Phase 7.0 Sprint 3**: E2E 검증 + LIVE 전환 게이트 (이 Phase 완료 후 진행)
- **PAPER ws_url 수정**: LIVE 안정 확인 후 PAPER에도 `/tryitout` 추가 (Sprint 3에서)
