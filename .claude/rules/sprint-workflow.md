---
paths:
  - "docs/phase/**"
  - "ROADMAP.md"
  - "deploy.md"
---

# 스프린트/핫픽스 워크플로우 규칙

## Sprint 프로세스

> **중요**: 모든 Sprint는 반드시 Phase를 경유합니다. Phase 문서(`docs/phase/phase{P}/phase{P}.md`)가 먼저 존재해야 Sprint를 시작할 수 있습니다.

### 1. 계획 (sprint-planner agent)
- ROADMAP.md + Phase 문서 + 코드베이스 분석 → `docs/phase/phase{P}/sprint{N}/sprint{N}.md` 생성
- sprint{N}.md는 **실행 명세서**: Task별 파일 경로, Step, 검증 명령, 커밋 메시지 포함
- 사용자가 검토/승인한 후 구현 단계로 진행

### 2. 구현 (sprint{N}.md 기준)
- `phase{P}-sprint{N}` 브랜치 생성 (`git checkout -b phase{P}-sprint{N}`)
- **`docs/phase/phase{P}/sprint{N}/sprint{N}.md`를 먼저 읽고** 실행 플랜과 Task 목록을 파악
- 각 Task의 `skill:` 헤더에 명시된 스킬을 Skill 도구로 로드
- 실행 플랜의 Phase 순서대로 Task 실행:
  - **병렬 가능 Phase**: 사용자 요청 시 팀으로 병렬 실행 가능
  - 각 Task의 Step을 따름 (skill별 실행 전략에 따라)
  - 검증 명령으로 결과 확인
  - **simplify** 스킬로 코드 정리 후 커밋
  - 명시된 커밋 메시지로 커밋
- 최종 검증 시 **verification-before-completion** 스킬 적용
- 계획과 다른 결정이 필요하면 사용자에게 확인
- karpathy-guidelines 준수
- worktree 사용 금지

### 3. 마무리 (sprint-close agent)
- sprint-close agent → ROADMAP 업데이트 + develop PR 생성 + 문서 정리
- 코드 리뷰와 자동 검증은 수행하지 않음

### 4. 리뷰 (sprint-review agent)
- PR 검토 후 sprint-review agent → 코드 리뷰 + 자동 검증 + deploy.md 결과 기록
- Critical 이슈 발견 시 수정 후 재실행 가능

### 5. 배포
- QA 후 deploy-prod agent → develop → main PR

## Hotfix 프로세스
1. `main` 기반 `hotfix/{설명}` 브랜치 생성
2. hotfix-close agent → main PR 생성 (develop 아님!)
3. main merge 후 develop 역머지

## Hotfix vs Sprint 판단 기준

`docs/dev-process.md` 섹션 2 참조.

## 문서 구조
- Phase 문서: `docs/phase/phase{P}/phase{P}.md`
- 실행 명세서: `docs/phase/phase{P}/sprint{N}/sprint{N}.md`
- Task 문서: `docs/phase/phase{P}/sprint{N}/task{N}/task{N}.md`
- 첨부 파일 (스크린샷, 보고서 등): `docs/phase/phase{P}/sprint{N}/task{N}/`
- 검증 원칙: `docs/dev-process.md` 섹션 5
