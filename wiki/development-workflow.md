# 개발 워크플로우

Claude Code와 협업하는 AI-first 개발 프로세스. 상세: `docs/dev-process.md`.

## 프로젝트 라이프사이클

```
PRD → prd-to-roadmap → ROADMAP.md
  → phase-planner → docs/phase/phase{N}/phase{N}.md
    → sprint-planner → docs/phase/phase{P}/sprint{N}/sprint{N}.md
      → 구현 (/sprint-dev)
        → sprint-close (PR 생성)
          → sprint-review (코드 리뷰 + 검증)
            → deploy-prod (프로덕션 배포)
```

## 브랜치 전략

| 브랜치 | 용도 |
|--------|------|
| `main` | 프로덕션 (직접 push 금지) |
| `develop` | 통합 개발 (직접 push 금지) |
| `sprint/{phase}-{sprint}` | 스프린트 작업 브랜치 |
| `hotfix/{issue}` | 핫픽스 브랜치 |

## 스프린트 워크플로우

1. `sprint-planner` 에이전트로 sprint.md 작성
2. `/sprint-dev {P}-{N}` 커맨드로 구현 실행
3. `sprint-close` 에이전트로 PR 생성
4. `sprint-review` 에이전트로 코드 리뷰 + 검증
5. `deploy-prod` 에이전트로 프로덕션 배포

## 핫픽스 워크플로우

프로덕션 버그 발견 시:
1. `hotfix/{issue}` 브랜치 생성
2. 수정 구현
3. `hotfix-close` 에이전트로 PR 생성 + 검증
4. `main` 머지 후 `develop`에 역머지

## 에이전트 도구

| 용도 | 에이전트 |
|------|---------|
| Phase 계획 | `phase-planner` |
| 스프린트 계획 | `sprint-planner` |
| 스프린트 구현 | `/sprint-dev` |
| PR 생성 | `sprint-close` |
| 코드 리뷰 | `sprint-review` |
| 프로덕션 배포 | `deploy-prod` |
| 핫픽스 마무리 | `hotfix-close` |

## 검증 원칙

- 코드 작성 후 반드시 테스트 실행
- 프로덕션 배포 전 develop 검증 필수
- 수동 검증 항목은 `deploy.md` 참조

## 문서 업데이트 의무

- `ROADMAP.md`: sprint-close 시 자동 업데이트
- `deploy.md`: 배포 후 수동 작업 추적
- `docs/index.json`: 주요 문서 인덱스

## Phase 데이터 의존성 원칙

후속 Phase가 역사적 데이터를 필요로 하면 이전 Phase에서 수집 파이프라인을 선행 구축. 데이터 미축적 상태에서 착수 시 경고 필수.

데이터 의존성 맵: `ROADMAP.md` 참조.
