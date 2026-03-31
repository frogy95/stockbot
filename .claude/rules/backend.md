---
paths:
  - "backend/**/*.py"
  - "docker/backend/**"
  - "requirements*.txt"
  - "alembic/**"
  - "alembic.ini"
---

# 백엔드 개발 규칙

## 기술 스택

- Python 3.12, FastAPI, uvicorn
- SQLAlchemy 2.0 (async) + Alembic 마이그레이션
- asyncpg (PostgreSQL 16 async 드라이버)
- Redis 7 (redis.asyncio)
- pytest + pytest-asyncio (테스트)
- pydantic-settings (환경변수 관리)
- APScheduler (스케줄러)

## 프로젝트 구조

```
backend/
├── api/                # REST 엔드포인트
│   ├── routes/         # 라우터 모듈 (health.py 등)
│   └── deps.py         # 의존성 주입 (DB 세션, Redis)
├── core/               # 핵심 인프라
│   ├── config.py       # pydantic-settings Settings 클래스
│   ├── database.py     # SQLAlchemy async engine + session
│   ├── redis.py        # Redis 연결 풀 + 캐시 유틸
│   └── models/         # SQLAlchemy 모델 (Stock, MarketData, Settings)
├── modules/            # 도메인 모듈 (Phase 2+에서 추가)
│   ├── trading/        # 매매 엔진
│   ├── collector/      # 데이터 수집
│   ├── screening/      # 종목 스크리닝
│   ├── notifier/       # 알림 (텔레그램)
│   └── analyzer/       # 성과 분석
├── scripts/            # 유틸리티 스크립트 (seed_settings.py)
├── tests/              # pytest 테스트
├── main.py             # FastAPI 앱 엔트리포인트
├── Dockerfile          # 프로덕션 이미지
└── requirements.txt    # 의존성
```

## 핵심 규칙

- **비동기 우선**: DB/Redis/HTTP 호출은 모두 async/await 사용
- **API 경로**: `/api/v1/` 하위에 배치, HTTPException으로 에러 처리
- **의존성 주입**: `api/deps.py`의 `get_db()`, `get_redis()`를 Depends로 사용
- **N+1 방지**: ORM relationship에 `selectinload`/`joinedload` 명시
- **구조화 로깅**: JSON 형식, Request ID 포함
- **환경변수**: `core/config.py`의 Settings 클래스로 관리, 하드코딩 금지
- **환경변수 추가 시**: `core/config.py`에 추가하는 동시에 `.env.example`에도 반드시 추가 (주석으로 용도 명시)
- **프로덕션 필수 환경변수**: Railway 등 외부 인프라에 수동 설정이 필요한 경우, deploy.md 수동 검증 항목에 `Railway 환경변수 추가 확인: VAR_NAME` 형식으로 기록

## 모델 규칙

- 테이블명: snake_case 복수형 (stocks, market_data, settings)
- PK: `id` (Integer, autoincrement)
- 타임스탬프: `created_at`, `updated_at` (UTC, server_default)
- Alembic 마이그레이션 필수 — 모델 변경 시 `alembic revision --autogenerate`

## 보안

- 시크릿/API 키는 `.env` 또는 Railway 환경변수로 관리
- 한투 API 토큰은 Redis에 캐싱, 만료 시 자동 갱신
- SQL 인젝션 방지: ORM 파라미터 바인딩 사용, raw SQL 최소화

## 테스트

```bash
docker compose exec backend pytest -v                # 전체 테스트
docker compose exec backend pytest tests/test_x.py   # 단일 파일
docker compose exec backend pytest -k "test_name"    # 이름 매칭
```

## 마이그레이션

```bash
docker compose exec backend alembic upgrade head              # 최신 적용
docker compose exec backend alembic revision --autogenerate -m "설명"  # 생성
docker compose exec backend alembic downgrade -1               # 롤백
```

## 배포

- **로컬**: Docker Compose (`docker compose up backend -d`)
- **프로덕션**: Railway (main merge 시 자동 배포, Dockerfile 기반)
