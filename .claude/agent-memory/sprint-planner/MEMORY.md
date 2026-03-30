# Sprint Planner 메모리

이 파일은 sprint-planner 에이전트의 영구 메모리입니다.
프로젝트 진행 상황, 기술 스택, 패턴 등을 기록합니다.

## 스프린트 현황 (2026-03-30 업데이트)

- [Phase 0.5 Sprint 1](phase0.5-sprint1-status.md) — 외부 API 5종 탐색/검증, ✅ 완료 (2026-03-29)
- [Phase 1 Sprint 1](phase1-sprint1-status.md) — Docker Compose + DB/Redis + 백엔드 스켈레톤, ✅ 완료 (2026-03-29) / PR: https://github.com/frogy95/stockbot/pull/2
- [Phase 1 Sprint 2](phase1-sprint2-status.md) — 한투 API 연동 + 토큰 관리 + 모의/실전 전환, ✅ 완료 (2026-03-29) / PR: https://github.com/frogy95/stockbot/pull/3
- [Phase 2 Sprint 1](phase2-sprint1-status.md) — 핵심 데이터 수집 (공공데이터포털 + 한투 WS/REST + 체결강도), ✅ 완료 (2026-03-29) / PR: https://github.com/frogy95/stockbot/pull/5
- [Phase 2 Sprint 2](phase2-sprint2-status.md) — 종목 스크리닝 엔진 (1차/2차 스크리닝 + 팩터 스코어링), ✅ 완료 (2026-03-29) / PR: https://github.com/frogy95/stockbot/pull/6
- Phase 2 Sprint 3 — 보조 데이터 + 통합 테스트 (DART 재무 + 네이버 센티멘트), ✅ 완료 (2026-03-30) / PR: https://github.com/frogy95/stockbot/pull/7
- Phase 2.5 Sprint 1 — ETF 마스터 수집 + 스케줄러 통합, ✅ 완료 (2026-03-30) / PR: https://github.com/frogy95/stockbot/pull/26

## 다음 사용 가능한 스프린트

- Phase 3 Sprint 1 — 리스크/자금 관리 모듈 (Phase 2.5 완료, Phase 3 계획 필요)

## 핵심 주의사항

- Phase 1 Sprint 1에서 확인: SQLAlchemy async 모델에서 UniqueConstraint는 `__table_args__`로 명시 필요
- redis[hiredis] 패키지명으로 설치 시 redis.asyncio 임포트 정상 동작 확인
- pytest-asyncio는 `asyncio_mode = "auto"` 설정 필수 (pytest.ini 또는 pyproject.toml)
- conftest.py에서 DB 엔진 글로벌 상태 리셋 (이벤트 루프 충돌 방지)
- exploration/kis/ 참조용 코드 있음 — 코드 복사 금지, 패턴만 참조
- Phase 2 Sprint 1에서 확인: DB 세션은 의존성 주입(get_db) 대신 독립 생성하여 테스트 격리 확보
- Phase 2 Sprint 1에서 확인: screening_results 테이블에 created_at/updated_at 추가 필요 (리뷰에서 지적)
- Phase 2 Sprint 3: DART corp_code XML은 93MB ZIP — lxml 파싱 필요, zipfile로 압축 해제 후 처리
- Phase 2 Sprint 3: DART 재무 조회 대상은 1차 스크리닝 통과 종목만 (최대 30건, 일 10,000건 한도 절약)
- Phase 2 Sprint 3: 네이버 센티멘트는 ML 모델 없이 키워드 사전 기반 간이 점수만 (보조 팩터용)
- Phase 2 Sprint 3: 보조 데이터는 팩터 스코어링에 통합하지 않음 — 별도 조회 API만 (Phase 5에서 통합 예정)
- Phase 2.5: mst URL(https://new.real.download.dws.co.kr/common/master/)은 SLA 미보장 — Sprint 착수 전 curl -I 수동 검증 필수
- Phase 2.5: KOSPI/KOSDAQ mst 파일은 필드 구조가 다름 — 파서 분리 구현 필수 (단일 파서 금지)
- Phase 2.5: Stock 모델 변경 없음 — 기존 stock_type/extra_data 필드 활용, Alembic 마이그레이션 불필요
- Phase 2.5: 기존 스케줄러의 ETF 시세 수집 시간을 08:05 -> 08:15로 변경해야 함 (확정 파라미터)
- Phase 2.5 Sprint 1: bash-guard 정규식이 소수점 브랜치명(phase2.5-*)을 차단 — .claude/hooks/pretooluse-bash-guard.sh 수정 완료
- Phase 2.5 Sprint 1: asyncio.gather 병렬 다운로드로 KOSPI+KOSDAQ mst 동시 처리 — httpx.AsyncClient 사용
- Phase 2.5 Sprint 1: func.count()로 DB ETF 종목 수 조회 후 prev_count 전달하여 sanity check ±10% 변동 감지
