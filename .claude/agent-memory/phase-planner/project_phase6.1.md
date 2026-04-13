---
name: Phase 6.1 계획
description: 거래량 시간가중 보정 + 돌파 강도 연동 + 5분봉 수집 구축 — 2차 검토 확정 (MIN_VOLUME_FLOOR 0.5, 돌파 연동 임계값, 데이터 의존성 관리)
type: project
---

Phase 6.1: 거래량 시간가중 보정 + 5분봉 수집 구축 (2차 검토 확정)
- 날짜: 2026-04-13
- 전문가: 정프로(PO) + 최리스크(리스크관리) + 김단타(단타) + 박퀀트(퀀트) — 4명 1차+2차 검토 완료
- Sprint: 단일 Sprint (범위 확장: 전략 수정 + 5분봉 수집 파이프라인)

2차 검토 변경사항:
- volume_ratio 임계값: 2.0 고정 → **돌파 강도 연동** (5%+: 1.5, 3~5%: 1.8, <3%: 2.0)
- MIN_VOLUME_FLOOR: 0.3 → **0.5** (최리스크 필수 안전장치)
- 범위 확장: **5분봉 거래량 수집 파이프라인 선행 구축** (Phase 7 데이터 의존성 해소)

확정 파라미터:
- 선형 보정: adjusted_ratio = V(t) / (V_prev * progress)
- progress = elapsed_min / 390 (KRX 09:00~15:30)
- MIN_MARKET_PROGRESS = 0.15
- MIN_VOLUME_FLOOR = 0.5 (2차 상향)
- 돌파 강도 연동: breakout_pct >= 5.0 → 1.5, >= 3.0 → 1.8, else → 2.0
- 5분봉 집계: Redis vol5m:{code}:{date}:{slot}, TTL 30일, 78슬롯

**Why:** 1차 확정안(고정 2.0)에서는 062040(+7.6% 돌파, ratio=1.694)이 미달. 돌파 강도 연동으로 강한 돌파는 거래량 요건 완화.

**How to apply:** momentum_breakout.py 수정 + volume_aggregator.py 신규 + scheduler.py 연동. Sprint 1에 모두 포함.

후속 Phase 데이터 로드맵:
- Phase 7: 5분봉 가속도 (데이터: Phase 6.1에서 20거래일 축적)
- Phase 8: Z-score + VWAP (데이터: Phase 7에서 20거래일 축적)
- Phase 9: U자형 비선형 (데이터: 3~6개월 운영 축적)
