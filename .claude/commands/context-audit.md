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
- **wiki/*.md가 `.claude/rules/*.md` 확정 사실을 복제** (`wiki_rules_duplication`) — 원본은 rules, wiki는 링크로 걸어야 함. 예: backend.md §KIS WebSocket 확정 사실 vs wiki/websocket-management.md
- 3종 README(`.claude/README.md`, `wiki/README.md`, `docs/README.md`) 간 "다른 자산과의 관계" 상호 참조의 사실 불일치
- `docs/harness-wiki-guide.md` §4.1 트리거 매트릭스와 `dev-process.md` §8.6 문서 최신화 테이블 간 불일치

**허용되는 중복**:
- 에이전트가 독립 실행되기 위한 최소 컨텍스트 (PR 대상 브랜치, 참조 링크)
- 훅이 자체 판단을 위해 필요한 임계값 (doc-rules.json의 hotfix 기준 등)
- wiki가 rules/*.md의 **한 문장 요약 + 링크** 형태로 반복 (확정 사실 전체가 아닌, 진입용 요약)

### 3단계: 상충 분석

체크 항목:
- 커맨드/에이전트의 bash 명령이 bash-guard 훅 패턴과 충돌하는지
- 브랜치 생성 기준점이 문서 간 일치하는지 (develop vs main)
- 허용 브랜치 목록이 `CLAUDE.md` "Bash 명령 실행 규칙", `.claude/rules/dev-process.md` §1, `bash-guard.sh` 정규식, `wiki/deployment.md` CI/CD 섹션 4곳에서 일치하는지
- 에이전트 간 역할 경계가 명확한지 (sprint-close vs sprint-review)
- rules의 paths 필터가 실제 트리거 대상과 맞는지
- doc-rules.json의 검증 기준이 dev-process.md와 일치하는지
- settings.json 훅 command 경로가 실제 스크립트 파일과 일치하는지
- settings.json 훅 matcher가 실제 훅이 처리하는 도구명과 일치하는지
- **wiki 문서 내부의 표 ↔ 본문 모순** (예: 표에서 PAPER가 `/tryitout` 필수라고 쓰고 본문에서는 LIVE만 필수라고 쓰는 경우)
- **wiki/*.md의 사실이 `.claude/rules/*.md` 확정 사실 섹션과 불일치** (예: WebSocket URL, REST 도메인 포트, 허용 브랜치 등)

### 4단계: 참조 정합성

모든 파일의 상호 참조가 유효한지 검증한다.

체크 항목:
- CLAUDE.md의 참조 링크 대상 파일이 실제 존재하는지
- 에이전트가 참조하는 문서(.claude/rules/dev-process.md, docs/index.json 등)가 존재하는지
- doc-rules.json의 `required` 파일이 실제 존재하는지
- settings.json 훅 command 경로가 실제 스크립트와 일치하는지
- **`wiki/*.md` 내의 `[[페이지명]]` 링크 대상이 wiki/에 실제 존재하는지** (`wiki_link_dead`)
- **`docs/index.json`의 `sharedDocs[].path` 필드가 실제 파일을 가리키는지**
- **3종 README(`.claude/README.md`, `wiki/README.md`, `docs/README.md`)의 상호 참조 + "다른 자산과의 관계" 링크 유효성**
- **`docs/harness-wiki-guide.md` §5.1 참조표 링크가 실제 파일과 일치하는지**
- 깨진 참조는 `dead_reference`(warning), 빈 참조는 `empty_reference`(minor), wiki 전용 깨진 위키링크는 `wiki_link_dead`(warning)로 분류

### 5단계: 고아/노후 분석

어디서도 참조되지 않는 파일과 대응 관계가 깨진 자산을 찾는다.

체크 항목:
- `.claude/agents/`에 있지만 CLAUDE.md 에이전트 테이블에 없는 파일
- `.claude/commands/`에 있지만 CLAUDE.md 주요 명령어 섹션에 없는 파일
- `docs/experts/`에 있지만 어떤 에이전트도 참조하지 않는 전문가
- `agent-memory/`에 대응하는 에이전트가 없는 메모리 디렉토리
- `docs/templates/`에 있지만 어떤 에이전트/커맨드도 참조하지 않는 템플릿
- **`wiki/*.md` 중 `wiki/index.md` 대분류 목록에서 링크되지 않은 페이지** (`wiki_orphan_page`) — `log.md`·`README.md`는 예외
- **`wiki/*.md` 수정일(git log -1)이 `wiki/log.md`의 최신 날짜 엔트리보다 최근인데, 해당 수정이 로그에 없는 경우** (`wiki_log_stale`)
- **`docs/index.json`의 `lastUpdated` 타임스탬프가 파일 자체의 git 최신 커밋 시각보다 오래된 경우** (`index_last_updated_stale`)

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
- `wiki_link_dead`: 링크 대상 오타 추정 수정 또는 링크 제거 제안, 승인 후 실행
- `wiki_log_stale`: `wiki/log.md`에 해당 날짜 엔트리 추가 제안, 승인 후 실행
- `wiki_rules_duplication`: wiki 복제본을 `.claude/rules/` 원본 참조 링크로 대체 제안, 승인 후 실행
- `wiki_orphan_page`: `wiki/index.md` 대분류 목록에 링크 추가 또는 페이지 삭제 제안, 승인 후 실행
- `index_last_updated_stale`: 현재 시각으로 `docs/index.json` `lastUpdated` 갱신 제안, 승인 후 실행

## 원칙

- **Single Source of Truth**: 프로세스 상세는 `.claude/rules/dev-process.md`, 경로별 규칙은 `rules/*.md`, 에이전트 동작은 `agents/*.md`에만 존재해야 한다.
- **CLAUDE.md는 인덱스**: 상세 내용이 아닌 참조 링크와 고유 규칙(언어, 체크리스트 형식 등)만 유지한다.
- **에이전트는 자족적**: 다른 에이전트를 읽지 않으므로, 독립 실행에 필요한 최소 정보는 중복을 허용한다.
- **훅과 커맨드는 정합성 필수**: bash-guard가 차단하는 패턴을 커맨드가 사용하면 안 된다.
- **전문가는 고유 역할**: experts 간 역할/책임이 중복되면 통합 또는 경계 명확화한다.
- **메모리는 에이전트와 1:1**: 대응 에이전트 없는 메모리는 고아로 분류한다.
- **wiki ↔ rules 경계**: 시스템 **지식**은 `wiki/`, **확정 사실·실행 규칙**은 `.claude/rules/`에 둔다. 중복 시 원본은 rules, wiki는 한 문장 요약 + 링크만 유지한다.
- **wiki는 스스로 교차 참조**: `wiki/index.md`에 링크되지 않은 페이지는 고아로 간주하며, 모든 수정은 `wiki/log.md`에 날짜별 기록을 남긴다.
- **docs/index.json은 관제판**: 상태·신선도 필드(`status`, `progress`, `lastUpdated`)를 실제와 동기화해야 한다.
