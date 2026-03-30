**사용자가 명시적으로 "1"을 선택하거나 "/sprint-dev"를 입력할 때만 실행한다. sprint-planner 완료 후 자동으로 호출하지 않는다. 반드시 사용자 응답을 기다린다.**

docs/phase/phase{P}/sprint{N}/sprint{N}.md에 따라 스프린트를 구현하는 오케스트레이터.

## 인수

`$ARGUMENTS`: phase와 sprint 번호 (예: `1-2`, `phase1-sprint2`, `34`)
- 형식 `1-2` 또는 `phase1-sprint2` → phase1, sprint2로 파싱
- `docs/phase/phase{P}/sprint{N}/sprint{N}.md` 경로를 결정한다.
- 하위호환: 숫자 하나만 오면 (`34` 등) `docs/index.json`을 읽어 `current_phase` 필드에서 활성 phase를 조회한 뒤 경로를 결정한다.

## 실행 절차

### 1단계: 스프린트 문서 읽기

1. `docs/phase/phase{P}/sprint{N}/sprint{N}.md`를 **전체** 읽는다.
2. 다음을 파악한다:
   - **실행 플랜**: Phase 구조와 각 Phase의 Task 목록
   - **의존성 그래프**: Task 간 선후 관계
   - **병렬 가능 표시**: Phase 제목에 `(병렬 가능)` 또는 본문에 병렬 관련 안내가 있는지
   - **각 Task의 skill 헤더**: 참조할 스킬
   - **각 Task의 Step**: 구체적 실행 순서
   - **각 Task의 검증 명령과 커밋 메시지**

### 2단계: 브랜치 준비

1. 현재 브랜치가 `phase{P}-sprint{N}`이 아니면:
   - `develop` 브랜치에서 `git checkout -b phase{P}-sprint{N}` 으로 생성
2. 이미 `phase{P}-sprint{N}` 브랜치면 그대로 진행

### 3단계: Phase 순차 실행

실행 플랜의 Phase를 **순서대로** 처리한다. 각 Phase에 대해:

#### 병렬 Phase인 경우 (Phase 제목에 "병렬 가능" 표시)

1. Skill 도구로 `dispatching-parallel-agents`를 로드하여 병렬 구성 가이드를 참조한다.
2. **사용자에게 팀 구성 제안**:
   ```
   📋 Phase {N} — 병렬 실행 가능

   | Agent | Task | skill | 설명 |
   |-------|------|-------|------|
   | agent-1 | Task X | karpathy-guidelines | ... |
   | agent-2 | Task Y | frontend-design | ... |

   팀으로 병렬 실행할까요? (y/순차로 진행)
   ```
3. 사용자가 승인하면:
   - Agent 도구로 **동시에** 여러 에이전트를 실행한다.
   - 각 에이전트의 프롬프트에는 해당 Task의 전체 Step, 파일 목록, 검증 명령을 포함한다.
   - **skill 주입**: Task의 `skill:` 헤더에 명시된 스킬명과 핵심 원칙을 에이전트 프롬프트에 포함한다.
   - 에이전트에게 **커밋은 하지 말 것**을 명시한다 (커밋은 메인 오케스트레이터가 수행).
   - 에이전트 완료 후 메인 세션에서 **simplify + 커밋**을 순차 수행한다.
4. 사용자가 거부하면 → 순차 Phase와 동일하게 처리

#### 순차 Phase인 경우

Phase 내 각 Task를 순서대로 실행한다. **매 Task마다 아래 체크리스트를 반드시 수행한다:**

```
Task 실행 체크리스트 (건너뛰기 금지):
1. ⬜ skill 로드 — `skill:` 헤더가 있으면 Skill 도구 호출
2. ⬜ Step 실행 — sprint{N}.md의 Step 순서대로 (skill별 실행 전략 참조)
3. ⬜ 검증 통과 — 명시된 검증 명령 실행
4. ⬜ simplify — Skill("simplify") 실행 (생략 불가)
5. ⬜ 커밋 — 커밋 메시지에 task ID 필수 포함 (예: `feat(phase1-sprint1): task3 — 내용`)
```

> **index.json 자동 동기화**: PostToolUse hook(`posttooluse-index-sync.sh`)이 `git commit` 감지 시 자동으로 task.status → completed, progress 갱신, commits[] 기록을 수행합니다. 수동 업데이트 불필요.

각 단계 상세:

