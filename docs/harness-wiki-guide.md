# 하네스 & 위키 사용자 가이드

> 이 문서는 **프로젝트에 참여하는 사람**을 위한 가이드입니다. Claude Code가 이 프로젝트에서 어떻게 "규칙대로 일하도록" 설정되어 있는지, 그리고 그 설정을 어떻게 유지보수하는지 설명합니다.
>
> 프롬프트 작성 방법은 [`docs/prompt-guide.md`](prompt-guide.md)를, 프로세스 규칙은 [`.claude/rules/dev-process.md`](../.claude/rules/dev-process.md)를 참조하세요.

---

## 1. 세 자산 한눈에 보기

StockBot은 Claude Code가 읽는 지식/규칙을 세 곳으로 나눠서 관리합니다. 각자 역할과 수명 주기가 다릅니다.

| 자산 | 역할 | 콘텐츠 성격 | 진입점 |
|------|------|------------|--------|
| **`.claude/`** | "LLM이 **어떻게 행동할지**" — 에이전트, 훅, 실행 규칙, 커맨드 | 실행 규칙. 대체로 불변, 버전 관리 | [`.claude/README.md`](../.claude/README.md) |
| **`wiki/`** | "시스템이 **지금 어떻게 동작하는지**" — 아키텍처, 흐름, 도메인 개념 | 살아있는 지식. 코드/인프라 변경 시 갱신 | [`wiki/index.md`](../wiki/index.md) |
| **`docs/`** | "우리가 **무엇을 결정했고 무엇을 했는지**" — 스펙, 히스토리, 사용자 가이드 | 시점 기록 중심. 대부분 불변 | [`docs/README.md`](README.md) |

세 자산의 관계를 한 줄로: **`.claude/`가 행동을 정하고, `wiki/`가 현실을 비추고, `docs/`가 기록을 남긴다.**

---

## 2. 하네스(`.claude/`) 구성

LLM(Claude Code)이 세션 시작 시 자동으로 로드하거나 특정 이벤트에 반응해 실행하는 파일들의 집합입니다. 하네스라는 이름대로, LLM을 "이 프로젝트의 규칙대로 움직이게 묶어두는" 장치입니다.

### 2.1 구성 요소

| 경로 | 내용 | 언제 읽히나 |
|------|------|------------|
| `agents/*.md` | 커스텀 에이전트 정의 (prd-to-roadmap, phase-planner, sprint-planner, sprint-close, sprint-review, sprint-pr-fix, deploy-prod, hotfix-close 등 8개) | 사용자가 해당 에이전트를 호출할 때 |
| `commands/*.md` | 슬래시 커맨드 (`/sprint-dev`, `/restart`, `/dashboard`, `/context-audit`) | 사용자가 `/` 커맨드 입력 시 |
| `rules/*.md` | 경로·상황별 실행 규칙 (backend, frontend, sprint-workflow, dev-process, ci-policy) | 프론트매터 `paths:` 매칭 시 자동, 또는 다른 문서에서 참조 시 |
| `hooks/*.sh` | 이벤트 훅 (bash-guard, posttooluse-index-sync, stop-doc-checker) | Claude Code 런타임이 이벤트마다 자동 실행 |
| `hooks/lib/*.json` | 훅이 참조하는 검증 룰 (audit-rules, doc-rules) | 훅 스크립트 실행 시 |
| `agent-memory/{agent}/*.md` | 에이전트별 세션 간 메모리 | 해당 에이전트가 호출될 때 자동 주입 |
| `settings.json` | Claude Code 전역 설정 (권한, 훅 등록, enabledPlugins) | 세션 시작 시 |
| `settings.local.json` | 로컬 전용 설정 (gitignore) | 세션 시작 시 |
| `feedback.md` | 하네스 개선 백로그 (`미반영` ↔ `반영 완료` 구분) | 사람이 직접 유지 |

### 2.2 에이전트

8개의 에이전트가 프로젝트 라이프사이클을 분할해서 담당합니다. 호출 방법과 모델 지정은 `CLAUDE.md`의 "에이전트 사용 규칙" 테이블 참조.

```
PRD → prd-to-roadmap → ROADMAP
         │
         ├─ phase-planner → phase{N}.md (Opus)
         │       │
         │       ├─ sprint-planner → sprint{N}.md (Opus)
         │       │       │
         │       │       ├─ /sprint-dev → 구현 (Sonnet, 사용자 호출)
         │       │       │
         │       │       ├─ sprint-close → develop PR (Sonnet)
         │       │       ├─ sprint-review → 코드 리뷰 + 검증 (Sonnet)
         │       │       └─ sprint-pr-fix → 리뷰 이슈 수정 (Sonnet)
         │       │
         │       └─ deploy-prod → 프로덕션 배포 (Sonnet)
         │
         └─ hotfix-close → 핫픽스 마무리 (Sonnet)
```

