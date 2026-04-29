---
name: Phase 8.6 계획
description: 2026-04-28 분기 D 트리거 선제 착수, 신호 생성 로직 구조 재설계 (병렬 OR + ATR 분위수 + volume_surge tier + walk-forward 60일)
type: project
---

# Phase 8.6 계획 (2026-04-28 수립)

## 트리거
- Phase 8.5 v2.6.1 5거래일 관찰 분기 D 확정 (2026-04-28 16:10 `auto_rollback_2d_zero_signals`)
- 4거래일 본 신호 1건 / 폴백 605회 / 시뮬 pass율 38.9% vs 실측 ~3% (10배 괴리)
- 사용자가 PO Sprint 2.6 제안 거부, 구조 재설계 노선(퀀트/단타) 선택

## 재정의 (Phase 8.6 ↔ 10.2 분리)
- 기존 Phase 8.6 (누적 백로그 통합: 피라미딩, 2차 하이브리드) → **Phase 10.1로 이관**
- 본 자리 Phase 8.6 = **신호 생성 로직 구조 재설계** (분기 D 선제 착수)

## 4 Sprint 구조
1. Sprint 1 — 선행 패치 + 가드레일 (PO Sprint 2.6 흡수 + 리스크 G1~G3 DoR)
2. Sprint 2 — 직렬 AND → 병렬 OR tier 분리 + ATR 분위수 동적 캘리브레이션
3. Sprint 3 — `volume_surge` tier 신설 + 시간대 필터 (09:00~09:10 금지, 점심 0.7, 14:30+ 진입 금지)
4. Sprint 4 — Walk-forward 60일+ + Bootstrap CI + 시뮬-실측 KS 자동 감지

## 핵심 확정 파라미터 (38건)
- ATR 하한 0.025 + 동적 상한 `min(0.08, KOSPI200 80퍼센타일×1.2)`
- volume_surge: vol_5m ≥ 평균×5 + 매수/매도 잔량 ≥ 2 + 가격 +0.5%, position 30%, dry_run 기본
- 자동 롤백 R1~R4 OR (R1=0건 3일 / R2=폴백 ≥50% 3일 / R3=tier 1종 5일 / R4=폴백 ≥70% 1일)
- 폴백 종목 일일 손실 -1% 별도 한도 (전체 -2%와 격리)

## DoR (Sprint 2 차단 해제)
- G1: M-F2 산출 (메타데이터 신호→체결 전파)
- G2: 자동 롤백 R1~R4 다변화
- G3: 1차→2차 통과율 <10% 3일 회로차단기
- Phase 7.0 LIVE 파라미터 코드 잠금

## DoD 핵심 (G-A~G-G)
- 일평균 신호 ≥1.5 / 0건 일수 ≤30% / tier ≥3종 활성 / tier 페어와이즈 상관 ≤0.3
- 시뮬-실측 KS p≥0.05 / 폴백 신호율 산출 / R1~R4 다중 트리거 동작

## 전문가 의견 매핑 (검토 출처)
- 직렬 AND→병렬 OR: 박퀀트 §3.2
- ATR 분위수: 박퀀트 §3.1 + 리스크 §3.2 패키지 수용
- volume_surge tier: 김단타 §2 패턴 1 / §3 1순위
- DoR G1~G3: 리스크 §3 P0
- Sprint 1 흡수 결정: PO §3 (Sprint 2.6 안)

## ROADMAP / index.json 갱신
- ROADMAP §장기 마일스톤 + 의존성 트리 + Phase 8.6·10.2 본문 섹션 (4군데)
- index.json: phase8.6 status=planned + phaseDoc 추가 + reviews(분기 D 4종) + phase10.1 신규

## 브랜치
- `docs/phase8.6-plan` (docs/* 브랜치, hotfix/observation-daily-api와 분리)
- deploy.md M 변경은 stash로 분리, hotfix 브랜치에 그대로 보존

## 데이터 의존성
- 없음 (분기 D는 구조 결함). Sprint 4 walk-forward는 KIS 분봉 백필 60일분 (Phase 9 Sprint 0 메커니즘 일부 차용)

## 사용자 결정 대기 항목
- KIS 분봉 백필 분리 진행 여부 / dry_run→LIVE 자동 토글 여부
- Phase 8.6↔10.2 분리는 본 Phase 전제로 채택 (사용자 명시 거부 시에만 재작성)
