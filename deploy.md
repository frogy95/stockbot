# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Hotfix: kospi200-real-200-backfill (2026-05-06, PR #196·#197 머지 + 배포 헬스 검증 완료)

선행 핫픽스 `kospi200-master-backfill`의 잔존 부채(정적 백업 placeholder 200종 중 production 매칭 52종 그침, ATR_COVERAGE_GAP_MAX=200 원복 작업 미등재) 해소. KIS `kospi_code.mst` Part2 char position 162 = KOSPI200 멤버십 플래그 검증 후 자동 동기화 잡 신설.

**브랜치**: `hotfix/kospi200-real-200-backfill` → main → develop

> 선행 핫픽스 `kospi200-master-backfill`의 검증 기록은 `docs/deploy-history/2026-05-06.md`로 아카이빙됨.

- ✅ 자동 검증 완료:
  - pytest tests/test_kis_master.py: 39 passed (10 신규, 0.13초)
  - pytest 전체 회귀: **1069 passed, 0 failed** (10분 49초)
  - 코드 리뷰: 75점 항목 2건(트랜잭션 안전성, deploy.md 형식)을 보강 커밋 `3956f97`로 해소
  - 타겟 API 검증: N/A — 백엔드 비활성 잡 추가
  - Playwright 타겟 검증: N/A — UI 변경 없음

- ✅ 배포 헬스 검증 완료 (2026-05-06 KST 15:30 이후, kill switch off 상태):
  - Railway 자동 배포 성공 — `Application startup complete.` 로그 정상
  - 백엔드 health: `https://api.stockbot.choiji.kr/api/v1/health` → 200, status=healthy, database/redis connected
  - 백엔드 readiness: `/api/v1/health/readiness` → 200, scheduler=running, pipeline=healthy
  - Railway 환경변수 `KOSPI200_MST_SYNC_ENABLED` 미설정 → default `False` → kill switch off (잡 no-op 보장)
  - `ATR_COVERAGE_GAP_MAX=200` 유지 (선행 핫픽스 일시 상향 — KOSPI200 sync 활성화 후 30 원복)
  - Application 부팅 import/config 오류 없음

- ✅ 기능 활성화 검증 완료 (5/7 장마감 후 확인):
  1. ✅ **Railway 환경변수 KOSPI200_MST_SYNC_ENABLED=true** (2026-05-07 장전 설정, 자동 재배포 후 health 200 healthy 확인)
  2. ✅ 5/7 08:11 ETF mst 잡 정상 실행, KOSPI200 is_kospi200 count=226 (정적 200종 → 실제 226종 정상화)
  3. ✅ production DB: is_kospi200 count ≈ 226 (spot-check 5종 005930/000660/005380/035420/035720 k200=True 확인)
  4. ✅ 후속 ATR 잡(08:35) 결과: sample_n=217, ceil=0.066963 (P80×1.2), safe_mode:active=None, fallback_count=0
  5. ⬜ 5/8 sample_n ≥200 안정 확인 후 `ATR_COVERAGE_GAP_MAX=30` 원복

- ⬜ Phase 8.6 Sprint 3 착수 전 추가 관찰:
  - **2026-05-06 PM 관찰 결과**: DEFERRED — R1 rollback active(의도적) + KOSPI200 226종 sync 미실행 → G1/G2/G3 모두 측정 불가.
  - **5/7 1거래일 판정 결과**: **CONDITIONAL GO** ✅
    - G1 ATR 캘리브레이션: PASS (sample_n=217, ceil=0.066963, safe_mode=None, fallback_count=0)
    - G2 병렬 OR 신호: INFO (0건 — 단일 영업일, NO-GO 아님)
    - G3 시뮬-실측 절대차: 측정 불가 (G2 신호 0건으로 산출 모집단 없음, FAIL 아님)
    - R1 자동 롤백: PASS (rollback_active=None), 백엔드 ERROR 0건, safe_mode=None
    - Sprint 3 사전 작업 착수 가능, G2/G3 정식 측정은 5/8 재관찰 필요
  - ⬜ **5/8 장마감 후 재관찰**: G2 신호 발생 여부 + G3 절대차 + portal_supplement/metrics_rollup 잡 실행 확인 → GO 확정

---

### Phase 8.6 Sprint 3 — volume_surge tier + 시간 필터 본 가드 (배포 대기)

**브랜치**: `phase8.6-sprint3` → develop → main
**관련 PR**: (sprint-close 시 생성)

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
- ⬜ 변경: `ATR_COVERAGE_GAP_MAX=30` 원복 (Sprint 2 hotfix에서 200으로 임시 상향한 것)
- ⬜ 제거: `TEMP_TIME_GUARD_SPRINT2` (코드 삭제됨)

**자동 검증 결과** (sprint-review 시점에 갱신):
- ✅ pytest 전체: **1116 passed, 0 failed** (640초, Task 3 대비 신규 47 PASS 추가)
- ✅ tsc: 0 에러
- ✅ Playwright /diagnostics 4종 카드: volume-surge-card + time-filter-card + tier-pass-rate-card + tier-correlation-card 렌더링 확인 (접근성 스냅샷 기반; 스크린샷 타임아웃으로 PNG 미저장)
- ⬜ Alembic 적용 (`f3b1c4d5e201` head): 배포 후 수동 확인

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
- ⬜ 시간 필터 차단 카운터: `redis-cli GET "metrics:time_filter:morning_lockout:$(date +%Y-%m-%d)"` ≥1 — **단, time_filter incr 적재 코드는 Sprint 3 미포함, Sprint 4 또는 hotfix 추가 필요. 본 Task에서 이슈 등록만**
- ⬜ R3 자동 롤백 미발동: `redis-cli GET "auto_rollback:active"` 결과 None 또는 R3 미포함
- ⬜ portal_supplement / metrics_rollup 잡 키 16:10 시점 적재: `redis-cli GET "scheduler:last_portal_supplement"`, `redis-cli GET "scheduler:last_metrics_rollup"` 모두 ISO timestamp

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
