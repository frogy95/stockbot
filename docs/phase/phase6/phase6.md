# Phase 6: 스케줄러 + WS 복원력 강화 — 실행 계획

> **Status**: ✅ 완료 (2026-04-12, PR #108)
> **ROADMAP 참조**: `ROADMAP.md` Phase 6
> **검토 리포트**:
>
> - `phase6-po-review.md` (정프로, PO)
> - `phase6-risk-review.md` (최리스크, 리스크관리)
> - `phase6-api-review.md` (윤에이피, API 개발자)
> - `phase6-trader-review.md` (김단타, 단타 전문가)

---

## 개요

2026-04-10(금) 프로덕션 장애 분석 결과, 장전 수집 -> 스크리닝 -> WS 구독 전체 파이프라인이 실패한 근본 원인 9건을 수정한다. Phase 5.2 Sprint 1에서 WS 재연결 안정화를 수행했으나, 실 운영에서 추가 결함이 발견되었다.

### 문제 분류

```
Phase A: 치명적 버그 수정 (5개 파일, 즉시 수정)
├─ 1. _reconnect() ConcurrencyError (kis_ws.py)
│     _receive_task 미취소 후 새 task 생성 -> 수신 루프 2개 동시 실행
├─ 2. WS 가드 조건 and -> or (ws_manager.py)
│     미연결 상태에서 구독 시도 미차단
├─ 3. _market_open() bare exception (scheduler.py)
│     WS 연결 실패 시 알림 없이 조용히 실패
├─ 4. _market_open_recovery() 연결 상태 미확인 (scheduler.py)
│     ws_manager.count(구독 수)로 판단, 실제 연결 상태 미확인
└─ 5. _reconnect() 좀비 연결 (kis_ws.py) [Phase 5.2 미해결 #6]
      구독 복원 실패 시 _receive_task 미생성 -> 좀비 연결

Phase B: 복원력 강화 (3개 파일)
├─ 6. KIS REST 재시도/백오프 (kis_daily_collector.py)
│     500/502/503/429 에러에 재시도 없음
├─ 7. recovery 단계적 재시도 (scheduler.py)
│     09:05 1회 -> 09:05/09:10/09:15 단계적 재시도
└─ 8. _premarket_collect() 예외 경로 KIS 폴백 (scheduler.py)
      예외 발생 시에도 KIS 일봉 폴백 시도

Phase C: 불필요한 실행 방지 (2개 파일)
├─ 9. 주말/공휴일 is_trading_day() 가드 (scheduler.py)
│     모든 핸들러 시작부에 거래일 체크
└─ 10. WS connect open_timeout (kis_ws.py)
       websockets.connect()에 open_timeout=10 추가 + subscribe() _ws None 가드
```

> **범위 제한**: ROADMAP Phase 6의 전체 범위(모바일 반응형, 센티멘트, DART 등)는 Phase 6.1+ 또는 후속 Phase에서 다룬다. 이번 Phase 6는 "프로덕션 안정화"에 집중한다.

---

## 검토팀 확정 파라미터 (2026-04-12)

> 정프로(PO), 최리스크(리스크관리), 윤에이피(API), 김단타(단타) — 4명 검토 완료

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | `_reconnect()` `_receive_task` 처리 | 미취소 후 새 task 생성 | **cancel+await 후 새 task 생성** | 전원 합의. `disconnect()`의 기존 패턴과 일관. ConcurrencyError + 주문 중복 방지 |
| 2 | `ws_manager` 가드 조건 | `and` (subscribe, unsubscribe 모두) | **`or`** | 전원 합의. 둘 중 하나라도 비정상이면 차단 |
| 3 | `_market_open()` 예외 처리 | bare exception, 로그만 | **텔레그램 알림 + 명시적 상태 기록** | 전원 합의. 조용한 실패 -> 포지션 모니터링 불가 -> 손절 미작동(최리스크) |
| 4 | `_market_open_recovery()` 판단 기준 | `ws_manager.count` (구독 수) | **`self._ws_client.connected`** (연결 상태) | 전원 합의. 구독 수 != 연결 상태. 연결 끊김 + 구독 잔존 케이스 대응 |
| 5 | `_reconnect()` 구독 복원 실패 대응 | 수신 루프 미시작 (좀비) | **구독 복원 try/except + 수신 루프 항상 시작 + 텔레그램 경고** | 최리스크 강력 요구, 전원 동의. Phase 5.2 미해결 #6 해결 |
| 6 | KIS REST 재시도 최대 횟수 | 0 (없음) | **3회** | 전원 합의. `kis_daily_collector.py`에만 적용 (주문 API 제외, 윤에이피 권고) |
| 7 | KIS REST 백오프 기저 | - | **2초** (2-4-8초) | 정프로+윤에이피 합의. KIS 서버 부하 회복 대기 |
| 8 | KIS REST 재시도 대상 HTTP 코드 | - | **500, 502, 503, 429** | 최리스크+윤에이피 합의. 400/401/403은 재시도 무의미 |
| 9 | recovery 재시도 시점 | 09:05 1회 | **09:05/09:10/09:15 (5분 간격, 3회)** | 정프로 안 채택. 김단타 09:03 안은 초기 구독 복원 미완료 우려로 09:05 유지. 최리스크 동의 |
| 10 | recovery 3회 실패 시 | 없음 | **텔레그램 긴급 알림 + pipeline_healthy=false 유지** | 최리스크+김단타 합의. 장중 전체 실시간 파이프라인 마비 상태 |
| 11 | WS connect open_timeout | 미설정 (무한) | **10초** | 전원 합의. `connect()`와 `_reconnect()` 모두 적용 |
| 12 | WS `subscribe()` `_ws None` 가드 | 없음 | **`_ws is None`이면 로그 경고 + 조용히 return** | 윤에이피 권고. AttributeError 방지 |
| 13 | `_premarket_collect()` 예외 시 KIS 폴백 | 미트리거 | **예외 경로에서도 KIS 폴백 시도 (try/except 감싸기)** | 전원 합의. 데이터 부재 -> 1차 스크리닝 불가 -> 장중 매매 불가 방지 |
| 14 | `is_trading_day()` 가드 | 없음 | **Sprint 1: `_run_scheduled_pipeline`, `_market_open`에 추가. Sprint 2: 나머지 핸들러** | 최리스크 요구 + 정프로 동의. 주말 WS 연결 시도 -> 불필요 에러 + approval_key 소진 방지 |
| 15 | recovery 재시도 시 WS 중복 연결 방지 | 없음 | **`if not self._ws_client.connected` 가드 후 `_market_open()` 호출** | 윤에이피 권고. 기존 연결 orphan 방지 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 ✅ | 치명적 버그 수정 + 최소 방어 | Phase A 5건 + is_trading_day() 핵심 가드 + WS open_timeout + subscribe _ws 가드 | 없음 |
| 2 ✅ | 복원력 강화 + 불필요 실행 방지 | Phase B 3건 + Phase C 나머지 (전체 핸들러 is_trading_day) | Sprint 1 |

---

## Sprint 1 상세 — 치명적 버그 수정 + 최소 방어 ✅ 완료

> PR #108 (2026-04-12). pytest 771 passed, 0 failed.

### 백엔드

| 파일 | 변경 내용 |
|------|----------|
| `backend/core/clients/kis_ws.py` | (1) `_reconnect()` 진입 시 기존 `_receive_task` cancel+await. (2) 구독 복원을 try/except로 감싸고, 실패해도 `_receive_task` 생성 + 텔레그램 경고(Phase 5.2 미해결 #6). (3) `connect()`에 `open_timeout=10` 추가. (4) `subscribe()`에 `_ws is None` 가드 추가 |
| `backend/modules/collector/ws_manager.py` | `subscribe()`(45줄)와 `unsubscribe()`(74줄)의 가드 조건 `and` -> `or` 수정 |
| `backend/modules/collector/scheduler.py` | (1) `_market_open()` bare exception에 텔레그램 알림 + pipeline 상태 기록. (2) `_market_open_recovery()` 판단 기준을 `ws_manager.count` -> `self._ws_client.connected`로 변경. (3) `_run_scheduled_pipeline()`과 `_market_open()`에 `is_trading_day()` 가드 추가 |

### 프론트엔드

없음 (백엔드 전용 수정)

### 재사용 자산

| 기존 자산 | 재사용 방식 |
|----------|------------|
| `KISWebSocketClient.disconnect()` cancel+await 패턴 | `_reconnect()`에 동일 패턴 적용 |
| `KISWebSocketClient.connected` 속성 | `_market_open_recovery()`에서 직접 참조 |
| `CollectorScheduler._send_failure_alert()` | `_market_open()` 실패 알림에 재사용 |
| `is_trading_day()` (trading_calendar.py) | 스케줄러 핸들러 가드에 재사용 |

### 테스트

| 테스트 | 검증 대상 |
|--------|----------|
| `test_reconnect_cancels_existing_receive_task` | `_reconnect()` 진입 시 기존 task cancel 확인 |
| `test_reconnect_starts_receive_loop_on_subscription_failure` | 구독 복원 실패해도 수신 루프 시작 확인 |
| `test_ws_manager_guard_or_condition` | `_ws is None or not connected` 조건에서 subscribe 차단 확인 |
| `test_market_open_failure_sends_telegram` | `_market_open()` 예외 시 텔레그램 알림 발송 확인 |
| `test_market_open_recovery_checks_connected` | `connected=False` + `count>0` 일 때 recovery 실행 확인 |
| `test_scheduled_pipeline_skips_non_trading_day` | 주말/공휴일에 파이프라인 스킵 확인 |
| `test_ws_connect_open_timeout` | `websockets.connect()` 호출 시 `open_timeout=10` 전달 확인 |
| `test_ws_subscribe_none_guard` | `_ws=None` 상태에서 `subscribe()` 호출 시 예외 미발생 확인 |

---

## Sprint 2 상세 — 복원력 강화 + 불필요 실행 방지 ✅ 완료

> PR #108 (2026-04-12). Sprint 1과 동일 브랜치 연속 구현. pytest 771 passed, 0 failed.

### 백엔드

| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/sources/kis_daily_collector.py` | 종목별 KIS REST 호출에 지수 백오프 재시도 추가: 최대 3회, 기저 2초, 대상 HTTP 500/502/503/429 |
| `backend/modules/collector/scheduler.py` | (1) `_market_open_recovery()`를 단계적 재시도로 확장: 09:05/09:10/09:15. 각 시점에서 `_ws_client.connected` 먼저 확인. 3회 실패 시 텔레그램 긴급 알림. (2) `_premarket_collect()` 예외 경로에서 `_run_kis_daily_fallback()` 시도 (try/except 감싸기). (3) 나머지 핸들러(`_market_close`, `_premarket_retry`, `_market_open_recovery`)에 `is_trading_day()` 가드 추가 |

### 프론트엔드

없음 (백엔드 전용 수정)

### 재사용 자산

| 기존 자산 | 재사용 방식 |
|----------|------------|
| `CollectorScheduler._run_kis_daily_fallback()` | `_premarket_collect()` 예외 경로에서 호출 |
| `CollectorScheduler._send_failure_alert()` | recovery 최종 실패 알림에 재사용 |
| `is_trading_day()` (trading_calendar.py) | 나머지 핸들러 가드에 재사용 |
| `KISRestClient._request()` Rate Limit 재시도 패턴 | 일봉 수집기 재시도 로직 참고 |

### 테스트

| 테스트 | 검증 대상 |
|--------|----------|
| `test_kis_daily_collector_retries_on_500` | HTTP 500 시 3회 재시도 후 성공 확인 |
| `test_kis_daily_collector_retries_on_429` | HTTP 429 시 재시도 + 백오프 확인 |
| `test_kis_daily_collector_no_retry_on_400` | HTTP 400 시 즉시 실패 (재시도 안 함) 확인 |
| `test_recovery_three_stage_retry` | 09:05/09:10/09:15 단계적 재시도 확인 |
| `test_recovery_skips_if_connected` | 이미 연결된 상태에서 recovery 스킵 확인 |
| `test_recovery_final_failure_alert` | 3회 실패 시 텔레그램 긴급 알림 확인 |
| `test_premarket_exception_triggers_kis_fallback` | 예외 경로에서 KIS 폴백 실행 확인 |
| `test_market_close_skips_non_trading_day` | 비거래일 market_close 스킵 확인 |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 대응 |
|---|------|--------|------|
| 1 | WS 완전 실패 시 REST 폴백 가격 감시 (Phase 5.2 미해결 #2) | ❌ 높음 | Phase 6.1 이관. 보유 포지션 + WS 미연결 = 손절 불가. 이번 Phase에서는 긴급 알림으로 수동 개입 유도 |
| 2 | `_reconnect()` 구독 복원 순서 개선 (수신 루프 먼저 시작) | ⚠️ 중간 | Phase 6.1 이관. 현재 구독 복원 -> 수신 루프 순서를 유지하되, 복원 실패 시에도 수신 루프 시작(Sprint 1에서 해결)으로 부분 대응 |
| 3 | `is_trading_day()` 2027년 공휴일 데이터 | ⚠️ 낮음 | 2026년 말까지 업데이트. 이번 Phase 범위 밖 |
| 4 | ROADMAP Phase 6 나머지 범위 (모바일, 센티멘트, DART) | 📋 정보 | Phase 6.1+ 또는 후속 Phase에서 별도 계획 |
| 5 | recovery 재시도 중 기존 포지션 보호 | ⚠️ 중간 | REST 기반 가격 감시는 Phase 6.1 이관. 이번 Phase에서는 "보유 포지션 + WS 미연결" 경고 알림만 추가 |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| `_reconnect()` ConcurrencyError 해소 | 재연결 시 `_receive_task` 1개만 존재 확인 | ⬜ |
| `_reconnect()` 좀비 연결 해소 | 구독 복원 실패해도 수신 루프 시작 확인 | ⬜ |
| WS 가드 조건 `or` 적용 | subscribe/unsubscribe 모두 `or` 조건 확인 | ⬜ |
| `_market_open()` 실패 시 텔레그램 알림 | 예외 발생 시 알림 수신 확인 | ⬜ |
| `_market_open_recovery()` 연결 상태 기반 판단 | `connected=False` 시 recovery 실행 확인 | ⬜ |
| `is_trading_day()` 가드 적용 | 주말에 스케줄러 핸들러 스킵 확인 | ⬜ |
| WS connect open_timeout 적용 | `open_timeout=10` 전달 확인 | ⬜ |
| KIS REST 재시도/백오프 동작 | HTTP 500 시 3회 재시도 + 백오프 확인 | ⬜ |
| recovery 단계적 재시도 동작 | 09:05/09:10/09:15 3회 재시도 확인 | ⬜ |
| `_premarket_collect()` 예외 시 KIS 폴백 | 예외 경로에서 폴백 실행 확인 | ⬜ |
| 테스트 전체 통과 | pytest 회귀 테스트 Green | ⬜ |
