# Phase 8.6 Sprint 5 — 정프로(PO) 검토

> 작성일: 2026-05-14
> 검토 대상: Phase 8.6 Sprint 5 초안 (2026-05-13~14 모니터링 결과 14개 결함 처리)
> 페르소나: `docs/experts/product-owner.md` — "동작하는 SW > 완벽한 문서 / MVP 최소이되 유용 / 한 스프린트 하나의 핵심 목표 / 위험한 것부터 먼저 검증 / 사용자 1명도 프로세스는 지킨다"

---

## 1. 요약 — ✅ **방향 채택 (단 Sprint 5/6 분할 + Sprint 7은 placeholder까지만)**

사용자가 정확히 짚었다. **"5거래일 일평균 ≥1" entry gate는 무의미하다.** 분기 D 사후 결정으로 합의된 기준이었지만 오늘(2026-05-14) 모니터링이 그 기준의 한계를 정량적으로 보여줬다 — 신호 2건 발생 = entry gate 충족 — 그러나 그 신호 2건의 출처(WS execution null 종목 100%, fallback 산물 가능성)가 의심스러워 LIVE 토글 불가.

→ **표면 카운트 게이트 폐기, 품질/신뢰도 게이트로 전환** 필요. 이건 본 Phase의 핵심 의사결정 변경이다.

다만 일정/스코프 관리상 다음 원칙 적용:

