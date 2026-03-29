> **개발 프로세스/검증 절차**: [`docs/dev-process.md`](dev-process.md) 참조
> **롤백 시나리오 상세(DB 백업 포함)**: [`docs/dev-process.md` 섹션 6.4](dev-process.md#64-롤백-시나리오) 참조

## Git 브랜치 전략 & 배포 흐름

### 브랜치 구조

| 브랜치 | 역할 | 배포 환경 |
|--------|------|----------|
| `phase{P}-sprint{N}` | 스프린트 단위 개발 작업 | 로컬 |
| `develop` | 스테이징 통합 브랜치 | 로컬 Docker |
| `main` | 프로덕션 브랜치 | Vercel + Railway |
| `hotfix/*` | 긴급 운영 패치 | main + develop 동시 반영 |

---

### 배포 흐름

```
phase{P}-sprint{N}
  ↓ PR & merge (스프린트 완료 시)
develop ──────────────→ 로컬 docker compose up --build 로 스테이징 검증
  ↓ PR & merge (QA 통과 후)
main    ──────────────→ Vercel 자동 배포 (프론트엔드)
                        Railway 자동 배포 (백엔드)
  ↓ tag
v1.0.0, v1.1.0 ...
```

### Hotfix 배포 흐름

```
hotfix/*
  ↓ PR & merge (긴급 패치)
main    ──────────────→ Vercel + Railway 자동 배포
  ↓ 역머지
develop ──────────────→ main 변경사항 동기화
```

---

### 핵심 규칙

- `main` 직접 push 금지 — 반드시 PR + 리뷰 후 merge
- `develop` → `main` merge는 QA 통과 후 진행
- 긴급 패치는 **`main` 기반**으로 `hotfix/*` 브랜치를 생성하여 작업
- hotfix PR은 **`main`으로 직접** 생성 (develop 거치지 않음)
- main merge 후 반드시 `develop`에 역머지하여 동기화
- hotfix 범위 제한: 파일 3개 이하, 코드 50줄 이하, DB 변경 없음, 새 의존성 없음

---

## CI 파이프라인 (PR 체크)

PR이 `develop` 또는 `main`으로 올라오면 GitHub Actions가 자동으로 실행됩니다.

### 필수 통과 조건

1. **pytest 통과** — `backend/tests/` 전체 테스트 통과 필수
2. **TypeScript 타입 체크** — `cd frontend && npx tsc --noEmit` 통과

PR merge는 위 조건이 모두 통과된 후에만 가능합니다 (Branch Protection Rule).

---

## CD 파이프라인 (배포 흐름)

### develop merge 후 (스테이징 검증)

`develop` 브랜치는 별도 서버 없이 **로컬 Docker**로 스테이징 검증합니다.

```bash
git pull origin develop
docker compose up --build
```

### main merge 후 (프로덕션 배포)

`main` 브랜치에 merge되면 자동 배포됩니다:

**프론트엔드 (Vercel)**:
- Vercel GitHub Integration이 자동 감지 → 빌드 → 배포
- PR 생성 시 Preview URL 자동 생성

**백엔드 (Railway)**:
- Railway GitHub Integration이 자동 감지 → 빌드 → 배포
- Dockerfile 기반 빌드 또는 Nixpacks 자동 감지

---

## 환경별 설정 관리

| 환경 | 설정 방법 | 비고 |
|------|----------|------|
| 로컬 개발 | `.env` 파일 | Git 미추적 (`.gitignore`) |
| Vercel 프론트엔드 | Vercel 환경변수 | 대시보드 또는 `vercel env` |
| Railway 백엔드 | Railway 환경변수 | 대시보드 또는 `railway variables` |

### 필수 환경변수

**Vercel (프론트엔드)**:

| 변수 | 설명 |
|------|------|
| `NEXT_PUBLIC_API_URL` | Railway 백엔드 API URL |

**Railway (백엔드)**:

| 변수 | 설명 |
|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL (Railway 자동 주입) |
| `REDIS_URL` | Redis 연결 URL (Railway 자동 주입) |
| `SECRET_KEY` | 앱 시크릿 키 |
| `JWT_SECRET` | JWT 서명 키 |
| `KIS_APP_KEY` / `KIS_APP_SECRET` | 한투 API 키 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 텔레그램 봇 |
| `CORS_ORIGINS` | Vercel 프론트엔드 도메인 |

---

## 롤백 절차

> 시나리오별 상세 절차(DB 백업 포함)는 [docs/dev-process.md 섹션 6.4](dev-process.md#64-롤백-시나리오) 참조.

### 프론트엔드 롤백 (Vercel)

```bash
vercel rollback
```

또는 Vercel 대시보드에서 이전 배포를 Promote.

### 백엔드 롤백 (Railway)

```bash
railway rollback --service backend
```

또는 Railway 대시보드에서 이전 배포를 Rollback.

### DB 마이그레이션 롤백

```bash
railway run --service backend alembic downgrade -1
```

> DB 마이그레이션 롤백은 데이터 손실이 발생할 수 있습니다. 롤백 전 반드시 DB 백업을 수행하세요.

---

## 도메인 & HTTPS

### Cloudflare DNS 설정

| 레코드 | 이름 | 값 | 프록시 |
|--------|------|-----|--------|
| CNAME | `@` 또는 `www` | `cname.vercel-dns.com` | DNS only (Vercel이 SSL 처리) |
| CNAME | `api` | Railway 제공 도메인 | Proxied (Cloudflare SSL) |

- Vercel: 커스텀 도메인 설정 후 자동 SSL 발급
- Railway: 커스텀 도메인 설정 후 Cloudflare Proxy로 SSL 처리
- Cloudflare SSL 모드: **Full (Strict)**