1. **Task 시작 알림**: `🔨 Task {N}: {제목} 시작`
2. **skill 로드**: Task의 `skill:` 헤더에 명시된 스킬이 있으면 Skill 도구로 로드하고 skill별 실행 전략에 따라 진행한다.
3. **Step 실행**: sprint{N}.md에 명시된 Step을 순서대로 수행한다.
4. **검증**: sprint{N}.md에 명시된 검증 명령을 실행하고 결과를 확인한다.
5. **simplify**: Skill 도구로 `simplify`를 로드하고, 이번 Task에서 수정한 코드를 정리한다.
6. **커밋**: 커밋 메시지에 **task ID를 반드시 포함**한다. 형식: `feat(phase{P}-sprint{N}): task{N} — 설명`
   - 예: `feat(phase1-sprint1): task3 — SQLAlchemy 모델 + Alembic 마이그레이션`
   - sprint{N}.md에 커밋 메시지가 명시되어 있으면 앞에 `task{N} — `를 추가한다.
   - hook이 task ID(`task1`, `task2` 등)로 매칭하여 index.json을 자동 업데이트한다 (task.status, progress, commits[]).
   - hook이 수정한 index.json은 **다음 커밋에 포함**시킨다 (별도 chore 커밋 불필요, 다음 task 커밋에 함께 stage).
7. **완료 보고**: 완료 기준 체크리스트를 표시한다.

### 4단계: Phase 체크포인트

각 Phase 완료 후 사용자에게 보고하고 다음 Phase 진행 여부를 확인한다:

```
✅ Phase {N} 완료

완료된 Task:
- [x] Task X: {제목} — {검증 결과 요약}
- [x] Task Y: {제목} — {검증 결과 요약}

다음: Phase {N+1} — {Task 목록 요약}
계속 진행할까요?
```

**예외**: 마지막 Phase가 아닌 경우에만 확인을 묻는다. 사용자가 "끝까지" 또는 "전부" 같은 지시를 한 경우 체크포인트를 건너뛴다.

### 5단계: 최종 검증

모든 Phase 완료 후:

1. Skill 도구로 `verification-before-completion`을 로드한다.
2. sprint{N}.md의 **최종 검증 계획** 섹션에 명시된 검증을 모두 실행한다.
3. 검증 명령 실행 결과를 **실증(로그/출력)**으로 제시한다. 결과 없이 "통과했다"고 주장하지 않는다.
4. 결과를 요약 보고하고, **사용자에게 다음 단계를 선택**하도록 묻는다:
   ```
   🏁 Sprint {N} 구현 완료

   | 검증 항목 | 결과 |
   |-----------|------|
   | pytest 전체 | ✅ X passed |
   | 타입체크 | ✅ 에러 없음 |
   | ... | ... |

   📋 다음 단계를 선택해주세요:
   1. sprint-close 진행 (PR 생성 + 문서 정리)
   2. 추가 작업 후 수동 진행

   반드시 사용자 응답을 기다린 후 진행합니다.
   ```
   사용자가 1을 선택하면 Agent 도구로 `sprint-close` 에이전트를 호출한다.

## skill별 실행 전략

Task의 `skill:` 헤더에 따라 Step 실행 방식이 달라진다:

| skill | 실행 방식 |
|-------|----------|
| `systematic-debugging` | Skill 로드 → 원인 분석 → 수정 |
| `frontend-design` | Skill 로드 → 디자인 탐색 후 구현 |
| `feature-dev:feature-dev` | code-explorer Agent로 탐색 → 결과 기반 구현 |
| `brainstorming` | Skill 로드 → 설계 탐색 → 사용자 확인 → 구현 |
| `simplify` | Skill 로드 → 기능 변경 없이 코드 정리 |
| (없음) | Step을 그대로 실행 |

## 주의사항

- **sprint{N}.md가 Single Source of Truth**: 문서에 명시되지 않은 작업은 하지 않는다.
- **계획과 다른 결정이 필요하면 사용자에게 확인**한다.
- **커밋 메시지**: sprint{N}.md에 명시된 것을 그대로 사용한다.
- **검증 실패 시**: 실패 원인을 분석하고 수정한 뒤 재검증한다. 3회 실패 시 사용자에게 보고한다.
- **코드 리뷰는 이 커맨드의 범위 밖**: `sprint-review` 에이전트가 담당한다.
- **worktree 사용 금지**: `git checkout -b`로 브랜치를 생성한다.
- **`cd /path &&` 접두사 사용 금지**.
- **브랜치명**: 반드시 `phase{P}-sprint{N}` 형태를 사용한다.
- **스프린트 문서 경로**: `docs/phase/phase{P}/sprint{N}/sprint{N}.md` 형태를 사용한다.