1. **Sprint 1~4 완료분 unchanged** (사용자 명시)
2. **Sprint 5만 풀 스펙** — 진단 + 측정 인프라
3. **Sprint 6은 placeholder** — Sprint 5 진단 결과 의존, 지금 스펙 못박지 말 것 (advisor §3 지지)
4. **Sprint 7은 작성 X** — 필요 여부도 Sprint 5 후 결정
5. **2건 hotfix 즉시 분리** (#7, #12) — Sprint 5 본 작업 외 핫픽스 트랙

---

## 2. 항목별 검증 결과

### Sprint 분할 방향 — Sprint 5/6 (필요 시 7) 으로 분리

| Sprint | 핵심 목표 | 기간 | 의존 |
|--------|----------|------|------|
| **Sprint 5** (풀 스펙) | **진단 + 측정 인프라** — #6 root cause trace + stage shadow mode + 안전망 신뢰도 검증 (#8/#9) + fallback 비중 정량화 | 1.5~2주 | hotfix #7/#12 사전 처리 |
| **Sprint 6** (placeholder) | **진단 결과 기반 구조 변경** — Sprint 5 결과 의존 (#6 fix / stage 결합 정책 변경 / 임계 회귀 후보 변경) | 1.5~2주 | Sprint 5 완료 |
| Sprint 7 | 미정 (Sprint 6 후 필요 시 결정) | — | — |

**PO 권고**: 사용자가 "Sprint 5(필요시 6, 7도)" 라고 했지만 PO 관점에서 **최소 Sprint 6까지는 필요** 함이 강하게 추정된다 (#6 fix는 진단만 1주, 구현 별도). Sprint 7 여부는 Sprint 6 후 결정.

### Hotfix 분리 의사결정 (PO 최종 판단)

| # | 결함 | PO 판단 | 근거 |
|---|------|---------|------|
| 7 | SECONDARY_POOL_FALLBACK_ENABLED unset 누락 | ✅ **즉시 hotfix** (단 윤에이피/최리스크 권고대로 enum 단일 진실 소스 묶음) | 단순 결함 + 안전망 신뢰도 P0 |
| 9 | G3 임계 부등호 | ⚠️ **Sprint 5 진단 Task 1번에 편입 → 코드 의도 확인 후 hotfix 여부 결정** | 코드 의도 확인 없이 hotfix 위험 (advisor §4 권고) |
| 12 | /screening/primary change_rate 노출 | ✅ **즉시 hotfix** | 진단 인프라 + 단순 read API 확장 |
| 8 | R1 발동 원인 의문 | ❌ hotfix 부적격 → Sprint 5 진단 본 작업 | 안전망 trigger 변경은 hotfix 부적격 |

→ **즉시 hotfix 2건** (#7 + #12), **Sprint 5 진단 편입 1건** (#9), **Sprint 5 본 작업 5건+** (#6/#8/#10/#13/#14/#11).

### 사용자 명시 "5건 hotfix 유지" 원칙 — ✅ 채택

기존 5개 적용 hotfix (change_rate_max 30, trade_strength_min 80, ATR_FILTER_PCT 0.07, MIN_VOLUME_FLOOR_HARD 0.25, virtual-signals filter) 모두 Sprint 5 동안 unchanged. Sprint 5는 진단 Sprint = 임계 노이즈 회피.

**Sprint 6 또는 Sprint 7에서 재평가 가능** (advisor §7 지지) — 단 진단 결과 기반.

### Phase 8.7 entry gate 재정의 — 사용자 요청 직접 응답

사용자: "5거래일 관찰 게이트는 무의미하다 — 표면 통과형 게이트 X."

PO 종합 (advisor §5 + 박퀀트 + 최리스크 권고 통합):

| 카테고리 | 지표 | 임계 | 출처 |
|---------|------|------|------|
| **데이터 인프라** | WS execution 누락률 (1차 풀) | ≤ 5% | 최리스크 (윤에이피 ≤10%보다 강화) |
| **신호 신뢰도** | fallback 신호 비중 (M-F2) | ≤ 20% | 최리스크 (advisor ≤30%보다 강화) |
| **신호 신뢰도** | 단일 stage 점유율 | ≤ 50% | 박퀀트 + advisor |
| **신호 신뢰도** | Secondary 4h 교체율 | ≤ 30% | 최리스크 (advisor ≤50%보다 강화) |
| **신호 성과** | Paper 신호 PnL 5거래일 누적 | 양(+) | advisor + 박퀀트 |
| **안전망 신뢰도** | 손절 체결 발생 (Paper 5거래일) | ≥ 1 | advisor + 최리스크 |
| **안전망 신뢰도** | R1~R4 plan-code 일치 단위 테스트 | 통과 | 최리스크 신규 |
| **안전망 신뢰도** | R3 자가치유 settings:override:* 전수 회귀 | 통과 | 최리스크 신규 |
| **통계 검증** | walk-forward KS 검정 p (G-Bt1) | ≥ 0.05 | 박퀀트 (Phase 8.6 §7.5 승계) |
| **통계 검증** | Bootstrap CI 하한 (G-Bt2) | ≥ 1 | 박퀀트 (Phase 8.6 §7.5 승계) |
| **참고 트래픽 지표** | Paper 일평균 신호 수 | (모니터링만, gate 아님) | advisor §5 — "참고용 트래픽 지표로만" |

**핵심 변경**: 기존 §7.5 G-Bt3 (Paper 5거래일 G-A/G-B/G-C 동시 충족) → 위 8개 (인프라+신뢰도+성과+안전망) 기반으로 **교체**. G-Bt1/G-Bt2(walk-forward 통계 검증)는 유지.

**참고 지표 위치**: 5거래일 평균이 0건이면 *모니터링* 으로는 의미 있으나 *gate* 로는 부적격. 이걸 모니터링 카드로 분리하고 gate에서 제외.

### Sprint 1~4 완료분 보존 원칙 — ✅ 채택

phase8.6.md §1~§8 본문 **수정 없음**. §10 DoD #9~#11 (5거래일 관찰 G-A/G-B/G-C) 도 **삭제 X, deprecated 표시만 추가**. Sprint 3·4 완료 시점의 기준이었고, Sprint 4 완료 보고에 인용됐기 때문에 추적성 유지.

### Sprint 5 진단 Task 후보 정리 (PO 정렬)

advisor §2 + 윤에이피 + 박퀀트 + 최리스크 권고 종합:

| Task | 내용 | 산출물 | 기간 |
|------|------|--------|------|
| T1 | **#6 KIS WS execution 35% 누락 root cause trace** (A: KIS 한도 / B: subscribe 레이스 / C: MST sync) — `WS_TRACE_ENABLED=true` 1~2 거래일 로깅 + KIS 응답 코드 분석 | 진단 결과 보고서 + root cause 후보 1개 채택 | 3~5일 |
| T2 | **stage shadow mode 도입** — momentum_breakout 4 stage 모두 평가하도록 read-only 측정 추가 (reject 차단 X, 평가 결과만 로깅) + 1차 풀 전종목 stage 통과 패턴 일별 집계 | shadow mode + Redis stream + 일별 stage 분포 API | 5~7일 |
| T3 | **#8 R1 발동 원인 진단** — `AutoRollbackEvaluator` 코드 vs plan §5.5 1:1 대조 + 05-15 자동 해제 분기 검증 + R1~R4 trigger snapshot Telegram 알림 추가 | 진단 보고 + plan-code 불일치 list | 2~3일 |
| T4 | **#9 G3 부등호 코드 의도 확인** — `pass_rate < 0.10` vs `≤ 0.10` 확인 + 임계 부등호 전수 검사 (R1~R4 + G3 + 기타) + 의도 어긋남 시 hotfix 분리 | 부등호 audit 결과 + (필요 시) hotfix PR | 1일 |
| T5 | **fallback 비중(M-F2) 정량화 + 신호 신뢰도 분리** — fallback 발동 종목에서 발생한 신호 vs 정상 종목 신호를 일별 분리 집계 + Phase 8.7 entry gate "fallback 신호 비중 ≤ 20%" 측정 기반 | M-F2 신호 비중 API + 일별 분리 대시보드 카드 | 3~4일 |
| T6 | **R3 자동 SET/UNSET audit log** — 시점·조건·trigger value 적재 + `settings:override:*` 키 enumeration 단일 진실 소스 (SettingsOverrideKey Enum) + R3 자가치유 전수 회귀 테스트 | audit log + enum + 회귀 테스트 | 2~3일 |
| T7 | **미검증 trace 3건 완료** — `_get_realtime_data` 폴백 trace + momentum_breakout +7% 종목 평가 경로 trace + R3 자동 SET 시점 관측 | trace 보고서 (T1/T6의 sub-체크리스트로 흡수 가능) | 1일 |
| T8 | **Phase 8.7 entry gate 재정의 문서화 + 측정 dashboard** — 위 8개 지표 대시보드 카드 + 일일 측정 + 통과/미통과 판정 자동화 | gate 문서 + dashboard 페이지 | 2~3일 |

**총 Sprint 5 기간 추정**: 1.5~2주 (병렬 가능 일부 있음, T2/T5는 인프라 의존).

### Sprint 6 placeholder (지금 스펙 못박지 말 것)

Sprint 5 진단 결과에 따라 분기:

| Sprint 5 결과 | Sprint 6 방향 |
|--------------|-------------|
| #6 root cause = KIS 한도 | 1차 풀 축소(20→18) + 우선순위 큐 + 잔여 슬롯 polling |
| #6 root cause = subscribe 레이스 | subscribe 응답 코드 0 미확인 시 재시도 + 누락 종목 분리 재구독 |
| #6 root cause = MST sync 타이밍 | MST sync 강제 동기화 |
| stage shadow mode 결과 = 다수결 ≥3/4 유효 | stage 결합 정책 변경 (직렬 → 다수결) shadow → dry_run → 본 도입 |
| R1~R4 plan-code 불일치 발견 | 안전망 plan-code 통일 + 회귀 테스트 강화 |

Sprint 6 풀 스펙은 Sprint 5 종료 시점 (예상 2026-05-30 전후) 에 별도 sprint-planner 호출로 작성.

### Sprint 7 — 작성 X

Sprint 6 종료 시점에 결정. 만약 Sprint 6 후 Phase 8.7 entry gate 통과 시 Sprint 7 미필요 → Phase 8.7 진입.

---

## 3. 파라미터 조정 권고

PO는 Sprint 5 진단 단계에서 **파라미터 변경 0건** 원칙 채택 (박퀀트 + 최리스크 권고 승계). 진단 노이즈 회피 + 사용자 명시.

### Phase 8.7 entry gate 임계 — 위 §2 표 참조 (최종 8개 지표)

### Sprint 6/7 후보 파라미터는 Sprint 5 결과 의존 — 지금 결정 X

---

## 4. 리스크 및 대안

### PO 일정/스코프 리스크

1. **Sprint 5 진단 결과가 "fix 불가" 또는 "복합 root cause"로 나오면 Phase 8.7 진입 무기한 지연** — 사용자 결정 항목. PO 권고: 무기한 지연 수용. 분기 D 같은 사고 재발 방지 가치가 더 크다.
2. **사용자가 Sprint 5/6 동안 임계 미세조정 욕망 표출 위험** — 박퀀트 + 최리스크 권고 강제. PO는 거부 입장 견지.
3. **Sprint 5 7~8개 Task가 1.5~2주에 안 끝날 위험** — 필요 시 Sprint 5를 5a (T1/T2/T3/T4) + 5b (T5/T6/T7/T8) 로 재분할 가능. 단 처음부터 분할하면 추적 비용 증가, 일단 단일 Sprint 5 시도.
4. **hotfix #7/#12 처리 중 Sprint 5 진단 코드 conflict 위험** — 동일 파일(`api/routes/metrics.py`, `safety/auto_rollback.py` 등) 변경 가능성. hotfix 먼저 머지 후 Sprint 5 브랜치 rebase.

### 대안

- Sprint 5 진단 결과가 빠르게 (1주 내) 명확해지면 Sprint 5 후반에 Sprint 6 일부 Task 흡수 가능.
- 반대로 진단이 길어지면 Sprint 6 무리하지 말고 Sprint 7로 미루기.

---

## 5. 결론 (PO 최종 의사결정)

1. **Phase 8.6 본문 (§1~§8 + §10 DoD #1~#8) unchanged** — 사용자 명시 + 추적성
2. **§10 DoD #9~#11 (5거래일 관찰) deprecated 표시 + 미삭제** — 추적성 + advisor §9
3. **Sprint 5 풀 스펙 신설** — 진단 + 측정 인프라 (T1~T8)
4. **Sprint 6 placeholder 신설** — Sprint 5 결과 의존
5. **Sprint 7 작성 X** — Sprint 6 후 결정
6. **즉시 hotfix 2건 분리**: #7 (SECONDARY_POOL_FALLBACK_ENABLED unset + enum 통합), #12 (`/screening/primary` change_rate 노출)
7. **#9 (G3 부등호) Sprint 5 T4 진단 후 hotfix 여부 결정**
8. **기존 5개 적용 hotfix 모두 unchanged** (Sprint 5/6 동안) — 측정 노이즈 회피
9. **Phase 8.7 entry gate 8개 지표 재정의** (§2 표) — 표면 카운트 게이트 폐기, 품질/신뢰도 게이트로 전환
10. **walk-forward Sprint 4 결과(G-Bt1/G-Bt2) 유지, G-Bt3만 8개 지표로 교체** — phase8.6 §7.5 갱신
11. **Phase 7.0 LIVE 파라미터 영구 잠금 유지 + LIVE_TRADING_ENABLED false 잠금 (Sprint 5/6 동안)**
12. **ROADMAP.md Phase 8.6 절 + Phase 8.7 entry 조건 갱신**

전문가 4명(윤에이피 + 박퀀트 + 최리스크 + PO) 합의: **Sprint 5는 진단·측정 Sprint, 임계 변경 0건**.
