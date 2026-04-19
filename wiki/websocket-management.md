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
- 최대 동시 구독 수: KIS API 제한에 따름

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
