# PRD to ROADMAP 메모리

이 파일은 prd-to-roadmap 에이전트의 영구 메모리입니다.
PRD 분석 패턴, 로드맵 생성 이력 등을 기록합니다.

## 문서 구조 (2026-03-27 업데이트)

- 문서 경로: `docs/phase/phase{N}/sprint{N}/task{N}/`
- Sprint 번호: phase 내 로컬 번호 (phase1/sprint1, phase1/sprint2, phase2/sprint1...)
- 브랜치명: `phase{P}-sprint{N}` (예: phase1-sprint1)
- 모든 Sprint는 반드시 Phase를 경유하여 생성
- index.json: `docs/index.json` — 프로젝트 히스토리 관리
- Hotfix 문서: `docs/hotfix/{name}/hotfix.md`
