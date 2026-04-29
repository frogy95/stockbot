# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Sprint: phase8.6/sprint1 — LIVE 보호 가드레일 (G1+G2+G3 + Phase 7.0 잠금)

브랜치: `phase8-sprint1` (develop 머지 예정)

**LIVE 게이트 합의**: 본 Sprint는 **LIVE 전환 아님** — Paper 모드에서 R1~R4/G3 가드레일 검증. LIVE 전환은 Sprint 2 병렬 OR 완료 + DoR 4종 모두 통과 후.

#### Railway 환경변수 추가 확인 (10종 — 신규/조정)

- ⬜ `SECONDARY_POOL_FALLBACK_THRESHOLD=5`  # Phase 8.6 Sprint 1 — 분기 D 풀 협소 대응 (3→5)
- ⬜ `SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP=5`
- ⬜ `AUTO_ROLLBACK_ENABLED=true`
- ⬜ `AUTO_ROLLBACK_R1_ENABLED=true`
- ⬜ `AUTO_ROLLBACK_R2_ENABLED=true`
- ⬜ `AUTO_ROLLBACK_R3_ENABLED=false`  # Sprint 2 tier 분리 후 true 전환
- ⬜ `AUTO_ROLLBACK_R4_ENABLED=true`
- ⬜ `CIRCUIT_BREAKER_ENABLED=true`
- ⬜ `CIRCUIT_BREAKER_PASS_RATE_THRESHOLD=0.10`
- ⬜ `CIRCUIT_BREAKER_CONSECUTIVE_DAYS=3`

#### 자동 검증 (Sprint 1 — develop PR 시점)

- ✅ pytest 전체: **1001 passed, 1 failed (test_ws_stability — Sprint 무관, 기존 환경 문제 / Sprint 1 변경분 64 PASS)**
- ✅ 신규 테스트 PASS:
  - G1 메타데이터 전파: 6 PASS (`tests/test_g1_fallback_metadata_propagation.py`)
  - G2 자동 롤백 R1~R4: 13 PASS (`tests/safety/test_auto_rollback.py`)
  - G3 회로차단기: 9 PASS (`tests/safety/test_circuit_breaker.py`)
- ✅ Alembic 왕복 테스트 (PR 머지 게이트): `upgrade head → downgrade -1 → upgrade head` 3단계 모두 성공 (Task 3 시점)
- ✅ frontend `npx tsc --noEmit`: 0 errors

#### DoR 4종 + P0 보강 5건 (반영 결과)

- ✅ **DoR §3 G1**: `is_fallback` candidate→signal→order 메타데이터 전파 + DB 컬럼 + M-F2 API
- ✅ **DoR §3 G2**: R1~R4 OR 자동 롤백 + 16:10 평가 + Phase 8.5 폴백 격리
- ✅ **DoR §3 G3**: 1차→2차 통과율 회로차단기 + counter pair + Phase 8.5 폴백 동시 차단
- ✅ **Phase 7.0 LIVE 잠금**: `Final` 상수 + 런타임 assert 이중 가드 (Task 1)

P0 보강 5건:

- ✅ **#1 (Daytrader Critical)** G3 분모 부재 — counter pair 동시 적재 + 분모=0 fail-safe 강제 ON (`test_zero_denominator_fails_safe_to_circuit_on`)
- ✅ **#2** R4 분모 baseline — `screener:candidates:primary:{date}` Redis counter 일별 적재 (TTL 30d)
- ✅ **#3 (Daytrader Critical)** G3 청산 신호 보존 — `signal.action in (exit/stop_loss/take_profit)` 또는 `signal_type=='sell'` 통과 (`test_circuit_breaker_does_not_block_exit_signals`, `test_circuit_breaker_blocks_only_entry_signals`)
- ✅ **#4 (Risk Critical)** dry_run 우회 방지 — `Final` 상수 + 런타임 assert + `test_phase7_constants_immutable_at_runtime`
- ✅ **#5** Alembic 왕복 회귀 — `upgrade head → downgrade -1 → upgrade head` 3단계 PASS

