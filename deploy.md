# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 2 Sprint 1 — 핵심 데이터 수집 (2026-03-29)

Sprint 브랜치: `phase2-sprint1` → `develop`
PR: https://github.com/frogy95/stockbot/pull/5

- ⬜ 코드 리뷰 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 (sprint-review 에이전트로 실행 필요)

---

### 프로덕션 배포 - v0.1.0 (2026-03-29) ✅ 완료

포함 스프린트: Phase 0.5 Sprint 1, Phase 1 Sprint 1, Phase 1 Sprint 2
PR: https://github.com/frogy95/stockbot/pull/4

#### 프로덕션 URL

| 서비스 | URL | 상태 |
|--------|-----|------|
| 프론트엔드 (Vercel) | https://stockbot-blush.vercel.app | ✅ 200 |
| 백엔드 (Railway) | https://stockbot-production-6a39.up.railway.app | ✅ healthy |
| Swagger UI | https://stockbot-production-6a39.up.railway.app/docs | ✅ 200 |

#### 배포 전 체크리스트

- ✅ pytest 95개 전체 통과 (0 failed)
- ✅ Docker 4컨테이너 정상 가동 확인
- ✅ 로컬 API 검증 완료 (/api/v1/health, /api/v1/settings, /api/v1/kis/status)
- ✅ develop → main PR #4 생성 및 머지 완료

#### 초기 인프라 설정 (첫 배포)

- ✅ Railway 프로젝트 생성 및 GitHub 연동 (main 브랜치 자동 배포)
- ✅ Railway 환경변수 설정 (POSTGRES_*, REDIS_URL, TRADING_ENV 등)
- ✅ Railway PostgreSQL + Redis 서비스 추가
- ✅ Railway Dockerfile 빌더 설정 (Root Directory: backend)
- ✅ Railway Start Command: `sh -c "alembic upgrade head && PYTHONPATH=/app python scripts/seed_settings.py && uvicorn main:app --host 0.0.0.0 --port $PORT"`
- ✅ Railway 배포 후 alembic upgrade head + seed_settings.py 자동 실행 확인
- ✅ Vercel 프로젝트 생성 및 GitHub 연동 (frontend/ 디렉토리, main 브랜치)
- ✅ Vercel 환경변수 설정 (NEXT_PUBLIC_API_URL)
- ⬜ Cloudflare DNS 설정 (커스텀 도메인 사용 시)

#### 배포 후 검증

- ✅ GET https://stockbot-production-6a39.up.railway.app/api/v1/health → {"status":"healthy","database":"connected","redis":"connected"}
- ✅ GET https://stockbot-production-6a39.up.railway.app/api/v1/settings/trading_env → {"key":"trading_env","value":"paper"}
- ✅ GET https://stockbot-production-6a39.up.railway.app/api/v1/kis/status → {"environment":"paper","token_valid":true}
- ✅ GET https://stockbot-blush.vercel.app → 200
- ✅ Swagger UI https://stockbot-production-6a39.up.railway.app/docs → 200
- ⬜ KIS API 실거래 확인: 평일 장중 수동 검증 필요 (모의거래 시세 조회 + 주문 체결 테스트)

#### 배포 중 트러블슈팅 기록

| 문제 | 원인 | 해결 |
|------|------|------|
| Railpack `pip not found` | Railpack 빌더가 Python 미인식 | Dockerfile 빌더로 변경 |
| `host "postgres" not found` | Docker Compose 기본값 사용 | Railway 참조 변수 `${{Postgres.PG*}}` 설정 |
| `password authentication failed` | Railway PostgreSQL 인증 정보 불일치 | Railway 참조 변수로 올바른 값 매핑 |
| Redis 연결 실패 (502) | Railway Redis 비밀번호 필요 | `REDIS_URL` 환경변수 추가 + 코드 수정 |
| `$PORT` 미확장 | Dockerfile CMD가 셸 변수 확장 안 함 | Start Command에 `sh -c` 래핑 |
| `ModuleNotFoundError: core` | PYTHONPATH 미설정 | `PYTHONPATH=/app` 추가 |
| alembic 행(hang) | 이전 배포의 잠긴 트랜잭션 | `pg_terminate_backend` + Redeploy |

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
