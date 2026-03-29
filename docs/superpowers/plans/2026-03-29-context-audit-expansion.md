# context-audit 확장 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/context-audit` 커맨드를 확장하여 전체 프로젝트 자산을 감사하고 리팩토링한다.

**Architecture:** audit-rules.json에 감사 대상/체크 항목/자동 수정 정책을 선언적으로 정의하고, context-audit.md 커맨드가 이를 참조하여 7단계 절차를 실행한다.

**Tech Stack:** Claude Code 커맨드(.md) + JSON 규칙 파일

---

## 파일 구조

| 파일 | 역할 | 변경 유형 |
|------|------|----------|
| `.claude/hooks/lib/audit-rules.json` | 감사 대상, 체크 항목, 자동 수정 정책 정의 | 신규 생성 |
| `.claude/commands/context-audit.md` | 7단계 감사 절차 오케스트레이션 | 전체 교체 |

---

### Task 1: audit-rules.json 생성

**Files:**
- Create: `.claude/hooks/lib/audit-rules.json`

- [ ] **Step 1: audit-rules.json 파일 생성**

`.claude/hooks/lib/audit-rules.json`을 아래 내용으로 생성한다:

```json
{
  "targets": [
    {
      "id": "claude-md",
      "paths": ["CLAUDE.md"],
      "role": "인덱스 — 참조 링크와 고유 규칙만 유지"
    },
    {
      "id": "rules",
      "paths": [".claude/rules/*.md"],
      "role": "경로별 상세 규칙"
    },
    {
      "id": "agents",
      "paths": [".claude/agents/*.md"],
      "role": "에이전트 정의 (자족적 실행)"
    },
    {
      "id": "commands",
      "paths": [".claude/commands/*.md"],
      "role": "슬래시 커맨드 정의"
    },
    {
      "id": "hooks",
      "paths": [".claude/hooks/*.sh", ".claude/hooks/lib/*.json"],
      "role": "도구 호출 시 자동 실행 스크립트"
    },
    {
      "id": "experts",
      "paths": ["docs/experts/*.md"],
      "role": "도메인 전문가 프로필"
    },
    {
      "id": "templates",
      "paths": ["docs/templates/*.md"],
      "role": "문서 템플릿"
    },
    {
      "id": "agent-memory",
      "paths": [".claude/agent-memory/*/MEMORY.md"],
      "role": "에이전트 영속 메모리"
    },
    {
      "id": "settings",
      "paths": [".claude/settings.json", ".claude/settings.local.json"],
      "role": "Claude Code 설정"
    },
    {
      "id": "docs",
      "paths": ["docs/dev-process.md", "docs/ci-policy.md", "docs/index.json"],
      "role": "핵심 프로세스 문서"
    }
  ],
  "checks": {
    "duplication": {
      "severity": "warning",
      "autofix": false,
      "description": "동일 정보가 2곳 이상에 구체적으로 기술"
    },
    "conflict": {
      "severity": "critical",
      "autofix": false,
      "description": "문서 간 상충되는 지시/기준"
    },
    "dead_reference": {
      "severity": "warning",
      "autofix": true,
      "description": "참조 경로가 실제 존재하지 않음"
    },
    "empty_reference": {
      "severity": "minor",
      "autofix": true,
      "description": "'→ X 참조'만 있고 내용 없는 줄"
    },
    "orphan_file": {
      "severity": "info",
      "autofix": false,
      "description": "어디서도 참조되지 않는 파일"
    },
    "stale_memory": {
      "severity": "info",
      "autofix": false,
      "description": "대응 에이전트가 없는 메모리 또는 오래된 엔트리"
    },
    "settings_mismatch": {
      "severity": "warning",
      "autofix": false,
      "description": "settings.json 훅 설정과 실제 훅 파일 불일치"
    }
  },
  "autofix_policy": {
    "auto": ["minor"],
    "approval_required": ["warning", "critical", "info"]
  }
}
```

- [ ] **Step 2: JSON 문법 검증**

