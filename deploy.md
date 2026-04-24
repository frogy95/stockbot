# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Phase 8.5 Sprint 2.5 — 인프라 보강 + 관측성·문서 정합성 (2026-04-23)

브랜치: `phase8.5-sprint3` → develop
PR: https://github.com/frogy95/stockbot/pull/172

#### 자동 검증 결과 (2026-04-23)

- ✅ pytest 전체: 963 passed / 1 failed (기존 플레이크 `test_ws_manager_env_max_subscriptions`, Sprint 2.5 무관)
- ✅ frontend tsc --noEmit: 에러 0건
- ✅ API `/api/v1/metrics/override-status`: 인증 가드 정상 (미인증 시 "인증 토큰이 필요합니다")
- ✅ `python scripts/check_env_sync.py`: `OK: 39 variables synced` (exit 0)
- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

#### 수동 검증 필요 항목 (Railway 프로덕션 배포 후)

- ⬜ `SETTINGS_OVERRIDE_ENABLED=True` Railway 반영 확인
- ⬜ Sprint 2 env 8종(`MIN_VOLUME_FLOOR_MODE` 외) Railway에 존재 확인 (Sprint 2 배포 시 반영되었어야 함 — 재확인 목적)
- ⬜ `python scripts/check_env_sync.py` 로컬 실행 결과 exit 0
- ⬜ Playwright `/diagnostics` 스크린샷 — 배너 미렌더 정상 상태
- ⬜ 5거래일 관찰 종료 후 의사결정 트리(A~E) 판정: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` 하단 참조
- ⬜ DB 마이그레이션 불필요 (Redis + env + 문서만 변경, 스키마 변경 없음)

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
- 5거래일 관찰 의사결정 트리: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` § 5거래일 관찰 종료 후 의사결정 트리
