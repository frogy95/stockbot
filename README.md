# choiji-guide-big

> Claude Code 설정 예제 + 개발 프로세스 템플릿

이 저장소는 Claude Code를 활용한 개발 워크플로우의 뼈대와 에이전트 설정 예제를 담고 있습니다.
동료 개발자들이 유사한 프로세스를 자신의 프로젝트에 적용할 수 있도록 공유용으로 만들어졌습니다.

---

## 📁 프로젝트 구조

```
choiji-guide-big/
├── .claude/
│   ├── agents/
│   │   ├── sprint-planner.md
│   │   ├── sprint-close.md
│   │   ├── sprint-review.md      # NEW
│   │   ├── phase-planner.md      # NEW
│   │   ├── hotfix-close.md
│   │   ├── deploy-prod.md
│   │   └── prd-to-roadmap.md
│   ├── rules/                     # NEW
│   │   ├── backend.md
│   │   ├── frontend.md
│   │   ├── sprint-workflow.md
│   │   └── notion.md
│   ├── commands/
│   │   ├── sprint-dev.md            # Sprint 구현 오케스트레이터
│   │   └── restart.md
│   ├── agent-memory/
│   │   ├── sprint-planner/
│   │   ├── phase-planner/         # NEW
│   │   ├── sprint-review/         # NEW
│   │   └── prd-to-roadmap/
│   ├── hooks/                        # NEW
│   │   ├── pretooluse-bash-guard.sh  # Bash 위험 명령 차단
│   │   ├── stop-doc-checker.sh       # 에이전트 문서 누락 검증
│   │   ├── lib/
│   │   │   └── doc-rules.json        # 에이전트별 필수 업데이트 규칙
│   │   └── test-hooks.sh             # 통합 테스트
│   └── settings.json
├── .github/workflows/
│   ├── ci.yml
│   └── deploy.yml
├── docs/
│   ├── dev-process.md
│   ├── ci-policy.md
│   ├── setup-guide.md
│   ├── prompt-guide.md            # NEW
│   ├── templates/                   ← EXAMPLE 템플릿 모음
│   │   ├── EXAMPLE-prd.md
│   │   ├── EXAMPLE-sprint.md
│   │   ├── EXAMPLE-phase.md
│   │   ├── EXAMPLE-task.md
│   │   ├── EXAMPLE-test-plan.md
│   │   ├── EXAMPLE-test-result.md
│   │   └── EXAMPLE-hotfix.md
│   ├── index.json
│   ├── phase/                     ← Phase 상위 폴더
│   │   └── phase{N}/
│   │       ├── phase{N}.md
│   │       └── sprint{N}/
│   │           ├── sprint{N}.md
│   │           └── task{N}/
│   ├── hotfix/                    ← Hotfix 문서
│   ├── dashboard/
│   └── deploy-history/
├── CLAUDE.md
├── ROADMAP.md
├── deploy.md
└── .env.example
```

---

## 🤖 Claude 에이전트 설명

이 프로젝트는 7개의 특화된 Claude 에이전트를 포함합니다.

### 1. sprint-planner
**트리거**: 새 스프린트 계획 수립 시

ROADMAP.md를 분석하고 코드베이스를 읽어 실행 가능한 스프린트 계획을 수립합니다. **판단 플로우차트**로 각 Task에 적절한 skill을 자동 배정합니다.

```
사용자: "다음 스프린트에서 사용자 인증 기능을 구현하고 싶어"
→ sprint-planner 에이전트가 ROADMAP.md를 분석하여 docs/phase/phase{P}/sprint{N}/sprint{N}.md 생성
```

### 2. sprint-close
**트리거**: 스프린트 구현 완료 후

스프린트 마무리 작업을 자동화합니다:
1. ROADMAP.md 상태 업데이트 (`🔄 진행 중` → `✅ 완료`)
2. `develop` 브랜치로 PR 생성
3. deploy.md 아카이빙 (완료 기록 → deploy-history/)
4. sprint-planner 메모리 업데이트

> 코드 리뷰와 자동 검증은 sprint-review 에이전트가 별도로 수행합니다.

```
사용자: "sprint 3 구현 끝났어. 마무리 작업 해줘"
→ sprint-close 에이전트가 ROADMAP 업데이트, develop PR 생성, 문서 정리
```

