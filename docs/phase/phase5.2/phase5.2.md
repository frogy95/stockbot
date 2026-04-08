# Phase 5.2: KIS WebSocket 모의 환경 안정화 — 실행 계획

> **Status**: 계획 수립 완료 (2026-04-08)
> **ROADMAP 참조**: `ROADMAP.md` Phase 5.2
> **검토 리포트**:
>
> - `phase5.2-po-review.md` (정프로, PO)
> - `phase5.2-risk-review.md` (최리스크, 리스크관리)
> - `phase5.2-api-review.md` (윤에이피, API 개발자)
> - `phase5.2-trader-review.md` (김단타, 단타 전문가)

---

## 개요

프로덕션(Railway, TRADING_ENV=paper)에서 KIS WebSocket이 **지속적으로 재연결을 반복**하며 장중 실시간 파이프라인(2차 스크리닝 + 매매 신호)이 마비되는 문제를 수정한다.

### 문제 분석

```
[2026-04-08 프로덕션 로그 분석]

1. 1차 스크리닝 통과: ~30종목 -> WS 구독 시도
2. WSSubscriptionManager.max=35 -> 30종목 x 2 tr_id = 60 WS 구독
3. KIS 모의 WS(port 31000) 비공식 한도: ~40건 (tr_id 단위 카운트)
4. 60건 > 40건 -> 서버 측 연결 해제 (close code 1003 "서버 과부하" 추정)
5. _reconnect() -> 60건 한번에 재구독 시도 -> 즉시 재해제 -> 무한 루프
6. Redis 실시간 캐시 TTL=5초 -> 데이터 만료 -> 2차 스크리닝 무효화
7. 10:14 이후 2차 스크리닝 실질 중단
```

### 근본 원인

1. **구독 수 초과**: `WSSubscriptionManager`는 종목 단위(max=35)로 관리하지만, KIS WS 서버는 tr_id 단위로 카운트. 35종목 x 2 tr_id = 70건은 모의 한도(~40건)의 175%
2. **환경별 제한 부재**: paper/live 동일한 max_subscriptions=35 적용
3. **재연결 폭주**: 전체 구독을 딜레이 없이 동시 복원 -> 서버 재과부하
4. **원인 미로깅**: ConnectionClosed에서 close code/reason 미출력

### 해결 아키텍처

```
[Sprint 1: WS 구독 제한 + 재연결 안정화]

1. 환경별 구독 제한
   KISEnvironment.max_ws_subscriptions 필드 추가
   ├─ PAPER: 20종목 (20 x 2 = 40 WS 구독, 한도 내)
   └─ LIVE: 35종목 (70 WS 구독, 실전 한도 충분)

2. 재연결 로직 안정화
   ├─ 구독 복원 딜레이: 0.5초/종목 (= 0.25초/tr_id)
   ├─ 백오프 기저: 1초 → 2초, 최대 시도: 5 → 7
   ├─ ping_timeout=10초 추가
   ├─ ConnectionClosed close code/reason 로깅
   └─ 재연결 실패(7회) 시 텔레그램 긴급 알림

3. 2차 스크리닝 WS 연동
   ├─ WS 미연결 시 스킵 + 경고 로그
   └─ 연속 3회 스킵 시 텔레그램 경고

4. 데이터 안정화
   ├─ REALTIME_CACHE_TTL: 5초 → 10초
   └─ 재연결 후 체결강도 5초 웜업 구간

5. 테스트
   ├─ 환경별 구독 제한 테스트
   ├─ 재연결 딜레이/실패 테스트
   └─ 2차 스크리닝 WS 미연결 스킵 테스트
```

---

## 검토팀 확정 파라미터 (2026-04-08)

> 정프로(PO), 최리스크(리스크관리), 윤에이피(API), 김단타(단타) — 4명 검토 완료

| # | 항목 | 원래 설계 | 확정값 | 근거 |
|---|------|----------|--------|------|
| 1 | paper max_ws_subscriptions | 35 (환경 구분 없음) | **20** | 전원 합의. 20종목 x 2 = 40 WS 구독. 모의 한도(~40) 내. 윤에이피: 18(90%)이 이상적이나 20 수용 |
| 2 | live max_ws_subscriptions | 35 | **35 유지** | 전원 합의. 실전 한도 충분. 실전 테스트 후 조정 가능 |
| 3 | 재연결 구독 복원 딜레이 | 0 (즉시) | **0.5초/종목** | 윤에이피: 0.25초/tr_id = 0.5초/종목. 모의 서버 처리 속도 감안. 실전은 0.2초/종목 |
| 4 | 재연결 최대 시도 (MAX_RECONNECT_ATTEMPTS) | 5 | **7** | 최리스크: 5회=31초, 7회=254초(~4분). 모의 서버 회복 대기 충분 |
| 5 | 재연결 백오프 기저 (BACKOFF_BASE) | 1초 | **2초** | 최리스크: 모의 서버 부하 회복 시간 감안. 2초 시작이 안전 |
| 6 | ping_timeout | 미설정 (라이브러리 기본) | **10초** | 윤에이피: 모의 서버 ping 응답 지연 대비. websockets.connect(ping_timeout=10) |
| 7 | REALTIME_CACHE_TTL | 5초 | **10초** | 전원 합의. 재연결 중 데이터 유지. 30초 스크리닝 주기 대비 적절 |
| 8 | 재연결 실패 시 텔레그램 알림 | 없음 | **필수** | 최리스크: 7회 실패 시 긴급 알림. 장애 인지 지연 방지 |
| 9 | 2차 스크리닝 WS 미연결 대응 | 실행 시도 (데이터 없어 무의미) | **스킵 + 연속 3회 시 텔레그램 경고** | 정프로+최리스크: 무음 스킵은 장애 인지 지연 |
| 10 | 재연결 후 체결강도 웜업 | 없음 | **5초 무시 구간** | 김단타: 재연결 직후 데이터 갭으로 비정상 체결강도 방지 |
| 11 | 실전 환경 구독 복원 딜레이 | - | **0.2초/종목** | 윤에이피: 실전 서버도 한번에 수십 건 보내면 일부 누락 |

