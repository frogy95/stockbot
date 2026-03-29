---
paths:
  - "backend/**/*.py"
  - "docker/backend/**"
  - "requirements*.txt"
---

# 백엔드 개발 규칙

## 기술 스택
# TODO: 프로젝트 기술 스택을 기입하세요
# 예: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic
# 예: 테스트 프레임워크 (pytest 등)

## 핵심 규칙
- 인증: 프로젝트 인증 라이브러리 사용
- 구조화 로깅: JSON 형식, Request ID 포함
- API 엔드포인트: `/api/v1/` 하위, HTTPException으로 에러 처리
- N+1 쿼리 방지: ORM relationship 로딩 전략 확인

## 보안
- 시크릿/API 키는 `.env` 또는 시크릿 매니저에서 관리 (코드에 하드코딩 금지)
- 인증 토큰은 안전한 방식으로 관리

## 테스트 실행
```bash
docker compose exec backend pytest -v
```

## 마이그레이션
```bash
docker compose exec backend alembic upgrade head
```
