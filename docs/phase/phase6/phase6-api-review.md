# Phase 6 전문가 검토 — 윤에이피 (API 개발자)

> **검토일**: 2026-04-12
> **검토 대상**: Phase 6 스케줄러 + WS 복원력 강화 아키텍처 초안

---

## 1. 요약

| 분류 | 항목 수 |
|------|--------|
| ✅ 통과 | 7 |
| ⚠️ 주의 | 2 |
| ❌ 재검토 | 0 |

---

## 2. 항목별 검증 결과

### ✅ 통과

1. **`_reconnect()` `_receive_task` cancel+await**: `disconnect()` 메서드에서는 이미 cancel+await 패턴을 사용중(78~87줄). `_reconnect()`에서도 동일 패턴 적용이 일관성 있음. 구현: `_reconnect()` 진입 시 `if self._receive_task: self._receive_task.cancel(); await self._receive_task` (CancelledError 무시)
2. **가드 조건 `and` -> `or`**: 코드 확인 완료. `self._ws._ws`는 내부 WebSocket 프로토콜 객체, `self._ws.connected`는 논리적 연결 상태. 둘 중 하나라도 비정상이면 차단해야 하므로 `or`이 맞음. `subscribe()`(45줄)와 `unsubscribe()`(74줄) 모두 동일하게 수정
3. **WS `open_timeout=10`**: `websockets.connect()`의 `open_timeout` 파라미터. 현재 `connect()` 메서드(69줄)와 `_reconnect()` 메서드(191줄) 모두에 적용 필요. 현재 `ping_timeout=10`은 있으나 `open_timeout`은 미설정
4. **`subscribe()`에 `_ws is None` 가드 추가**: 현재 `kis_ws.py:98`에서 `await self._ws.send()`를 호출하는데, `_ws`가 None이면 AttributeError. `if self._ws is None: raise ConnectionError("WS 미연결")` 또는 조용히 return False
5. **KIS REST 재시도/백오프**: 현재 `_request()` 메서드(148줄)에는 Rate Limit 재시도만 있음. HTTP 500/502/503에 대한 재시도는 없음. `kis_daily_collector.py`의 개별 종목 호출 레벨에서 재시도 추가가 적절 (전체 `_request`에 넣으면 주문 API에도 영향)
6. **`_market_open_recovery()` 연결 상태 확인**: `self._ws_client.connected` 속성이 이미 존재(44~46줄). `ws_manager.count` 대신 이것을 사용하면 됨
7. **`_premarket_collect()` 예외 경로 KIS 폴백**: 564줄의 `except Exception` 블록에서 `_run_kis_daily_fallback()` 호출 추가. 단, 예외 원인이 DB 연결 실패 등이면 KIS 폴백도 실패할 수 있으므로 폴백 자체도 try/except로 감싸야 함

### ⚠️ 주의

1. **KIS REST 재시도 적용 범위**: 재시도를 `kis_daily_collector.py`(일봉 수집기)에만 넣을 것인지, `kis_rest.py`의 `_request()`에 넣을 것인지 결정 필요. **권고: `kis_daily_collector.py`에만 적용**. 이유: (1) 주문 API에 재시도를 넣으면 중복 주문 위험, (2) 일봉 수집은 멱등 작업이므로 재시도 안전
2. **recovery 재시도 시 WS 중복 연결 방지**: `_market_open()`은 `self._ws_client.connect()`를 호출. 이미 연결이 있는 상태에서 다시 `connect()`를 호출하면 기존 연결이 orphan됨. recovery에서는 `if not self._ws_client.connected: await self._market_open()` 패턴 사용 필요. 이미 연결은 있으나 구독이 0인 경우를 위해 `elif self._ws_manager.count == 0: await self._subscribe_candidates()` 분기 추가 권고

---

## 3. 파라미터 조정 권고

| 항목 | 원래값 | 권고값 | 근거 |
|------|--------|--------|------|
| KIS REST 재시도 횟수 (일봉 수집) | 0 | **3회** | 종목당 재시도. 실패 종목만 재시도하므로 전체 시간 영향 최소 |
| KIS REST 백오프 기저 (일봉 수집) | - | **2초** | 2-4-8초. KIS 서버 부하 회복 대기 |
| KIS REST 재시도 대상 | - | **HTTP 500, 502, 503, 429** | 4xx 중 429만 포함. 400/401/403은 재시도 무의미 |
| WS connect open_timeout | 미설정(무한) | **10초** | `connect()`와 `_reconnect()` 모두 적용 |
| WS subscribe _ws None 가드 | 없음 | **추가** | `_ws is None`이면 로그 경고 + return (예외 미발생) |
| recovery 재시도 간격 | - | **5분(09:05/09:10/09:15)** | 5분이면 WS 서버 회복 + approval_key 갱신에 충분 |

---

## 4. 리스크 및 대안

1. **`_reconnect()` 구독 복원 순서**: 현재 구독 복원 -> 수신 루프 시작 순서. 구독 복원 중 서버가 데이터를 보내기 시작하면 수신 루프가 없어 메시지 유실. **대안**: 수신 루프를 먼저 시작하고 구독 복원을 나중에 실행. 단, 이 변경은 기존 동작을 크게 바꾸므로 Sprint 2에서 검토 권고
2. **KIS 모의 서버 approval_key 만료**: Phase 5.2에서 재연결 시 `get_approval_key()`를 호출하여 갱신 중. recovery 재시도에서도 동일하게 적용되는지 확인 필요
3. **`is_trading_day()` 공휴일 데이터 갱신**: 현재 `KR_HOLIDAYS_2026` 하드코딩. 2027년 진입 시 업데이트 필요. 이번 Phase 범위는 아니나 주의

---

## 5. 최종 판단

**✅ 승인 — KIS REST 재시도는 `kis_daily_collector.py`에만 적용, `_request()`에는 넣지 않을 것**

구현 난이도 낮음. Sprint 1은 5개 파일 소규모 수정, Sprint 2는 3개 파일 로직 추가. 전체 2-Sprint 구조 적절.
