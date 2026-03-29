# Sprint 1: Docker Compose + DB/Redis + 백엔드 스켈레톤 (Phase 1)

**Goal:** Docker Compose 4컨테이너 환경을 구축하고, FastAPI 백엔드 스켈레톤 + DB 3테이블 + Redis 연결 + Next.js 플레이스홀더를 완성한다.

**Architecture:** Docker Compose로 FastAPI(:8000), Next.js(:3000), PostgreSQL(:5432), Redis(:6379) 4컨테이너를 구성한다. 백엔드는 pydantic-settings 기반 환경변수 관리, SQLAlchemy 2.0 async 엔진, aioredis 연결 풀을 사용한다. Alembic으로 DB 마이그레이션을 관리하며, settings/stocks/market_data 3테이블을 생성하고 리스크/매매 파라미터 21개를 시드 데이터로 적재한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, asyncpg, redis (aioredis), pydantic-settings, uvicorn, Next.js (App Router), PostgreSQL 16, Redis 7, Docker Compose

**Sprint 기간:** 2026-03-29 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 0.5 Sprint 1 (전체 통과, PR 없음 — 탐색 Phase)
**브랜치명:** `phase1-sprint1`

---

## 제외 범위

- 한투 API 연동 (Sprint 2)
- 토큰 관리, Rate Limit 스로틀러 (Sprint 2)
- 모의/실전 전환 로직 (Sprint 2)
- settings CRUD API (Sprint 2)
- 프론트엔드 기능 구현 (Phase 4)
- 모듈별 비즈니스 로직 (modules/trading, modules/collector 등은 빈 __init__.py만)
- APScheduler 설정 (Sprint 2에서 토큰 갱신과 함께)
- Playwright E2E 테스트 (Phase 4)

---

## 실행 플랜

의존성 그래프: Task 1(Docker) -> Task 2(Config) -> Task 3(DB+모델) -> Task 4(Redis) -> Task 5(API+헬스체크) -> Task 6(프론트엔드) -> Task 7(시드 데이터+통합 테스트)

모든 Task가 순차 의존성을 가지므로 단일 Phase로 실행한다.

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | Docker Compose + Dockerfile 구성 | 인프라 | -- |
| Task 2 | pydantic-settings 환경변수 관리 | 백엔드 | -- |
| Task 3 | SQLAlchemy 모델 + Alembic 마이그레이션 | 백엔드 | -- |
| Task 4 | Redis 연결 풀 + 기본 캐시 유틸 | 백엔드 | -- |
| Task 5 | FastAPI 앱 팩토리 + 헬스체크 API | 백엔드 | -- |
| Task 6 | Next.js 플레이스홀더 앱 | 프론트엔드 | -- |
| Task 7 | 시드 데이터 + 통합 테스트 | 백엔드 | -- |

---

### Task 1: Docker Compose + Dockerfile 구성

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `backend/requirements.txt`
- Create: `frontend/Dockerfile`
- Create: `frontend/package.json` (Next.js 초기화용 — 실제로는 `npx create-next-app`으로 생성)

**Step 1: backend/requirements.txt 생성**
- 의존성 목록:
  - fastapi, uvicorn[standard]
  - sqlalchemy[asyncio], asyncpg, alembic
  - redis[hiredis]
  - pydantic-settings
  - httpx, websockets
  - apscheduler
  - pytest, pytest-asyncio, httpx (테스트용)
- 버전 핀 방식: 메이저.마이너까지 고정 (예: `fastapi>=0.115,<1.0`)
- 검증: 파일 존재 확인

**Step 2: backend/Dockerfile 생성**
- 베이스: `python:3.12-slim`
- 작업 디렉토리: `/app`
- requirements.txt COPY 후 `pip install --no-cache-dir -r requirements.txt`
- 소스 COPY
- CMD: `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- 검증: 문법 확인

**Step 3: frontend 초기화**
- `frontend/` 디렉토리에 Next.js App Router 프로젝트 생성
- `npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*"` 또는 수동 구성
- `frontend/Dockerfile` 생성:
  - 베이스: `node:20-slim`
  - 작업 디렉토리: `/app`
  - package.json + package-lock.json COPY 후 `npm install`
  - 소스 COPY
  - CMD: `npm run dev`
- 검증: 파일 존재 확인

**Step 4: docker-compose.yml 생성**
- 서비스 4개:
  - `backend`: build context `./backend`, 포트 8000:8000, depends_on [postgres, redis], env_file .env, volumes `./backend:/app` (개발용 핫리로드)
  - `frontend`: build context `./frontend`, 포트 3000:3000, env_file .env, volumes `./frontend:/app`
  - `postgres`: image `postgres:16`, 포트 5432:5432, env (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD from .env), volumes `pgdata:/var/lib/postgresql/data`
  - `redis`: image `redis:7-alpine`, 포트 6379:6379, volumes `redisdata:/data`
