# Sprint Planner 메모리

이 파일은 sprint-planner 에이전트의 영구 메모리입니다.
프로젝트 진행 상황, 기술 스택, 패턴 등을 기록합니다.

## 문서 구조 (2026-03-27 업데이트)

- 문서 경로: `docs/phase/phase{N}/sprint{N}/task{N}/`
- Sprint 번호: phase 내 로컬 번호 (phase1/sprint1, phase1/sprint2, phase2/sprint1...)
- 브랜치명: `phase{P}-sprint{N}` (예: phase1-sprint1)
- 모든 Sprint는 반드시 Phase를 경유하여 생성
- index.json: `docs/index.json` — 프로젝트 히스토리 관리
- Hotfix 문서: `docs/hotfix/{name}/hotfix.md`

## 스프린트 현황 (2026-03-29 업데이트)

- [Phase 0.5 Sprint 1](phase0.5-sprint1-status.md) — 외부 API 5종 탐색/검증, ✅ 완료 (2026-03-29)
- [Phase 1 Sprint 1](phase1-sprint1-status.md) — Docker Compose + DB/Redis + 백엔드 스켈레톤, ✅ 완료 (2026-03-29) / PR: https://github.com/frogy95/stockbot/pull/2
- Phase 1 Sprint 2 — 한투 API 연동 + 토큰 관리 + 모의/실전 전환, 🔄 계획 완료 (2026-03-29)

## 다음 사용 가능한 스프린트

- Phase 2 Sprint 1 — 데이터 수집 + 종목 스크리닝 (📋 예정, Phase 1 완료 후)

## 핵심 주의사항

- Phase 1 Sprint 1에서 확인: SQLAlchemy async 모델에서 UniqueConstraint는 `__table_args__`로 명시 필요
- redis[hiredis] 패키지명으로 설치 시 redis.asyncio 임포트 정상 동작 확인
- pytest-asyncio는 `asyncio_mode = "auto"` 설정 필수 (pytest.ini 또는 pyproject.toml)
- Sprint 2 관련: conftest.py에서 DB 엔진 글로벌 상태 리셋 (이벤트 루프 충돌 방지)
- Sprint 2 관련: 기존 main.py lifespan에 Redis connect/disconnect만 있음 -> KIS 클라이언트 초기화 추가 필요
- Sprint 2 관련: exploration/kis/ 참조용 코드 있음 (01_auth, 02_stock_price, 05_order_test, 06_websocket) -- 코드 복사 금지, 패턴만 참조