---

## Sprint 분할 계획

| Sprint | 주제 | 주요 작업 | 의존성 |
|--------|------|----------|--------|
| 1 | WS 구독 제한 + 재연결 안정화 | 환경별 구독 제한, 재연결 로직 개선, 2차 스크리닝 연동, 캐시 TTL 조정, 테스트 | 없음 |

---

## Sprint 1 상세 — WS 구독 제한 + 재연결 안정화

### 백엔드

| 파일 | 변경 내용 |
|------|----------|
| `backend/core/clients/kis_config.py` | KISEnvironment에 `max_ws_subscriptions` 필드 추가. PAPER=20, LIVE=35 |
| `backend/core/clients/kis_ws.py` | MAX_RECONNECT_ATTEMPTS=7, BACKOFF_BASE=2. _reconnect() 구독 복원 딜레이 추가(환경별). ConnectionClosed close code/reason 로깅. ping_timeout=10 추가. 재연결 실패 시 콜백(on_ws_failure) 호출 |
| `backend/modules/collector/ws_manager.py` | 생성자에서 환경 기반 max_subscriptions 주입. 환경별 구독 복원 딜레이 파라미터 |
| `backend/modules/collector/scheduler.py` | REALTIME_CACHE_TTL=10. _secondary_screen()에 WS 연결 상태 확인 추가. 연속 스킵 카운터 + 텔레그램 경고. WS 재연결 실패 시 텔레그램 긴급 알림 콜백 등록 |
| `backend/modules/collector/trade_strength.py` | 재연결 후 웜업 지원: reset_stock() 또는 warmup_period 파라미터 |

### 프론트엔드

없음 (백엔드 전용 수정)

### 재사용 자산

| 기존 자산 | 재사용 방식 |
|----------|------------|
| `WSSubscriptionManager` 우선순위 로직 | 그대로 유지. max값만 환경에서 주입 |
| `KISWebSocketClient._reconnect()` | 기존 구조 유지, 딜레이/파라미터 추가 |
| `CollectorScheduler._send_failure_alert()` | WS 재연결 실패 알림에 재사용 |
| `TradeStrengthCalculator` | 기존 구조에 reset/warmup 메서드 추가 |

---

## 미해결 사항 / 리스크

| # | 항목 | 심각도 | 대응 |
|---|------|--------|------|
| 1 | 모의 서버 자체 불안정 (10~30분 간격 끊김) | ⚠️ 중간 | 재연결 로직으로 대응. 근본 해결은 실전 전환 |
| 2 | WS 완전 실패 시 기존 포지션 모니터링 불가 | ❌ 높음 | Phase 6 이관: REST 폴백 가격 감시 메커니즘 |
| 3 | 20종목 제한으로 장중 급등 종목 누락 | ⚠️ 중간 | 모의 환경에서 수용. 실전 전환 시 35종목 자동 복원 |
| 4 | 장중 동적 우선순위 조정 (2차 스코어 기반) | 📋 개선 | Phase 6 이관 |
| 5 | approval_key 모의 환경 만료 이슈 | ⚠️ 중간 | 재연결 시 갱신(기존 로직) + 실패 시 1회 재시도 추가 |

---

## 완료 기준 (Phase 전체)

| 항목 | 기준 | 상태 |
|------|------|------|
| 모의 환경 WS 재연결 반복 해소 | 장중(09:00~15:30) 연속 1시간 안정 연결 유지 | ⬜ |
| 2차 스크리닝 30초 주기 정상 실행 | 10회 연속 실행 확인 (5분간) | ⬜ |
| 환경별 구독 제한 동작 | paper=20, live=35 자동 적용 | ⬜ |
| WS 재연결 실패 시 텔레그램 알림 | 7회 실패 시 알림 발송 확인 | ⬜ |
| REALTIME_CACHE_TTL 10초 적용 | Redis TTL 확인 | ⬜ |
| 재연결 후 체결강도 웜업 | 5초 무시 구간 동작 확인 | ⬜ |
| 테스트 전체 통과 | pytest 회귀 테스트 Green | ⬜ |
