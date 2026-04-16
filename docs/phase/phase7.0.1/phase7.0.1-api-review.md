# Phase 7.0.1 API 개발자 검토 리포트 — 윤에이피

> 검토일: 2026-04-16
> 대상: KIS LIVE WebSocket 연결 실패 진단 + 수정 계획

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| 원인 분석 | ✅ 통과 — A(IP) + B(경로) 두 원인 모두 유력, diagnose로 확정 |
| URL 경로 수정 | ✅ 통과 — 공식 예제 100% `/tryitout` 사용 |
| IP 관리 | ⚠️ 주의 — KIS REST/WS IP 관리 독립 가능성 |
| approval_key 로직 | ✅ 통과 — 기존 코드 스펙 준수 |
| PAPER 호환성 | ⚠️ 주의 — 경로 추가 영향 사전 확인 필요 |

## 2. 항목별 검증 결과

### KIS WS URL 분석

**공식 스펙 (KIS GitHub 예제, 2025-07-09 기준):**
```
kis_devlp.yaml:
  ops: "ws://ops.koreainvestment.com:21000"   # 실전 베이스
  vops: "ws://ops.koreainvestment.com:31000"  # 모의 베이스

kis_auth.py:
  url = f"{getTREnv().my_url_ws}{self.api_url}"
  # api_url="/tryitout" → 최종: ws://ops.koreainvestment.com:21000/tryitout

모든 실시간 예제 (ccnl_krx, ccnl_total, asking_price_total 등):
  kws = ka.KISWebSocket(api_url="/tryitout")
```

**현재 코드:**
```python
# kis_config.py
LIVE ws_url = "ws://ops.koreainvestment.com:21000"   # ← /tryitout 누락
PAPER ws_url = "ws://ops.koreainvestment.com:31000"  # ← /tryitout 누락
```

**결론: 경로 `/tryitout` 누락 확정 (원인 B)**

### IP 화이트리스트 분석

- KIS REST API(`openapi.koreainvestment.com:9443`): approval_key 발급 성공 → REST IP는 등록됨
- KIS WS(`ops.koreainvestment.com:21000`): 다른 서버/포트 → IP 관리가 독립적일 수 있음
- PAPER WS(`:31000`): 모의환경은 IP 제한이 느슨할 수 있음 (공식 문서 미명시)
- Railway 동적 IP: 재배포마다 변경 → Static IP 필수

**결론: IP 화이트리스트도 원인일 가능성 높음 (원인 A). 단, 경로 누락이 더 확실한 1차 원인**

### approval_key 발급 로직 검증

```python
# token_manager.py:107-126
body = {
    "grant_type": "client_credentials",
    "appkey": self._env.app_key,
    "secretkey": self._env.app_secret,  # ← 공식 예제와 일치
}
resp = await http.post("/oauth2/Approval", json=body)
```

- 파라미터명 `secretkey` (공식 예제와 일치) ✅
- REST URL `/oauth2/Approval` (공식 예제와 일치) ✅
- approval_key 발급은 성공 (로그 확인) ✅

### 오류 패턴 분석

```
EOFError: stream ends after 0 bytes, before end of line
websockets.exceptions.InvalidMessage: did not receive a valid HTTP response
```

이 패턴의 의미:
1. TCP 연결은 성공 (소켓 열림)
2. HTTP Upgrade 요청 전송
3. 서버가 HTTP 응답 없이 즉시 연결 종료 (0 bytes)

이것은 두 가지 원인으로 발생 가능:
- **IP 차단**: L4/L7 방화벽이 연결 후 즉시 RST/FIN 전송
- **잘못된 경로**: 서버가 경로 없는 요청을 거부하고 연결 종료

**경로 누락 시 서버 동작**: 일부 WS 서버는 잘못된 경로에 HTTP 404를 보내지만, KIS 서버는 연결을 즉시 종료할 수 있음 (비표준이지만 가능)

## 3. 파라미터 조정 권고

| 항목 | 원래 설계 | 권고값 | 근거 |
|------|----------|--------|------|
| LIVE ws_url | `ws://ops.koreainvestment.com:21000` | `ws://ops.koreainvestment.com:21000/tryitout` | 공식 예제 100% 일치 |
| PAPER ws_url | `ws://ops.koreainvestment.com:31000` | `ws://ops.koreainvestment.com:31000/tryitout` | 공식 예제 일치, 단 기존 동작 확인 후 |
| diagnose_ws.py 테스트 경로 | `/tryitout/H0STCNT0` | `/tryitout` | 공식 예제 경로는 `/tryitout` (TR_ID는 구독 메시지에 포함) |
| websockets.connect 추가 헤더 | 없음 | 없음 유지 | 공식 예제도 추가 헤더 없이 연결 |

## 4. 리스크 및 대안

### 실전 이슈 (문서에 없는 것들)

1. **KIS WS 서버 재시작**: KIS는 주기적으로 WS 서버를 재시작함 (보통 새벽). 재연결 로직이 `/tryitout` 포함 URL로 재연결하는지 확인 필요
   - 현재 코드: `_reconnect()`에서 `self._env.ws_url`을 사용 → `kis_config.py` 수정하면 자동 반영 ✅

2. **PAPER/LIVE 서버 동작 차이**: PAPER 서버(31000)는 경로 없이도 동작할 수 있지만, LIVE 서버(21000)는 경로를 강제할 수 있음
   - KIS가 LIVE 서버를 업데이트하면서 경로 요구 조건을 추가했을 가능성

3. **Railway Static IP 비용**: Railway Static IP는 유료 기능($5/month)
   - 그러나 LIVE 거래에 필수 인프라이므로 비용 대비 가치 충분

### 권고 실행 순서

```
1. Railway에서 diagnose_ws.py 실행 (원인 확정)
2. kis_config.py LIVE ws_url에 /tryitout 추가
3. Railway Static IP 활성화 + KIS 포털 IP 등록 (원인 A 해당 시)
4. Railway 재배포
5. /api/v1/kis/status 확인 또는 수동 market-open-recovery 트리거
6. 안정 확인 후 PAPER ws_url도 /tryitout 추가 (별도 PR)
```
