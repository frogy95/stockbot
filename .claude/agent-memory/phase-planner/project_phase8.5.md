---
name: Phase 8.5 계획 제안
description: Phase 8 Sprint 3 착수 전 신호 0건 교차 단절 해소 브리지 Phase — 2차 스크리닝 풀 하한 폴백 + 동적 min_volume_floor + 관측성 강화
type: project
---

# Phase 8.5 계획 제안 (2026-04-22)

**Status**: 제안 문서 작성 완료. 사용자 승인 전 ROADMAP·index.json 미반영.

## 문제 정의
- 2026-04-22 관측: 2차 스크리닝 1종목(073490)만 통과, 오늘 신호 0건
- 오전 `min_volume_floor` 100% 컷, 13:00+ `prev_close_time_guard` 100% 컷 → 교차 불가 구조
- Phase 8 Sprint 3 DoD "신호 3거래일 연속"이 현 조건에서 논리적 달성 불가

## 결정 사항
- 브리지 Phase 8.5 제안 (Sprint 1 관측성 + Sprint 2 풀 폴백 + 동적 floor), 최대 2 Sprint / 1.5주
- **시간 슬라이딩 min_volume_floor 거부** (전원) — 돌파 강도 연동 동적 floor(0.4/0.5/0.6)로 대체
- **prev_close_time_guard 13:00→14:00 연장 거부** (전원) — Sprint 2 안전장치 유지, 가상 신호 로깅으로 1개월 후 재평가
- **Phase 9/10/10.1 순서·전제 변경 없음** — 병행·조기 착수 전원 거부
- **Phase 10.1 하이브리드 MVP (풀 하한 폴백)**만 Phase 8.5에 흡수, 본격 하이브리드는 Phase 10.1 유지

## 핵심 확정 파라미터
- 폴백 발동: `passed_count < 3` → 1차 상위 total_score 보강, 상한 5, `is_fallback=True` 메타데이터
- 폴백 종목: position 50%, 손절 -1.5%, 전일 대비 -3% 이하 제외
- `MIN_VOLUME_FLOOR`: 동적 (0.4: gap5%+/강한 prev_high / 0.5: 기본 / 0.6: prev_close tier), HARD 하한 0.3
- 2차 `pass_threshold=75.0` 유지 (분포 관측 후 재교정)
- 전 파라미터 env 변수화 + 자동 롤백 트리거 (2거래일 연속 신호 0건)

## Sprint 3 DoD 재정의
- 일평균 신호 ≥1 (5일 합 ≥5)
- 신호 0건 일수 ≤2/5
- tier 최소 2개 각 1회 (gap_open 필수 아님)
- 손절 체결 최소 1회
- Paper 핫픽스 0건 (유지)
- 3거래일 연속 0건 시 자동 중단

## 검토 방식 제약
- phase-planner 서브에이전트 스폰 툴 미제공 세션 — 4명 페르소나 기반 직접 순차 작성
- 필요 시 독립 세션 병렬 재검토 가능

## Why
현 조건에서 Sprint 3 DoD 달성 경로 없음 → 무의미한 대기 발생. 사용자 지시: "이뤄지지도 않는 거래 기다리며 데이터만 살펴보는 건 무의미, 문제점 해소 후 최소 검증으로 Phase 계속 진행".

## How to apply
사용자 승인 시 ROADMAP에 Phase 8.5 섹션 추가 + Phase 8 Sprint 3 DoD 문장 업데이트. Phase 9/10/10.1은 손대지 않음.
