# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

한국 주식/ETF 단타 자동 매매 시스템. 자동 종목 스크리닝, 매매 신호 분석, 주문 실행(반자동/완전자동), 웹 대시보드, 텔레그램 알림을 제공한다.

- **원격 저장소**: https://github.com/frogy95/stockbot.git
- **기술 스택**: Python 3.12(FastAPI) + Next.js(App Router) + PostgreSQL 16 + Redis 7
- **인프라**: Vercel (프론트엔드) + Railway (백엔드 + PostgreSQL + Redis) + Cloudflare (도메인/DNS)
- **PRD**: `docs/prd.md` | **로드맵**: `ROADMAP.md`

## 언어 및 커뮤니케이션 규칙

- 기본 응답 언어: 한국어
- 코드 주석/커밋 메시지/문서: 한국어
- 변수명/함수명: 영어

## 주요 명령어

```bash
# 로컬 개발 환경 (Docker Compose)
cp .env.example .env            # 환경변수 설정
docker compose up -d            # 전체 서비스 기동 (FastAPI, Next.js, PostgreSQL, Redis)

# 개발 서버
docker compose up backend -d    # 백엔드만 기동
docker compose up frontend -d   # 프론트엔드만 기동

# 백엔드 테스트/마이그레이션
docker compose exec backend pytest -v              # 전체 테스트
docker compose exec backend pytest tests/test_x.py # 단일 파일 테스트
docker compose exec backend alembic upgrade head    # DB 마이그레이션

# 프론트엔드 타입 체크
cd frontend && npx tsc --noEmit

# 커스텀 커맨드
/sprint-dev {P}-{N}             # Phase P의 Sprint N 구현 실행
/restart [service]              # Docker 서비스 재시작 (backend|frontend|db|all)
/dashboard                      # 프로젝트 대시보드 열기
```

## 시스템 아키텍처

```
┌── Cloudflare (DNS/CDN) ─────────────────────┐
│                                               │
│  stockbot.{domain}     api.stockbot.{domain}  │
│       │                        │              │
│       ▼                        ▼              │
│  ┌─ Vercel ──┐    ┌─── Railway ───────────┐  │
│  │ Next.js   │───►│ FastAPI :8000         │  │
│  │ Dashboard │    │  ├ modules/trading/    │  │
│  └───────────┘    │  ├ modules/collector/  │  │
│                   │  ├ modules/screening/  │  │
│  [Telegram Bot]◄──│  ├ modules/notifier/   │  │
│                   │  ├ modules/analyzer/   │  │
│                   │  ├ core/               │  │
│                   │  └ api/                │  │
│                   │                        │  │
│                   │ [PostgreSQL] [Redis]    │  │
│                   └────────────────────────┘  │
└───────────────────────────────────────────────┘
 외부: 한투 API, 공공데이터포털 API, DART API, 네이버 API, Telegram Bot API
```

### 데이터 수집 흐름

```
장전(08:00) 공공데이터포털 → 전 종목 일괄 수집 → DB → 1차 스크리닝 → 후보 종목
장중(09:00) 한투 REST/WS → 후보 종목 실시간 → 2차 스크리닝 → 매매 신호
장후(15:30) 한투 REST → 체결/잔고 정산 → 일일 리포트 → 텔레그램
```

> 상세 데이터 흐름: `docs/data-flow.md`

### 매매 실행 흐름

```
collector(수집) → screening(스크리닝) → trading.strategy(신호 분석)
  → [반자동] notifier(승인 요청) → 사용자 응답 → trading.order(주문)
  → [완전자동] trading.order(즉시 주문)
  → trading.position(포지션 업데이트) → analyzer(결과 기록) → notifier(결과 알림)
```

### 모의/실전 전환

`TRADING_ENV` 플래그(paper/live)로 일괄 전환. 도메인, APP_KEY/SECRET, 계좌번호, tr_id 접두사가 환경별 독립. 모의거래는 Rate Limit 초당 1건 스로틀링 내장.

## Bash 명령 실행 규칙

bash-guard hook(`.claude/hooks/pretooluse-bash-guard.sh`)이 자동 차단:
- `cd /path &&` 체이닝, main/develop 직접 push, force push, `git reset --hard`, 비정상 브랜치명

## Git 브랜치 전략