Run: `python3 -c "import json; json.load(open('.claude/hooks/lib/audit-rules.json')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add .claude/hooks/lib/audit-rules.json
git commit -m "feat: audit-rules.json 생성 — 감사 대상/체크 항목/자동 수정 정책 정의"
```

---

### Task 2: context-audit.md 교체

**Files:**
- Modify: `.claude/commands/context-audit.md` (전체 교체)

- [ ] **Step 1: context-audit.md를 아래 내용으로 전체 교체**

```markdown
CLAUDE.md, 규칙, 훅, 에이전트, 커맨드, 전문가, 템플릿, 메모리, 설정 간의 중복/상충/참조 오류/고아 파일을 감사하고 리팩토링한다.

## 목적

프로젝트의 전체 자산을 감사하여 중복/상충/깨진 참조/고아 파일을 발견하고, 경미한 건은 자동 수정하고 중대한 건은 사용자 승인 후 수정한다. 컨텍스트 윈도우 효율성을 높이고 에이전트 동작의 일관성을 보장한다.

## 감사 규칙

`.claude/hooks/lib/audit-rules.json`을 읽어 감사 대상(`targets`), 체크 항목(`checks`), 자동 수정 정책(`autofix_policy`)을 로드한다.

## 감사 절차

### 1단계: 파일 수집

`audit-rules.json`의 `targets` 전체를 glob 패턴으로 확장하여 실제 파일 목록을 구성한다. 존재하지 않는 경로는 기록해둔다 (4단계에서 dead_reference로 보고).

### 2단계: 중복 분석

**컨텍스트 낭비 기준**: 동일한 정보가 2곳 이상에 구체적으로 기술되어 있는 경우.

체크 항목:
- CLAUDE.md와 rules/*.md 간 내용 중복 (CLAUDE.md는 참조 링크만 유지해야 함)
- CLAUDE.md와 dev-process.md 간 프로세스 상세 중복
- 에이전트 간 동일 절차 반복 (deploy.md 아카이빙 등)
- rules/*.md와 dev-process.md 간 기준/목록 중복
- experts/*.md 간 역할/책임 중복
- templates/*.md 간 구조/내용 중복

**허용되는 중복**:
- 에이전트가 독립 실행되기 위한 최소 컨텍스트 (PR 대상 브랜치, 참조 링크)
- 훅이 자체 판단을 위해 필요한 임계값 (doc-rules.json의 hotfix 기준 등)

### 3단계: 상충 분석

체크 항목:
- 커맨드/에이전트의 bash 명령이 bash-guard 훅 패턴과 충돌하는지
- 브랜치 생성 기준점이 문서 간 일치하는지 (develop vs main)
- 에이전트 간 역할 경계가 명확한지 (sprint-close vs sprint-review)
- rules의 paths 필터가 실제 트리거 대상과 맞는지
- doc-rules.json의 검증 기준이 dev-process.md와 일치하는지
- settings.json 훅 command 경로가 실제 스크립트 파일과 일치하는지
- settings.json 훅 matcher가 실제 훅이 처리하는 도구명과 일치하는지

### 4단계: 참조 정합성

모든 파일의 상호 참조가 유효한지 검증한다.

체크 항목:
- CLAUDE.md의 참조 링크 대상 파일이 실제 존재하는지
- 에이전트가 참조하는 문서(docs/dev-process.md, docs/index.json 등)가 존재하는지
- doc-rules.json의 `required` 파일이 실제 존재하는지
- settings.json 훅 command 경로가 실제 스크립트와 일치하는지
- 깨진 참조는 `dead_reference`(warning), 빈 참조는 `empty_reference`(minor)로 분류

### 5단계: 고아/노후 분석

어디서도 참조되지 않는 파일과 대응 관계가 깨진 자산을 찾는다.

체크 항목:
- `.claude/agents/`에 있지만 CLAUDE.md 에이전트 테이블에 없는 파일
- `.claude/commands/`에 있지만 CLAUDE.md 주요 명령어 섹션에 없는 파일
- `docs/experts/`에 있지만 어떤 에이전트도 참조하지 않는 전문가
- `agent-memory/`에 대응하는 에이전트가 없는 메모리 디렉토리
- `docs/templates/`에 있지만 어떤 에이전트/커맨드도 참조하지 않는 템플릿

### 6단계: 보고서 출력

minor 항목은 이 시점에서 자동 수정을 먼저 실행한 뒤, 아래 형식으로 결과를 보고한다.

```
## 컨텍스트 감사 결과

