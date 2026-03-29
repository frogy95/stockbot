# 프로젝트 로드맵

> 이 파일은 프로젝트 전체 진행 상황의 Single Source of Truth입니다.
> - **prd-to-roadmap** 에이전트가 PRD를 기반으로 초기 로드맵을 생성합니다.
> - **sprint-close** 에이전트가 스프린트 완료 시 상태를 업데이트합니다.
> - Phase/Sprint 구조는 `docs/phase/phase{N}/phase{N}.md`, `docs/phase/phase{P}/sprint{N}/sprint{N}.md`와 연동됩니다.

## 개요

- **프로젝트 목표**: (TODO: 프로젝트 목표를 한 줄로 요약하세요)
- **전체 예상 기간**: (TODO)
- **현재 진행 단계**: Phase 0 — 프로젝트 초기 설정

## 진행 상태 범례

- ✅ 완료
- 🔄 진행 중
- 📋 예정
- ⏸️ 보류

---

## 📊 프로젝트 현황 대시보드

| 항목 | 내용 |
|------|------|
| 전체 진행률 | 0% |
| 현재 Phase | Phase 0 |
| 다음 마일스톤 | Sprint 1 시작 |

---

## Phase 0: 프로젝트 초기 설정 ✅

- ✅ 저장소 생성 및 브랜치 전략 설정
- ✅ Claude Code 에이전트 설정
- ✅ CI/CD 파이프라인 구성
- ✅ 개발 프로세스 문서화

---

## Phase 1: (TODO: 첫 번째 단계 이름) 📋

> TODO: `prd-to-roadmap` 에이전트를 사용하여 PRD를 기반으로 상세 로드맵을 생성하세요.
> 또는 수동으로 Phase와 Sprint를 직접 작성하세요.

**Phase 문서**: `docs/phase/phase1/phase1.md` (phase-planner 에이전트가 생성)

### Sprint 예시 구조

| Sprint | 주제 | 상태 | PR |
|--------|------|------|-----|
| Sprint 1 | (TODO: 핵심 기능) | 📋 예정 | — |
| Sprint 2 | (TODO: 추가 기능) | 📋 예정 | — |
| Sprint 3 | (TODO: 테스트/마무리) | 📋 예정 | — |

> sprint-planner 에이전트가 각 Sprint의 상세 계획(`docs/phase/phase{P}/sprint{N}/sprint{N}.md`)을 생성합니다.

---

## ⚠️ 리스크 및 완화 전략

| 리스크 | 영향도 | 완화 방안 |
|--------|--------|----------|
| (TODO) | - | - |

---

## 📈 마일스톤

| 마일스톤 | 목표 날짜 | 상태 |
|---------|---------|------|
| MVP 출시 | (TODO) | 📋 예정 |

---

## 🔮 향후 계획 (Backlog)

- (TODO: MVP 이후 고려할 기능들)
