# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

한국 주식/ETF 단타 자동 매매 시스템. 자동 종목 스크리닝, 매매 신호 분석, 주문 실행(반자동/완전자동), 웹 대시보드, 텔레그램 알림을 제공한다.

- **원격 저장소**: https://github.com/frogy95/stockbot.git
- **기술 스택**: Python 3.12(FastAPI) + Next.js(App Router) + PostgreSQL 16 + Redis 7
- **인프라**: Vercel (프론트엔드) + Railway (백엔드 + PostgreSQL + Redis) + Cloudflare (도메인/DNS)
- **PRD**: `docs/prd.md` | **로드맵**: `ROADMAP.md`

## 자산 구조

프로젝트의 지식/설정 자산은 세 곳에 역할별로 분리되어 있다. 상세는 각 루트의 `README.md` 참조.

- **`.claude/`** — LLM 실행 규칙 (에이전트, 훅, 경로별 규칙, 커맨드). 진입점: `.claude/README.md`
- **`wiki/`** — 시스템 현재 상태 지식 베이스 (아키텍처, 데이터 흐름, 도메인 개념). 진입점: `@wiki/index.md`
- **`docs/`** — 불변 아티팩트 (PRD, Phase 스펙, 배포 히스토리) + 사용자 가이드. 진입점: `docs/README.md`

## 언어 및 커뮤니케이션 규칙

- 기본 응답 언어: 한국어
- 코드 주석/커밋 메시지/문서: 한국어
- 변수명/함수명: 영어

## 주요 명령어

```bash
# 로컬 개발 환경 (Docker Compose)
cp .env.example .env            # 환경변수 설정
docker compose up -d            # 전체 서비스 기동 (FastAPI, Next.js, PostgreSQL, Redis)

# 개발 서버
docker compose up backend -d    # 백엔드만 기동
docker compose up frontend -d   # 프론트엔드만 기동

# 백엔드 테스트/마이그레이션
docker compose exec backend pytest -v              # 전체 테스트
docker compose exec backend pytest tests/test_x.py # 단일 파일 테스트
docker compose exec backend alembic upgrade head    # DB 마이그레이션

# 프론트엔드 타입 체크
docker compose exec frontend npx tsc --noEmit

# 커스텀 커맨드
/sprint-dev {P}-{N}             # Phase P의 Sprint N 구현 실행
/restart [service]              # Docker 서비스 재시작 (backend|frontend|db|all)
/dashboard                      # 프로젝트 대시보드 열기
/context-audit                  # 컨텍스트 자산 감사 (중복/상충/고아 파일 검출)
```

## 시스템 아키텍처 / 데이터 흐름 / 외부 API

상세는 `wiki/`를 참조한다 (현재 상태 지식 베이스):

- 시스템 구성: `@wiki/system-overview.md`, `@wiki/tech-stack.md`, `@wiki/module-structure.md`
- 데이터 수집 흐름 (Mermaid 포함): `@wiki/data-collection-flow.md`
- 매매 실행 흐름: `@wiki/signal-generation.md`, `@wiki/order-execution.md`, `@wiki/trading-modes.md`
- 모의/실전 전환: `@wiki/paper-vs-live.md`
- 외부 API 의존성 (Rate Limit, 환경변수, 인증): `@wiki/external-apis.md`

## Bash 명령 실행 규칙

bash-guard hook(`.claude/hooks/pretooluse-bash-guard.sh`)이 자동 차단:
- `cd /path &&` 체이닝, main/develop 직접 push, force push, `git reset --hard`, 비정상 브랜치명
- 허용 브랜치: `phase{P}-sprint{N}`, `hotfix/*`, `chore/*`, `docs/*`, `refactor/*`

## Git 브랜치 전략

`main`/`develop` 직접 push 금지, PR만 허용. 상세: `.claude/rules/dev-process.md` §1, `.claude/rules/ci-policy.md`

## 개발 프로세스

