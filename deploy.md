# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Phase 8.6 Sprint 2 — 병렬 OR tier + ATR 분위수 캘리브레이션

브랜치: `phase8.6-sprint2` → develop
PR: https://github.com/frogy95/stockbot/pull/184

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

배포 대상 변경 요약: Sprint 1 직렬 AND tier가 병렬 OR + tier별 독립 sub-게이트로 분리. ATR 5% 고정 상한이 KOSPI200 분위수 동적 상한(P80×1.2, HARD 0.08 캡)으로 전환. 시뮬-실측 통과율 절대차 메트릭(`metrics:quant:sim_vs_real_diff`) 도입.

#### Railway 환경변수 추가 확인 (10종)

- ⬜ `PARALLEL_OR_TIER_ENABLED=true` — Kill-switch 마스터 토글
- ⬜ `ATR_CALIBRATION_ENABLED=true` — 08:35 캘리브레이션 잡 활성화
- ⬜ `ATR_CALIBRATION_METHOD=sma` — `sma`(20일) 또는 `ewma`(λ=0.94)
- ⬜ `ATR_FLOOR=0.025` — ATR 하한 (모든 tier 공통)
- ⬜ `ATR_CEIL_HARD=0.08` — ATR 상한 절대 한계 (gap_open 우회 X)
- ⬜ `ATR_CEIL_FALLBACK=0.05` — 폴백 종목 정적 상한
- ⬜ `ATR_CEIL_MULT=1.2` — P80×mult 계수 (shadow grid 1.0/1.1/1.2/1.3 중 실 진입값)
- ⬜ `ATR_CALIBRATION_WINDOW_DAYS=20`
- ⬜ `TEMP_TIME_GUARD_SPRINT2=true` — 09:00~09:10 / 14:30+ 차단 (Sprint 3에서 본 가드 도입 후 제거)
- ⬜ `SAFE_MODE_TIMEOUT_MIN=120` — 폴백 3단 안전모드 신호 중단(분)

#### Alembic 마이그레이션 적용 (2종)

- ⬜ `c1f2a30b8201` — `stocks.is_kospi200 BOOLEAN NOT NULL DEFAULT FALSE` + `ix_stocks_is_kospi200`
- ⬜ `d2a30b8201ef` — `trade_signals.matched_tiers JSONB NULL` (Kill-switch 시 NULL 안전)

#### Kill-switch 런북 (Phase 8.6 Sprint 2)

##### 즉시 원복 (1줄)

Railway 환경변수 `PARALLEL_OR_TIER_ENABLED=false` 설정 후 backend 재배포. Sprint 1 직렬 동작 100% 복원.

##### 검증 (3단)

1. `curl https://api.stockbot.choiji.kr/api/v1/diagnostics | jq .parallel_or_enabled` → `false` 확인 (또는 `/api/v1/metrics/phase86-status` 응답 확인)
2. PostgreSQL: `SELECT COUNT(*) FROM trade_signals WHERE matched_tiers IS NULL AND created_at >= NOW() - INTERVAL '1 hour';` → 신규 신호 NULL 안전 확인 (Kill-switch 모드에서는 모두 NULL)
3. 텔레그램 신호 발행 확인 — Sprint 1 직렬 동작과 동일한 reject stage 패턴

##### 안전모드 해제 (수동)

```
docker compose exec redis redis-cli DEL safe_mode:active
```

또는 Railway Redis CLI에서 동일 명령. 자동 해제는 `SAFE_MODE_TIMEOUT_MIN=120`분 TTL.

##### 캘리브레이션만 비활성

`ATR_CALIBRATION_ENABLED=false` → 동적 P80 캐싱 무시, 모든 tier에서 정적 `ATR_CEIL_HARD=0.08` 사용. `ATR_FLOOR`/`gap_open HARD`는 그대로 유지.

#### 자동 검증 결과 (sprint-review에서 갱신)

- ⬜ pytest 전체 PASS — sprint-review 시점 실측
- ⬜ `npx tsc --noEmit` 에러 0건
- ⬜ env 토글 OFF 회귀 0건 (`PARALLEL_OR_TIER_ENABLED=false` + `ATR_CALIBRATION_ENABLED=false` + `TEMP_TIME_GUARD_SPRINT2=false`)
- ⬜ tier 카드 2종 (`/diagnostics`) Playwright 시각 검증
- ⬜ `/api/v1/metrics/tier-correlation` / `tier-pass-rate` / `sim-vs-real-diff` 200 응답

#### 관찰 항목 (Sprint 3 착수 게이트, 종료 조건 X)

- ⬜ Paper 1거래일 (2026-04-30) ATR 캘리브레이션 잡 → Redis 4종 키(`metrics:atr:ceil`/`dist`/`ceil_grid`/`fallback_count`) 적재
- ⬜ 병렬 OR tier 신호 1건 이상 + `matched_tiers` 메타데이터 JSON 기록
- ⬜ 시뮬-실측 절대차 ≤0.15 유지 (≥0.15 시 텔레그램 알림 + 분기 D 회귀 의심)
- ⬜ L5 사전 시뮬: `docs/phase/phase8.6/sprint2/atr_floor_simulation.md` (fail율 추정 35~45% < 60% → ATR_FLOOR=0.025 시작값 유지)

배포 모드: Paper — Sprint 3에서 시간 필터 본 가드 + volume_surge tier 도입 후 LIVE 전환 검토

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
- 5거래일 관찰 의사결정 트리: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` § 5거래일 관찰 종료 후 의사결정 트리
