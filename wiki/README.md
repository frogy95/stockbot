# `wiki/` — 현재 상태 지식 베이스

**역할**: 시스템이 "지금 어떻게 동작하는지"를 짧고 링크 가능한 문서로 유지한다. 아키텍처, 데이터 흐름, 도메인 개념이 여기에 모인다.

**주 소비자**: Claude Code (`@wiki/` 참조) + 사람 (Obsidian 등으로 탐색)

**콘텐츠 성격**: 살아있는 지식 — 코드/인프라 변경 시 함께 업데이트. 파일당 1~3KB, `[[링크]]`로 상호 참조.

## 인덱스

진입점은 `index.md`. 대분류:

- 시스템 아키텍처 (system-overview, tech-stack, module-structure)
- 데이터 수집 (data-collection-flow, kis-api, websocket-management, public-data-sources)
- 스크리닝 (screening-pipeline, screening-factors, scoring-system)
- 매매 실행 (trading-modes, signal-generation, momentum-breakout-strategy, order-execution, position-management)
- 리스크 관리 (risk-management, position-sizing)
- 인프라 (deployment, database-schema, redis-usage)
- API 연동 (telegram-integration, external-apis)
- 개발 환경 (paper-vs-live, trading-calendar, setup-guide)

## 편집 규칙

- 1 파일 = 1 개념. 길어지면 분할.
- 상호 참조는 `[[페이지명]]`.
- 세부 실행 규칙은 `.claude/rules/`로, 결정 기록/스펙은 `docs/`로 분리.
- 수정 로그는 `log.md`에 날짜별로 짧게 기록.

## 다른 자산과의 관계

- **`.claude/`** — LLM 실행 규칙(프로세스·컨벤션)은 하네스에 위치. wiki는 지식만.
- **`docs/`** — 시점 기록(PRD, Phase 스펙, 배포 히스토리)은 docs에 위치. wiki는 현재 상태만.
