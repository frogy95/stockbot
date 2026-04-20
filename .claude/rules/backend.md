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
- **타임존**: `date.today()` 사용 금지 — Railway 서버는 UTC로 동작하므로 KST 기준 날짜와 불일치. 반드시 `datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()` 사용. 테스트 코드에서도 프로덕션 동작을 모사할 때는 동일 패턴 적용

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

## KIS WebSocket 연결 — 확정 사실 (2026-04-16 검증)

> 이 섹션을 무시하면 WS 연결 디버깅에 수 시간을 낭비한다.

### 올바른 WebSocket URL

```python
# LIVE
ws_url = "ws://ops.koreainvestment.com:21000/tryitout"   # ✅ 필수 경로
ws_url = "ws://ops.koreainvestment.com:21000"             # ❌ 경로 없으면 즉시 EOF

# PAPER (경로 불필요 — 다른 서버 동작)
ws_url = "ws://ops.koreainvestment.com:31000"             # ✅
```

- **LIVE는 `/tryitout` 경로가 필수.** 경로 없이 연결하면 서버가 HTTP 101 응답 후 즉시 연결을 종료한다.
- PAPER(31000)는 경로 없이 동작한다 — LIVE/PAPER 서버 동작이 다르다.
- KIS 공식 GitHub 예제 100%가 `/tryitout` 사용 (`kis_auth.py`: `url = f"{my_url_ws}{api_url}"`, `api_url="/tryitout"`).

### IP 등록 정책 없음

- **KIS WebSocket에 IP 화이트리스트 등록은 불필요하다.**
- Railway Static Outbound IP를 KIS에 등록할 필요 없음.
- (KIS 개발자 포털 공식 확인 — 2026-04-16)

### diagnose_ws.py의 한계

- `diagnose_ws.py`의 HTTP 101 응답 체크는 **핸드셰이크 시작 여부만 확인**한다.
- 서버가 101 응답 후 즉시 연결을 닫아도 "101 성공"으로 보인다.
- 실제 WebSocket 라이브러리는 연결 유지가 필요하므로 진단 결과와 실제 동작이 다를 수 있다.