**설계 이유**: 계획(Opus)과 실행(Sonnet)을 모델 수준에서 분리. 각 에이전트는 자신의 컨텍스트 윈도우만 점유 → 메인 세션에 불필요한 히스토리가 쌓이지 않음.

### 2.3 훅

| 훅 | 시점 | 하는 일 |
|---|------|--------|
| `pretooluse-bash-guard.sh` | Bash 도구 실행 직전 | 위험 명령 즉시 차단 (`cd /path &&` 체이닝, main/develop 직접 push, `git push --force`, `git reset --hard`, 허용 외 브랜치명) |
| `posttooluse-index-sync.sh` | Bash 도구 실행 직후 | `git checkout`/`git commit` 감지 시 `docs/index.json` 상태 필드 자동 갱신 |
| `stop-doc-checker.sh` | 에이전트 종료 직전 | 필수 문서 업데이트(`ROADMAP.md`, `index.json`, `deploy.md`, MEMORY.md 등) 누락 검증 |

허용 브랜치: `phase{P}-sprint{N}`, `hotfix/*`, `chore/*`, `docs/*`, `refactor/*`.

**실무 의미**: 에이전트가 빠뜨려도 훅이 자동으로 경고/차단하므로, 프로세스 이탈이 한 단계에서 막힙니다.

### 2.4 규칙(`rules/`)

`rules/*.md` 파일은 두 방식으로 로드됩니다.

1. **경로 매칭 자동 로드** — 프론트매터에 `paths: ["backend/**/*.py", ...]`가 있으면 해당 경로 수정 시 자동 주입. `backend.md`, `frontend.md`가 이 방식.
2. **명시적 참조 로드** — `CLAUDE.md`, 에이전트 `.md`, 다른 규칙 파일에서 상대 경로로 링크 → 필요 시에만 로드. `dev-process.md`, `ci-policy.md`, `sprint-workflow.md`가 이 방식.

`dev-process.md`는 "Single Source of Truth"로 선언되어 있어 검증 매트릭스·문서 관리 규칙·브랜치 전략이 이 한 파일에 모입니다. 다른 문서는 여기를 가리킵니다.

### 2.5 커맨드(`commands/`)

슬래시 커맨드는 사용자가 직접 호출하는 오케스트레이터입니다.

- `/sprint-dev {P}-{N}` — `docs/phase/phase{P}/sprint{N}/sprint{N}.md`를 읽어 Task를 순서대로 구현 + simplify + 커밋
- `/restart [service]` — Docker 서비스 재시작
- `/dashboard` — 프로젝트 대시보드 HTML 실행
- `/context-audit` — 자산 간 중복/상충/고아 파일 감사

### 2.6 에이전트 메모리(`agent-memory/`)

에이전트별로 디렉토리가 있고, 그 안의 `MEMORY.md`가 해당 에이전트 호출 시마다 자동 주입됩니다. 스프린트 현황, Phase 상태 등 **세션 간 유지**가 필요한 정보가 저장됩니다. 에이전트가 직접 쓰거나 사용자가 편집.

---

## 3. 위키(`wiki/`)

### 3.1 역할

"지금 시스템이 어떻게 동작하는지"를 **짧고 링크 가능한** 문서로 유지합니다. 대체로 파일당 1~3KB. `@wiki/`로 Claude Code가 필요할 때만 로드합니다.

### 3.2 구조

[`wiki/index.md`](../wiki/index.md)가 진입점. 대분류는 다음과 같습니다.

| 분류 | 주요 문서 |
|------|----------|
| 시스템 아키텍처 | `system-overview`, `tech-stack`, `module-structure` |
| 데이터 수집 | `data-collection-flow`, `kis-api`, `websocket-management`, `public-data-sources` |
| 스크리닝 | `screening-pipeline`, `screening-factors`, `scoring-system` |
| 매매 실행 | `trading-modes`, `signal-generation`, `momentum-breakout-strategy`, `order-execution`, `position-management` |
| 리스크 | `risk-management`, `position-sizing` |
| 인프라 | `deployment`, `database-schema`, `redis-usage` |
| API 연동 | `telegram-integration`, `external-apis` |
| 개발 환경 | `setup-guide`, `paper-vs-live`, `trading-calendar` |

### 3.3 작성 규칙

- 1 파일 = 1 개념. 길어지면 분할.
- 상호 참조는 `[[페이지명]]` 또는 `[[페이지명|표시]]` (Obsidian 호환).
- 세부 **실행 규칙**은 `.claude/rules/`로, **결정 기록/스펙**은 `docs/`로 분리.
- 수정 로그는 `log.md`에 날짜별로 짧게 기록.
- 절대로 검증 안 된 사실을 넣지 말 것. 위키가 "권위 있는 지식"으로 취급되기 때문에, 틀린 URL이나 파라미터가 들어가면 에이전트가 그걸 그대로 사용합니다.