프로세스 상세는 `.claude/rules/dev-process.md` 참조. 스프린트/핫픽스 워크플로우 규칙은 `.claude/rules/sprint-workflow.md` 참조.

### 프로젝트 라이프사이클

```
PRD → prd-to-roadmap → ROADMAP.md (Phase 구조)
  → phase-planner → docs/phase/phase{N}/phase{N}.md (전문가 검토 + 확정 파라미터)
    → sprint-planner → docs/phase/phase{P}/sprint{N}/sprint{N}.md (실행 명세서)
      → 구현 → sprint-close → sprint-review → deploy-prod
```

### 핵심 원칙

- **수정사항 → Hotfix vs Sprint 의사결정 먼저**: `.claude/rules/dev-process.md` 섹션 2 기준
- **karpathy-guidelines** 준수
- **검증 원칙**: `.claude/rules/dev-process.md` 섹션 5 참조
- 배포 후 수동 작업: `deploy.md` 참조 (완료 기록은 `docs/deploy-history/` 아카이브)
- 브랜치/워크플로우 상세 규칙: `.claude/rules/sprint-workflow.md` 참조

## 에이전트 사용 규칙

다음 요청에는 반드시 **Agent 도구**(`subagent_type` 파라미터)로 해당 에이전트를 호출한다. **Skill 도구로 호출하지 않는다** — 이들은 `.claude/agents/` 디렉토리의 커스텀 에이전트이며 스킬이 아니다. 직접 탐색/계획하지 않는다.

| 요청 | Agent subagent_type | 모델 |
|------|---------------------|------|
| PRD → 로드맵 | `prd-to-roadmap` | Opus |
| Phase 계획 | `phase-planner` | Opus |
| 스프린트 계획 | `sprint-planner` | Opus |
| 스프린트 마무리 (PR 생성) | `sprint-close` | Sonnet |
| 스프린트 리뷰 (코드 리뷰 + 검증) | `sprint-review` | Sonnet |
| PR 이슈 수정 + 재리뷰 | `sprint-pr-fix` | Sonnet |
| 프로덕션 배포 | `deploy-prod` | Sonnet |
| 핫픽스 마무리 | `hotfix-close` | Sonnet |

## 경로별 상세 규칙

- 백엔드: `.claude/rules/backend.md`
- 프론트엔드: `.claude/rules/frontend.md`
- 스프린트 워크플로우: `.claude/rules/sprint-workflow.md`
- 개발 프로세스: `.claude/rules/dev-process.md`
- CI/CD 정책: `.claude/rules/ci-policy.md`
- Notion 문서 관리: Notion 설정 시 `.claude/rules/notion.md` 생성 예정

## 하네스 피드백 수집

- **피드백 파일**: `.claude/feedback.md` — skill/agent/hook/rule 개선 백로그
- 세션 중 "피드백 기록해줘: ~~" 라고 하면 해당 파일 `미반영` 섹션에 추가
- 반영은 사용자가 수동으로 진행, 반영 후 `반영 완료` 섹션으로 이동

## 훅 시스템

- **PreToolUse (bash-guard)**: 위험 명령 차단 (force push, hard reset, 잘못된 브랜치명 등)
- **Stop (doc-checker)**: 에이전트 완료 전 필수 파일 업데이트 검증 (`docs/index.json`, `deploy.md`, `MEMORY.md` 등)
- 검증 규칙 상세: `.claude/hooks/lib/doc-rules.json`, `.claude/hooks/lib/audit-rules.json`

## 체크리스트 작성 형식

- 완료 항목: `- ✅ 항목 내용`
- 미완료 항목: `- ⬜ 항목 내용`
- GFM `[x]`/`[ ]` 대신 이모지 사용

## Notion 기술 문서 관리

업데이트 트리거: `.claude/rules/dev-process.md` 섹션 8.5 참조. 상세 규칙: `.claude/rules/notion.md` (Notion 설정 후 생성 예정).
