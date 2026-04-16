# Sprint 1: KIS LIVE WebSocket 연결 복구 (Phase 7.0.1)

**Goal:** LIVE WS URL 경로 누락 수정 + Railway Static IP 활성화로 내일 장 전 ws_connected=True 달성

**Architecture:** kis_config.py의 LIVE ws_url에 `/tryitout` 경로 추가 (1줄), diagnose_ws.py 테스트 경로 수정 (1줄). 인프라는 Railway Static Outbound IP 활성화 + KIS 개발자 포털 IP 등록.

**Tech Stack:** Python (socket), Railway Static IP, KIS WebSocket

**Sprint 기간:** 2026-04-16 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 7.0 Sprint 2 (837 passed / 5 failed 기존 무관, PR #135)
**브랜치명:** `phase7.0.1-sprint1`

---

## 제외 범위

- PAPER ws_url 수정 (확정 파라미터 #2: LIVE 검증 후 별도 수정)
- WS 클라이언트(kis_ws.py) 코드 수정 (ws_url 자동 반영)
- 스케줄러/수집기 수정 (WS 연결만 복구하면 기존 로직 정상 동작)

## 실행 플랜

### Phase 1 (순차 -- 사용자 수동)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | diagnose_ws.py Railway 실행 (원인 확정) | 인프라 | -- |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | diagnose_ws.py 테스트 경로 수정 | 백엔드 | -- |
| Task 3 | LIVE ws_url 경로 추가 | 백엔드 | -- |

### Phase 3 (순차 -- 사용자 수동)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | Railway Static IP + KIS IP 등록 | 인프라 | -- |

### Phase 4 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 5 | 배포 + 검증 | 전체 | -- |

---

### Task 1: diagnose_ws.py Railway 실행 (사용자 수동)

**실행 주체:** 사용자 (Railway CLI 필요)

**Files:**
- 수정 없음 (읽기 전용 진단)

**Step 1: Railway에서 diagnose_ws.py 실행**
- `railway run python3 backend/scripts/diagnose_ws.py`
- 검증: 출력 결과로 원인 A/B/C/D 판별

**판별 로직:**

| PAPER (31000) | LIVE (21000, /) | LIVE (21000, /tryitout) | 확정 원인 | 조치 |
|---------------|----------------|------------------------|----------|------|
| 101 | EOF | EOF | A (IP 차단) | Static IP + KIS 등록 |
| 101 | EOF | 101 | B (경로 누락) | ws_url 경로 추가 |
| 101 | 101 | 101 | C (라이브러리/키) | approval_key 디버깅 |
| EOF | EOF | EOF | D (전면 차단) | Railway 네트워크 확인 |

**Step 2: 결과 공유**
- 진단 결과를 sprint-dev에 공유하여 Task 2~4 실행 여부 결정

**완료 기준:**
- ⬜ diagnose_ws.py 실행 완료
- ⬜ 원인 A/B/C/D 중 하나 확정

---

### Task 2: diagnose_ws.py 테스트 경로 수정

**Files:**
- Modify: `backend/scripts/diagnose_ws.py` (line 16: LIVE+path 테스트 경로 수정)

**Step 1: 테스트 경로 수정**
- `backend/scripts/diagnose_ws.py` line 16 수정
- 변경 전: `("LIVE+path", 21000, "/tryitout/H0STCNT0")`
- 변경 후: `("LIVE+path", 21000, "/tryitout")`
- 이유: TR_ID(H0STCNT0)는 구독 메시지에 포함, URL 경로는 `/tryitout`만 (확정 파라미터 #6)
- 검증: `grep "LIVE+path" backend/scripts/diagnose_ws.py`
- 예상: `("LIVE+path", 21000, "/tryitout")`

**Step 2: 커밋**
```
git add backend/scripts/diagnose_ws.py
git commit -m "feat(phase7.0.1-sprint1): task2 -- diagnose_ws.py 테스트 경로 /tryitout으로 수정"
```

**완료 기준:**
- ⬜ TESTS[2]의 path가 `/tryitout`으로 변경됨

---

### Task 3: LIVE ws_url 경로 추가

**Files:**
- Modify: `backend/core/clients/kis_config.py` (line 52: LIVE ws_url 경로 추가)

**Step 1: LIVE ws_url 수정**
- `backend/core/clients/kis_config.py` line 52 수정
- 변경 전: `ws_url="ws://ops.koreainvestment.com:21000",`
- 변경 후: `ws_url="ws://ops.koreainvestment.com:21000/tryitout",`
- PAPER ws_url은 변경하지 않음 (확정 파라미터 #2)
- 검증: `grep 'ws_url=' backend/core/clients/kis_config.py`
- 예상: PAPER는 `:31000`, LIVE는 `:21000/tryitout`

**Step 2: 기존 테스트 회귀 확인**
- 검증: `docker compose exec backend pytest tests/ -k "kis" -v --timeout=30`
- 예상: 기존 KIS 관련 테스트 모두 통과 (ws_url은 모킹 대상이므로 영향 없음)

**Step 3: 커밋**
```
git add backend/core/clients/kis_config.py
git commit -m "feat(phase7.0.1-sprint1): task3 -- LIVE ws_url에 /tryitout 경로 추가"
```

**완료 기준:**
- ⬜ LIVE ws_url이 `ws://ops.koreainvestment.com:21000/tryitout`으로 변경됨
- ⬜ PAPER ws_url은 기존 유지 (`ws://ops.koreainvestment.com:31000`)
- ⬜ 기존 KIS 테스트 회귀 없음

---

### Task 4: Railway Static IP + KIS IP 등록 (사용자 수동)

**실행 주체:** 사용자 (Railway 대시보드 + KIS 개발자 포털 접근 필요)

**Files:**
- 수정 없음 (인프라 작업)

**Step 1: Railway Static Outbound IP 활성화**
- Railway 대시보드 > backend 서비스 > Settings > Networking > Static Outbound IP 활성화
- 할당된 고정 IP 확인 후 기록

**Step 2: KIS 개발자 포털 IP 등록**
- KIS 개발자 포털 > 실전투자 API > IP 관리 > 할당된 고정 IP 등록
- 등록 반영 확인 (즉시 반영이 아닐 수 있음)
- 비상: KIS IP 등록 반영 지연 시 KIS 고객센터(1544-5000) 긴급 반영 요청

**완료 기준:**
- ⬜ Railway Static Outbound IP 활성화 완료
- ⬜ KIS 개발자 포털에 고정 IP 등록 완료

---

### Task 5: 배포 + 검증

**Files:**
- 수정 없음 (배포 + 검증만)

**Step 1: develop PR 생성 + 머지**
- sprint-close 에이전트로 phase7.0.1-sprint1 -> develop PR 생성
- develop -> main PR 생성 (deploy-prod)
- Railway 자동 배포 대기

**Step 2: 배포 후 즉시 검증**
- 검증: `curl -s https://api.stockbot.choiji.kr/api/v1/kis/status | jq .`
- 예상: `ws_connected: true, subscriptions > 0`
- 대안: 수동 트리거 `curl -X POST https://api.stockbot.choiji.kr/api/v1/collector/trigger/market-open`

**Step 3: 내일 08:55 자동 확인**
- 검증: `curl -s https://api.stockbot.choiji.kr/api/v1/kis/status | jq .`
- 예상: `ws_connected: true` (장 시작 전 자동 연결)

**완료 기준:**
- ⬜ WS 연결 성공 (ws_connected=True)
- ⬜ 1종목 이상 구독 성공 (subscriptions > 0)
- ⬜ 내일 09:00 자동 연결 성공

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| KIS 테스트 회귀 | `docker compose exec backend pytest tests/ -k "kis" -v` | 기존 테스트 통과 |
| WS 연결 상태 | `curl -s https://api.stockbot.choiji.kr/api/v1/kis/status` | ws_connected=true |
| 구독 현황 | 위 API 응답의 subscriptions 필드 | > 0 |
| 내일 장 시작 | 08:55 KST 수동 확인 | ws_connected=true |
