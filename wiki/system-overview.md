# 시스템 개요

StockBot은 한국 주식/ETF 단타 자동 매매 시스템이다. KOSPI/KOSDAQ 전 종목을 대상으로 [[screening-pipeline|자동 스크리닝]]하고, [[signal-generation|매매 신호]]를 생성하며, [[order-execution|주문을 실행]]한다.

## 핵심 목표

- 전체 시장(약 2,880종목)에서 매일 자동으로 거래 후보 종목 탐색
- 반자동(승인 필요) 또는 완전자동으로 주문 실행 — [[trading-modes]] 참조
- 웹 대시보드 + 텔레그램으로 모니터링/제어 — [[telegram-integration]] 참조

## 주요 구성 요소

```
Cloudflare (DNS/CDN)
  ├── Vercel: Next.js 대시보드 (stockbot.choiji.kr)
  └── Railway: FastAPI 백엔드 (api.stockbot.choiji.kr)
       ├── PostgreSQL 16
       └── Redis 7
```

[[deployment]] 참조.

## 데이터 흐름 요약

1. **장전 (08:00)**: 공공데이터포털에서 전 종목 일괄 수집 → DB → 1차 스크리닝
2. **장중 (09:00~15:30)**: 한투 REST/WS로 후보 종목 실시간 시세 → 2차 스크리닝 → 매매 신호
3. **장후 (15:30~)**: 체결/잔고 정산 → 일일 리포트 → 텔레그램 발송

상세 흐름: [[data-collection-flow]]

## 모듈 구조

백엔드는 5개 모듈로 구성된다: [[module-structure]] 참조.

| 모듈 | 책임 |
|------|------|
| `collector` | 외부 API에서 데이터 수집/저장 |
| `screening` | 종목 스크리닝 및 스코어링 |
| `trading` | 신호 생성, 주문 실행, 포지션 관리 |
| `analyzer` | 성과 분석 및 기록 |
| `notifier` | 텔레그램 알림 및 승인 처리 |

## 환경 전환

`TRADING_ENV=paper|live` 플래그 하나로 모의/실전 전환. [[paper-vs-live]] 참조.

## 신호 생성 구조 (Phase 8.6)

Phase 8.6 Sprint 2(2026-04-29, v2.8.0 prod)부터 신호 생성은 직렬 AND → 병렬 OR 다중 진입 경로로 재설계되었다. 3개 tier(`gap_open`/`prev_high`/`prev_close`)가 독립 sub-게이트로 평가되며 하나라도 통과하면 신호 발행. ATR 임계는 08:35 KOSPI200 분위수 잡으로 매일 동적 캘리브레이션. 상세: [[tier-architecture]].

LIVE 자금 보호 가드레일(G1~G3 + Phase 7.0 코드 잠금)은 Phase 8.6 Sprint 1로 도입되어 분기 D 같은 사고 시 자동 롤백 R1~R4 + 회로차단기로 차단된다. 상세: [[risk-management]].
