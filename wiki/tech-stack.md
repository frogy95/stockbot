# 기술 스택

[[system-overview|시스템]]에서 사용하는 기술 스택과 선택 이유.

## 백엔드

| 기술 | 버전 | 선택 이유 |
|------|------|----------|
| Python | 3.12 | 금융 라이브러리 풍부, 비동기 성숙 |
| FastAPI | 최신 | 비동기 지원, 자동 API 문서화 |
| SQLAlchemy | 2.0 | 비동기 ORM, type-safe |
| Alembic | 최신 | DB 마이그레이션 관리 |
| APScheduler | 최신 | FastAPI 내장 크론 스케줄러 |
| pydantic-settings | 최신 | 환경변수 타입 안전 관리 |

## 프론트엔드

| 기술 | 선택 이유 |
|------|----------|
| Next.js (App Router) | React 기반 SSR, 실시간 업데이트 |
| TypeScript | 타입 안전성 |
| Tailwind CSS | 빠른 UI 개발 |

## 저장소

| 저장소 | 용도 |
|--------|------|
| PostgreSQL 16 | 시계열 + 관계형 데이터 통합. [[database-schema]] 참조 |
| Redis 7 | 실시간 시세, 세션, 승인 대기 큐. [[redis-usage]] 참조 |

## 인프라

| 레이어 | 기술 | 용도 |
|--------|------|------|
| 프론트엔드 호스팅 | Vercel | Next.js 자동 배포 |
| 백엔드 호스팅 | Railway | FastAPI + PostgreSQL + Redis |
| DNS/CDN | Cloudflare | 도메인 관리 |
| 컨테이너 | Docker Compose | 로컬/서버 동일 환경 |

[[deployment]] 참조.

## 외부 연동

- 한국투자증권 API (REST + WebSocket) — [[kis-api]]
- 공공데이터포털, DART, 네이버 — [[public-data-sources]]
- Telegram Bot API — [[telegram-integration]]

## 아키텍처 패턴

**모놀리식 + 모듈 경계**: 단일 FastAPI 앱이지만 `modules/` 하위에 명확한 경계로 분리. Railway 단일 서비스로 배포하면서도 향후 마이크로서비스 분리를 고려한 구조.
