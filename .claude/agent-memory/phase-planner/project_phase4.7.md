---
name: Phase 4.7 계획
description: 1차 스크리닝 스코어링 구조 수정 — 실시간 팩터 제외 + 3팩터 분리 + 임계값 조정
type: project
---

Phase 4.7 계획 수립 완료 (2026-04-02).

**Why:** 1차 스크리닝에서 실시간 데이터 없는 팩터(체결강도/호가잔량)에 고정값을 넣었더니 동률 처리로 percentile ~2% 고정, 이론적 최대 60.91 < 임계값 80.0으로 절대 통과 불가 버그.

**How to apply:**
- 전문가 4명 검토 (PO, 리스크, 퀀트, 단타): 전원 A안(3팩터 분리) 합의, B안(고정 percentile=50) 기각
- 확정 파라미터 11건: PRIMARY_STOCK_FACTORS 3개, 1차 가중치 1/3, 1차 임계값 60.0, 2차 임계값 75.0
- 단일 Sprint: scorer.py 팩터 분리 + screener.py 3팩터 빌드 + 테스트 전면 수정
- Phase 4.6 미해결 #14 ("primary_screen 0건 성공 반환") 해결
