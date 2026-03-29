# context-audit 확장 설계

## 개요

기존 `/context-audit` 커맨드를 확장하여 프로젝트의 전체 자산(에이전트, 커맨드, 규칙, 훅, 전문가, 템플릿, 메모리, 설정, 핵심 문서)을 감사하고 리팩토링한다.

## 의사 결정 기록

| 항목 | 결정 | 이유 |
|------|------|------|
| 기존 커맨드와의 관계 | context-audit 확장 | 70~80% 부합, 별도 도구 불필요 |
| 구현 방식 | 커맨드 + 외부 규칙 파일 분리 | doc-rules.json 패턴과 일관, 커맨드 간결 유지 |
| 자동 수정 정책 | minor 자동, 나머지 승인 | 안전한 변경만 자동, 중대한 건 사용자 판단 |
| 실행 시점 | 수동 호출만 | `/context-audit` 명령으로 필요 시 실행 |
| 감사 범위 | 항상 전체 | 선택적 실행 불필요 |

## 파일 변경 범위

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `.claude/hooks/lib/audit-rules.json` | 신규 생성 | 감사 대상, 체크 항목, 자동 수정 정책 |
| `.claude/commands/context-audit.md` | 수정 | 기존 6단계 → 7단계 절차로 교체 |

## audit-rules.json 구조

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

## 감사 절차 (7단계)

### 1단계: 파일 수집

`audit-rules.json`의 `targets` 전체를 읽어 감사 대상 파일 목록을 구성한다.

### 2단계: 중복 분석

기존 체크 항목 유지 + 확장:

- CLAUDE.md와 rules/*.md 간 내용 중복
- CLAUDE.md와 dev-process.md 간 프로세스 상세 중복
- 에이전트 간 동일 절차 반복
- rules/*.md와 dev-process.md 간 기준/목록 중복
- **(신규)** experts/*.md 간 역할/책임 중복
- **(신규)** templates/*.md 간 구조/내용 중복

**허용되는 중복**: 에이전트 독립 실행을 위한 최소 컨텍스트.

### 3단계: 상충 분석

기존 체크 항목 유지 + 확장:

- 커맨드/에이전트 bash 명령 vs bash-guard 패턴 충돌
- 브랜치 생성 기준점 문서 간 일치 여부
- 에이전트 간 역할 경계 명확성
- rules paths 필터 vs 실제 트리거 대상
- doc-rules.json 검증 기준 vs dev-process.md
- **(신규)** settings.json 훅 command 경로 vs 실제 스크립트 파일 존재 여부
- **(신규)** settings.json 훅 matcher vs 실제 훅이 처리하는 도구명 일치 여부

### 4단계: 참조 정합성 (신규)

- CLAUDE.md의 "→ X 참조" 링크 대상 파일 존재 확인
- 에이전트가 참조하는 문서 존재 확인
- doc-rules.json의 `required` 파일 존재 확인
- settings.json 훅 command 경로가 실제 스크립트와 일치하는지
- 깨진 참조는 `dead_reference`, 빈 참조는 `empty_reference`로 분류

### 5단계: 고아/노후 분석 (신규)

- `.claude/agents/`에 있지만 CLAUDE.md 에이전트 테이블에 없는 파일
- `.claude/commands/`에 있지만 CLAUDE.md 주요 명령어 섹션에 없는 파일
- `docs/experts/`에 있지만 어떤 에이전트도 참조하지 않는 전문가
- `agent-memory/`에 대응하는 에이전트가 없는 메모리 디렉토리
- `docs/templates/`에 있지만 어떤 에이전트/커맨드도 참조하지 않는 템플릿

### 6단계: 보고서 출력

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

**자동 수정 (보고서 출력 시 즉시):**
- `empty_reference`: 빈 참조 줄 채우기
- `dead_reference` 중 경로 오타/파일명 변경으로 추정 가능한 건

**승인 후 수정 (Critical → Warning → Info 순서):**
- `conflict`: 수정 방향을 제안하고 승인 후 실행
- `duplication`: Single Source of Truth를 제안하고 승인 후 참조로 대체
- `orphan_file`: 삭제 또는 참조 추가 제안, 승인 후 실행
- `stale_memory`: 정리 또는 유지 제안, 승인 후 실행
- `settings_mismatch`: 수정 방향 제안, 승인 후 실행

## 원칙 (기존 유지 + 확장)

- **Single Source of Truth**: 프로세스 상세는 `docs/dev-process.md`, 경로별 규칙은 `rules/*.md`, 에이전트 동작은 `agents/*.md`에만 존재
- **CLAUDE.md는 인덱스**: 상세 내용이 아닌 참조 링크와 고유 규칙만 유지
- **에이전트는 자족적**: 독립 실행에 필요한 최소 정보는 중복 허용
- **훅과 커맨드는 정합성 필수**: bash-guard가 차단하는 패턴을 커맨드가 사용하면 안 됨
- **(신규) 전문가는 고유 역할**: experts 간 역할/책임이 중복되면 통합 또는 경계 명확화
- **(신규) 메모리는 에이전트와 1:1**: 대응 에이전트 없는 메모리는 고아로 분류
