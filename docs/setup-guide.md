# 환경 설정 가이드

> 프로젝트 최초 시작 시 1회 수행하는 환경 설정 가이드입니다.

---

## 1. 사전 요구사항

> TODO: 프로젝트에 필요한 도구 목록을 작성하세요.

- [ ] Git
- [ ] Docker Desktop
- [ ] Node.js (버전: TODO)
- [ ] Python (버전: TODO)
- [ ] 기타 도구...

---

## 2. 저장소 클론

```bash
git clone https://github.com/frogy95/stockbot.git
cd stockbot
```

---

## 3. 환경변수 설정

```bash
# .env.example을 복사하여 .env 파일 생성
cp .env.example .env
```

`.env` 파일을 열고 필요한 값을 입력합니다:

> TODO: 각 환경변수에 대한 설명과 획득 방법을 작성하세요.

---

## 4. 로컬 개발 환경 실행

```bash
# Docker Compose로 전체 스택 실행
docker compose up --build

# 백엔드 DB 마이그레이션 (최초 1회)
docker compose exec backend alembic upgrade head

# 초기 데이터 시드 (필요한 경우)
docker compose exec backend python scripts/seed.py
```

서비스 접속:
- 프론트엔드: http://localhost:3000
- 백엔드 API: http://localhost:8000
- API 문서: http://localhost:8000/docs

---

## 5. 외부 서비스 설정

> TODO: 프로젝트에서 사용하는 외부 서비스 설정 방법을 작성하세요.

### 5.1 {외부 서비스 1}

> TODO

### 5.2 {외부 서비스 2}

> TODO

---

## 6. 개발 도구 설정

### VS Code 권장 익스텐션

> TODO: 프로젝트에 맞는 권장 익스텐션 목록을 작성하세요.

---

## 7. Claude Code 설정

이 프로젝트는 Claude Code와 함께 사용하도록 설계되었습니다.

### 전제 조건

- Claude Code 설치: https://claude.ai/claude-code
- MCP 서버 설정 (선택사항): Playwright, Notion 등

### 에이전트 활용

- `sprint-planner`: 스프린트 계획 수립
- `sprint-close`: 스프린트 마무리 (PR, 문서 정리)
- `sprint-review`: 코드 리뷰 + 자동 검증
- `phase-planner`: 대규모 기능 Phase 계획
- `hotfix-close`: 핫픽스 마무리
- `deploy-prod`: 프로덕션 배포
- `prd-to-roadmap`: PRD → ROADMAP.md 변환

자세한 내용은 `README.md` 참조.
