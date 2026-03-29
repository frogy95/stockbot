---
paths:
  - "frontend/**/*.{ts,tsx,css}"
  - "frontend/package.json"
  - "frontend/next.config.*"
---

# 프론트엔드 개발 규칙

## 기술 스택
# TODO: 프로젝트 기술 스택을 기입하세요
# 예: Next.js App Router, TypeScript strict, TailwindCSS, shadcn/ui
# 예: 상태 관리 라이브러리 (TanStack Query, zustand 등)

## 핵심 규칙
- API 클라이언트: 별도 모듈로 분리 (fetch 기반, 인증 토큰 자동 첨부)
- Mock 데이터: 별도 디렉토리에 분리 # TODO: Mock 데이터 경로를 기입하세요
- shadcn/ui 컴포넌트 우선 활용
- TypeScript `any` 사용 최소화

## 타입 체크
```bash
cd frontend && npx tsc --noEmit
```
