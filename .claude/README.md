# `.claude/` — LLM 하네스

**역할**: LLM이 "어떻게 행동할지"를 정의한다. 에이전트, 훅, 실행 규칙, 커맨드, 세션 메모리로 구성된다.

**주 소비자**: Claude Code (LLM)

**콘텐츠 성격**: 실행 규칙 — 프로세스·컨벤션·자동화. 대체로 불변이며 버전 관리된다.

## 구조

| 경로 | 목적 |
|------|------|
| `agents/` | 커스텀 에이전트 정의 (deploy-prod, sprint-*, hotfix-close, phase-planner, prd-to-roadmap) |
| `commands/` | 슬래시 커맨드 (`/sprint-dev`, `/restart`, `/dashboard`, `/context-audit`) |
| `rules/` | 경로·상황별 실행 규칙 (backend, frontend, sprint-workflow, dev-process, ci-policy) |
| `hooks/` | PreToolUse/Stop 훅 스크립트 + 검증 룰 |
| `agent-memory/` | 에이전트별 세션 간 메모리 |
| `settings.json` | Claude Code 설정 |
| `feedback.md` | 하네스 개선 백로그 |

## 다른 자산과의 관계

- **`wiki/`** — 도메인 지식 참조 (LLM이 작업 중 필요한 시스템 현재 상태를 `@wiki/`로 로드).
- **`docs/`** — 불변 아티팩트 생성/참조 (Phase 스펙, 배포 히스토리, 핫픽스 기록 등).
