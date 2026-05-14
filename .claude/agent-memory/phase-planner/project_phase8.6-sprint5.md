---
name: project_phase8.6-sprint5
description: Phase 8.6 Sprint 5 신설 (2026-05-14) — 진단·측정 Sprint, 14개 결함 처리, Phase 8.7 entry gate 재정의
metadata:
  type: project
---

Phase 8.6 Sprint 5 계획 수립 완료 (2026-05-14, 사용자 승인 대기). Sprint 1~4 완료 후 2026-05-13~14 모니터링에서 14개 결함 발견 → Sprint 5(진단+측정) + Sprint 6(placeholder) 신설.

**Why**: 2026-05-14 모니터링에서 신호 2건 발생했으나 출처 신뢰도 미입증 (KIS WS execution 35% 누락, fallback 456건, breakout 72.2% 편중). 사용자가 "5거래일 일평균 ≥1 entry gate는 무의미하다"고 거부 → 표면 카운트 게이트 폐기, 품질/신뢰도 게이트로 전환 결정.

**How to apply**: Phase 8.7 진입 또는 LIVE 토글 검토 시 §11.5 10개 지표 (WS 누락률 ≤5% / fallback 비중 ≤20% / 단일 stage ≤50% / 4h 교체율 ≤30% / Paper PnL 양(+) / 손절 ≥1 / R1~R4 plan-code 일치 / R3 자가치유 전수 회귀 / G-Bt1 / G-Bt2) 모두 통과를 기준으로 사용. 표면 카운트(일평균 신호)는 모니터링 카드로만.

핵심 결정:
- Sprint 1~4 본문 unchanged (사용자 명시), §10 DoD #9~#11 deprecated 표시만 (삭제 X).
- Sprint 5 = 진단·측정 Sprint, 임계 변경 0건, dry_run 변경 0건. 기존 5개 hotfix 유지.
- #11(임계 게임) 진짜 본체는 momentum_breakout 내부 stage 직렬 AND 결합 (tier는 Sprint 2에서 이미 OR로 변경 완료).
- #6 KIS WS execution 35% 누락이 #10/#13/#14 root cause 후보 — Sprint 5 T1 진단 1순위.
- hotfix 즉시 분리 2건: #7 (SECONDARY_POOL_FALLBACK_ENABLED unset + SettingsOverrideKey Enum), #12 (/screening/primary change_rate 노출). #9 (G3 부등호)는 Sprint 5 T4 진단 후 결정.
- Phase 7.0 LIVE 파라미터 영구 잠금 유지 (최리스크 G9).
- Sprint 6은 placeholder만 — Sprint 5 결과 의존, advisor §3 권고 (미리 풀 스펙 X).
- §7.5 G-Bt3 정의 갱신: 기존 Paper 5거래일 G-A/G-B 동시 충족 → §11.5 10개 지표 통과로 교체. G-Bt1/G-Bt2 walk-forward 통계 검증은 유지.

전문가 4명 합의 (`docs/phase/phase8.6/phase8.6-sprint5-{api,quant,risk,po}-review.md`): 윤에이피(API) + 박퀀트(퀀트) + 최리스크(리스크) + 정프로(PO). 김단타 미참여 (Sprint 5는 진단 Sprint).

Related: [[project_phase8.6]] [[feedback_phase_data_dependency]] [[feedback_kis_ws_url]] [[project_phase8.6_signal_zero_diagnosis]]
