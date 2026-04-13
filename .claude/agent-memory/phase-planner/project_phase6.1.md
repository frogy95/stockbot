---
name: Phase 6.1 계획
description: 매매 전략 거래량 시간가중 보정 — volume_ratio 단위 불일치(장중 누적 vs 전일 마감 누적) 시간가중 보정으로 해결
type: project
---

Phase 6.1: 매매 전략 거래량 시간가중 보정
- 날짜: 2026-04-13
- 전문가: 정프로(PO) + 최리스크(리스크관리) + 김단타(단타) + 박퀀트(퀀트) — 4명 전원 합의
- Sprint: 단일 Sprint (파일 2~3개 수정)
- 핵심 결정: 옵션 (c) 시간가중 보정 채택 (전원 합의)
  - 옵션 (a) 현행 유지: 전원 거부 (시스템 존재 의의 부정)
  - 옵션 (b) 임계값 하향: 전원 거부 (수학적으로 동일 문제, 차원이 다름)
  - 옵션 (c) 시간가중 보정: 전원 권장
- 확정 파라미터 8건:
  - volume_ratio 임계값 2.0 유지 (시간보정으로 해결)
  - 선형 보정: adjusted_ratio = V(t) / (V_prev * progress)
  - progress = elapsed_min / 390 (KRX 09:00~15:30)
  - MIN_MARKET_PROGRESS = 0.15 (09:58 이전 극단적 비율 방지)
  - MIN_VOLUME_FLOOR = 0.3 (전일 30% 미만 유동성 부족 탈락)
  - confidence volume_score도 adjusted_ratio 사용

**Why:** momentum_breakout 전략이 장중 누적 거래량과 전일 마감 거래량을 직접 비교하여 장 전반부에는 구조적으로 2.0 도달 불가능. 박퀀트: "단위 불일치(unit mismatch) 오류".

**How to apply:** momentum_breakout.py 수정. calc_market_progress() 추가, 거래량 조건 블록에 시간가중 보정 적용. 테스트에 시간대별 보정 케이스 5건 이상 추가.

주의사항:
- 선형 보정은 장 중반에 10-20% 보수적 (리스크 관리에 유리)
- U자형 비선형 보정은 Phase 7+에서 20거래일 데이터 축적 후 검토 (박퀀트)
- 거래량 가속도 지표는 WS 틱데이터 기반으로 Phase 7+에서 추가 가능 (김단타)