### 🔴 상충 (Critical) — 승인 후 수정
| # | 위치 A | 위치 B | 내용 | 수정 방향 |
|---|--------|--------|------|----------|

### 🟡 중복/정합성 (Warning) — 승인 후 수정
| # | 위치 A | 위치 B | 내용 | 수정 방향 |
|---|--------|--------|------|----------|

### 🟢 자동 수정 완료 (Minor)
| # | 파일 | 수정 내용 |
|---|------|----------|

### 🔵 참고 (Info) — 승인 후 조치
| # | 파일 | 내용 | 권장 조치 |
|---|------|------|----------|

### 허용된 중복 (참고)
| 위치 | 이유 |
|------|------|

---
**요약**: Critical N건 / Warning N건 / 자동 수정 N건 / Info N건
**수정할까요?** (Critical → Warning → Info 순서로 진행합니다)
```

### 7단계: 수정 실행

사용자가 수정을 승인하면 severity 순서(Critical → Warning → Info)로 진행한다.

**자동 수정 (6단계에서 즉시 실행):**
- `empty_reference`: 빈 참조 줄 채우기
- `dead_reference` 중 경로 오타/파일명 변경으로 추정 가능한 건

**승인 후 수정:**
- `conflict`: 수정 방향을 제안하고 승인 후 실행
- `duplication`: Single Source of Truth를 제안하고 승인 후 참조로 대체
- `orphan_file`: 삭제 또는 참조 추가 제안, 승인 후 실행
- `stale_memory`: 정리 또는 유지 제안, 승인 후 실행
- `settings_mismatch`: 수정 방향 제안, 승인 후 실행

## 원칙

- **Single Source of Truth**: 프로세스 상세는 `docs/dev-process.md`, 경로별 규칙은 `rules/*.md`, 에이전트 동작은 `agents/*.md`에만 존재해야 한다.
- **CLAUDE.md는 인덱스**: 상세 내용이 아닌 참조 링크와 고유 규칙(언어, 체크리스트 형식 등)만 유지한다.
- **에이전트는 자족적**: 다른 에이전트를 읽지 않으므로, 독립 실행에 필요한 최소 정보는 중복을 허용한다.
- **훅과 커맨드는 정합성 필수**: bash-guard가 차단하는 패턴을 커맨드가 사용하면 안 된다.
- **전문가는 고유 역할**: experts 간 역할/책임이 중복되면 통합 또는 경계 명확화한다.
- **메모리는 에이전트와 1:1**: 대응 에이전트 없는 메모리는 고아로 분류한다.
```

- [ ] **Step 2: 커밋**

```bash
git add .claude/commands/context-audit.md
git commit -m "feat: context-audit 커맨드 확장 — 7단계 감사 절차 + 10개 자산 카테고리"
```

---

### Task 3: 검증

- [ ] **Step 1: audit-rules.json이 doc-rules.json과 같은 디렉토리에 있는지 확인**

Run: `ls -la .claude/hooks/lib/`
Expected: `audit-rules.json`과 `doc-rules.json` 모두 존재

- [ ] **Step 2: context-audit.md가 audit-rules.json을 참조하는지 확인**

Run: `grep "audit-rules.json" .claude/commands/context-audit.md`
Expected: `.claude/hooks/lib/audit-rules.json`을 읽어 감사 대상... 출력

- [ ] **Step 3: /context-audit 실행하여 동작 확인**

커맨드를 실행하여 감사 보고서가 정상 출력되는지 확인한다. 7단계가 순서대로 진행되고 보고서 형식이 설계와 일치하는지 검증한다.
