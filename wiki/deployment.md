# 배포 환경

프로덕션은 Vercel(프론트엔드) + Railway(백엔드)로 분리 배포.

## 인프라 구성

```
Cloudflare (DNS/CDN)
  ├── stockbot.choiji.kr     → Vercel (Next.js)
  └── api.stockbot.choiji.kr → Railway (FastAPI)
                                  ├── PostgreSQL 16
                                  └── Redis 7
```

## Vercel (프론트엔드)

- 역할: Next.js 대시보드 호스팅
- 브랜치 자동 배포: `main` → 프로덕션
- 환경변수: `NEXT_PUBLIC_API_URL` (Railway 백엔드 URL)
- 배포 URL: `stockbot.choiji.kr`

## Railway (백엔드)

- 역할: FastAPI + PostgreSQL + Redis
- Start Command: `uvicorn main:app --host 0.0.0.0 --port 8000`
- 환경변수: `.env` 파일 내 모든 설정 — [[tech-stack|기술 스택]] 참조
- 배포 URL: `api.stockbot.choiji.kr`

### Railway 서비스 구성

| 서비스 | 설명 |
|--------|------|
| `backend` | FastAPI 앱 |
| `postgres` | PostgreSQL 16 |
| `redis` | Redis 7 |

## 로컬 개발 환경

Docker Compose 4컨테이너:
```yaml
services:
  backend:  # FastAPI :8000
  frontend: # Next.js :3000
  postgres: # PostgreSQL :5432
  redis:    # Redis :6379
```

```bash
cp .env.example .env
docker compose up -d
```

## 배포 프로세스

`.claude/rules/dev-process.md` 및 `ROADMAP.md` 참조.

```
develop 브랜치 개발
→ Sprint Close (PR 생성)
→ Sprint Review (코드 리뷰 + 검증)
→ deploy-prod 에이전트 (develop → main PR + 체크리스트)
→ Vercel/Railway 자동 배포 트리거
→ 수동 검증 (deploy.md 참조)
```

## 현재 버전

- 프로덕션: v2.1.1 (Phase 7.0.1 Sprint 1, 2026-04-16 배포)
- 최신 커밋: KIS LIVE WebSocket 연결 복구 (`/tryitout` 경로 추가)

## 마이그레이션

DB 마이그레이션은 Alembic:
```bash
# 로컬
docker compose exec backend alembic upgrade head
# Railway: 배포 시 Start Command에 포함하거나 수동 실행
```

## CI/CD

`.claude/rules/ci-policy.md` 참조:
- `main`, `develop` 직접 push 금지, PR만 허용
- 허용 브랜치: `phase{P}-sprint{N}`, `hotfix/*`, `chore/*`, `docs/*`, `refactor/*`