- volumes: pgdata, redisdata
- 네트워크: 기본 bridge 사용 (별도 정의 불필요)
- 검증: `docker compose config` (문법 검증)
- 예상: 정상 출력 (에러 없음)

**Step 5: 컨테이너 기동 테스트**
- 검증: `docker compose up -d --build`
- 예상: 4개 컨테이너 모두 running 상태
- 추가 검증: `docker compose ps`
- 예상: backend, frontend, postgres, redis 모두 Up

**Step 6: 커밋**
```
git add docker-compose.yml backend/Dockerfile backend/requirements.txt frontend/Dockerfile frontend/
git commit -m "feat(phase1-sprint1): Docker Compose 4컨테이너 + Dockerfile 구성"
```

**완료 기준:**
- ⬜ docker compose config 문법 통과
- ⬜ 4개 컨테이너 정상 기동 (docker compose ps)

---

### Task 2: pydantic-settings 환경변수 관리

**Files:**
- Create: `backend/core/__init__.py`
- Create: `backend/core/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_config.py`

**Step 1: 테스트 작성**
- `backend/tests/test_config.py` 생성
- 테스트 항목:
  - Settings 인스턴스 생성 확인 (환경변수 또는 기본값)
  - TRADING_ENV 기본값이 "paper"인지 확인
  - DATABASE_URL 프로퍼티가 asyncpg 형식인지 확인 (`postgresql+asyncpg://...`)
  - REDIS_URL 프로퍼티가 올바른 형식인지 확인 (`redis://...`)
- 검증: `docker compose exec backend pytest tests/test_config.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: config.py 구현**
- `backend/core/config.py` 생성
- `pydantic_settings.BaseSettings` 상속한 `Settings` 클래스:
  - 필드: DEBUG, SECRET_KEY, JWT_SECRET, TRADING_ENV (기본값 "paper")
  - DB 필드: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
  - Redis 필드: REDIS_HOST, REDIS_PORT
  - 프로퍼티: `database_url` -> `postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}`
  - 프로퍼티: `redis_url` -> `redis://{host}:{port}`
  - KIS 필드: KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_ACCOUNT_NO, KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO (모두 기본값 빈 문자열)
  - 기타: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, DART_API_KEY, DATA_GO_KR_API_KEY
  - 기타: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  - model_config: `env_file = ".env"`, `env_file_encoding = "utf-8"`
- 모듈 수준 싱글턴: `settings = Settings()`
- `backend/core/__init__.py` 빈 파일
- 검증: `docker compose exec backend pytest tests/test_config.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/ backend/tests/
git commit -m "feat(phase1-sprint1): pydantic-settings 환경변수 관리 (Settings 클래스)"
```

**완료 기준:**
- ⬜ pytest test_config.py 통과
- ⬜ Settings 클래스에서 .env 파일 로드 확인

---

### Task 3: SQLAlchemy 모델 + Alembic 마이그레이션

**Files:**
- Create: `backend/core/database.py`
- Create: `backend/core/models/__init__.py`
- Create: `backend/core/models/settings.py`
- Create: `backend/core/models/stock.py`
- Create: `backend/core/models/market_data.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/` (자동 생성)
- Create: `backend/tests/test_models.py`

**Step 1: 테스트 작성**
- `backend/tests/test_models.py` 생성
- 테스트 항목:
  - SystemSetting 모델: 필수 필드(key, value, value_type, category) 존재 확인
  - Stock 모델: 필수 필드(stock_code, stock_name, market, market_type, stock_type) 존재 확인
  - MarketData 모델: 필수 필드(stock_code, data_date, source) 존재 확인
  - MarketData 유니크 제약: (stock_code, data_date, source) 조합
  - Base.metadata.tables에 3개 테이블 등록 확인
