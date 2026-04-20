---
name: Phase 7.2 계획
description: 매매 전략 진입 조건 개선 — OHLC 미파싱 수정 + 다층 진입 조건 (prev_close+prev_high)
type: project
---

Phase 7.2 계획 수립 완료 (2026-04-17). 전문가 4명 검토 (PO, 리스크, 단타, 퀀트).

**Why:** LIVE 모니터링에서 매매 신호 0건 발생. 2가지 근본 원인: (1) H0STCNT0 WS에서 시가/고가/저가 미파싱 → snapshot OHLC 오류, (2) prev_high 단일 진입 조건 과도 보수.

**How to apply:**
- Sprint 1: OHLC 파싱 수정 (kis_realtime.py idx 7/8/9 추가) + 갭 분기 버그 수정 (high→open_price)
- Sprint 2: 다층 진입 (prev_close 1단계 + prev_high 2단계) + 리스크 안전장치
- Sprint 1→2 간 최소 2거래일 관찰 필수
- Phase 7.0 Sprint 3(E2E 검증)의 선행 조건

핵심 파라미터 확정 14건:
- prev_close 돌파: confidence 상한 0.75, momentum min(pct/7.0,1.0)*0.7, volume_threshold 고정 2.5, position_size 50%
- 일일 최대 거래 10건, 13:00 이후 prev_close 돌파 비활성화
- 갭 3%+ breakout_ref = open_price
- 당일 고가 갱신 진입은 미도입 (후속 Phase)

주요 발견: KIS H0STCNT0 WS 스펙에 STCK_OPRC(idx 7), STCK_HGPR(idx 8), STCK_LWPR(idx 9) 포함 확인됨 — 파싱만 추가하면 즉시 사용 가능
