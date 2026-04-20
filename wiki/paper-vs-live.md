# 모의거래 vs 실전거래

`TRADING_ENV` 환경변수 하나로 모의(paper)/실전(live) 전환.

## 환경별 차이

| 항목 | 모의 (paper) | 실전 (live) |
|------|-------------|------------|
| `TRADING_ENV` | `paper` | `live` |
| REST 도메인 | `openapivts.koreainvestment.com` | `openapi.koreainvestment.com` |
| App Key/Secret | `KIS_MOCK_APP_KEY/SECRET` | `KIS_APP_KEY/SECRET` |
| 계좌번호 | `KIS_MOCK_ACCOUNT_NO` | `KIS_ACCOUNT_NO` |
| tr_id 접두사 | `V` (예: `VTTC0802U`) | `T` (예: `TTTC0802U`) |
| WebSocket URL | `ws://ops.koreainvestment.com:31000` (경로 없음) | `ws://ops.koreainvestment.com:21000/tryitout` |
| Rate Limit | 초당 1건 (스로틀링 내장) | 초당 ~20건 |
| 실제 자금 | 아니오 | 예 |

## 전환 방법

```bash
# .env 파일
TRADING_ENV=paper   # 모의거래
TRADING_ENV=live    # 실전거래
```

설정 변경 후 백엔드 재시작 필요.

## 대시보드 표시

실전/모의 여부가 대시보드에 명확히 표시:
- 실전: **빨간 배지** ("LIVE")
- 모의: **초록 배지** ("PAPER")

실수로 실전 모드 진입 방지.

## 모의거래 제약

- Rate Limit 초당 1건 → 연속 주문 시 자동 대기
- 모의거래 체결가가 실전과 다를 수 있음 (참고용)
- 일부 API 기능 모의 미지원 (KIS 정책)

## 실전 전환 게이트

Phase 7.0 Sprint 3에서 E2E 검증 + LIVE 전환 체크리스트:
1. 모의에서 N일 이상 수익성 검증
2. 리스크 파라미터 최종 확인
3. 최소 투자금으로 첫 실전 시작
4. 비상 정지 동작 테스트

> **선행 의존성**: Phase 7.0 Sprint 3 실행 전 **Phase 8 Sprint 1 (OHLC 파싱 버그 수정)** 이 완료되어야 유효한 신호 기반 검증이 가능하다.

[[risk-management]] 참조.

## KIS WebSocket LIVE 주의사항

LIVE WebSocket 연결 시 `/tryitout` 경로가 필수 (Phase 7.0 Sprint 1에서 발견된 버그 수정). PAPER는 다른 서버(포트 31000)이므로 경로 불필요 — 자세한 확정 사실은 `.claude/rules/backend.md` 참조.

```
# LIVE (포트 21000)
ws://ops.koreainvestment.com:21000/tryitout  ← 올바름
ws://ops.koreainvestment.com:21000           ← 잘못됨 (HTTP 101 후 즉시 연결 종료)

# PAPER (포트 31000, 경로 없음)
ws://ops.koreainvestment.com:31000           ← 올바름
```

[[websocket-management]], [[kis-api]] 참조.
