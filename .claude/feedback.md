# Harness Feedback Log

하네스(skills, agents, hooks, rules) 개선을 위한 피드백 수집 파일.
세션 중 발견한 문제점, 개선 아이디어, 교정 사항을 기록한다.

## 사용법

- **수동 기록**: "피드백 기록해줘: ~~" 라고 말하면 여기에 추가
- **반영**: 원할 때 이 파일을 읽고 해당 skill/agent/hook/rule 정의를 수정
- **반영 후**: 해당 항목을 `반영 완료` 섹션으로 이동 (날짜 포함)

## 미반영

<!-- 형식: - [대상] 내용 (날짜) -->
<!-- 대상: skill | agent | hook | rule | claude.md -->
<!-- 예시: - [agent] sprint-planner가 task 의존성 순서를 잘못 잡음 → 의존성 검증 단계 추가 필요 (2026-03-30) -->

- [rule] backend.md — 새 환경변수를 config.py에 추가할 때 .env.example에도 반드시 추가하는 규칙 없음 → 명시 필요 (2026-03-30)
- [rule] backend.md 또는 sprint-workflow.md — 신규 환경변수가 프로덕션(Railway 등) 수동 설정이 필요한 경우 deploy.md 수동 검증 항목에 기록하는 규칙 없음 → sprint-close/sprint-review 체크리스트에 추가 필요 (2026-03-30)
- [agent] hotfix-close — develop 역머지 시 GitHub 저장소 규칙(PR 필수)을 고려하지 않음. `git merge main` 직접 push 안내 대신 역머지 PR 생성 절차로 변경 필요 (2026-03-31)
- [rule] dev-process.md §4 — Hotfix 흐름이 `main을 develop에 역머지`로만 기술되어 있으나, GitHub branch protection으로 직접 push 불가. PR 기반 역머지 절차 명시 필요 (2026-03-31)
- [agent] hotfix-close — hotfix 완료 후 업데이트된 문서(예: docs/hotfix/market-open-recovery/hotfix.md)가 커밋되지 않은 채 남아있음. hotfix-close가 PR 생성 전 변경된 문서 파일을 자동으로 스테이징·커밋하는 단계가 누락된 것으로 보임 → 문서 변경사항 커밋 단계 추가 필요 (2026-03-31)
- [hook] bash-guard — 운영 로그성 문서(docs/hotfix/**, docs/deploy-history/**, deploy.md)는 소스 변경 없이 develop에 직접 커밋/push해도 무방하나, 현재 bash-guard가 파일 종류 구분 없이 develop 직접 push를 일괄 차단함 → docs 전용 커밋에 한해 develop 직접 push 예외 허용. 단 main 직접 push는 계속 차단 유지. 에이전트 소비 문서(CLAUDE.md, .claude/rules/*, .claude/agents/*, docs/index.json 등)는 예외 대상에서 제외 (2026-03-31)

## 반영 완료

<!-- 형식: - [대상] 내용 (기록일 → 반영일) -->
