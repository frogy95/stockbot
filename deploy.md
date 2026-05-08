# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### 프로덕션 배포 - v2.9.0 (2026-05-07)

포함 스프린트: Phase 8.6 Sprint 3
PR: https://github.com/frogy95/stockbot/pull/201

- ✅ Vercel 프론트엔드 자동 배포 (PR merge 후 자동 기동)
- ✅ Railway 백엔드 자동 배포 (PR merge 후 자동 기동)

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

---

### Phase 8.6 Sprint 3 — volume_surge tier + 시간 필터 본 가드 (배포 대기)

**브랜치**: `phase8.6-sprint3` → develop → main
**관련 PR**: #200 (develop)

> 선행 Hotfix `kospi200-real-200-backfill` 검증 기록은 `docs/deploy-history/2026-05-08.md`로 아카이빙됨.

**Railway 환경변수 (수동 추가/변경/제거 필요)**:
- ⬜ 추가: `VOLUME_SURGE_ENABLED=true`
- ⬜ 추가: `VOLUME_SURGE_DRY_RUN=true` (Sprint 4 G-Bt1~3 통과 전 false 금지)
- ⬜ 추가: `VOLUME_SURGE_VOL_RATIO=5.0`
- ⬜ 추가: `VOLUME_SURGE_BID_ASK_RATIO=2.0`
- ⬜ 추가: `VOLUME_SURGE_PRICE_THRESHOLD=0.005`
- ⬜ 추가: `VOLUME_SURGE_POSITION_SIZE=0.30`
- ⬜ 추가: `TIME_FILTER_ENABLED=true`
- ⬜ 추가: `SIGNAL_PRIORITY_QUEUE_ENABLED=true`
- ⬜ 변경: `AUTO_ROLLBACK_R3_ENABLED=true` (코드 기본값 True로 변경됨, 환경변수도 일치 확인)
- ⬜ 변경: `ATR_COVERAGE_GAP_MAX=30` 원복 (Sprint 2 hotfix에서 200으로 임시 상향한 것 — 5/7~5/8 sample_n ≥200 안정 확인 완료)
- ⬜ 제거: `TEMP_TIME_GUARD_SPRINT2` (코드 삭제됨)

**자동 검증 결과** (sprint-review 2026-05-08):
- ✅ pytest 전체: **1116 passed, 0 failed** (635초, sprint-review 재실행 완료)
  - 이전 세션 GroupingError 발견(metrics volume-surge-stats GROUP BY) → fix 커밋 aca388a 적용 후 재검증
  - Sprint 3 신규 43개 테스트 PASS 포함
- ✅ Phase 7.0 CI grep 가드: 0줄 (LIVE 파라미터 우회 없음)
- ✅ TEMP_TIME_GUARD_SPRINT2 잔재 grep: 0건 (완전 제거 확인)
- ✅ API 검증: `/api/v1/metrics/volume-surge-stats` + `/api/v1/metrics/time-filter-stats` 정상 응답 (인증 포함)
- ✅ Playwright /diagnostics 4종 카드: volume-surge-card + time-filter-card 렌더링 확인 (접근성 스냅샷 기반; 스크린샷 타임아웃으로 PNG 미저장 — 수동 캡처 권장)
- ✅ 코드 리뷰 (섹션 7 체크리스트): 이슈 없음 — 보안/성능/품질/테스트/패턴 모두 통과
  - dry_run 신호: OrderExecutor.place_order 호출 차단 확인 (_handle_volume_surge_signal 메서드 분기)
  - 일일 한도: dry_run 경로에서 incr_daily_trade_count 미호출 확인 (체결 콜백에서만 증가)
  - 우선순위 큐 토글: SIGNAL_PRIORITY_QUEUE_ENABLED=false 시 병렬 OR 동작 복원 확인
- ✅ Alembic 왕복 테스트 (`f3b1c4d5e201` head): downgrade -1 → upgrade head 성공 (로컬 docker 검증 완료)
- ✅ tsc 타입 체크: 0 에러 (로컬 docker frontend 검증 완료)

**Kill-switch 런북**:

`volume_surge` 신호 폭증 시:
```
railway variables --set "VOLUME_SURGE_ENABLED=false"
# 즉시 적용 — 신호 발행 차단
```

시간 필터 오작동 시:
```
railway variables --set "TIME_FILTER_ENABLED=false"
# Sprint 2 동작과 동등 (시간대 차단 미적용)
```

dry_run → LIVE 토글 (⚠️ Sprint 4 G-Bt1~3 통과 후에만):
```
railway variables --set "VOLUME_SURGE_DRY_RUN=false"
# Sprint 4 walk-forward + Bootstrap CI 하한 ≥1 + Paper 5거래일 G-A·G-B 충족 동시 확인 필수
```

우선순위 큐 비활성화 (병렬 OR 동작 복원):
```
railway variables --set "SIGNAL_PRIORITY_QUEUE_ENABLED=false"
```

**Paper 1거래일 관찰 항목** (배포 후 다음 영업일 16:30 KST):
- ⬜ `volume_surge` dry_run 신호 1건 이상: `SELECT COUNT(*) FROM trade_signals WHERE strategy_name='volume_surge' AND dry_run=true AND created_at::date = current_date`
- ⬜ 호가창 Redis 키 적재: `redis-cli SCAN 0 MATCH "realtime:*:orderbook" COUNT 50` 결과 ≥10종
- ⬜ 5분봉 vol5m 적재: `redis-cli SCAN 0 MATCH "vol5m:*:$(date +%Y%m%d):*" COUNT 100` 결과 ≥10종
- ⬜ 시간 필터 차단 카운터: `redis-cli GET "metrics:time_filter:morning_lockout:$(date +%Y-%m-%d)"` ≥1 — **단, time_filter incr 적재 코드는 Sprint 3 미포함, Sprint 4 또는 hotfix 추가 필요**
- ⬜ R3 자동 롤백 미발동: `redis-cli GET "auto_rollback:active"` 결과 None 또는 R3 미포함
- ⬜ portal_supplement / metrics_rollup 잡 키 16:10 시점 적재: `redis-cli GET "scheduler:last_portal_supplement"`, `redis-cli GET "scheduler:last_metrics_rollup"` 모두 ISO timestamp

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