- 검증: `docker compose exec backend pytest tests/test_models.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: database.py 구현**
- `backend/core/database.py` 생성
- SQLAlchemy 2.0 async 엔진:
  - `create_async_engine(settings.database_url, echo=settings.DEBUG)`
  - `async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`
  - `async def get_session()` — AsyncGenerator로 세션 yield (FastAPI Depends용)
- 검증: import 성공 확인

**Step 3: 모델 구현**
- `backend/core/models/__init__.py`: DeclarativeBase 정의 (`class Base(DeclarativeBase): pass`), 모델 import
- `backend/core/models/settings.py`: SystemSetting 모델
  - 테이블명: `settings`
  - 컬럼: id (Integer, PK), key (String(100), unique, not null), value (Text, not null), value_type (String(20), not null), category (String(50), not null), description (Text, nullable), updated_at (DateTime(timezone=True)), created_at (DateTime(timezone=True), server_default=func.now())
- `backend/core/models/stock.py`: Stock 모델
  - 테이블명: `stocks`
  - 컬럼: id (Integer, PK), stock_code (String(10), unique, not null), stock_name (String(100), not null), market (String(10), not null, default="kr"), market_type (String(10), not null), stock_type (String(20), not null), is_active (Boolean, default=True), listed_shares (BigInteger, nullable), extra_data (JSON, default={}), updated_at, created_at
- `backend/core/models/market_data.py`: MarketData 모델
  - 테이블명: `market_data`
  - 컬럼: id (BigInteger, PK), stock_code (String(10), ForeignKey("stocks.stock_code"), not null), data_date (Date, not null), open_price (Numeric(12,0)), high_price (Numeric(12,0)), low_price (Numeric(12,0)), close_price (Numeric(12,0)), volume (BigInteger), market_cap (BigInteger), listed_shares (BigInteger), change_rate (Numeric(8,4)), extra_data (JSON, default={}), source (String(20), not null), collected_at (DateTime(timezone=True), server_default=func.now())
  - UniqueConstraint: (stock_code, data_date, source)
  - Index: (data_date), (stock_code, data_date)
- 검증: `docker compose exec backend pytest tests/test_models.py -v`
- 예상: PASS

**Step 4: Alembic 초기 설정**
- `backend/alembic.ini` 생성: sqlalchemy.url은 env.py에서 오버라이드
- `backend/alembic/env.py` 생성:
  - `target_metadata = Base.metadata`
  - `run_migrations_online()`: settings.database_url 사용 (async 지원은 sync URL로 변환: `postgresql://` 프리픽스)
- `backend/alembic/script.py.mako` 생성 (기본 템플릿)
- 검증: `docker compose exec backend alembic --help`
- 예상: 도움말 출력

**Step 5: 초기 마이그레이션 생성 및 적용**
- 마이그레이션 생성: `docker compose exec backend alembic revision --autogenerate -m "초기 테이블 생성: settings, stocks, market_data"`
- 마이그레이션 적용: `docker compose exec backend alembic upgrade head`
- 검증: `docker compose exec backend alembic current`
- 예상: head 리비전 출력
- 추가 검증: `docker compose exec postgres psql -U stockbot -d stockbot -c "\dt"`
- 예상: settings, stocks, market_data, alembic_version 4개 테이블

**Step 6: 커밋**
```
git add backend/core/database.py backend/core/models/ backend/alembic.ini backend/alembic/ backend/tests/test_models.py
git commit -m "feat(phase1-sprint1): SQLAlchemy 모델 3테이블 + Alembic 마이그레이션"
```

**완료 기준:**
- ⬜ pytest test_models.py 통과
- ⬜ alembic upgrade head 성공
- ⬜ psql \dt로 3테이블 + alembic_version 확인

---

### Task 4: Redis 연결 풀 + 기본 캐시 유틸

**Files:**
- Create: `backend/core/redis.py`
- Create: `backend/tests/test_redis.py`

**Step 1: 테스트 작성**
- `backend/tests/test_redis.py` 생성
- 테스트 항목 (실제 Redis 연결 — 통합 테스트):
  - Redis 연결 성공 (ping)
  - get/set/delete 기본 동작
  - TTL이 있는 set 동작 (expires)
  - get_or_set 패턴 (캐시 히트/미스)
