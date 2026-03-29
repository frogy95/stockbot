> **개발 프로세스/검증 절차**: [`docs/dev-process.md`](dev-process.md) 참조
> **롤백 시나리오 상세(DB 백업 포함)**: [`docs/dev-process.md` 섹션 6.4](dev-process.md#64-롤백-시나리오) 참조

## Git 브랜치 전략 & 배포 흐름

### 브랜치 구조

| 브랜치 | 역할 | 배포 환경 |
|--------|------|----------|
| `sprint{n}` | 스프린트 단위 개발 작업 | 로컬 |
| `develop` | 스테이징 통합 브랜치 | 로컬 Docker |
| `main` | 프로덕션 브랜치 | 프로덕션 서버 |
| `hotfix/*` | 긴급 운영 패치 | main + develop 동시 반영 |

---

### 배포 흐름

```
sprint{n}
  ↓ PR & merge (스프린트 완료 시)
develop ──────────────→ 로컬 docker compose up --build 로 스테이징 검증
  ↓ PR & merge (QA 통과 후)
main    ──────────────→ GitHub Actions → 프로덕션 서버 자동 배포
  ↓ tag
v1.0.0, v1.1.0 ...
```

### Hotfix 배포 흐름

```
hotfix/*
  ↓ PR & merge (긴급 패치)
main    ──────────────→ GitHub Actions → 프로덕션 서버 자동 배포
  ↓ 역머지
develop ──────────────→ main 변경사항 동기화
```

---

### Docker 이미지 태깅 규칙

> TODO: 프로젝트 GHCR 이미지명을 설정하세요.

| 이미지 | Registry |
|--------|---------|
| 백엔드 | `ghcr.io/{GITHUB_ORG}/{PROJECT}-backend` |
| 프론트엔드 | `ghcr.io/{GITHUB_ORG}/{PROJECT}-frontend` |
| nginx | `ghcr.io/{GITHUB_ORG}/{PROJECT}-nginx` |

| 브랜치 | Image Tag |
|--------|-----------|
| `develop` merge | 이미지 빌드 없음 — 로컬 Docker로만 검증 |
| `main` merge | `backend:latest`, `backend:{commit SHA}`, `frontend:latest`, `frontend:{commit SHA}` |
| `hotfix` | `backend:{MAJOR.MINOR.PATCH}`, `frontend:{MAJOR.MINOR.PATCH}` |

> 버전은 Semantic Versioning (`MAJOR.MINOR.PATCH`) 기준

---

### 핵심 규칙

- `main` 직접 push 금지 — 반드시 PR + 리뷰 후 merge
- `develop` → `main` merge는 QA 통과 후 진행
- 긴급 패치는 **`main` 기반**으로 `hotfix/*` 브랜치를 생성하여 작업
- hotfix PR은 **`main`으로 직접** 생성 (develop 거치지 않음)
- main merge 후 반드시 `develop`에 역머지하여 동기화
- hotfix 범위 제한: 파일 3개 이하, 코드 50줄 이하, DB 변경 없음, 새 의존성 없음
- 스프린트 병렬 진행 시 `develop` merge 충돌 주의

---

## CI 파이프라인 (PR 체크)

PR이 `develop` 또는 `main`으로 올라오면 GitHub Actions가 자동으로 실행됩니다.

### 필수 통과 조건

1. **pytest 통과** — `backend/tests/` 전체 테스트 통과 필수
2. **Docker 이미지 빌드 성공** — `backend/` 멀티스테이지 빌드 확인
3. **TypeScript 빌드 체크** — Docker 빌드 job에서 프론트엔드 이미지 빌드 시 `next build`가 실행되어 TypeScript/빌드 오류가 자동으로 감지됨

PR merge는 위 조건이 모두 통과된 후에만 가능합니다 (Branch Protection Rule).

---

## CD 파이프라인 (배포 흐름)

### develop merge 후 (스테이징 검증)

`develop` 브랜치는 별도 서버 없이 **로컬 Docker**로 스테이징 검증합니다.

```bash
# 로컬에서 최신 코드 반영 후 검증
git pull origin develop
docker compose up --build
```

### main merge 후 (프로덕션 배포)

`main` 브랜치에 merge되면 GitHub Actions가 자동으로:

1. Docker 이미지 빌드 (backend + frontend + nginx)
2. GHCR(`ghcr.io/{GITHUB_ORG}/{PROJECT}`)에 3개 이미지 push
3. 프로덕션 서버에 SSH 접속 (appleboy/ssh-action, timeout: 60s)
4. SSH 세션 내에서 curl로 `docker-compose.prod.yml` 다운로드 (`{APP_PATH}/`)
5. `docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d` 실행

---

## 환경별 설정 관리

| 환경 | 설정 방법 | 비고 |
|------|----------|------|
| 로컬 개발 | `.env` 파일 | Git 미추적 (`.gitignore`) |
| 프로덕션 | GitHub Secrets | Actions에서 주입 |

> **프로덕션 .env 파일 관리:** 서버의 `{APP_PATH}/.env`는 서버에 수동으로 생성합니다. GitHub Secrets와 별도로 관리되며, 배포 시 자동으로 덮어쓰지 않습니다. 최초 서버 설정 시 `.env.example`을 복사하여 작성하세요.

### GitHub Secrets 목록 (프로덕션 필수)

| Secret 이름 | 설명 |
|------------|------|
| `LIGHTSAIL_SSH_KEY` | 서버 인스턴스 SSH 프라이빗 키 |
| `LIGHTSAIL_HOST` | 서버 IP 또는 도메인 |
| `LIGHTSAIL_USER` | SSH 사용자명 (예: `ubuntu`) |
| `POSTGRES_PASSWORD` | DB 비밀번호 |
| `JWT_SECRET` | JWT 서명 키 |
| `SECRET_KEY` | 앱 시크릿 키 |
| `NEXT_PUBLIC_API_URL` | 프론트엔드에서 사용하는 백엔드 API URL |

---

## 롤백 절차

> 아래는 CI/CD 관점의 롤백 요약입니다.
> 시나리오별 상세 절차(DB 백업 포함)는 [docs/dev-process.md 섹션 6.4](dev-process.md#64-롤백-시나리오) 참조.

### 빠른 롤백 (Docker 이미지)

```bash
# 서버 SSH 접속 후
cd {APP_PATH}
docker compose -f docker-compose.prod.yml down
docker pull ghcr.io/{GITHUB_ORG}/{PROJECT}-backend:v{이전_버전}
docker pull ghcr.io/{GITHUB_ORG}/{PROJECT}-frontend:v{이전_버전}
docker compose -f docker-compose.prod.yml up -d
```

### DB 마이그레이션 롤백

```bash
# Alembic 다운그레이드 (주의: 데이터 손실 가능)
alembic downgrade -1
```

> ⚠️ DB 마이그레이션 롤백은 데이터 손실이 발생할 수 있습니다.
> 롤백 전 반드시 DB 백업을 수행하세요.

---

## HTTPS/TLS

### 방법 1: Let's Encrypt + certbot (권장)

```bash
# 서버 인스턴스에서
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

Nginx 설정에서 certbot이 자동으로 SSL 블록을 추가합니다. 90일마다 자동 갱신됩니다.

### 방법 2: 로드밸런서 SSL

AWS Lightsail 또는 다른 클라우드 콘솔에서 로드밸런서 생성 후 SSL 인증서를 연결합니다.
추가 비용이 발생하지만 관리가 단순합니다.
