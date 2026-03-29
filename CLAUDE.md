# choiji-guide-big

Claude Code 설정 예제 + 개발 프로세스 템플릿 프로젝트입니다.

## 저장소

- **원격 저장소**: [https://github.com/frogy95/choiji-guide-big.git](https://github.com/frogy95/choiji-guide-big.git)

## 언어 및 커뮤니케이션 규칙

- 기본 응답 언어: 한국어
- 코드 주석: 한국어로 작성
- 커밋 메시지: 한국어로 작성
- 문서화: 한국어로 작성
- 변수명/함수명: 영어 (코드 표준 준수)

## Bash 명령 실행 규칙

bash-guard hook(`.claude/hooks/pretooluse-bash-guard.sh`)이 다음을 자동 차단합니다:
- `cd /path &&` 체이닝, main/develop 직접 push, force push, `git reset --hard`, 비정상 브랜치명

## 개발 프로세스

프로세스 상세는 `docs/dev-process.md` 참조. 스프린트/핫픽스 워크플로우 규칙은 `.claude/rules/sprint-workflow.md` 참조.

### 프로젝트 라이프사이클
```
PRD → prd-to-roadmap → ROADMAP.md (Phase 구조)
  → phase-planner → docs/phase/phase{N}/phase{N}.md (전문가 검토 + 확정 파라미터)
    → sprint-planner → docs/phase/phase{P}/sprint{N}/sprint{N}.md (실행 명세서)
      → 구현 → sprint-close → sprint-review → deploy-prod
```

### 핵심 원칙

- **수정사항 → Hotfix vs Sprint 의사결정 먼저**: `docs/dev-process.md` 섹션 2 기준
- **sprint{N}.md가 Single Source of Truth** — Task를 순서대로 실행
- **worktree 사용 금지**: `git checkout -b phase{P}-sprint{N}` 으로 브랜치 생성
- **karpathy-guidelines** 준수
- **검증 원칙**: `docs/dev-process.md` 섹션 5 참조
- 배포 후 수동 작업: `deploy.md` 참조 (완료 기록은 `docs/deploy-history/` 아카이브)

## 에이전트 사용 규칙

다음 요청에는 반드시 **Agent 도구**(`subagent_type` 파라미터)로 해당 에이전트를 호출한다. **Skill 도구로 호출하지 않는다** — 이들은 `.claude/agents/` 디렉토리의 커스텀 에이전트이며 스킬이 아니다. 직접 탐색/계획하지 않는다.

| 요청 | Agent subagent_type |
|------|---------------------|
| 스프린트 계획 | `sprint-planner` |
| 스프린트 마무리 (PR 생성) | `sprint-close` |
| 스프린트 리뷰 (코드 리뷰 + 검증) | `sprint-review` |
| Phase 계획 | `phase-planner` |
| PRD → 로드맵 | `prd-to-roadmap` |
| 프로덕션 배포 | `deploy-prod` |
| 핫픽스 마무리 | `hotfix-close` |

## 경로별 상세 규칙

- 백엔드: `.claude/rules/backend.md`
- 프론트엔드: `.claude/rules/frontend.md`
- 스프린트 워크플로우: `.claude/rules/sprint-workflow.md`
- Notion 문서 관리: `.claude/rules/notion.md`

## 체크리스트 작성 형식

- 완료 항목: `- ✅ 항목 내용`
- 미완료 항목: `- ⬜ 항목 내용`
- GFM `[x]`/`[ ]` 대신 이모지를 사용하여 마크다운 미리보기에서 시각적 구분을 보장합니다.

## Notion 기술 문서 관리

상세 규칙은 `.claude/rules/notion.md` 참조. 업데이트 트리거는 `docs/dev-process.md` 섹션 8.5 참조.