#### 수동 검증 필요 항목 (Railway 프로덕션 배포 후 — 본 Sprint는 LIVE 아니지만 Paper 회귀 + env 등록 확인 필요)

- ⬜ `docker compose up --build` 빌드 검증 (DB 컬럼 추가 — `trade_signals.fallback`, `orders.fallback`)
- ⬜ Paper 모드 1거래일 회귀: `signals.fallback=true` 1건 이상 DB 기록 + M-F2 API 응답 정상
- ⬜ Playwright `/diagnostics` 페이지 접속 — `FallbackSignalRateCard` + `AutoRollbackMultiTrigger` 정상 렌더
- ⬜ CI grep 가드 (주문 실행 경로 git diff 0줄) — Sprint 1은 `core/clients/kis_rest.py` / `modules/trading/order_manager.py` 변경분에 LIVE 토글/하드코딩 시도 없음 확인 (sprint-review에서 재확인)

---

### Hotfix: observation-daily-api — 분기 D 확정 (2026-04-27 ~ 2026-04-29)

PR (코드): https://github.com/frogy95/stockbot/pull/175 (2026-04-27 머지)
PR (문서): https://github.com/frogy95/stockbot/pull/177 (2026-04-29 머지)

- ✅ 자동 검증 완료:
  - pytest: 963 passed, 1 failed (test_ws_stability — 무관)
  - 타겟 API 검증: `GET /api/v1/health/observation-daily` → 200 정상
  - Phase 8.5 5거래일 관찰 완료: **분기 D 확정** (M-R true, 2026-04-28T16:10 자동 롤백 발동)

- ⬜ 수동 검증 필요 항목:
  - Railway 배포 완료 후 실 API 호출 확인: `curl -s "https://api.stockbot.choiji.kr/api/v1/health/observation-daily"`
  - `.claude/settings.local.json`에 수동 추가 (allowlist 확장):
    - `"Bash(curl -s https://api.stockbot.choiji.kr/api/v1/health/observation-daily)"`
    - `"Bash(curl -s https://api.stockbot.choiji.kr/api/v1/health/observation-daily?date=*)"`

---

### 프로덕션 배포 - v2.6.1 (2026-04-23)

포함 스프린트: Phase 8.5 Sprint 2.5 — 인프라 보강 + 관측성·문서 정합성
PR: https://github.com/frogy95/stockbot/pull/173 (develop → main)

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

#### 신규 환경변수 (Railway 수동 설정 필요)

- ⬜ `SETTINGS_OVERRIDE_ENABLED=True` Railway에 추가 (기본값 True, 미설정 시에도 동작하나 명시 권장)

#### 수동 검증 필요 항목 (Railway 프로덕션 배포 후)

- ⬜ `SETTINGS_OVERRIDE_ENABLED=True` Railway 반영 확인
- ⬜ Sprint 2 env 8종(`MIN_VOLUME_FLOOR_MODE` 외) Railway에 존재 확인 (재확인 목적)
- ⬜ Playwright `/diagnostics` 스크린샷 — 배너 미렌더 정상 상태
- ✅ 5거래일 관찰 종료 후 의사결정 트리(A~E) 판정: **분기 D 확정** — 2026-04-28 16:10 자동 롤백 발동 (reason: auto_rollback_2d_zero_signals). legacy 모드 유지 + Phase 10.1 선제 착수 검토. 전문가 4명(PO/리스크/퀀트/단타) 재리뷰 필수.
  - M-R: true (triggered_at: 2026-04-28T16:10:00+09:00, reason: auto_rollback_2d_zero_signals)
  - M-S1: 1 (목표 ≥5 — 크게 미달)
  - M-S2: 3 (0건 일수: 04-23·04-27·04-28 — 목표 ≤2 초과)
  - M-S3: 1종 (prev_high만 — 목표 ≥2종 미달)
  - M-F1: 4일 모두 발동 (605회 누적)
  - M-F2: 측정 불가 — 분기 E 자동 진입 금지, 전문가 검토 요청
  - M-R 존재로 분기 D 최우선 확정. 04-29 관찰 생략 가능 (04-28에 이미 충족).
