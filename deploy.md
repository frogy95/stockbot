# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: Claude Code 설정 파일 컨텍스트 중복/상충 정리 (2026-03-28)

PR: https://github.com/frogy95/choiji-guide-big/pull/3

- ✅ 자동 검증 완료 항목:
  - pytest: 해당 없음 (설정/문서 파일만 변경)
  - 타겟 API 검증: 해당 없음 (코드 변경 없음)
  - Playwright 타겟 검증: 해당 없음 (UI 변경 없음)

- ⬜ 수동 검증 필요 항목:
  - Docker 미실행으로 자동 검증 미수행 — main merge 후 `docker compose up --build` 로 재시작 시 설정 파일이 정상 로드되는지 확인
  - restart.md의 `cd /path &&` 패턴 제거 후 `/restart` 커맨드 정상 동작 확인 (Docker 실행 환경에서)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