### 3. sprint-review
**트리거**: sprint-close 완료 후 PR 검토 후

코드 리뷰와 자동 검증을 수행합니다:
1. 코드 리뷰 (보안/성능/품질 체크리스트)
2. 자동 검증 실행 (pytest, API curl, Playwright UI)
3. Phase 문서 반영 검증 (실측 결과, 완료 상태, 리스크 업데이트)
4. deploy.md 검증 결과 기록
5. Notion 업데이트 필요 여부 안내

```
사용자: "PR 확인했어. 스프린트 리뷰 해줘"
→ sprint-review 에이전트가 코드 리뷰, 자동 검증 수행
```

### 4. phase-planner
**트리거**: 여러 Sprint에 걸친 대규모 기능 계획 시

코드베이스를 분석하고 도메인 전문가 에이전트들의 병렬 검토를 거쳐 Phase 문서를 생성합니다.

```
사용자: "요구사항 정리됐어. Phase 문서 만들어줘."
→ phase-planner 에이전트가 전문가 검토 후 docs/phase/phase{N}/phase{N}.md 생성
```

### 5. hotfix-close
**트리거**: 핫픽스 구현 완료 후

sprint-close의 경량 버전. ROADMAP 업데이트 없이 `main` 브랜치로 직접 PR을 생성합니다.

```
사용자: "hotfix 마무리 해줘"
→ hotfix-close 에이전트가 main PR 생성, 타겟 검증, develop 역머지 안내
```

### 6. deploy-prod
**트리거**: develop 브랜치 QA 완료 후 프로덕션 배포 시

`develop` → `main` PR 생성, 사전 점검, 배포 후 실서버 검증을 수행합니다.

```
사용자: "develop 검증 완료됐어. 프로덕션 배포 해줘"
→ deploy-prod 에이전트가 PR 생성, 헬스체크, 컨테이너 상태 검증
```

### 7. prd-to-roadmap
**트리거**: PRD 문서가 있을 때 ROADMAP.md 생성 시

PRD(제품 요구사항 문서)를 분석하여 Agile/스크럼 방법론에 기반한 ROADMAP.md를 자동 생성합니다.

```
사용자: "docs/PRD.md 기반으로 ROADMAP 만들어줘"
→ prd-to-roadmap 에이전트가 Phase/Sprint 구조의 ROADMAP.md 생성
```

---

## 🔒 Hook 시스템 (자동 규칙 강제화)

에이전트와 사용자가 규칙을 빠뜨리지 않도록 두 가지 hook이 자동으로 동작합니다.

### PreToolUse: bash-guard (위험 명령 즉시 차단)

Bash 도구 호출 시 다음 6개 패턴을 **즉시 차단**합니다:

| # | 차단 패턴 | 이유 |
|---|----------|------|
| 1 | `cd ... &&` 체이닝 | 프로젝트 루트에서 직접 실행 |
| 2 | `git push origin main` | PR만 허용 |
| 3 | `git push origin develop` | PR만 허용 |
| 4 | `git push --force` | 이력 파괴 방지 |
| 5 | `git reset --hard` | 변경사항 손실 방지 |
| 6 | 잘못된 브랜치명 | `phase{P}-sprint{N}` 또는 `hotfix/*` 형식만 허용 |

### Stop: doc-checker (에이전트 문서 누락 검증)

에이전트가 응답을 마치려 할 때, 변경 파일 패턴으로 **어떤 에이전트 작업인지 추론**하고 필수 파일 업데이트 여부를 체크합니다.

| 에이전트 | 필수 업데이트 체크 |
|---------|-----------------|
| prd-to-roadmap | index.json (`project` 필드) |
| phase-planner | ROADMAP, index.json, MEMORY, 전문가 리뷰 파일 ≥1 |
| sprint-planner | ROADMAP, index.json, MEMORY |
| sprint-close | deploy.md, index.json, MEMORY, 아카이빙, 체크박스, PR→develop |
| sprint-review | phase.md 반영, Critical 미해결 경고 |
| hotfix-close | deploy.md, index.json, 아카이빙, hotfix 문서, PR→main, 범위 초과 |
| deploy-prod | deploy.md, index.json, 아카이빙 |

누락 발견 시 경고 메시지를 출력하여 Claude가 보충 작업을 수행합니다.