### 3.4 Claude가 위키를 읽는 시점

- `CLAUDE.md`에서 `@wiki/xxx.md`로 명시 참조한 경우 세션 시작 시 자동 로드.
- 에이전트/규칙 파일에서 상대 경로로 참조한 경우 해당 에이전트가 호출될 때 로드.
- 사람이 대화 중 "`@wiki/signal-generation.md`"처럼 직접 주소를 넣은 경우 즉시 로드.

---

## 4. 유지보수 권고

세 자산은 서로 참조하므로, 한 곳을 바꾸면 다른 곳도 영향을 받습니다. 아래 권고는 **"언제 / 어디를 / 어떻게"** 수정해야 일관성이 유지되는지를 정리한 것입니다.

### 4.1 변경 트리거 매트릭스

| 변경 사건 | 업데이트 대상 | 담당 |
|----------|--------------|------|
| 새 스프린트 완료 | `ROADMAP.md`, sprint-planner `MEMORY.md`, `docs/index.json` | sprint-close 에이전트 |
| 새 Phase 완료 | `ROADMAP.md`, phase-planner `MEMORY.md` | phase-planner / sprint-close |
| DB 스키마 변경 | `wiki/database-schema.md`, Notion "데이터 모델" | 구현 작업자 |
| API 엔드포인트 변경 | `wiki/kis-api.md` 또는 해당 도메인 위키, Notion "API 명세" | 구현 작업자 |
| 외부 API 키/URL/스펙 변경 | `wiki/external-apis.md`, `.claude/rules/backend.md` 확정 사실 섹션 | 구현 작업자 |
| 매매 전략/팩터 변경 | `wiki/momentum-breakout-strategy.md`, `wiki/screening-factors.md`, `wiki/signal-generation.md` | 구현 작업자 |
| 인프라/배포 변경 (Vercel/Railway/Cloudflare) | `wiki/deployment.md`, `.claude/rules/ci-policy.md` | 구현 작업자 |
| 새 환경변수 추가 | `backend/core/config.py`, `.env.example`, `wiki/setup-guide.md` | 구현 작업자 |
| 검증 원칙 변경 | `.claude/rules/dev-process.md` §5 | 직접 수정 |
| 브랜치 전략/허용 브랜치 변경 | `.claude/rules/dev-process.md` §1, `.claude/hooks/pretooluse-bash-guard.sh`, `CLAUDE.md` "Bash 명령 실행 규칙" | 직접 수정 + 훅 동기화 필수 |
| 에이전트 워크플로우 변경 | `.claude/agents/*.md`, 관련 규칙 파일 | 직접 수정 |
| 새 버전 배포 | `docs/deploy-history/YYYY-MM-DD.md`, Notion "릴리즈 노트" | deploy-prod 에이전트 |
| 핫픽스 마무리 | `docs/hotfix/{name}/hotfix.md`, `deploy.md`, `docs/deploy-history/` | hotfix-close 에이전트 |

### 4.2 일관성 유지 원칙

1. **한 사실은 한 곳에만 쓴다.** 같은 내용을 여러 문서에 복제하면, 한쪽만 고쳐져서 충돌이 생깁니다. 예: WebSocket URL은 `.claude/rules/backend.md` 확정 사실 섹션이 원본. `wiki/`는 그걸 참조하고 링크만 겁니다.
2. **wiki는 참조하는 위치가 많으므로 가장 신중하게 유지한다.** 위키에 잘못된 URL/파라미터가 들어가면 에이전트가 그걸 사용합니다. 사실 변경은 원본 규칙 파일 → 위키 순으로.
3. **파일 이동·이름 변경 시 전체 grep을 돌린다.** `grep -r "docs/old-path"` 같은 방식으로 참조 잔존을 확인. 히스토리 문서는 각주로 남기고 본문은 유지.
4. **`settings.local.json`의 stale 경로 주의.** gitignore 되지만 다른 개발자에게는 영향 없는 대신, 본인 환경에서는 권한 프롬프트로 나타날 수 있음. 경로 이관 시 본인 파일도 같이 갱신.

### 4.3 주기적 점검

**매 스프린트 종료 시 (sprint-close/review):**
- `/context-audit` 실행 → 자산 간 중복/상충/고아 파일 검출
- sprint-review의 코드 리뷰 단계에서 `wiki/`의 변경 사항도 검증 대상

