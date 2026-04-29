# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Sprint: phase8.6/sprint1 — LIVE 보호 가드레일 (G1+G2+G3 + Phase 7.0 잠금)

브랜치: `phase8-sprint1` (develop 머지 예정)
PR: https://github.com/frogy95/stockbot/pull/181

#### sprint-review 상태

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

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

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
- 5거래일 관찰 의사결정 트리: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` § 5거래일 관찰 종료 후 의사결정 트리
