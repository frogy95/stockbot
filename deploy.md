# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 1 Sprint 1: Docker Compose + DB/Redis + 백엔드 스켈레톤 (2026-03-29)

PR: https://github.com/frogy95/stockbot/pull/2 (phase1-sprint1 → develop)

#### 코드 리뷰 결과

- ✅ 코드 리뷰 완료 (2026-03-29)
- Critical/High 이슈: 없음
- Medium 이슈 1건:
  - `backend/api/routes/health.py` L20: `except Exception: pass` — DB/Redis 연결 실패 시 예외를 조용히 무시하고 로깅 없음. 다음 Sprint에서 구조화 로깅 도입 시 함께 개선 권장.

#### 자동 검증 결과

- ✅ Docker 4컨테이너 정상 기동 (backend, frontend, postgres, redis 모두 Up/healthy)
- ✅ pytest -v: 24개 테스트 전체 통과 (test_config 4개, test_health 3개, test_integration 7개, test_models 5개, test_redis 4개 + test_get_or_set)
- ✅ GET /api/v1/health: `{"status": "healthy", "database": "connected", "redis": "connected"}`
- ✅ Swagger UI (/docs): HTTP 200
- ✅ 프론트엔드 (http://localhost:3000): HTTP 200
- ✅ DB 테이블: settings, stocks, market_data, alembic_version (4개)
- ✅ 시드 데이터: settings 테이블 21개 행 확인
- ✅ Phase 문서 반영 완료 (docs/phase/phase1/phase1.md Sprint 1 완료 표시)

#### 수동 검증 필요 항목

- ⬜ 배포 후 develop → main PR 생성 (sprint-review 완료 — deploy-prod 시 실행)
- ⬜ alembic upgrade head (DB 스키마 변경 있으므로 배포 환경에서 수동 실행 필요)
- ⬜ UI 디자인/시각적 품질 판단 (브라우저에서 http://localhost:3000 직접 확인)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