**분기 단위 점검 권장:**
- `.claude/feedback.md` "미반영" 항목을 훑어보고 반영 여부 결정
- `wiki/log.md`에서 오래된 "임시 사실"이 남아 있는지 확인
- `docs/deploy-history/` 중 오래된 수동 검증 항목이 `deploy.md`에 안 남았는지 확인 (누락된 아카이빙)

**대규모 리팩토링 후:**
- 이관된 경로가 `CLAUDE.md`, 에이전트, 규칙, 훅, 커맨드 전반에서 일관되게 갱신됐는지 전체 grep
- 신규로 생성된 위키 문서는 같은 주제의 `.claude/rules/` 확정 사실 섹션과 교차 검증

### 4.4 자주 생기는 함정

| 함정 | 증상 | 방지 |
|------|------|------|
| wiki 복제본이 원본과 어긋남 | 에이전트가 구식 URL/파라미터를 사용 | 원본 한 곳만 유지, 나머지는 링크 |
| 파일 이동 후 stale 참조 잔존 | 에이전트가 "파일 없음" 오류로 멈춤 | 이동 직후 `grep -r "old/path"` + `/context-audit` |
| `CLAUDE.md`와 `dev-process.md` 동기화 실패 | 한 문서는 허용하고 다른 문서는 금지하는 모순 | 원본은 `dev-process.md`, `CLAUDE.md`는 요약만 |
| 훅이 허용하지 않는 브랜치명 생성 | 에이전트 작업 중 Bash 명령이 즉시 차단 | 허용 패턴 변경 시 훅/CLAUDE.md/dev-process.md §1 세 곳 동기화 |
| `agent-memory` 누적으로 MEMORY.md 비대화 | 메모리 주입 비용 증가, 최근 사실이 묻힘 | 분기 단위로 MEMORY.md 정리, 구버전 사실은 `docs/deploy-history/`로 이관 |
| `docs/index.json` 상태 필드 방치 | 대시보드·대시보드 쿼리가 실상황과 다름 | `posttooluse-index-sync` 훅이 자동 갱신, 수동 편집 시 스키마 준수 |
| 위키 문서끼리 모순 | 같은 사실이 서로 다른 페이지에서 다른 값 | `log.md`에 변경 기록 + 관련 페이지 동시 수정 |

### 4.5 권장 워크플로우 (요약)

1. **규칙을 바꿀 때** — `.claude/rules/` 원본 수정 → 관련 훅·CLAUDE.md·에이전트 문서 동기화 → 커밋.
2. **코드/시스템을 바꿀 때** — 코드 수정 → 관련 `wiki/` 문서 갱신 → 변경 트리거 매트릭스 따라 `docs/`/Notion 업데이트.
3. **새 자산을 추가할 때** — 먼저 "어느 자산에 속하는가?" 판단 (행동규칙/지식/기록) → 해당 README 업데이트 → 필요 시 `index.md`/`index.json` 등록.
4. **자산을 삭제할 때** — `grep -r`로 참조 전수 조사 → 히스토리 보존이 필요하면 각주로 남기고 `docs/deploy-history/` 또는 `wiki/log.md`에 변경 기록.

---

## 5. 참고

### 5.1 관련 문서

| 문서 | 용도 |
|------|------|
| [`CLAUDE.md`](../CLAUDE.md) | 프로젝트 규칙 요약 + 에이전트 라우팅 (매 세션 자동 로드) |
| [`.claude/README.md`](../.claude/README.md) | 하네스 구조 선언 |
| [`wiki/README.md`](../wiki/README.md) | 위키 구조 선언 |
| [`docs/README.md`](README.md) | 아티팩트 저장소 구조 선언 |
| [`.claude/rules/dev-process.md`](../.claude/rules/dev-process.md) | 검증 매트릭스, 코드 리뷰 체크리스트, 문서 관리 규칙 (SSOT) |
| [`.claude/rules/ci-policy.md`](../.claude/rules/ci-policy.md) | Git 브랜치 전략, CI/CD |
| [`.claude/rules/sprint-workflow.md`](../.claude/rules/sprint-workflow.md) | 스프린트·핫픽스 브랜치 워크플로우 |
| [`docs/prompt-guide.md`](prompt-guide.md) | 사용자 프롬프트 작성 가이드 |
| [`wiki/index.md`](../wiki/index.md) | 위키 진입점 |

### 5.2 점검 커맨드

```bash
# 자산 감사
/context-audit

# 이관 경로 잔존 확인 (예: 이전 경로를 모든 .claude/wiki/docs/CLAUDE.md에서 찾기)
grep -r "docs/old-path" .claude/ wiki/ docs/ CLAUDE.md README.md

# 대시보드로 docs/index.json 상태 확인
/dashboard

# 피드백 백로그 확인
cat .claude/feedback.md
```
