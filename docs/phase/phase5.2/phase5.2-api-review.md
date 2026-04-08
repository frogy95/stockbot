# Phase 5.2 검토 리포트 — 윤에이피 (API 개발자)

> **검토일**: 2026-04-08
> **검토 대상**: KIS WebSocket 모의 환경 안정화 아키텍처 초안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| 원인 분석 | ✅ 통과 — 구독 수 초과가 주 원인으로 정확 |
| 환경별 구독 제한 | ✅ 통과 — KISEnvironment에 필드 추가 방식 적절 |
| 재연결 로직 | ⚠️ 주의 — 구독 복원 딜레이 외 추가 고려사항 있음 |
| 로깅 | ✅ 통과 — close code/reason 로깅 필수 |

---

## 2. 항목별 검증 결과

### KIS 모의 WebSocket 제약 (실전 경험 기반)

한투 모의 WS(port 31000)의 비공식 제한사항:
1. **구독 수**: 문서에는 "최대 40건"이라 되어있지만, 실제로는 **종목당 tr_id를 별도 카운트**. 즉 1종목 x 2 tr_id = 2건으로 카운트
2. **모의 서버 안정성**: 실전(port 21000)보다 현저히 불안정. 10~30분 간격으로 서버 측 연결 해제가 발생하는 것이 일반적
3. **approval_key**: 모의 환경 approval_key의 유효 시간이 실전보다 짧을 수 있음 (비공식)

### 현재 코드의 구체적 문제

1. **구독 카운팅 불일치**: `WSSubscriptionManager._subscriptions`는 종목 단위(35개)로 관리하지만, 실제 WS 서버는 tr_id 단위로 카운트. 35종목 x 2 = 70건은 40건 한도의 175%
2. **_reconnect() 구독 복원**: `subscriptions_snapshot`을 순회하며 `self.subscribe()`를 호출하는데, 이때 `subscribe()` 내부에서 다시 `_subscriptions`에 추가하므로 **중복 추가 방지는 되어 있으나**, 70건을 한번에 보내면 서버가 즉시 끊음
3. **ConnectionClosed 미상세화**: `websockets.exceptions.ConnectionClosed`에는 `code`와 `reason` 속성이 있는데 현재 미사용
4. **ping_interval=30**: 모의 서버는 ping 응답이 느려서 timeout이 발생할 수 있음. `ping_timeout` 파라미터도 명시 필요

### 구독 복원 딜레이 구현 주의

- 0.3초/종목은 적절하나, **tr_id당 0.3초**가 더 정확. 1종목 = 2 tr_id이므로 종목당 실질 0.6초
- 실전 환경에서도 딜레이 적용 권고 (0.1초/tr_id). 실전 서버도 한번에 수십 건 보내면 일부 누락
- **구독 복원 중 수신 메시지 처리**: 복원 중에도 이미 복원된 종목의 데이터가 들어오므로, 수신 루프가 별도 Task로 동작해야 함 (현재 구조 OK)

---

## 3. 파라미터 조정 권고

| 항목 | 초안 | 권고 | 근거 |
|------|------|------|------|
| paper max_ws_subscriptions | 20 | **20 유지** | 20종목 x 2 tr_id = 40건. 한도의 100%. 여유를 주려면 **18** (36건, 한도 90%)이 이상적이나 20도 수용 가능 |
| live max_ws_subscriptions | 35 | **35 유지** | 실전 한도가 더 높을 가능성. 추후 실전 테스트 시 조정 |
| 재연결 구독 복원 딜레이 | 0.3초/종목 | **0.5초/종목 (= 0.25초/tr_id)** | 모의 서버 처리 속도 감안. 실전은 0.2초/종목 |
| ping_timeout | 미설정 | **10초** | 모의 서버 ping 응답 지연 대비. websockets.connect(ping_timeout=10) |
| 재연결 시 approval_key 갱신 | 있음 (기존) | **유지 + 실패 시 한 번 더 재시도** | 모의 approval_key 만료 이슈 대비 |
| REALTIME_CACHE_TTL | 5초 | **10초** | 재연결 소요 시간(최대 ~30초) 동안 데이터 유지. 단, 10초 초과 데이터는 stale 표시 권고 |

---

## 4. 리스크 및 대안

### 기술적 리스크
1. **모의 서버 자체 불안정**: 구독 수를 줄여도 10~30분 간격 끊김은 계속될 수 있음. 재연결 로직의 견고성이 핵심
2. **approval_key 레이스 컨디션**: 재연결 중 approval_key 갱신과 구독 요청이 교차하면 인증 실패 가능. 갱신 완료 후 구독 시작 보장 필요 (현재 코드는 순차적이므로 OK)

### 구현 팁
- `ConnectionClosed` 예외 로깅: `except ConnectionClosed as e: logger.warning("WS 끊김: code=%s reason=%s", e.code, e.reason)`
- websockets 라이브러리 버전 확인: v10+에서는 `ping_interval`과 `ping_timeout` 기본값이 다름
- 모의 환경에서 "1003" close code는 "서버 과부하"를 의미 — 구독 수 초과의 직접적 증거
