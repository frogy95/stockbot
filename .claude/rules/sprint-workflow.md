---
paths:
  - "docs/phase/**"
  - "ROADMAP.md"
  - "deploy.md"
---

# 스프린트/핫픽스 워크플로우 규칙

> **프로세스 상세**: `docs/dev-process.md` §3(Sprint), §4(Hotfix), §2(판단 기준) 참조
> **검증 매트릭스**: `docs/dev-process.md` §5 참조

## 핵심 규칙

- 모든 Sprint는 반드시 **Phase를 경유** — Phase 문서가 먼저 존재해야 Sprint 시작 가능
- sprint{N}.md가 **Single Source of Truth** — Task를 순서대로 실행
- 브랜치: `git checkout -b phase{P}-sprint{N}` (develop 기반)
- **worktree 사용 금지**
- 커밋 메시지에 **task ID 필수** (PostToolUse hook이 index.json 자동 동기화)
- Hotfix vs Sprint 판단: `docs/dev-process.md` §2 기준
- **신규 환경변수**: 프로덕션(Railway) 수동 설정이 필요한 환경변수를 추가했다면 sprint-close/hotfix-close 마무리 시 deploy.md 수동 검증 항목에 `Railway 환경변수 추가 확인: VAR_NAME` 형식으로 기록

## 에이전트 역할 분담

| 단계 | 에이전트 | PR 대상 | 핵심 산출물 |
|------|---------|---------|------------|
| 계획 | sprint-planner | — | sprint{N}.md |
| 구현 | /sprint-dev | — | 코드 + 커밋 |
| 마무리 | sprint-close | **develop** | PR + ROADMAP 업데이트 |
| 리뷰 | sprint-review | — | deploy.md 검증 결과 |
| 배포 | deploy-prod | **main** | develop→main PR |
| 핫픽스 | hotfix-close | **main** | main PR 자동 머지 + develop 역머지 자동 머지 |

## 문서 구조

- Phase 문서: `docs/phase/phase{P}/phase{P}.md`
- 실행 명세서: `docs/phase/phase{P}/sprint{N}/sprint{N}.md`
- Task 문서: `docs/phase/phase{P}/sprint{N}/task{N}/task{N}.md`
- 첨부 파일 (스크린샷, 보고서 등): `docs/phase/phase{P}/sprint{N}/task{N}/`
