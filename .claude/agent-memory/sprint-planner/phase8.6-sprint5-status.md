---
name: phase8.6-sprint5-status
description: Phase 8.6 Sprint 5 (진단 Sprint, 2026-05-14 계획 수립) — 5 Task 구성, 임계 변경 0건, T3 WS trace Paper 1주 병행, Hotfix A/B 머지 완료
metadata:
  type: project
---

# Phase 8.6 Sprint 5 — 진단 Sprint

**상태**: 🔄 계획 수립 완료 (2026-05-14), sprint-dev 착수 대기
**브랜치**: `phase8.6-sprint5` (develop 7e4c15d 기반)
**문서**: `docs/phase/phase8.6/sprint5/sprint5.md`
**근거**: `docs/phase/phase8.6/phase8.6.md` §11 (develop commit 5a162fa)

## Task 구성 (5 Task, 3~5일 + T3 병행 1주)

1. **T1 — 코드 즉답** (#8 R1 발동 + #9 G3 부등호 + #11 stage 결합 위치) — 반나절~1일
2. **T2 — DB/백테스트** (#10 walk-forward 60일 stage reject + #13 fallback DB + #14 secondary 4h churn) — 1~2일
3. **T3 — 라이브 WS trace** (#6 KIS WS 35% 누락 root cause, `WS_TRACE_ENABLED=true` Paper 1주 병행) — 시간축 분리
4. **Task 4 — 조건부 Hotfix C** (#9 G3 부등호, T1 결과 어긋남 시에만 분리)
5. **Task 5 — 종합 보고 + Phase 8.7 entry gate 평가** (E1/E2/G-Bt1/G-Bt2)

## 금지 사항 (절대 변경 금지)

- 임계값 (change_rate_max, trade_strength_min, ATR_FILTER_PCT, MIN_VOLUME_FLOOR_HARD, volume_threshold 등)
- dry_run 기본값
- LIVE_TRADING_ENABLED 토글 (false 잠금)
- Phase 7.0 LIVE 파라미터 (Final 상수 잠금)
- Sprint 1~4 본문
- 5개 기존 hotfix (#1~#5)
- 새 Sprint 신설 (Sprint 6 등 — Sprint 5 결과 후 사용자 판단)

## 제외 (이미 처리)

- Hotfix A (#7 SECONDARY_POOL_FALLBACK_ENABLED unset + SettingsOverrideKey Enum) → PR #237 머지 완료
- Hotfix B (#12 /screening/primary,/secondary raw change_rate/trade_strength 노출) → PR #238 머지 완료

## 신규 환경변수 (Railway 수동)

- `WS_TRACE_ENABLED` (기본 false) — T3 Paper 1주 동안만 true, 종료 후 false 복귀. deploy.md 기록 필수

## Phase 8.7 entry gate (3개, 직렬 AND)

- **E1**: WS execution 누락률 ≤ 5% (T3 라이브 1주 산출)
- **E2**: fallback 신호 비중 ≤ 20% (M-F2, T2 DB 측정 산출, 라이브 검증 병행)
- **G-Bt1 + G-Bt2**: walk-forward KS p≥0.05 + Bootstrap 95% CI 하한 ≥ 1 (Sprint 4 산출 승계)

§10 DoD #9~#11 (5거래일 관찰 G-A/G-B/G-C) deprecated. §7.5 G-Bt3 = 본 §11.5 3개 지표로 재정의.

## 다음 액션

1. 사용자 검토 후 `/sprint-dev 8.6-5` (또는 팀 실행 — Phase 1 T1/T2/T3 병렬)
2. sprint-dev 착수 즉시 `WS_TRACE_ENABLED=true` Railway 설정 (T3 Paper 1주 시간축 분리)
3. T1 Step 2 결과에 따라 Hotfix C 분리 여부 즉시 결정
