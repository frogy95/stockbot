# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 — v1.9.0 (2026-04-14)

포함 스프린트: Phase 6.2 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/128

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 자동 검증 완료 (sprint-review 결과)

- ✅ pytest: 805 passed, 0 failed
- ✅ /api/v1/health: healthy (database: connected, redis: connected)
- ✅ /api/v1/collector/status: running=True, job_count=8
- ✅ portal_supplement job 등록 확인
- ✅ Playwright UI 검증 정상
- ✅ 코드 리뷰: Critical/High/Medium 이슈 없음

#### 수동 검증 항목 (배포 후 확인 필요)

- ✅ /api/v1/health 헬스체크 확인 (프로덕션) — healthy, database: connected, redis: connected
- ✅ 주요 페이지 접속 확인 — 307 redirect 정상, job_count=8, portal_supplement 등록 확인
- ✅ 16:00 포털 보조 수집 cron 동작 확인 — 2026-04-14 16:00 KST, 2882종목 수집 완료 (기준일: 20260413)
- ✅ 08:00 KIS 직접 수집 정상 동작 확인 — 2026-04-15 08:00 KST, 2113/2641 수집 (validation=PASS), 전체 파이프라인 888.8초
- ✅ 08:30 KIS 재시도 동작 확인 — premarket 성공 상태이므로 즉시 스킵 (정상)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
