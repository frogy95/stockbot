# WebSocket 관리

KIS WebSocket을 통해 장중 실시간 체결 스트림을 수신한다. `collector/ws_manager.py` 참조.

## 역할

- 한국투자증권 WebSocket에 연결하여 실시간 체결 데이터 수신
- 체결 틱 → 체결강도 계산 (`trade_strength.py`)
- 수신 데이터 → [[redis-usage|Redis]] 저장 → [[screening-pipeline|2차 스크리닝]] 에 제공

## 핵심 설정

**중요**: LIVE와 PAPER의 WS 엔드포인트가 다르다. LIVE는 `/tryitout` 경로 필수, PAPER는 경로 없음. 상세 근거는 `.claude/rules/backend.md` §"KIS WebSocket 연결 — 확정 사실" 섹션 참조.

| 환경 | WebSocket URL |
|------|--------------|
| 모의 (PAPER) | `ws://ops.koreainvestment.com:31000` |
| 실전 (LIVE)  | `ws://ops.koreainvestment.com:21000/tryitout` |

LIVE에서 경로 누락 시 서버가 HTTP 101 응답 후 즉시 연결을 종료한다. PAPER는 다른 서버(포트 31000)이므로 경로가 필요 없다. [[kis-api]], [[paper-vs-live]] 참조.

## 연결 생명주기

```
장 시작 (09:00)
  → WebSocket 연결 수립
  → 1차 스크리닝 통과 종목 구독 (H0STCNT0)
  → 실시간 체결 수신 루프

장중
  → 체결 틱마다: 체결강도 갱신 → Redis 업데이트
  → 하트비트 유지
  → 연결 끊김 감지 시: 자동 재연결

장 마감 (15:30)
  → 구독 해제
  → WebSocket 연결 종료
```

## 종목 구독 관리

- 장 시작 시 1차 스크리닝 후보 종목 일괄 구독
- 장중 스크리닝 결과에 따라 구독 종목 동적 추가/제거

### 구독 한도 — 확정 사실 (2026-05-15 검증)

| 항목 | 값 | 출처 |
|------|-----|------|
| KIS WS 한 연결당 구독 상한 | **40건 (메시지 단위)** | `backend/core/clients/kis_config.py:45` 주석 |
| 종목당 사용 TR_ID | **2개** (`H0STCNT0` 체결가 + `H0STASP0` 호가) | `backend/modules/collector/ws_manager.py:15` `DEFAULT_TR_IDS` |
| **종목 단위 한도** | **20종목** (= 40 / 2) | `kis_config.py:45,58` `max_ws_subscriptions=20` (PAPER/LIVE 동일) |

- `ws_manager.py:41`의 라이브러리 디폴트값 `max_subscriptions=35`는 미사용. 실제 운영값은 `env.max_ws_subscriptions=20`이 `main.py:91`에서 명시 주입된다.
- 한도 초과 동작:
  - 신규 종목 우선순위 > 최소 우선순위 → **rotate** (최저 우선순위 종목 evict 후 신규 구독, `path=rotate`)
  - 그 외 → reject (`path=over_limit_low_priority`)

### 구조 위험 — Phase 8.6 진단 결과 (2026-05-15 09:06 KST)

WS trace 인프라(`WS_TRACE_ENABLED=true`)로 09:00 정각 수신을 확인한 결과 다음 구조 위험이 식별되었다:

- **1차 풀 정원(20) = WS 종목 한도(20)** — 마진 0
- 풀 갱신 시 신규 종목 1건이라도 진입하면 **반드시 1종목 evict** 필요
- 풀 갱신이 잦거나 KIS ACK 지연이 있으면 구독↔해제 진동 → **체결 메시지 누락** 가능
- 체결 누락 → 체결강도/거래량 계산 결손 → 2차 스크리닝 입력 결손 → **신호 생성 0건의 직접 원인 후보** (Phase 8.6 진단 후보 A의 정정된 형태)

다음 단계:
- 2026-05-15 17:08 KST aggregate에서 `path=rotate` / `path=over_limit_low_priority` / subscribe→result 지연 분포 / 종목 토글 빈도 확인 → root cause 확정
- Sprint 6 후속 조치 후보: 1차 풀 정원 축소(16~18)로 마진 확보, 또는 풀 갱신 주기 완화

> 진단 상세: `docs/phase/phase8.6/sprint5/sprint5-closing-report.md`, root cause 후보 #6.

## 체결강도 계산

```python
# trade_strength.py
체결강도 = 매수체결량 / (매수체결량 + 매도체결량) * 100
```

- 50 초과: 매수 우세
- 50 미만: 매도 우세
- [[screening-factors|스크리닝 팩터]]의 `trade_strength_factor`로 활용

## 오류 복구

- `websockets` 라이브러리의 내장 재연결 + 수동 재시도 로직
- 최대 재연결 시도 후 알림 발송 — [[telegram-integration]]
- Phase 7.0 Sprint 1에서 LIVE WebSocket URL 경로 문제 수정 완료