- 검증: `docker compose exec backend pytest tests/test_redis.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: redis.py 구현**
- `backend/core/redis.py` 생성
- `redis.asyncio`(aioredis 후속) 사용:
  - `RedisClient` 클래스:
    - `__init__(self, url: str)`: 연결 URL 저장
    - `async def connect(self)`: `redis.asyncio.from_url(url, decode_responses=True)` 로 연결 풀 생성
    - `async def disconnect(self)`: 연결 풀 종료
    - `async def ping(self) -> bool`: 연결 확인
    - `async def get(self, key: str) -> str | None`
    - `async def set(self, key: str, value: str, ttl: int | None = None)`
    - `async def delete(self, key: str) -> bool`
    - `async def get_or_set(self, key: str, factory: Callable, ttl: int | None = None) -> str`: 캐시 히트 시 반환, 미스 시 factory() 호출 후 저장
  - 모듈 수준: `redis_client = RedisClient(settings.redis_url)`
- 검증: `docker compose exec backend pytest tests/test_redis.py -v`
- 예상: PASS

**Step 3: 커밋**
```
git add backend/core/redis.py backend/tests/test_redis.py
git commit -m "feat(phase1-sprint1): Redis 연결 풀 + 기본 캐시 유틸 (get/set/delete)"
```

**완료 기준:**
- ⬜ pytest test_redis.py 통과
- ⬜ Redis ping/get/set/delete 동작 확인

---

### Task 5: FastAPI 앱 팩토리 + 헬스체크 API

**Files:**
- Create: `backend/main.py`
- Create: `backend/api/__init__.py`
- Create: `backend/api/deps.py`
- Create: `backend/api/routes/__init__.py`
- Create: `backend/api/routes/health.py`
- Create: `backend/modules/__init__.py`
- Create: `backend/modules/trading/__init__.py`
- Create: `backend/modules/collector/__init__.py`
- Create: `backend/modules/screening/__init__.py`
- Create: `backend/modules/notifier/__init__.py`
- Create: `backend/modules/analyzer/__init__.py`
- Create: `backend/tests/test_health.py`

**Step 1: 테스트 작성**
- `backend/tests/test_health.py` 생성
- httpx.AsyncClient + FastAPI TestClient 사용
- 테스트 항목:
  - GET /health 응답 200
  - 응답 JSON에 status, database, redis 키 존재
  - database: "connected", redis: "connected" (정상 시)
- 검증: `docker compose exec backend pytest tests/test_health.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 모듈 스켈레톤 생성**
- `backend/modules/__init__.py` 빈 파일
- `backend/modules/trading/__init__.py` 빈 파일
- `backend/modules/collector/__init__.py` 빈 파일
- `backend/modules/screening/__init__.py` 빈 파일
- `backend/modules/notifier/__init__.py` 빈 파일
- `backend/modules/analyzer/__init__.py` 빈 파일
- 검증: import 성공 확인

**Step 3: 의존성 주입 (deps.py)**
- `backend/api/deps.py` 생성
- `async def get_db() -> AsyncGenerator[AsyncSession, None]`: database.get_session() 위임
- `async def get_redis() -> RedisClient`: redis_client 반환
- 검증: import 성공 확인

**Step 4: 헬스체크 라우터**
- `backend/api/routes/health.py` 생성
- `router = APIRouter()`
- `GET /health`:
  - DB 연결 확인: `SELECT 1` 실행
  - Redis 연결 확인: `ping()` 실행
  - 응답: `{"status": "healthy", "database": "connected"|"disconnected", "redis": "connected"|"disconnected"}`
  - DB/Redis 중 하나라도 실패 시 status: "unhealthy", HTTP 503
- 검증: import 성공 확인

**Step 5: FastAPI 앱 팩토리 (main.py)**
- `backend/main.py` 생성
- `create_app() -> FastAPI`:
  - lifespan 컨텍스트 매니저:
    - startup: redis_client.connect()
    - shutdown: redis_client.disconnect()
  - FastAPI 인스턴스 생성 (title="StockBot API", version="0.1.0")
  - 라우터 등록: health_router (prefix="/api/v1")
  - CORS 미들웨어 추가 (origins: ["http://localhost:3000"])
- `app = create_app()`
- 검증: `docker compose exec backend pytest tests/test_health.py -v`
- 예상: PASS

**Step 6: curl 검증**
- 검증: `curl -s http://localhost:8000/api/v1/health | python3 -m json.tool`
- 예상: `{"status": "healthy", "database": "connected", "redis": "connected"}`
- 검증: `curl -s http://localhost:8000/docs`
- 예상: Swagger UI HTML

**Step 7: 커밋**
```
git add backend/main.py backend/api/ backend/modules/ backend/tests/test_health.py
git commit -m "feat(phase1-sprint1): FastAPI 앱 팩토리 + 헬스체크 API + 모듈 스켈레톤"
```

**완료 기준:**
- ⬜ pytest test_health.py 통과
- ⬜ curl /api/v1/health 응답 정상
- ⬜ Swagger UI (/docs) 접근 가능

---

### Task 6: Next.js 플레이스홀더 앱

**Files:**
- Modify: `frontend/app/page.tsx` (create-next-app 기본 페이지 수정)
- Modify: `frontend/app/layout.tsx` (다크 모드 기본 설정)

**Step 1: page.tsx 수정**
- 기존 create-next-app 기본 콘텐츠를 제거
- "StockBot Dashboard — Coming Soon" 플레이스홀더로 교체
- 중앙 정렬, 간단한 타이포그래피
- 검증: 파일 내용 확인

