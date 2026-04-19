# `docs/` — 아티팩트 저장소

**역할**: 우리가 "무엇을 결정했고 무엇을 했는지"의 시점 기록과, 사람이 직접 유지하는 가이드 문서를 보관한다.

**주 소비자**: Claude Code (에이전트가 생성/참조) + 사람

**콘텐츠 성격**: 대부분 불변 시점 기록 — PRD, Phase/Sprint 스펙, 배포·핫픽스 히스토리. 일부 사용자 가이드(`prompt-guide.md`)는 직접 유지.

## 구조

| 경로 | 목적 |
|------|------|
| `prd.md` | 제품 요구사항 (Single Source of Truth) |
| `phase/phase{N}/phase{N}.md` | Phase 계획 (전문가 검토 + 확정 파라미터) |
| `phase/phase{N}/sprint{N}/sprint{N}.md` | 스프린트 실행 명세서 |
| `hotfix/{name}/hotfix.md` | 핫픽스 기록 |
| `deploy-history/YYYY-MM-DD.md` | 배포 기록 아카이브 |
| `experts/` | 에이전트가 참조하는 전문가 프로필 |
| `templates/` | 문서 템플릿 |
| `dashboard/` | 프로젝트 대시보드 HTML |
| `superpowers/specs/` | 설계서 (로컬 전용, gitignore) |
| `superpowers/plans/` | 구현 계획서 (로컬 전용, gitignore) |
| `index.json` | 문서 인덱스 (훅이 자동 갱신) |
| `prompt-guide.md` | 프롬프트 작성 가이드 (사용자 직접 유지) |
| `harness-wiki-guide.md` | 하네스/위키 구성·유지보수 가이드 (사용자 직접 유지) |

## 다른 자산과의 관계

- **시스템 "현재 상태" 지식** — `wiki/`에서 찾는다.
- **LLM 실행 규칙·프로세스** — `.claude/rules/`에서 찾는다.
- `docs/`는 "이 시점에 무엇을 결정했는가"의 감사 기록으로 남는다.
