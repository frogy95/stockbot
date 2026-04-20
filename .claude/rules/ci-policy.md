> **Git 브랜치 전략/배포 흐름/롤백 시나리오**: [`dev-process.md`](dev-process.md) §1, §6 참조
> **검증 매트릭스/코드 리뷰 체크리스트**: [`dev-process.md`](dev-process.md) §5, §7 참조

이 문서는 **인프라/CI 설정** 전용입니다. 개발 프로세스/워크플로우는 위 참조를 따릅니다.

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

## 도메인 & HTTPS

### Cloudflare DNS 설정

| 레코드 | 이름 | 값 | 프록시 |
|--------|------|-----|--------|
| CNAME | `@` 또는 `www` | `cname.vercel-dns.com` | DNS only (Vercel이 SSL 처리) |
| CNAME | `api` | Railway 제공 도메인 | Proxied (Cloudflare SSL) |

- Vercel: 커스텀 도메인 설정 후 자동 SSL 발급
- Railway: 커스텀 도메인 설정 후 Cloudflare Proxy로 SSL 처리
- Cloudflare SSL 모드: **Full (Strict)**
