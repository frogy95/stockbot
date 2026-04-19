# 프롬프트 가이드

> 이 문서는 **사용자 참고용**입니다. Claude Code가 자동으로 읽지 않습니다.
> 바이브코딩이 처음이라면 "시작하기 전에" 섹션부터 읽어주세요.

---

## 시작하기 전에

### 바이브코딩이란?

자연어로 AI에게 개발 작업을 지시하는 방식입니다. 코드를 직접 쓰지 않아도 됩니다.
이 프로젝트에서는 **Claude Code**를 사용하며, 터미널에서 `claude` 명령으로 실행합니다.

> 📖 [Claude Code 개요](https://code.claude.com/docs/ko/overview) · [Quickstart](https://code.claude.com/docs/ko/quickstart)

### 용어 정리

| 용어 | 의미 |
|------|------|
| **PRD** | 제품 요구사항 문서. 무엇을 만들지 정의 |
| **ROADMAP** | 프로젝트 전체 계획. Phase와 Sprint로 구성 |
| **Phase** | 여러 Sprint에 걸친 대규모 기능 단위. 전문가 검토 포함 |
| **Sprint** | 1~2일 단위의 개발 작업. docs/phase/phase{P}/sprint{N}/sprint{N}.md가 실행 명세서 |
| **Hotfix** | 프로덕션 긴급 패치. 파일 3개, 50줄 이하 |
| **에이전트** | Claude Code가 특정 역할을 수행하는 자동화 도구 |
| **develop** | 스테이징 브랜치 (로컬 Docker 검증용) |
| **main** | 프로덕션 브랜치 (merge 시 자동 배포) |

### 처음 이 프로젝트에 참여할 때

1. 저장소 클론: `git clone {YOUR_REPO_URL}`
2. `.env` 파일 생성: `.env.example`을 복사하여 필요한 값 입력
3. Docker 실행: `docker compose up --build`
4. DB 마이그레이션: `docker compose exec backend alembic upgrade head`
5. 접속 확인: `http://localhost:3000` (프론트), `http://localhost:8000/docs` (백엔드 API)
6. 테스트 로그인: `.env`의 테스트 계정 정보 사용

### 에이전트 파이프라인 전체 그림

> 📖 [커스텀 에이전트 생성](https://code.claude.com/docs/ko/sub-agents) · 설계 이유: 각 단계를 독립 에이전트로 분리하여 컨텍스트 윈도우를 절약하고, 역할별 model/skill을 최적화합니다.

```
PRD ──→ prd-to-roadmap ──→ ROADMAP.md
                              │
                     👤 ROADMAP 검토/수정/확정
                              │
                    Phase별로 반복:
                              │
              요구사항 인터뷰 ──→ phase-planner ──→ phase{N}/phase{N}.md
                                                      │
                                             👤 Phase 문서 검토/파라미터 확정
                                                      │
                                          Sprint별로 반복:
                                                      │
                                        sprint-planner ──→ phase{P}/sprint{N}/sprint{N}.md
                                                              │
                                                     👤 Sprint 계획 검토/승인
                                                              │
                                                        /sprint-dev {P}-{N} ──→ 구현 (Task 순서대로)
                                                              │
                                                        sprint-close ──→ develop PR + 문서 정리
                                                              │
                                                     👤 PR 검토
                                                              │
                                                        sprint-review ──→ 코드 리뷰 + 검증
                                                              │
                                                     👤 수동 검증 수행 + Notion 업데이트
                                                              │
                                                        deploy-prod ──→ main 배포
                                                              │
                                                     👤 PR 머지 + 실서버 확인
```

### 핵심 규칙 3가지

1. **docs/phase/phase{P}/sprint{N}/sprint{N}.md가 실행의 기준**: 계획 문서에 적힌 대로 Task를 순서대로 구현합니다.
2. **계획과 다르면 물어본다**: Claude가 임의로 변경하지 않고 사용자에게 확인합니다.
3. **검증 명령을 반드시 실행**: 각 Task에 적힌 검증 명령으로 결과를 확인합니다.

### Hook 자동 안전장치

사용자가 신경 쓰지 않아도 **두 가지 hook**이 자동으로 규칙을 강제합니다:

- **bash-guard** (PreToolUse): 위험한 Bash 명령을 즉시 차단합니다.
  - `cd /path && ...` 체이닝, `git push origin main/develop`, `git push --force`, `git reset --hard`, 잘못된 브랜치명
  - 사용자가 따로 확인할 필요 없음 — 실행 전에 자동 차단됩니다.

- **doc-checker** (Stop): 에이전트가 작업을 끝내려 할 때, 빠뜨린 문서 업데이트를 자동 감지합니다.
  - ROADMAP.md, index.json, deploy.md, MEMORY.md 업데이트 여부
  - deploy-history 아카이빙, PR 대상 브랜치, sprint.md 체크박스
  - 누락이 있으면 경고가 출력되고, Claude가 자동으로 보충합니다.

> 📖 [Hooks 가이드](https://code.claude.com/docs/ko/hooks-guide) — 규칙 확장: `.claude/hooks/lib/doc-rules.json`에 항목을 추가하면 됩니다.

> 📖 [CLAUDE.md로 프로젝트 기억하기](https://code.claude.com/docs/ko/memory) — 이 규칙들은 `CLAUDE.md`에도 기록되어 매 세션마다 자동 로드됩니다. docs/phase/phase{P}/sprint{N}/sprint{N}.md를 SSOT로 쓰는 이유: 세션이 바뀌어도 문서 하나만 읽으면 어디서든 구현을 이어갈 수 있습니다.

### 모델 선택 가이드

Claude Code에서 `/model` 명령으로 모델을 변경할 수 있습니다.

> 📖 [모델 설정](https://code.claude.com/docs/ko/model-config) — 에이전트 frontmatter의 `model:` 필드로 에이전트별 모델을 지정합니다. 설계 이유: 계획(Opus)과 실행(Sonnet)을 분리하여 비용을 최적화합니다.

**기본 설정: Sonnet** — 대부분의 작업에 충분합니다. 에이전트는 자체 모델이 지정되어 있어 메인 세션 모델과 무관하게 동작합니다.

| 단계 | 메인 세션 모델 | 에이전트 모델 | 비고 |
|------|--------------|-------------|------|
| 요구사항 인터뷰 / brainstorming | Opus 권장 | — | 깊은 추론 필요 |
| PRD → ROADMAP 생성 | — | **Opus** (자동) | 에이전트가 처리 |
| Phase 문서 생성 | — | **Opus** (자동) | 에이전트가 처리 |
| Sprint 계획 수립 | — | **Opus** (자동) | 에이전트가 처리 |
| **Sprint 구현** | **Sonnet** (기본) | — | 복잡하면 `/model opus` |
| Sprint 마무리 | — | **Sonnet** (자동) | 에이전트가 처리 |
| Sprint 리뷰 | — | **Sonnet** (자동) | 에이전트가 처리 |
| Hotfix | **Sonnet** (기본) | — | 범위가 좁은 수정 |
| 배포 | — | **Sonnet** (자동) | 에이전트가 처리 |

> **"자동"**: 에이전트에 모델이 지정되어 있어 사용자가 변경할 필요 없음
>
> **Opus 전환이 필요한 경우**: 요구사항 인터뷰, brainstorming, 또는 복잡한 구현 로직에서만 `/model opus`로 전환하세요.

**비용 팁:**
- Opus는 Sonnet 대비 ~5배 비용. 계획/설계 에이전트가 이미 Opus를 사용하므로, 메인 세션은 Sonnet으로 충분합니다.
- 복잡한 알고리즘이나 아키텍처 결정이 필요할 때만 `/model opus`로 전환하세요.

---

## 어떤 경로를 선택해야 하나?

```
"이거 하고 싶은데" →  규모가 얼마나 큰가?
                    │
                    ├─ 새 프로젝트다          → A. 프로젝트 시작
                    ├─ 여러 Sprint 필요       → B. 메이저 업데이트
                    ├─ Sprint 하나면 될 것 같다 → B. 메이저 업데이트 (Phase 경유)
                    ├─ 파일 몇 개만 수정       → C. 간단한 수정
                    └─ 프로덕션 버그다!        → D. 긴급 버그 수정
```

| 경로 | 기준 | 프로세스 | 권장 모델 |
|------|------|---------|----------|
| **A. 프로젝트 시작** | 새 프로젝트, PRD가 있음 | PRD → ROADMAP → Phase → Sprint | Opus (인터뷰) → Sonnet (구현) |
| **B. 메이저 업데이트** | 기능 추가 또는 여러 Sprint, 반드시 Phase 경유 | Phase → Sprint | Opus (인터뷰) → Sonnet (구현) |
| **C. 간단한 수정** | 파일 3개 이하, 50줄 이하, DB 변경 없음 | 바로 수정 | Sonnet |
| **D. 긴급 버그 수정** | 프로덕션 장애 | Hotfix → main 배포 | Sonnet |

---

## A. 프로젝트 시작

> **모델**: 인터뷰 시 `/model opus` 권장, 에이전트는 자동으로 Opus 사용

### A-1. PRD에서 ROADMAP 생성

```
PRD 작성했어. ROADMAP 만들어줘.
```

> prd-to-roadmap 에이전트 → Phase 기반 ROADMAP.md 생성

### A-2. ROADMAP 검토/수정

```
ROADMAP 확인했어.
- Phase 3의 Sprint 범위를 조정해줘. 알림 기능은 Sprint 6으로 옮기자.
- Phase 2의 완료 기준에 "API 응답 시간 200ms 이하" 추가해줘.
```

### A-3. 첫 Phase 시작

```
ROADMAP 확정. Phase 0부터 시작하자.
```

> 이후 B 경로(메이저 업데이트)와 동일하게 진행

---

## B. 메이저 업데이트 (Phase → Sprint)

> **모델**: 인터뷰 시 `/model opus` 권장, 구현은 Sonnet(기본)으로 충분

여러 Sprint에 걸친 신규 시스템, 또는 도메인 전문가 검토가 필요한 기능.

### B-1. 요구사항 인터뷰

무엇을 만들고 싶은지 설명합니다. 구체적일수록 좋습니다.

```
실시간 알림 시스템을 만들고 싶어.
- WebSocket으로 서버 이벤트를 실시간 전달
- 사용자별 알림 설정 관리
- 알림 센터 UI 구현
- 읽지 않은 알림 배지 표시
```

> brainstorming이 시작됩니다. 목표, 제약조건, 기존 시스템 관계 등을 인터뷰합니다.
> 잘 모르는 부분이 있어도 괜찮습니다 — 전문가 에이전트가 보완합니다.

**대화 중 유용한 표현들:**

```
나는 이 분야는 잘 몰라서 전문가 의견이 필요해.
```

```
WebSocket 연결 관리에 대한 모범 사례가 뭔지 확인해줘.
```

```
이 기능에 리스크가 있을까? 안전장치가 필요한 부분을 알려줘.
```

### B-2. Phase 문서 생성

인터뷰로 요구사항이 정리되면:

```
요구사항 정리됐어. Phase 문서 만들어줘.
```

> phase-planner 에이전트가:
> 1. ROADMAP + 코드베이스 분석
> 2. 도메인 전문가 2~4명 병렬 검토
> 3. 검토 결과 통합
> 4. docs/phase/phase{N}/phase{N}.md + review 리포트 생성

### B-3. Phase 문서 검토/수정

> Phase 문서의 **"검토팀 확정 파라미터"** 섹션이 핵심입니다.
> 이 값들을 sprint-planner가 실행 명세서를 만들 때 참조합니다.
> 모르는 파라미터가 있으면 그대로 두셔도 됩니다 — 전문가 에이전트가 검토한 값입니다.

```
docs/phase/phase{N}/phase{N}.md 확인했어.
- 3단계 파라미터에서 타임아웃을 30s → 60s로 변경해줘.
- Sprint 분할은 좋은데, Sprint {N+2}에 성능 테스트도 넣어줘.
- 나머지는 확정.
```

### B-4. 첫 번째 Sprint 시작

```
phase{P}의 sprint {N} 계획 세워줘. docs/phase/phase{P}/phase{P}.md의 첫 번째 Sprint야.
```

> sprint-planner 에이전트가 docs/phase/phase{P}/phase{P}.md를 참조하여 docs/phase/phase{P}/sprint{N}/sprint{N}.md 생성

### B-5. Sprint 계획 검토 후 구현

> `/sprint-dev {P}-{N}` 커맨드는 docs/phase/phase{P}/sprint{N}/sprint{N}.md를 읽고 Task를 순서대로 구현하는 오케스트레이터입니다.
> 각 Task의 `skill:` 헤더에 따라 적절한 스킬을 자동 로드하고, 구현 → 검증 → 코드 정리(simplify) → 커밋을 체크리스트로 관리합니다.

```
docs/phase/phase{P}/sprint{N}/sprint{N}.md 검토 완료. /sprint-dev {P}-{N}
```

또는 수정이 필요하면:

```
docs/phase/phase{P}/sprint{N}/sprint{N}.md 확인했어.
- Task 3의 API 응답에 total_count 필드 추가해줘.
- Task 5는 다음 Sprint으로 넘기자.
수정 후 /sprint-dev {P}-{N}
```

> 📖 설계 이유: sprint-close와 sprint-review를 분리한 이유는 sprint-close가 코드 리뷰/검증까지 포함하면 Critical 이슈 발생 시 흐름이 중단되고 문서 업데이트가 누락되기 때문입니다. 분리 후 sprint-close는 항상 완결되고, sprint-review는 재실행 가능합니다.

### B-6. Sprint 마무리

```
phase{P}-sprint{N} 구현 끝났어. 마무리 해줘.
```

> sprint-close 에이전트 → ROADMAP 업데이트, develop PR 생성, 문서 정리

### B-7. Sprint 리뷰

PR을 검토한 후:

```
PR 확인했어. 스프린트 리뷰 해줘.
```

> sprint-review 에이전트 → 코드 리뷰, 자동 검증, deploy.md 결과 기록

Critical 이슈가 발견되면 수정 후 다시 실행:

```
수정 완료. 다시 스프린트 리뷰 해줘.
```

### B-8. 다음 Sprint 계속

```
phase{P}의 sprint {N+1} 계획 세워줘. docs/phase/phase{P}/phase{P}.md 기준으로.
```

### B-9. Phase 완료 후 배포

```
develop 검증 완료됐어. 프로덕션 배포 해줘.
```

> deploy-prod 에이전트 → develop → main PR, 실서버 검증

---

## C. 간단한 수정

> **모델: Sonnet** — 빠르고 비용 효율적
>
> Hotfix vs Sprint 판단 기준은 `.claude/rules/dev-process.md` 섹션 2에 정의되어 있습니다. 파일 3개/50줄 이하 + DB 변경 없음 + 새 의존성 없음이면 Sprint 없이 바로 수정합니다.

파일 몇 개만 수정하면 되는 작업. Sprint/Phase 문서 불필요.

### C-1. 바로 수정 요청

```
대시보드 차트의 Y축 라벨이 잘려서 안 보여. 수정해줘.
```

```
설정 페이지에서 저장 버튼 눌러도 반응이 없어. 확인해줘.
```

```
백엔드 로그에 민감정보가 평문으로 찍히고 있어. 마스킹 처리해줘.
```

> Claude가 직접 코드를 수정합니다. Hotfix vs Sprint 판단은 자동으로 합니다.

### C-2. 수정 후 커밋

```
수정 확인했어. 커밋해줘.
```

---

## D. 긴급 버그 수정 (Hotfix)

> **모델: Sonnet** — 빠른 대응이 중요

프로덕션에서 장애가 발생했을 때.

### D-1. 증상 설명

```
프로덕션에서 로그인 페이지가 500 에러 나고 있어. 긴급 수정해줘.
```

```
프로덕션에서 대시보드 실행하면 무한 로딩이야. 빨리 확인해줘.
```

```
사용자 알림이 오늘 아침부터 안 오고 있어.
```

> Hotfix vs Sprint 자동 판단 → hotfix 브랜치 생성 → 수정

### D-2. Hotfix 마무리

```
hotfix 구현 끝났어. 마무리해줘.
```

> hotfix-close 에이전트 → main PR, 경량 리뷰, 타겟 검증, develop 역머지 안내

### D-3. 실서버 확인 (필요시)

```
배포됐어? 실서버 확인해줘.
```

> deploy-prod 에이전트의 5단계(실서버 검증) 사용

---

## F. 구현 중 유용한 프롬프트

### 중간부터 재개

```
docs/phase/phase{P}/sprint{N}/sprint{N}.md의 Task 4부터 이어서 구현해줘. Task 1~3은 완료됐어.
```

### 특정 Task만 실행

```
docs/phase/phase{P}/sprint{N}/sprint{N}.md의 Task 6만 구현해줘.
```

### 계획 변경이 필요할 때

```
docs/phase/phase{P}/sprint{N}/sprint{N}.md의 Task 3을 구현하다 보니 API 스키마가 달라졌어.
Task 3을 수정하고 이어서 진행해줘.
```

### 막혔을 때

```
Task 4에서 외부 API가 예상과 다른 응답을 줘.
실제 응답은 이거야: {...}
어떻게 처리할지 같이 봐줘.
```

### 구현 도중 다른 버그 발견

```
Task 5 구현 중에 기존 대시보드 페이지에서 버그 발견했어.
이건 나중에 별도로 고치자. 일단 phase{P}-sprint{N} 계속 진행해.
```

### 병렬 실행 (에이전트 팀)

> 📖 [에이전트 팀](https://code.claude.com/docs/ko/agent-teams) — 각 팀원은 독립 컨텍스트 윈도우를 가지며, 공유 태스크 리스트로 조율됩니다. 설계 이유: 백엔드/프론트엔드 Task가 파일이 겹치지 않으면 병렬 실행으로 구현 시간을 단축할 수 있습니다.

docs/phase/phase{P}/sprint{N}/sprint{N}.md의 실행 플랜에 `(병렬 가능)` Phase가 있으면 팀으로 실행할 수 있습니다.

```
docs/phase/phase{P}/sprint{N}/sprint{N}.md의 Phase 2를 팀으로 병렬 실행해줘.
Task 2는 백엔드 팀원, Task 3은 프론트엔드 팀원에게 할당해.
```

팀원 작업 확인:

```
팀원들 작업 상태 알려줘.
```

팀 정리 후 다음 Phase 진행:

```
팀 정리하고 Phase 3 이어서 진행해.
```

> **주의사항:**
> - 같은 파일을 수정하는 Task는 팀으로 실행하지 마세요 (충돌 발생)
> - docs/phase/phase{P}/sprint{N}/sprint{N}.md 실행 플랜에서 `(병렬 가능)` 표시된 Phase만 가능
> - 팀 실행은 토큰 비용이 증가합니다 (별도 인스턴스)
> - 팀원이 작업 중일 때 확인하려면 `Shift+Down`으로 팀원 전환

---

## G. 배포 관련

### 로컬 Docker 스테이징

```
develop 브랜치에서 Docker로 검증하고 싶어.
```

### 프로덕션 배포

```
develop 검증 완료됐어. 프로덕션 배포 해줘.
```

### 여러 Sprint 한번에 배포

```
phase{P}-sprint{N}, phase{P}-sprint{N+1} 배포 준비됐어. 프로덕션 올려줘.
```

### 배포 후 문제 발생

```
방금 배포했는데 헬스체크가 실패해. 확인해줘.
```

```
롤백해야 할 것 같아. 이전 버전으로 돌려줘.
```

---

## H. 문서/관리

### Notion 업데이트

```
phase{P}-sprint{N}에서 DB 스키마 변경했으니 Notion 데이터 모델 페이지 업데이트해줘.
```

```
Phase {N} 완료됐어. Notion 릴리즈 노트 업데이트해줘.
```

### 현재 상태 확인

```
지금 프로젝트 상태 알려줘. 어디까지 진행됐어?
```

```
Phase {N} 남은 작업이 뭐야?
```

### Docker 재시작

```
/restart backend
/restart all
/restart db
```

### 코드 리뷰 요청

```
지금까지 작업한 코드 리뷰해줘.
```

### 로그/디버깅

```
프로덕션 백엔드 로그에서 최근 에러 확인해줘.
```

```
Docker 컨테이너 상태 확인해줘.
```

---

## 팁

### 좋은 프롬프트의 공통점

1. **목적을 먼저 말한다**: "~하고 싶어" → 왜 하는지 맥락 제공
2. **제약조건을 같이 말한다**: "단, 외부 API 호출은 최소화해줘"
3. **기존 시스템을 언급한다**: "기존 대시보드 페이지처럼"
4. **모르는 건 모른다고 한다**: "이 부분은 잘 몰라서 전문가 의견 필요해"

### Claude가 엉뚱하게 갈 때

```
아니야, 그게 아니라 [원래 의도 설명]. docs/phase/phase{P}/sprint{N}/sprint{N}.md 다시 읽고 Task 3부터 해줘.
```

```
지금 하고 있는 건 docs/phase/phase{P}/sprint{N}/sprint{N}.md의 범위 밖이야. Task 목록에 집중해줘.
```

### 세션이 길어져서 컨텍스트가 부족할 때

> 📖 [Claude Code 작동 원리](https://code.claude.com/docs/ko/how-claude-code-works) — 컨텍스트 윈도우가 한계에 도달하면 이전 메시지가 자동 압축됩니다. docs/phase/phase{P}/sprint{N}/sprint{N}.md를 다시 읽으면 압축된 맥락을 복원할 수 있습니다.

```
docs/phase/phase{P}/sprint{N}/sprint{N}.md 다시 읽고 현재 진행 상황 정리해줘.
```

```
새 세션이야. docs/phase/phase{P}/sprint{N}/sprint{N}.md의 Task 5부터 이어서 구현해줘.
```

---

## 참고 문서

### Claude Code 공식 문서

| 주제 | URL |
|------|-----|
| 개요 | https://code.claude.com/docs/ko/overview |
| Quickstart | https://code.claude.com/docs/ko/quickstart |
| 작동 원리 | https://code.claude.com/docs/ko/how-claude-code-works |
| 모델 설정 | https://code.claude.com/docs/ko/model-config |
| CLAUDE.md (프로젝트 메모리) | https://code.claude.com/docs/ko/memory |
| 설정 (settings.json) | https://code.claude.com/docs/ko/settings |
| 커스텀 에이전트 | https://code.claude.com/docs/ko/sub-agents |
| 에이전트 팀 | https://code.claude.com/docs/ko/agent-teams |
| 스킬 | https://code.claude.com/docs/ko/skills |
| Hooks | https://code.claude.com/docs/ko/hooks-guide |
| 권한 설정 | https://code.claude.com/docs/ko/permissions |
| CLI 레퍼런스 | https://code.claude.com/docs/ko/cli-reference |
| Best Practices | https://code.claude.com/docs/ko/best-practices |

### 프로젝트 내부 문서

| 문서 | 용도 |
|------|------|
| `CLAUDE.md` | 프로젝트 규칙, 에이전트 라우팅, 구현 규칙 (매 세션 자동 로드) |
| `.claude/rules/dev-process.md` | 검증 매트릭스, 코드 리뷰 체크리스트, 문서 관리 규칙 (SSOT) |
| `.claude/rules/ci-policy.md` | Git 브랜치 전략, CI/CD 파이프라인 |
| `wiki/setup-guide.md` | 초기 환경 설정 (외부 서비스, Docker) |
| `.claude/agents/*.md` | 7개 에이전트 정의 (model, skills, maxTurns 등) |
| `.claude/rules/*.md` | 경로별 조건부 규칙 (백엔드, 프론트엔드, 워크플로우, Notion) |
| `.claude/hooks/*.sh` | 자동 규칙 강제화 (bash-guard: 위험 명령 차단, doc-checker: 문서 누락 검증) |
| `.claude/hooks/lib/doc-rules.json` | 에이전트별 필수 업데이트 규칙 정의 (확장 시 이 파일만 수정) |

### 설계 의사결정 기록

| 결정 | 이유 |
|------|------|
| sprint-close / sprint-review 분리 | sprint-close에서 코드 리뷰까지 하면 Critical 이슈 시 문서 업데이트가 누락됨. 분리 후 sprint-close는 항상 완결, sprint-review는 재실행 가능 |
| 에이전트별 model 지정 | 계획(Opus)과 실행(Sonnet)을 분리하여 비용 ~70% 절감. 메인 세션은 Sonnet으로 충분 |
| docs/phase/phase{P}/sprint{N}/sprint{N}.md를 SSOT로 | 세션이 바뀌거나 에이전트가 교체되어도 문서 하나만 읽으면 구현 이어감 가능 |
| 실행 플랜(Phase 기반 병렬 그룹) | 독립 Task(백엔드/프론트)를 에이전트 팀으로 병렬 실행하여 구현 시간 단축 |
| 에이전트에 skills 프리로딩 | 에이전트가 스킬을 별도로 호출하는 턴을 절약하여 컨텍스트 소비 감소 |
| 사용자 다음 단계 안내 | 에이전트 종료 후 다음 액션이 명확하여 워크플로우 끊김 방지 |
| 자기 검증 → Hook 자동 검증 | 기존 에이전트 자기 검증 체크리스트를 Stop hook(`doc-checker`)으로 대체. 에이전트가 빠뜨려도 hook이 자동 감지 |
| bash-guard hook | 위험 명령(main push, force push, cd 체이닝 등)을 PreToolUse에서 즉시 차단. 에이전트/사용자 모두 적용 |