- `main`: 프로덕션 배포 (직접 push 금지, PR만 허용)
- `develop`: 통합 브랜치 (직접 push 금지, PR만 허용)
- `phase{P}-sprint{N}`: 스프린트 작업 브랜치 (`git checkout -b`로 생성, worktree 사용 금지)
- `hotfix/*`: 긴급 수정 브랜치

## 개발 프로세스

프로세스 상세는 `docs/dev-process.md` 참조. 스프린트/핫픽스 워크플로우 규칙은 `.claude/rules/sprint-workflow.md` 참조.

### 프로젝트 라이프사이클
```
PRD → prd-to-roadmap → ROADMAP.md (Phase 구조)
  → phase-planner → docs/phase/phase{N}/phase{N}.md (전문가 검토 + 확정 파라미터)
    → sprint-planner → docs/phase/phase{P}/sprint{N}/sprint{N}.md (실행 명세서)
      → 구현 → sprint-close → sprint-review → deploy-prod
```

### 핵심 원칙

- **수정사항 → Hotfix vs Sprint 의사결정 먼저**: `docs/dev-process.md` 섹션 2 기준
- **sprint{N}.md가 Single Source of Truth** — Task를 순서대로 실행
- **worktree 사용 금지**: `git checkout -b phase{P}-sprint{N}` 으로 브랜치 생성
- **karpathy-guidelines** 준수
- **검증 원칙**: `docs/dev-process.md` 섹션 5 참조
- 배포 후 수동 작업: `deploy.md` 참조 (완료 기록은 `docs/deploy-history/` 아카이브)

## 에이전트 사용 규칙

다음 요청에는 반드시 **Agent 도구**(`subagent_type` 파라미터)로 해당 에이전트를 호출한다. **Skill 도구로 호출하지 않는다** — 이들은 `.claude/agents/` 디렉토리의 커스텀 에이전트이며 스킬이 아니다. 직접 탐색/계획하지 않는다.

| 요청 | Agent subagent_type | 모델 |
|------|---------------------|------|
| PRD → 로드맵 | `prd-to-roadmap` | Opus |
| Phase 계획 | `phase-planner` | Opus |
| 스프린트 계획 | `sprint-planner` | Opus |
| 스프린트 마무리 (PR 생성) | `sprint-close` | Sonnet |
| 스프린트 리뷰 (코드 리뷰 + 검증) | `sprint-review` | Sonnet |
| 프로덕션 배포 | `deploy-prod` | Sonnet |
| 핫픽스 마무리 | `hotfix-close` | Sonnet |

## 외부 API 의존성

| API | 용도 | Rate Limit | 환경변수 |
|-----|------|-----------|---------|
| 한국투자증권 (실전) | 시세 + 주문 | 초당 ~20건 | `KIS_APP_KEY`, `KIS_APP_SECRET` |
| 한국투자증권 (모의) | 개발/테스트 | 초당 ~1건 | `KIS_MOCK_APP_KEY`, `KIS_MOCK_APP_SECRET` |
| 네이버 검색 | 뉴스/트렌드 | 일 25,000건 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| Open Dart | 재무/공시 | 일 10,000건 | `DART_API_KEY` |
| 공공데이터포털 | 시가총액/상장주식수 | 일 1,000건 | `DATA_GO_KR_API_KEY` |
| Telegram Bot | 알림/승인 | 초당 30건 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

## 경로별 상세 규칙

- 백엔드: `.claude/rules/backend.md`
- 프론트엔드: `.claude/rules/frontend.md`
- 스프린트 워크플로우: `.claude/rules/sprint-workflow.md`
- Notion 문서 관리: `.claude/rules/notion.md`

## 훅 시스템

- **PreToolUse (bash-guard)**: 위험 명령 차단 (force push, hard reset, 잘못된 브랜치명 등)
- **Stop (doc-checker)**: 에이전트 완료 전 필수 파일 업데이트 검증 (`docs/index.json`, `deploy.md`, `MEMORY.md` 등)
- 검증 규칙 상세: `.claude/hooks/lib/doc-rules.json`

## 체크리스트 작성 형식

- 완료 항목: `- ✅ 항목 내용`
- 미완료 항목: `- ⬜ 항목 내용`
- GFM `[x]`/`[ ]` 대신 이모지 사용

## Notion 기술 문서 관리

상세 규칙은 `.claude/rules/notion.md` 참조. 업데이트 트리거는 `docs/dev-process.md` 섹션 8.5 참조.