> 규칙 추가/변경: `.claude/hooks/lib/doc-rules.json`만 수정하면 됩니다.
> 테스트: `bash .claude/hooks/test-hooks.sh` (14개 케이스)

---

## 🔄 개발 워크플로우

### Sprint 흐름

```
1. sprint-planner → docs/phase/phase{P}/sprint{N}/sprint{N}.md 생성 (skill 매칭 포함)
2. git checkout -b sprint{N}
3. /sprint-dev {N} → Task 순서대로 구현 (skill 로드 → 검증 → simplify → 커밋)
4. sprint-close → develop PR + 문서 정리
5. sprint-review → 코드 리뷰 + 검증 + Phase 문서 반영
6. QA 통과 후 deploy-prod → main 배포
```

### Hotfix 흐름

```
1. git checkout -b hotfix/{설명} (main 기반)
2. 긴급 수정...
3. hotfix-close → main PR + 타겟 검증 + develop 역머지 안내
```

자세한 내용은 `docs/dev-process.md` 참조.

---

## ⚙️ 설정 방법

### 1. 이 저장소를 새 프로젝트에 적용하기

1. `CLAUDE.md`에서 저장소 URL을 새 프로젝트로 변경
2. `docs/dev-process.md` 섹션 6.3에 실서버 SSH 접속 정보 기입
3. `.github/workflows/deploy.yml`에서 이미지명 플레이스홀더 (`YOUR_GITHUB_ORG`, `YOUR_PROJECT`) 변경
4. GitHub Secrets 설정 (`LIGHTSAIL_SSH_KEY`, `LIGHTSAIL_HOST`, 등)
5. `.env.example`을 복사하여 `.env` 생성 후 값 입력
6. `docs/setup-guide.md`에 프로젝트별 설정 가이드 작성
7. `.claude/rules/` 디렉토리의 규칙 파일을 프로젝트에 맞게 커스터마이징
   - `backend.md`: 기술 스택, 인증 방식, 테스트 명령
   - `frontend.md`: 프레임워크, 상태 관리, UI 라이브러리
   - `notion.md`: Notion 루트 페이지 URL 및 하위 페이지 ID

### 2. CLAUDE.md 커스터마이징

CLAUDE.md는 Claude Code가 이 프로젝트에서 작동하는 방식을 정의합니다:
- **언어 규칙**: 한국어 응답, 코드 주석, 커밋 메시지
- **Git 브랜치 전략**: Sprint/Hotfix 흐름
- **의사결정 기준**: Hotfix vs Sprint 자동 분류
- **Notion 연동**: 문서 관리 규칙 (선택사항)

### 3. 에이전트 메모리

`.claude/agent-memory/` 디렉토리의 `MEMORY.md` 파일들은 에이전트가 세션 간 지식을 축적하는 데 사용됩니다. 이 파일들은 버전 관리되므로 팀 전체가 공유합니다.

---

## 📋 슬래시 커맨드

| 커맨드 | 설명 |
|--------|------|
| `/sprint-dev {N}` | Sprint 구현 오케스트레이터 (skill 로드 → 검증 → simplify → 커밋) |
| `/restart` | Docker Compose 서비스 재시작 |

---

## 🔧 GitHub Actions

### CI (`.github/workflows/ci.yml`)

PR이 `develop` 또는 `main`으로 올라오면 자동 실행:
- 백엔드 pytest 테스트
- Docker 이미지 빌드 검증
- TypeScript 빌드 체크 (프론트엔드 이미지 빌드 시 자동 감지)

### CD (`.github/workflows/deploy.yml`)

`main`에 push되면 자동 실행:
- Docker 이미지 빌드 & GHCR push
- SSH를 통한 프로덕션 서버 배포

> **TODO**: `deploy.yml`의 이미지명과 서버 경로를 실제 프로젝트 값으로 변경하세요.

---

## 🧩 Skill 설치 가이드

이 프로젝트의 에이전트와 커맨드는 다음 스킬들을 활용합니다. Claude Code에서 설치하세요.

### 필수 스킬 (sprint-dev 자동 사용)

| 스킬 | 설치 명령 | 용도 |
|------|----------|------|
| `simplify` | `/install brianlovin/claude-config` | 매 Task 완료 후 코드 정리 |
| `karpathy-guidelines` | `/install andrej-karpathy-skills` | 코드 품질 가이드라인 (CLAUDE.md 전역) |

