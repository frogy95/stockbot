# StockBot

> 한국 주식/ETF 단타 자동 매매 시스템

자동 종목 스크리닝, 매매 신호 분석, 주문 실행을 수행하는 단타 자동 매매 시스템. 반자동(추천+승인)과 완전 자동 모드를 지원하며, 웹 대시보드와 텔레그램으로 모니터링/제어한다.

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 | Python 3.12 + FastAPI |
| 프론트엔드 | Next.js (App Router) |
| DB | PostgreSQL 16 |
| 캐시 | Redis 7 |
| ORM | SQLAlchemy 2.0 + Alembic |
| 스케줄러 | APScheduler |
| 텔레그램 | python-telegram-bot |
| 컨테이너 | Docker Compose (로컬 개발) |
| 프론트엔드 배포 | Vercel |
| 백엔드 배포 | Railway |
| 도메인/DNS | Cloudflare |

## 주요 기능

- **자동 종목 스크리닝** — 거래량, 변동성 등 조건으로 종목 탐색 + 스코어링
- **매매 신호 분석** — 전략 기반 신호 생성 (신뢰도 0~1 + 판단 근거)
- **매매 실행** — 반자동(텔레그램/웹 승인) 또는 완전 자동 모드
- **자금 관리** — 비율 기반 투자, 포지션 제한, 손절/익절
- **웹 대시보드** — 손익, 포지션, 주문, 신호, 스크리닝, 설정 (다크 모드)
- **텔레그램 봇** — 알림, 매매 승인, 일일 리포트, 조회 명령어
- **모의/실전 전환** — `TRADING_ENV` 플래그 하나로 일괄 전환

## 시스템 아키텍처

```
┌── Cloudflare (DNS/CDN) ─────────────────────┐
│                                               │
│  ┌─ Vercel ──┐    ┌─── Railway ───────────┐  │
│  │ Next.js   │───►│ FastAPI               │  │
│  │ Dashboard │    │  ├ modules/trading/    │  │
│  └───────────┘    │  ├ modules/collector/  │  │
│                   │  ├ modules/screening/  │  │
│  [Telegram Bot]◄──│  ├ modules/notifier/   │  │
│                   │  └ modules/analyzer/   │  │
│                   │                        │  │
│                   │ [PostgreSQL] [Redis]    │  │
│                   └────────────────────────┘  │
│                                               │
│  외부: 한투 API, 네이버 API, DART API         │
└───────────────────────────────────────────────┘
```

## 빠른 시작

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 등 입력

# 2. 서비스 기동
docker compose up -d

# 3. DB 마이그레이션
docker compose exec backend alembic upgrade head
```

## 개발 명령어

```bash
# 개별 서비스 기동
docker compose up backend -d
docker compose up frontend -d

# 백엔드 테스트
docker compose exec backend pytest -v
docker compose exec backend pytest tests/test_x.py  # 단일 파일

# 프론트엔드 타입 체크
cd frontend && npx tsc --noEmit

# DB 마이그레이션
docker compose exec backend alembic upgrade head
```

## 외부 API

| API | 용도 | Rate Limit |
|-----|------|-----------|
| 한국투자증권 (실전) | 시세 + 주문 | 초당 ~20건 |
| 한국투자증권 (모의) | 개발/테스트 | 초당 ~1건 |
| 네이버 검색 | 뉴스/트렌드 | 일 25,000건 |
| Open Dart | 재무/공시 | 일 10,000건 |
| Telegram Bot | 알림/승인 | 초당 30건 |

## 프로젝트 구조

```
stockbot/
├── .claude/                    # Claude Code 에이전트/훅/규칙
│   ├── agents/                 #   7개 커스텀 에이전트
│   ├── rules/                  #   경로별 개발 규칙
│   ├── commands/               #   슬래시 커맨드
│   └── hooks/                  #   자동 규칙 강제화
├── backend/                    # FastAPI 백엔드 (예정)
│   ├── modules/                #   도메인 모듈 (trading, collector, screening, notifier, analyzer)
│   ├── core/                   #   공통 (config, DB, Redis, auth, models)
│   └── api/                    #   REST 엔드포인트
├── frontend/                   # Next.js 프론트엔드 (예정)
├── docs/
│   ├── prd.md                  #   제품 요구사항 문서
│   ├── experts/                #   7명 전문가 프로필 (AI 페르소나)
│   ├── dev-process.md          #   개발 프로세스 가이드
│   ├── phase/                  #   Phase/Sprint 문서
│   └── templates/              #   문서 템플릿
├── CLAUDE.md                   # Claude Code 프로젝트 지침
├── ROADMAP.md                  # 프로젝트 로드맵 (Phase 0~6)
├── deploy.md                   # 미완료 배포 항목
└── docker-compose.yml          # 4컨테이너 구성 (예정)
```

## 개발 프로세스

이 프로젝트는 Claude Code 에이전트 기반으로 Phase-Sprint-Task 계층 워크플로우를 사용한다.

```
PRD → ROADMAP.md → Phase 문서 → Sprint 문서 → 구현 → PR → 리뷰 → 배포
```

### 에이전트

| 에이전트 | 역할 |
|---------|------|
| `prd-to-roadmap` | PRD → Phase 기반 ROADMAP.md 생성 |
| `phase-planner` | 전문가 검토 기반 Phase 상세 계획 |
| `sprint-planner` | 실행 가능한 Sprint 명세서 생성 |
| `sprint-close` | Sprint 마무리 (ROADMAP 업데이트, develop PR) |
| `sprint-review` | 코드 리뷰 + 자동 검증 |
| `deploy-prod` | develop → main 프로덕션 배포 |
| `hotfix-close` | 긴급 수정 → main PR |

### 전문가 패널 (AI 페르소나)

Phase 계획 시 도메인 전문가가 설계를 리뷰한다:

| 전문가 | 역할 |
|--------|------|
| 김단타 | 매매 전략, 타이밍, 운영 시간 |
| 박퀀트 | 알고리즘, 지표, 스코어링 |
| 이펀드 | 포트폴리오, 자산 배분 |
| 최리스크 | 손절/익절, 자금 관리 |
| 정프로 | 기능 우선순위, 일정 |
| 한유엑 | 대시보드 UX, 정보 계층 |
| 윤에이피 | API 연동, 에러 핸들링 |

### Hook 시스템

| Hook | 역할 |
|------|------|
| `bash-guard` (PreToolUse) | 위험 명령 차단 (force push, hard reset 등) |
| `doc-checker` (Stop) | 에이전트 완료 전 필수 파일 업데이트 검증 |

## Git 브랜치 전략

- `main`: 프로덕션 (직접 push 금지, PR만)
- `develop`: 통합 브랜치 (직접 push 금지, PR만)
- `phase{P}-sprint{N}`: 스프린트 작업
- `hotfix/*`: 긴급 수정

## CI/CD

- **CI** (`.github/workflows/ci.yml`): PR → pytest, TypeScript 체크
- **CD**: main merge → Vercel 자동 배포 (프론트엔드) + Railway 자동 배포 (백엔드)

## 참고 문서

- `docs/prd.md` — 제품 요구사항 문서
- `.claude/rules/dev-process.md` — 개발 프로세스 가이드
- `.claude/rules/ci-policy.md` — CI/CD 정책
- `wiki/setup-guide.md` — 환경 설정 가이드
- `docs/prompt-guide.md` — 사용자 프롬프트 가이드
- `wiki/index.md` — 시스템 지식 베이스 진입점
