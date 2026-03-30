---
name: Phase 4 Sprint 1 상태
description: Phase 4 Sprint 1 (대시보드 기본 구조 + 핵심 페이지) 계획 및 진행 상태
type: project
---

## Phase 4 Sprint 1: 대시보드 기본 구조 + 핵심 페이지

**상태**: 계획 수립 완료 (2026-03-31)
**브랜치**: `phase4-sprint1`
**문서**: `docs/phase/phase4/sprint1/sprint1.md`

### Task 목록 (9개)

1. 백엔드: 환경변수 + CORS + JWT 인증 API (PyJWT, Redis 로그인 실패 카운터)
2. 백엔드: 대시보드 집계 API (/dashboard/summary)
3. 프론트엔드: shadcn/ui + SWR + API 클라이언트 + 색상 상수
4. 프론트엔드: 인증 (로그인 페이지 + AuthProvider + 미들웨어)
5. 프론트엔드: 대시보드 레이아웃 (사이드바 + 모드배너)
6. 프론트엔드: 메인 대시보드 페이지 (4개 카드)
7. 프론트엔드: 포지션 페이지
8. 프론트엔드: 주문 현황 페이지 (상태별 필터)
9. 통합 테스트 + 회귀 검증

### 주의사항

- Next.js 16 미들웨어 API 변경 가능 (middleware.ts -> proxy.ts 확인 필요)
- CORS는 글로벌 미들웨어가 아닌 settings.ALLOWED_ORIGINS.split(",") 방식
- 인증은 글로벌 미들웨어가 아닌 Depends(get_current_user) 방식 (라우터별 보호)
- 기존 API(health, auth/login, telegram/webhook)는 인증 제외
- shadcn/ui 초기 설정에 시간 충분히 배분 (미해결 사항 #7)
- 한국 증시 색상: 빨강=#EF4444(수익), 파랑=#3B82F6(손실), 회색=#9CA3AF(보합)
- 모드배너 3중 표시: 상단 배너(40px) + 사이드바 배지 + 페이지 인디케이터
- SWR 폴링: 기본 5초, refreshWhenHidden=false (탭 비활성화 시 중단)
- frontend/app/layout.tsx에 이미 `dark` 클래스 + zinc-950 배경색 적용됨
- frontend/package.json: Next.js 16.2.1, React 19, Tailwind 4 이미 설치됨
