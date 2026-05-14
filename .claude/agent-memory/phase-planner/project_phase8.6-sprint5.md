---
name: project_phase8.6-sprint5
description: Phase 8.6 Sprint 5 (2026-05-14 축소 재설계) — 3 Task 진단 Sprint, entry gate 3개, Sprint 6 폐기
metadata:
  type: project
---

Phase 8.6 Sprint 5 — **2026-05-14 축소 재설계** (사용자 승인 완료). 직전 plan(8 Task / 1.5~2주 / entry gate 10지표) 사용자 명시 거부 → 3 Task / 3~5일 / entry gate 3개로 축소.

**Why**: 사용자 명시 인용 "과거의 데이터를 기반으로 측정가능한 항목은 없는거야? 우리가 저장하지 않은 데이터라도 kis api를 통해 과거를 소급 확인가능하잖아? 왜이렇게 검증하고 가고 싶은게 많은거야?" — 9개 미해결 결함 중 #6 KIS WS만 라이브 필수, 나머지 8개는 코드 리딩 / DB 쿼리 / Sprint 4 walk-forward 인프라 재활용으로 2~3일 내 답.

**How to apply**:
- Phase 8.7 entry gate = **3개 지표만**: E1(WS 누락률 ≤5%, 라이브 T3), E2(fallback 비중 ≤20%, DB 측정 T2), G-Bt1/G-Bt2(walk-forward KS + Bootstrap CI, Sprint 4 인프라 승계).
- 직전 plan E3~E10(단일 stage / 4h 교체율 / Paper PnL / 손절 / R1~R4 plan-code / R3 회귀)은 **게이트가 아니라 Sprint 5 T1/T2 Task 종료 조건**으로 흡수.
- 향후 entry gate 추가 검토 시: "라이브로만 입증 가능한 지표"인지 확인. 과거 데이터로 답 나오는 것은 게이트 X, Task 종료 조건으로 흡수.

축소 후 핵심 결정:
- **T1 코드 즉답 (반나절~1일)**: #7 R3 unset / #8 R1 발동 / #9 G3 부등호 / #11 stage 직렬 AND 위치 확정. 진단서 1장.
- **T2 DB/백테스트 (1~2일)**: #10 breakout 72.2% 편중 walk-forward 60일 + #13 fallback M-F2 DB + #14 secondary 4h 교체율 DB.
- **T3 라이브 trace (병행 1주)**: #6 KIS WS execution 35% 누락 A/B/C 3후보 trace, T1/T2와 시간축 분리.
- **Hotfix 분리**: A(#7 R3 unset Enum) + B(#12 /screening/primary change_rate) + 조건부 C(#9 G3 부등호, T1 진단 후).
- **Sprint 6 placeholder 삭제** — T2/T3 결과로 본질 진단되면 추가 Sprint 자체가 불필요할 수 있음.
- **5거래일 Paper 윈도우 별도 게이트 X** — T3 라이브 1주에 자연 흡수.
- Sprint 1~4 본문 unchanged + 기존 5개 hotfix(#1~#5) 유지 + 전문가 4명 재호출 금지(본질 합의 끝남).
- §7.5 G-Bt3 = §11.5 3개 지표로 정의 갱신, §10 DoD #9~#11 deprecated 표시 유지(삭제 X).
- Phase 7.0 LIVE 파라미터 영구 잠금 유지.

전문가 4명 합의 (`docs/phase/phase8.6/phase8.6-sprint5-{api,quant,risk,po}-review.md`): 윤에이피(API) + 박퀀트(퀀트) + 최리스크(리스크) + 정프로(PO). 김단타 미참여 (Sprint 5는 진단 Sprint).

Related: [[project_phase8.6]] [[feedback_phase_data_dependency]] [[feedback_kis_ws_url]] [[project_phase8.6_signal_zero_diagnosis]]