### Task별 스킬 (sprint-planner가 배정)

| 스킬 | 설치 명령 | 용도 |
|------|----------|------|
| `frontend-design` | `/install frontend-design` | UI/페이지 개발 시 디자인 탐색 |
| `systematic-debugging` | `/install superpowers` | 버그 수정/디버깅 |
| `feature-dev:feature-dev` | `/install feature-dev` | 기존 코드 3개+ 파일 통합 시 탐색 |
| `brainstorming` | `/install superpowers` | 설계 대안 분기 시 탐색 |

### 프로세스 스킬 (sprint-dev 자동 호출)

| 스킬 | 설치 명령 | 용도 |
|------|----------|------|
| `verification-before-completion` | `/install superpowers` | 최종 검증 시 실증 확인 |
| `dispatching-parallel-agents` | `/install superpowers` | 병렬 Phase 실행 |

### 코드 리뷰 스킬

| 스킬 | 설치 명령 | 용도 |
|------|----------|------|
| `code-review` | `/install code-review` | sprint-review의 PR 리뷰 |

> **참고**: `superpowers` 패키지 하나로 `systematic-debugging`, `brainstorming`, `verification-before-completion`, `dispatching-parallel-agents` 등 여러 스킬이 함께 설치됩니다.

---

## 📜 변경 이력

### 2026-03-28: Hook 시스템 도입 — 에이전트 문서 누락 자동 검증

- **PreToolUse hook** (`bash-guard`): Bash 위험 명령 6개 패턴 즉시 차단 (`cd &&`, main/develop push, force push, reset hard, 브랜치명 형식)
- **Stop hook** (`doc-checker`): 7개 에이전트의 필수 파일 업데이트 누락 자동 검증 (ROADMAP, index.json, deploy.md, MEMORY, 아카이빙, PR 대상 등)
- **doc-rules.json**: 에이전트별 규칙을 분리하여 확장성 확보
- **에이전트 지침 간결화**: hook이 강제화하는 체크리스트를 에이전트 파일에서 제거, "hook이 자동 검증" 안내로 대체
- **CLAUDE.md**: Bash 규칙 섹션을 hook 안내로 간결화

### 2026-03-24: 문서 최신화 (mystock.bot develop 기준)

- **sprint-planner**: 스킬 매칭 방식을 단순 테이블에서 **판단 플로우차트**(5단계 순서 기반)로 전면 교체. `feature-dev:feature-dev`, `brainstorming` 스킬 추가. 프로세스 스킬(simplify, verification-before-completion 등) 구분 도입
- **sprint-dev**: Skill 도구 자동 로딩, **매 Task 완료 후 simplify 필수**, Task 실행 체크리스트(5단계 건너뛰기 금지), skill별 실행 전략 테이블 추가
- **sprint-review**: **Phase 문서 반영 검증** 4단계 신설 — Sprint 실측 결과 vs Phase 원안 비교, 완료 상태/리스크 업데이트
- **sprint-close**: sprint{N}.md의 각 **Task 완료 기준 체크박스 `⬜`→`✅` 업데이트** 절차 추가
- **dev-process**: sprint-dev 자동 스킬 로드/simplify 반영, Playwright 검증 범위 명시, 문서 최신화 트리거 세분화
- **sprint-workflow**: skill 참조 체계 정비 (simplify, verification-before-completion)
- **ci-policy**: CI 필수 조건에 **TypeScript 빌드 체크** 추가, CD 파이프라인 상세화
- **phase-planner**: PO 검토 기준 범용화, 전문가 수 "최소 2명, 최대 5명" 명확화
- **prompt-guide**: `/sprint-dev` 커맨드 안내, 📖 문서 링크 아이콘, 👤 파이프라인 이모지

---

## 📚 참고 문서

- `docs/dev-process.md` — 개발 프로세스 전체 가이드
- `docs/ci-policy.md` — CI/CD 정책 상세
- `docs/setup-guide.md` — 환경 설정 가이드
- `docs/prompt-guide.md` — 사용자 프롬프트 가이드 (바이브코딩 입문)
- `docs/templates/EXAMPLE-prd.md` — PRD 작성 템플릿
- `ROADMAP.md` — 프로젝트 로드맵
