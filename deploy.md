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

- ⬜ 기능 활성화 검증 (5/7 16:00 ATR 잡 관찰 종료 후, 별도 트리거):
  1. **Railway 환경변수 추가 확인: KOSPI200_MST_SYNC_ENABLED=true** (관찰 신호 보존을 위해 5/7 16:00 이후로 토글 지연)
  2. 다음 영업일 08:10 ETF mst 잡 로그: `KOSPI200 sync 완료: codes=226, marked=226`
  3. production DB: `SELECT COUNT(*) FROM stocks WHERE is_kospi200` ≈ 226
  4. 후속 ATR 잡(08:35) 결과: `metrics:atr:dist:{date}.sample_n ≈ 200+`, `safe_mode:active = None`
  5. 1~2영업일 정상 동작 후 `ATR_COVERAGE_GAP_MAX=30` 원복

- ⬜ Phase 8.6 Sprint 3 착수 전 추가 관찰 (R1 자동 롤백 해제 별도 결정):
  - 5/7 baseline signals ≥ 1 확인 후 `parallel_or_tier:rollback_active` Redis override 해제 → 5/8 거래일 Sprint 2 병렬 OR tier 재시험 → 결과 확인 후 Sprint 3 GO/NO-GO 판정.

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
