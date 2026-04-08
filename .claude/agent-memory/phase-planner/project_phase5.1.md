---
name: Phase 5.1 계획
description: 1차 스크리닝 change_rate 필터 수정 — change_rate_min 1.0->-2.0, 적응형 포함, 하락 종목 안전장치
type: project
---

Phase 5.1: 1차 스크리닝 change_rate 필터 수정 (2026-04-08 계획)

**Why:** Phase 5에서 volume_ratio를 완화했지만 change_rate_min=1.0이 전체 종목의 ~70-75%를 즉시 탈락시켜 1차 스크리닝 0건 재발. 적응형 필터가 volume_ratio만 완화하고 change_rate는 고정이었음.

**How to apply:**
- Sprint 1 (단일): filters.py change_rate_min=-2.0, screener.py 적응형 change_rate 추가 [-2.0, -3.0], 하락 종목 auto_trade_blocked + position_size_ratio 0.5
- 전문가 4명 검토: PO/리스크/퀀트/단타
- 확정 파라미터 9건: change_rate_min=-2.0, max=7.0 유지, 적응형 [-2.0, -3.0], 하한 -5.0, 하락 종목 자동매매 금지
- 절대값 필터(|change_rate| >= 0.3) → Phase 6 이관
- 주의: change_rate 임계값은 시장 상황에 따라 변동. 10거래일 모니터링 필요