**Step 2: layout.tsx 수정**
- html 태그에 `className="dark"` 추가
- body 배경색: 다크 모드 기본값 (Tailwind dark 클래스 활용)
- metadata: title "StockBot", description "한국 주식/ETF 단타 자동 매매 시스템"
- 검증: 파일 내용 확인

**Step 3: 브라우저 확인**
- 검증: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000`
- 예상: 200

**Step 4: 커밋**
```
git add frontend/app/page.tsx frontend/app/layout.tsx
git commit -m "feat(phase1-sprint1): Next.js 플레이스홀더 앱 (다크 모드 Coming Soon)"
```

**완료 기준:**
- ⬜ http://localhost:3000 접속 시 200 응답
- ⬜ "StockBot Dashboard" 텍스트 표시

---

### Task 7: 시드 데이터 + 통합 테스트

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/seed_settings.py`
- Create: `backend/tests/test_integration.py`

**Step 1: 시드 스크립트 작성**
- `backend/scripts/seed_settings.py` 생성
- Phase 1 문서의 초기 시드 데이터 21개 항목을 settings 테이블에 INSERT (upsert — key 기준 중복 시 UPDATE)
- 시드 데이터 목록 (phase1.md에서 확정):
  - trading_env: paper (system)
  - max_loss_per_trade_pct: -2.0 (risk)
  - max_profit_per_trade_pct: 3.0 (risk)
  - trailing_stop_pct: -1.0 (risk)
  - daily_max_loss_pct: -3.0 (risk)
  - monthly_max_loss_pct: -10.0 (risk)
  - position_size_pct: 10.0 (risk)
  - max_position_count: 5 (risk)
  - leverage_etf_loss_pct: -1.5 (risk)
  - leverage_etf_size_pct: 7.0 (risk)
  - force_close_start: 15:00 (trading)
  - force_close_end: 15:20 (trading)
  - trading_start: 09:30 (trading)
  - trading_end: 14:30 (trading)
  - no_entry_start: 09:00 (trading)
  - no_entry_end: 09:30 (trading)
  - approval_timeout_trading: 30 (trading)
  - approval_timeout_closing: 15 (trading)
  - approval_timeout_default: 60 (trading)
  - emergency_stop_enabled: true (risk)
  - data_collection_start: 08:00 (schedule)
- 실행 방법: `python -m scripts.seed_settings` (async main 함수)
- 검증: `docker compose exec backend python -m scripts.seed_settings`
- 예상: "21개 설정 시드 완료" 출력

**Step 2: 통합 테스트 작성**
- `backend/tests/test_integration.py` 생성
- 테스트 항목:
  - 시드 데이터 적재 후 settings 테이블에 21개 행 존재 확인
  - key="trading_env"인 행의 value가 "paper"인지 확인
  - key="max_loss_per_trade_pct"인 행의 value_type이 "float"인지 확인
  - Stock 모델 CRUD: 생성 -> 조회 -> 삭제
  - MarketData 모델: Stock FK 정상 동작 확인
  - MarketData UniqueConstraint: 동일 (stock_code, data_date, source) 중복 시 에러
  - 헬스체크 API 응답 정상 (httpx AsyncClient)
  - Redis ping 정상
- 검증: `docker compose exec backend pytest tests/test_integration.py -v`
- 예상: PASS (전체)

**Step 3: 커밋**
```
git add backend/scripts/ backend/tests/test_integration.py
git commit -m "feat(phase1-sprint1): 시드 데이터 21개 + 통합 테스트"
```

**완료 기준:**
- ⬜ 시드 스크립트 실행 후 21개 설정 적재 확인
- ⬜ pytest test_integration.py 통과
- ⬜ Stock/MarketData CRUD 동작 확인

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| Docker 4컨테이너 | `docker compose ps` | backend, frontend, postgres, redis 모두 Up |
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 통과 (test_config, test_models, test_redis, test_health, test_integration) |
| 헬스체크 API | `curl -s http://localhost:8000/api/v1/health \| python3 -m json.tool` | `{"status": "healthy", "database": "connected", "redis": "connected"}` |
| Swagger UI | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs` | 200 |
| 프론트엔드 | `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000` | 200 |
| DB 테이블 | `docker compose exec postgres psql -U stockbot -d stockbot -c "\dt"` | settings, stocks, market_data, alembic_version |
| 시드 데이터 | `docker compose exec postgres psql -U stockbot -d stockbot -c "SELECT count(*) FROM settings"` | 21 |
| Redis 연결 | `docker compose exec redis redis-cli ping` | PONG |
| 프론트 타입체크 | `docker compose exec frontend npx tsc --noEmit` | 에러 없음 |
