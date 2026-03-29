---
paths:
  - "frontend/**/*.{ts,tsx,css}"
  - "frontend/package.json"
  - "frontend/next.config.*"
  - "frontend/tsconfig.json"
  - "frontend/tailwind.config.*"
---

# 프론트엔드 개발 규칙

## 주의: Next.js 16 Breaking Changes

Next.js 16은 이전 버전과 호환되지 않는 변경사항이 있다. 학습 데이터의 API/컨벤션이 다를 수 있으므로, 코드 작성 전 `node_modules/next/dist/docs/`의 공식 문서를 확인할 것. 폐기 예정(deprecation) 경고에 주의.

## 기술 스택

- Next.js 16.2 (App Router)
- React 19
- TypeScript 5 (strict)
- Tailwind CSS 4
- ESLint 9 + eslint-config-next

## 프로젝트 구조

```
frontend/
├── app/                # App Router (페이지, 레이아웃)
│   ├── layout.tsx      # 루트 레이아웃
│   ├── page.tsx        # 메인 페이지
│   └── globals.css     # 글로벌 스타일 (Tailwind)
├── components/         # 재사용 컴포넌트 (Phase 4에서 추가)
├── lib/                # 유틸리티, API 클라이언트
├── public/             # 정적 파일
├── next.config.ts      # Next.js 설정
├── tsconfig.json       # TypeScript 설정
├── package.json        # 의존성
└── Dockerfile          # 프로덕션 이미지
```

## 핵심 규칙

- **Server Components 기본**: `'use client'`는 인터랙션/브라우저 API 필요 시에만
- **`'use client'` 경계를 최대한 아래로**: 페이지가 아닌 리프 컴포넌트에 배치
- **비동기 API**: `await cookies()`, `await headers()`, `await params` (Next.js 16)
- **TypeScript `any` 금지**: 불가피한 경우 `unknown` + 타입 가드 사용
- **API 클라이언트**: `lib/` 하위에 fetch 기반 모듈로 분리, 인증 토큰 자동 첨부
- **한국 증시 색상 관례**: 빨강=상승/수익, 파랑=하락/손실

## 스타일링

- Tailwind CSS 4 유틸리티 클래스 사용
- 다크 모드 기본 (트레이딩 대시보드 특성)
- 컴포넌트 라이브러리: shadcn/ui 도입 예정 (Phase 4)

## 타입 체크

```bash
cd frontend && npx tsc --noEmit
```

## 배포

- **로컬**: Docker Compose (`docker compose up frontend -d`)
- **프로덕션**: Vercel (main merge 시 자동 배포)
- **환경변수**: `NEXT_PUBLIC_API_URL` — Railway 백엔드 API URL