- ⬜ DB 마이그레이션 불필요 (Redis + env + 문서만 변경, 스키마 변경 없음)

#### Phase 8.5 5거래일 관찰 누적 (2026-04-23 ~ 2026-04-29)

> 관찰 기준: Phase 8.5 Sprint 2 배포(v2.6.1, 2026-04-23) 이후 5거래일.
> 거래일: 04-23(목), 04-24(금), 04-27(월), 04-28(화), 04-29(수).
> 수집 방법: `curl -s "https://api.stockbot.choiji.kr/api/v1/health/observation-daily?date=YYYY-MM-DD"` (관측 전용 unauth API).

| 거래일 | 신호 수(M-S1) | tier 분포(M-S3) | 폴백 발동(M-F1) | 자동 롤백(M-R) | 비고 |
|--------|--------------|----------------|----------------|--------------|------|
| 04-23 | 0 | gap_open=0, prev_high=0, prev_close=0 | 0회 | false | 배포일 |
| 04-24 | 1 | gap_open=0, prev_high=1, prev_close=0 | 253회 / codes: 006340 외 6종 | false | |
| 04-27 | 0 | gap_open=0, prev_high=0, prev_close=0 | 81회 / codes: 008770 외 4종 | false | auto_rollback_check: today=0, prev(04-24)=1 — 2일 연속 미충족 |
| 04-28 | 0 | gap_open=0, prev_high=0, prev_close=0 | 271회 / codes: 042700 외 3종 | **true — 자동 롤백 발동** | triggered_at: 2026-04-28T16:10:00+09:00 / reason: auto_rollback_2d_zero_signals |
| 04-29 | ⬜ 미수집 (분기 D 확정으로 수집 불필요) | — | — | — | 분기 D 확정, 04-29 관찰 생략 가능 |
| **합계** | M-S1= 1 (4일 누적) | M-S3= 1종(prev_high) / 4일 누적 | M-F1= 4일 모두 발동 (605회) | **M-R= true (04-28 16:10 발동)** | auto_rollback_2d_zero_signals (04-27·04-28 연속 0건) |

**부수 관찰**

- ✅ Paper 핫픽스 0건 — `git log --since=2026-04-23 --oneline | grep hotfix` 결과 0건 (Paper 로직 핫픽스 없음. observation-daily-api 핫픽스는 관측 전용 API 추가로 Paper 로직과 무관)
- ⬜ 09:00 일일 리스크 카운터 초기화 로그 5일 연속 — 로그에서 `_reset_daily` 패턴 미발견 (로그 보존 기간 내 04-27 장 시작 정상 확인 — APScheduler job 정상 실행 확인됨)
- ✅ 장중 OHLC 파싱 경고율 < 1% — 04-27 Railway 로그 전체에서 OHLC/ParseError 미발생 (0건)
- ✅ WS 재연결/일일 리포트 중복 발송 재발 없음 — 04-27 로그에서 reconnect/중복 발송 패턴 미발견. 일일 마감 리포트 1회 정상 발송 확인 (06:30:10 KST)

**수집 방법**

hotfix `observation-daily-api` 배포 후 단일 호출로 6개 지표 수집:

```bash
curl -s "https://api.stockbot.choiji.kr/api/v1/health/observation-daily?date=2026-04-24"
```

응답 예시:
```json
{
  "date": "2026-04-24",
  "signals": {"gap_open": 0, "prev_high": 0, "prev_close": 0, "other": 0, "total": 0},
  "fallback": {"triggered_count": 0, "codes": []},
  "rollback": {"is_active": false, "triggered_at": null, "reason": null}
}
```

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
- 5거래일 관찰 의사결정 트리: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` § 5거래일 관찰 종료 후 의사결정 트리
