# Phase 8.6 Sprint 1 — 통합 검증 결과

작성일: 2026-04-29
브랜치: `phase8-sprint1` → develop 머지 예정
LIVE 게이트: **Sprint 1 완료 ≠ LIVE 전환** (합의 재확인)

---

## 1. 전체 pytest 결과

```
1001 passed, 1 failed, 74 warnings in 613.60s (0:10:13)
```

- 실패 1건: `tests/test_ws_stability.py::test_ws_manager_env_max_subscriptions`
  - 사유: PAPER `max_ws_subscriptions` env 기본값이 20으로 등록되어 테스트 기대값(25)과 불일치
  - **본 Sprint 변경분과 무관** (Phase 8.6 Sprint 1은 WS subscription 변경 없음)
  - Sprint 2 또는 별도 hotfix로 해결 (테스트 기대값 갱신 또는 env 기본값 정렬)
- Sprint 1 신규/회귀 검증 전체 PASS:
  - G1 메타데이터 전파: 6 PASS (`tests/test_g1_fallback_metadata_propagation.py`)
  - G2 자동 롤백 R1~R4: 13 PASS (`tests/safety/test_auto_rollback.py`)
  - G3 회로차단기: 9 PASS (`tests/safety/test_circuit_breaker.py`)
  - SignalGenerator/scheduler 회귀 64 PASS

## 2. 프론트엔드 타입체크

```
docker compose exec -T frontend npx tsc --noEmit
EXIT=0
```

- 0 errors. M-F2 카드 + R1~R4 멀티 트리거 카드 신규 컴포넌트 포함.

## 3. Alembic 왕복 테스트 (PR 머지 게이트)

Task 3 시점 검증 — 3단계 모두 성공:
- `alembic upgrade head` (b8f1c2a30201 적용 → fallback 컬럼 + `ix_trade_signals_fallback_created`)
- `alembic downgrade -1` (인덱스 → 컬럼 순서로 안전 롤백)
- `alembic upgrade head` 재적용

서버 디폴트 `false`로 NULL→False 자동 처리. 별도 UPDATE 백필 불필요.

## 4. CI grep 가드 (주문 실행 경로 변경 0줄)

본 Sprint는 `core/clients/kis_rest.py` / `modules/trading/order_manager.py`의 LIVE 토글·하드코딩에 손대지 않았다.
sprint-review에서 다음 명령으로 재확인:

```bash
git diff develop...HEAD -- backend/modules/trading/order_manager.py backend/core/clients/kis_rest.py \
  | grep -E "(max_position|position_size|daily_max_loss|emergency_stop|TRADING_ENV|live)"
# 기대: 0줄
```

`order_manager.py` 변경분은 G1 메타데이터 전파(`fallback=signal.fallback`)만 — 위 패턴 매칭 없음.

## 5. DoR 4종 + P0 보강 5건

| # | 항목 | 결과 |
|---|------|------|
| DoR §3 G1 | is_fallback 메타데이터 전파 + DB 컬럼 + M-F2 API | ✅ Task 3 |
| DoR §3 G2 | R1~R4 OR 자동 롤백 + 16:10 평가 + Phase 8.5 격리 | ✅ Task 4 |
| DoR §3 G3 | 1차→2차 통과율 회로차단기 + counter pair + Phase 8.5 폴백 동시 차단 | ✅ Task 5 |
| Phase 7.0 잠금 | Final + 런타임 assert 이중 가드 | ✅ Task 1 |
| P0 #1 (Critical) | G3 counter pair 동시 적재 + 분모=0 fail-safe | ✅ Task 5 — `test_zero_denominator_fails_safe_to_circuit_on` PASS |
| P0 #2 | R4 baseline `screener:candidates:primary:{date}` TTL 30d | ✅ Task 4 — scheduler `_primary_screen` 종점 적재 |
| P0 #3 (Critical) | G3 청산 신호 보존 (entry만 차단) | ✅ Task 5 — exit/stop_loss/take_profit + signal_type==sell 통과 검증 |
| P0 #4 (Critical) | dry_run 가드 이중화 (Final + 런타임 assert + grep 가드) | ✅ Task 1 |
| P0 #5 | Alembic 왕복 테스트 PR 게이트 + 백필 정책 명시 | ✅ Task 3 — 3단계 통과 |

## 6. Paper 1거래일 회귀

본 Sprint는 인프라 가드레일만 추가. Paper 회귀는 다음 거래일 (2026-04-30 목 또는 2026-05-04 월) Railway 배포 후 다음 항목으로 검증:

- `signals.fallback=true` 1건 이상 DB 기록 (M-F2 분자)
- `GET /api/v1/metrics/fallback-signal-rate?date=YYYY-MM-DD` 응답 정상
- `screener:candidates:primary:{date}`, `screener:candidates:total/passed:{date}` Redis 키 존재
- `/diagnostics` 페이지에 두 신규 카드 정상 렌더

## 7. Railway 환경변수 등록 (10종 — deploy.md 미완료 항목)

| 변수 | 기본값 | 비고 |
|------|--------|------|
| `SECONDARY_POOL_FALLBACK_THRESHOLD` | 5 | 분기 D 풀 협소 대응 (3→5) |
| `SECONDARY_POOL_FALLBACK_BACKFILL_HARD_CAP` | 5 | 보강 종목수 상한 |
| `AUTO_ROLLBACK_ENABLED` | true | 마스터 토글 |
| `AUTO_ROLLBACK_R1_ENABLED` | true | 신호 0건 3일 |
| `AUTO_ROLLBACK_R2_ENABLED` | true | 폴백 발동 3일 (v0) |
| `AUTO_ROLLBACK_R3_ENABLED` | **false** | tier ≤1 5일 (Sprint 2 후 true) |
| `AUTO_ROLLBACK_R4_ENABLED` | true | 폴백 비중 ≥70% 1일 |
| `CIRCUIT_BREAKER_ENABLED` | true | G3 마스터 토글 |
| `CIRCUIT_BREAKER_PASS_RATE_THRESHOLD` | 0.10 | 1차→2차 통과율 임계 |
| `CIRCUIT_BREAKER_CONSECUTIVE_DAYS` | 3 | 발동 연속 일수 |

## 8. 잔존 리스크 (Sprint 2 이관 — 합의됨)

1. R2 v0 단순화 — 가중 streak / 분모 정확화 Sprint 2 보강. `auto_rollback.py` TODO 주석 명시.
2. R3 기본 비활성 — Sprint 2 병렬 OR 완료 후 true 전환. tier label은 메타데이터로만 적재.
3. is_fallback 종목 별도 포지션 한도 — Sprint 2 risk_manager 동반 작업.
4. Alembic 일반 회귀 — Task 3 PR 게이트로 차단.

## 9. 결론

- 본 Sprint 1의 모든 Task(1~7)는 합의된 DoR 4종 + P0 보강 5건을 충족한다.
- LIVE 전환 게이트(Sprint 2 R2 v1 / R3 OR + Sprint 4 walk-forward 60일)는 별도 PR + sprint-review에서 다시 검증한다.
- develop 머지 후 Railway env 10종 등록 + 1거래일 Paper 회귀 후 Sprint 2 착수 가능.
