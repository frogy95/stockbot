---
name: 2026-04-30 Sprint 2 관찰 결과
description: Phase 8.6 Sprint 2 (v2.8.0) 첫 거래일 관찰 판정 — NO-GO, G2 자동롤백 R1 발동
type: project
---

# 2026-04-30 관찰 최종 판정

**판정: NO-GO**

## G1: ATR 캘리브레이션 잡 (목표: Redis 4종 키 적재)

- 결과: 측정 불가 (PARTIAL 처리)
- 사유: KST 08:35(UTC 23:35) 잡 실행 흔적이 로그 보존 범위 밖 (로그는 UTC 00:38부터 시작)
- 확인: 잡 자체는 scheduler 등록 확인됨 (배포 시 ERROR 0건)
- 미확인: Redis 실제 키 적재 여부 — 사용자가 `railway run` 으로 직접 확인 필요

**Why:** railway logs 최대 1000줄 보존 범위가 UTC 00:38부터 시작되어 UTC 23:35 잡 실행 시점 커버 불가.

## G2: 병렬 OR tier 신호 발생 (목표: 신호 ≥1 + matched_tiers 기록)

- 결과: FAIL — 신호 0건 (2026-04-28/29/30 연속 3일)
- KST 16:10 자동 롤백 R1 발동 확인 (로그 실측): `should_rollback=True triggers=['R1']`
- Redis override 설정 완료 (WARNING 로그 확인)
- matched_tiers DB 저장 건수 = 0
- 원인 추정: `prev_close_volume_confirm` 게이트 과도제한 + `min_volume_floor` 동시 작용으로 신호 통로 완전 차단

**Why:** 2차 스크리닝 완료 후 20후보 모두 `데이터없음=20`으로 필터 탈락. 동시호가 구간 no_data 가드 반복.

## G3: 시뮬-실측 절대차 (목표: ≤ 0.15)

- 결과: 측정 불가 (G2 신호 0건으로 분모=0)
- G3 회로차단기 발동: `reason=zero_denominator:2026-04-28`
- 3일 연속 rates: [('2026-04-30', 0.0633), ('2026-04-29', 0.0483), ('2026-04-28', None)]

## 부수 관찰

- 백엔드 ERROR/CRITICAL: 0건 (정상)
- WARNING 2건: G2 자동롤백 + G3 회로차단기 (정상 경보)
- PARALLEL_OR_TIER_ENABLED: true (환경변수 유지, Redis 레벨 override만 발동)
- 환경변수 10종 전부 확인됨

## 종합 판정

**NO-GO** — G2 신호 0건(2거래일 연속) + G2 자동 롤백 R1 발동 + G3 회로차단기 동시 발동

**How to apply:** Sprint 3 착수 전 prev_close_volume_confirm 게이트 완화 또는 min_volume_floor 파라미터 조정 후 재관찰 필요. Kill-switch(`PARALLEL_OR_TIER_ENABLED=false`) 적용 여부는 사용자 결정.
