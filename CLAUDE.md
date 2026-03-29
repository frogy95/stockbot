# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Claude Code 에이전트 기반 개발 프로세스 템플릿. 7개 전문 에이전트와 훅 시스템으로 Phase-Sprint-Task 계층 워크플로우를 자동화한다.

- **원격 저장소**: [https://github.com/frogy95/stockbot.git](https://github.com/frogy95/stockbot.git)
- **예정 기술 스택**: Python(FastAPI) + Next.js + PostgreSQL + Redis + Docker Compose

## 언어 및 커뮤니케이션 규칙

- 기본 응답 언어: 한국어
- 코드 주석/커밋 메시지/문서: 한국어
- 변수명/함수명: 영어

## 주요 명령어

```bash
# 환경 구성
cp .env.example .env            # 환경변수 설정
docker compose up -d            # 전체 서비스 기동

# 개발 서버
docker compose up backend -d    # 백엔드만 기동
docker compose up frontend -d   # 프론트엔드만 기동

# 스프린트 구현 (커스텀 커맨드)
/sprint-dev {P}-{N}             # Phase P의 Sprint N 구현 실행
/restart [service]              # Docker 서비스 재시작 (backend|frontend|db|all)
/dashboard                      # 프로젝트 대시보드 열기
```

## Bash 명령 실행 규칙

bash-guard hook(`.claude/hooks/pretooluse-bash-guard.sh`)이 자동 차단:
- `cd /path &&` 체이닝, main/develop 직접 push, force push, `git reset --hard`, 비정상 브랜치명

## Git 브랜치 전략

- `main`: 프로덕션 배포 (직접 push 금지, PR만 허용)
- `develop`: 통합 브랜치 (직접 push 금지, PR만 허용)
- `phase{P}-sprint{N}`: 스프린트 작업 브랜치 (`git checkout -b`로 생성, worktree 사용 금지)
- `hotfix/*`: 긴급 수정 브랜치

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

| 요청 | Agent subagent_type | 모델 |
|------|---------------------|------|
| PRD → 로드맵 | `prd-to-roadmap` | Opus |
| Phase 계획 | `phase-planner` | Opus |
| 스프린트 계획 | `sprint-planner` | Opus |
| 스프린트 마무리 (PR 생성) | `sprint-close` | Sonnet |
| 스프린트 리뷰 (코드 리뷰 + 검증) | `sprint-review` | Sonnet |
| 프로덕션 배포 | `deploy-prod` | Sonnet |
| 핫픽스 마무리 | `hotfix-close` | Sonnet |

## 문서 구조

```
docs/
├── dev-process.md          # 개발 프로세스 전체 가이드 (10개 섹션)
├── ci-policy.md            # CI/CD 정책 (Docker 태깅, 롤백)
├── setup-guide.md          # 환경 셋업 가이드
├── prompt-guide.md         # 바이브 코딩 프롬프트 가이드
├── index.json              # 프로젝트 상태 추적 (phases, hotfixes, deployHistory)
├── phase/phase{N}/         # Phase 문서 + 하위 Sprint 문서
├── hotfix/                 # 핫픽스 문서
├── deploy-history/         # 배포 기록 아카이브
└── templates/              # PRD, Sprint, Phase, Task 등 문서 템플릿
```

## 경로별 상세 규칙

- 백엔드: `.claude/rules/backend.md`
- 프론트엔드: `.claude/rules/frontend.md`
- 스프린트 워크플로우: `.claude/rules/sprint-workflow.md`
- Notion 문서 관리: `.claude/rules/notion.md`

## 훅 시스템

- **PreToolUse (bash-guard)**: 위험 명령 차단 (force push, hard reset, 잘못된 브랜치명 등)
- **Stop (doc-checker)**: 에이전트 완료 전 필수 파일 업데이트 검증 (`docs/index.json`, `deploy.md`, `MEMORY.md` 등)
- 검증 규칙 상세: `.claude/hooks/lib/doc-rules.json`

## 체크리스트 작성 형식

- 완료 항목: `- ✅ 항목 내용`
- 미완료 항목: `- ⬜ 항목 내용`
- GFM `[x]`/`[ ]` 대신 이모지 사용

## Notion 기술 문서 관리

상세 규칙은 `.claude/rules/notion.md` 참조. 업데이트 트리거는 `docs/dev-process.md` 섹션 8.5 참조.
