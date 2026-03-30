# Sprint 1: 대시보드 기본 구조 + 핵심 페이지 (Phase 4)

**Goal:** Next.js 프론트엔드에 인증, 레이아웃(사이드바+모드배너), 메인 대시보드, 포지션, 주문 현황 페이지를 구현하고 SWR 폴링으로 실시간 업데이트한다.

**Architecture:** 백엔드에 JWT 인증 API + 대시보드 집계 API를 추가하고, CORS를 환경변수 기반으로 전환한다. 프론트엔드에 shadcn/ui 기반 다크 모드 대시보드를 구축하며, SWR의 refreshInterval + revalidateOnFocus로 5초 폴링을 구현한다. 기존 trading API(/positions, /orders, /history, /risk-status, /engine-status)를 그대로 재활용한다.

**Tech Stack:** Next.js 16 (App Router) + React 19 + shadcn/ui + SWR + Tailwind CSS 4 + PyJWT + FastAPI

**Sprint 기간:** 2026-03-31 ~ (사용자 검토 후 구현)
**이전 스프린트:** Phase 3 Sprint 3 (텔레그램 봇 + 반자동 승인, PR: https://github.com/frogy95/stockbot/pull/35 등)
**브랜치명:** `phase4-sprint1`

---

## 제외 범위

- 매매 신호 페이지 (Sprint 2)
- 스크리닝 페이지 (Sprint 2)
- 매매 이력 페이지 (Sprint 2)
- 성과 분석 페이지 (Sprint 2)
- 설정 페이지 및 모드 전환 기능 (Sprint 2)
- 웹 매매 승인/거부 (Sprint 2)
- 모바일 반응형 (Phase 6)
- 라이트 모드 (미지원, 다크 모드 전용)
- Playwright E2E 테스트 (Sprint 완료 후 sprint-review에서 수행)

## 실행 플랜

의존성: 백엔드 API(인증+집계+CORS)가 프론트엔드보다 먼저 완성되어야 한다. 프론트엔드 셋업(shadcn/ui)은 백엔드와 병렬 가능하나, 실제 페이지 구현은 API 완성 후.

### Phase 1 (순차 -- 백엔드 인증 + 인프라)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 백엔드: 환경변수 + CORS + JWT 인증 API | 백엔드 | -- |
| Task 2 | 백엔드: 대시보드 집계 API | 백엔드 | -- |

### Phase 2 (순차 -- 프론트엔드 셋업)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 3 | 프론트엔드: shadcn/ui + SWR + API 클라이언트 + 색상 상수 | 프론트엔드 | -- |

### Phase 3 (순차 -- 레이아웃 + 인증)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 프론트엔드: 인증 (로그인 페이지 + AuthProvider + 미들웨어) | 프론트엔드 | `frontend-design` |
| Task 5 | 프론트엔드: 대시보드 레이아웃 (사이드바 + 모드배너) | 프론트엔드 | `frontend-design` |

### Phase 4 (순차 -- 핵심 페이지)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | 프론트엔드: 메인 대시보드 페이지 | 프론트엔드 | `frontend-design` |
| Task 7 | 프론트엔드: 포지션 페이지 | 프론트엔드 | `frontend-design` |
| Task 8 | 프론트엔드: 주문 현황 페이지 | 프론트엔드 | `frontend-design` |

### Phase 5 (순차 -- 통합 검증)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 9 | 통합 테스트 + 회귀 검증 | 전체 | -- |

---

### Task 1: 백엔드 -- 환경변수 + CORS + JWT 인증 API

**Files:**
- Modify: `backend/core/config.py` (ALLOWED_ORIGINS, ADMIN_PASSWORD, JWT_EXPIRY_HOURS 환경변수 추가)
- Create: `backend/api/routes/auth.py` (JWT 로그인/갱신/사용자정보 API)
- Modify: `backend/api/deps.py` (get_current_user JWT 검증 의존성 추가)
- Modify: `backend/main.py` (CORS origins 환경변수화, auth 라우터 등록)
- Modify: `backend/.env.example` (신규 환경변수 추가)
- Modify: `backend/requirements.txt` (PyJWT 추가)
- Test: `backend/tests/test_auth.py`

**Step 1: 테스트 작성**
- `backend/tests/test_auth.py` 생성
- 테스트 케이스:
  - 올바른 비밀번호로 로그인 -> 200 + JWT 토큰 반환
  - 잘못된 비밀번호로 로그인 -> 401
  - 5회 실패 후 15분 잠금 -> 429
  - 유효한 토큰으로 /auth/me -> 200 + 사용자 정보
  - 만료/잘못된 토큰으로 /auth/me -> 401
  - 토큰 갱신 -> 200 + 새 토큰
  - 인증 제외 경로 (health, auth/login) -> 인증 없이 200
- 검증: `docker compose exec backend pytest tests/test_auth.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 환경변수 추가**
- `backend/core/config.py`의 Settings 클래스에 추가:
  - `ALLOWED_ORIGINS: str = "http://localhost:3000"` (쉼표 구분 문자열)
  - `ADMIN_PASSWORD: str = ""` (빈 문자열 기본값, 미설정 시 로그인 차단)
  - `JWT_EXPIRY_HOURS: int = 24`
- `backend/.env.example`에 `ALLOWED_ORIGINS`, `ADMIN_PASSWORD`, `JWT_EXPIRY_HOURS` 추가
- 검증: `docker compose exec backend python -c "from core.config import settings; print(settings.ALLOWED_ORIGINS)"`
- 예상: `http://localhost:3000`

**Step 3: JWT 인증 라우터 구현**
- `backend/requirements.txt`에 `PyJWT>=2.8.0` 추가
- `backend/api/routes/auth.py` 생성:
  - `POST /auth/login` -- 비밀번호 검증 -> JWT 발급 (HS256, settings.JWT_SECRET 사용)
    - 요청: `{"password": "..."}`
    - 응답: `{"access_token": "...", "token_type": "bearer", "expires_in": 86400}`
    - 로그인 실패 카운터: Redis key `login:fail_count`, TTL 15분, 5회 초과 시 429
  - `POST /auth/refresh` -- Authorization 헤더의 JWT 검증 후 새 토큰 발급
  - `GET /auth/me` -- 현재 사용자 정보 반환 `{"username": "admin", "trading_env": "paper|live"}`
- 검증: `docker compose exec backend pytest tests/test_auth.py -v -k "login"`
- 예상: login 관련 테스트 PASS

**Step 4: JWT 검증 의존성 + CORS 환경변수화**
- `backend/api/deps.py`에 `get_current_user` 함수 추가:
  - Authorization 헤더에서 Bearer 토큰 추출
  - jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
  - 만료/유효하지 않은 토큰 -> HTTPException(401)
- `backend/main.py` 수정:
  - `allow_origins=["http://localhost:3000"]` -> `allow_origins=settings.ALLOWED_ORIGINS.split(",")`
  - auth 라우터 등록: `app.include_router(auth_router, prefix="/api/v1")`
  - 인증 제외 경로: health, auth/login, telegram/webhook 은 인증 불필요 (각 라우터 레벨에서 Depends 적용 방식으로 처리 -- 글로벌 미들웨어 아님, 보호 필요한 라우터에만 Depends(get_current_user) 추가)
- 검증: `docker compose exec backend pytest tests/test_auth.py -v`
- 예상: 전체 PASS

**Step 5: 커밋**
```
git add backend/core/config.py backend/api/routes/auth.py backend/api/deps.py backend/main.py backend/.env.example backend/requirements.txt backend/tests/test_auth.py
git commit -m "feat(phase4-sprint1): task1 -- JWT 인증 API + CORS 환경변수화"
```

**완료 기준:**
- ⬜ pytest test_auth.py 전체 통과
- ⬜ CORS origins 환경변수 반영 확인
- ⬜ 인증 제외 경로 정상 동작

---

### Task 2: 백엔드 -- 대시보드 집계 API

**Files:**
- Create: `backend/api/routes/dashboard.py` (대시보드 집계 엔드포인트)
- Modify: `backend/main.py` (dashboard 라우터 등록)
- Test: `backend/tests/test_dashboard_api.py`

**Step 1: 테스트 작성**
- `backend/tests/test_dashboard_api.py` 생성
- 테스트 케이스:
  - `GET /dashboard/summary` -> 200 + 오늘 손익 합계, 보유 종목 수, 거래 건수, 엔진 상태, 리스크 상태 포함
  - 거래 이력 없는 경우 -> 손익 0, 거래 건수 0
  - 포지션 존재 시 -> 보유 종목 수 > 0
- 검증: `docker compose exec backend pytest tests/test_dashboard_api.py -v`
- 예상: FAIL (모듈 미존재)

**Step 2: 집계 API 구현**
- `backend/api/routes/dashboard.py` 생성:
  - `GET /dashboard/summary` (Depends(get_current_user) 보호)
  - 반환 스키마:
    ```
    {
      "today_pnl": int,           // 오늘 실현 손익 합계 (trade_history.exit_time = today)
      "today_pnl_rate": float,    // 오늘 평균 수익률
      "today_trade_count": int,   // 오늘 거래 건수
      "active_positions": int,    // 활성 포지션 수 (positions 테이블 count)
      "unrealized_pnl": int,      // 미실현 손익 합계
      "trading_env": str,         // "paper" | "live"
      "engine_running": bool,     // 매매 엔진 실행 중 여부
      "risk_status": {...}        // risk_manager.get_risk_status() 결과
    }
    ```
  - DB 쿼리: TradeHistory(오늘 손익), PositionRecord(포지션), 엔진/리스크 상태는 app.state에서 조회
- `backend/main.py`에 dashboard 라우터 등록
- 검증: `docker compose exec backend pytest tests/test_dashboard_api.py -v`
- 예상: PASS

**Step 3: curl 검증**
- 검증: `curl -s -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/dashboard/summary | python -m json.tool`
- 예상: 위 스키마 형태의 JSON 응답

**Step 4: 커밋**
```
git add backend/api/routes/dashboard.py backend/main.py backend/tests/test_dashboard_api.py
git commit -m "feat(phase4-sprint1): task2 -- 대시보드 집계 API (/dashboard/summary)"
```

**완료 기준:**
- ⬜ pytest test_dashboard_api.py 전체 통과
- ⬜ /dashboard/summary 응답에 모든 필수 필드 포함

---

### Task 3: 프론트엔드 -- shadcn/ui + SWR + API 클라이언트 + 색상 상수

**Files:**
- Modify: `frontend/package.json` (swr, shadcn/ui 관련 의존성 추가)
- Modify: `frontend/next.config.ts` (API 프록시 rewrites 추가)
- Modify: `frontend/app/globals.css` (shadcn/ui CSS 변수 통합)
- Create: `frontend/lib/api.ts` (fetch 기반 API 클라이언트, JWT 토큰 자동 첨부)
- Create: `frontend/lib/colors.ts` (한국 증시 색상 상수)
- Create: `frontend/lib/hooks/use-polling.ts` (SWR 기반 폴링 훅)
- Create: `frontend/components/ui/` (shadcn/ui 컴포넌트: button, card, table, badge, input, dialog, separator, skeleton)
- Create: `frontend/lib/utils.ts` (cn 유틸리티 -- shadcn/ui 필수)
- Create: `frontend/components.json` (shadcn/ui 설정)

**Step 1: 의존성 설치 + shadcn/ui 초기화**
- `frontend/` 디렉토리에서:
  - `npm install swr` -- 폴링 라이브러리
  - shadcn/ui 초기화: `npx shadcn@latest init` (다크 모드, zinc 테마)
  - 필수 컴포넌트 설치: `npx shadcn@latest add button card table badge input dialog separator skeleton`
- `frontend/next.config.ts`에 API rewrites 추가:
  - `/api/:path*` -> `process.env.NEXT_PUBLIC_API_URL + /api/:path*` (로컬 개발 프록시)
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 타입 에러 없음

**Step 2: 색상 상수**
- `frontend/lib/colors.ts` 생성:
  - `PROFIT = "#EF4444"` (빨강, 수익/상승 -- 한국 증시 관례)
  - `LOSS = "#3B82F6"` (파랑, 손실/하락)
  - `NEUTRAL = "#9CA3AF"` (회색, 보합)
  - `LIVE_BANNER_BG = "#DC2626"` (실전 모드 배너)
  - `LIVE_BANNER_TEXT = "#FFFFFF"`
  - `PAPER_BANNER_BG = "#16A34A"` (모의 모드 배너)
  - `PAPER_BANNER_TEXT = "#FFFFFF"`
  - `getPnlColor(value: number): string` 헬퍼 함수 (양수->PROFIT, 음수->LOSS, 0->NEUTRAL)
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 타입 에러 없음

**Step 3: API 클라이언트**
- `frontend/lib/api.ts` 생성:
  - `getToken(): string | null` -- localStorage에서 JWT 토큰 조회
  - `setToken(token: string)` -- localStorage에 저장
  - `removeToken()` -- localStorage에서 제거
  - `apiFetch(path: string, options?: RequestInit): Promise<Response>` -- fetch 래퍼:
    - 자동으로 Authorization: Bearer 헤더 첨부
    - 401 응답 시 토큰 제거 + /login 리다이렉트
    - Content-Type: application/json 기본 설정
  - `apiGet<T>(path: string): Promise<T>` -- GET 단축
  - `apiPost<T>(path: string, body: unknown): Promise<T>` -- POST 단축

**Step 4: SWR 폴링 훅**
- `frontend/lib/hooks/use-polling.ts` 생성:
  - `usePolling<T>(path: string, intervalMs?: number)` 커스텀 훅:
    - SWR의 `useSWR` 사용, fetcher는 `apiGet`
    - `refreshInterval: intervalMs ?? 5000` (기본 5초)
    - `revalidateOnFocus: false` (탭 포커스 시 재요청 안 함)
    - `refreshWhenHidden: false` (탭 비활성화 시 폴링 중단)
    - 반환: `{ data, error, isLoading, mutate }`
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 타입 에러 없음

**Step 5: 커밋**
```
git add frontend/package.json frontend/package-lock.json frontend/next.config.ts frontend/app/globals.css frontend/lib/ frontend/components/ frontend/components.json frontend/lib/utils.ts
git commit -m "feat(phase4-sprint1): task3 -- shadcn/ui + SWR + API 클라이언트 + 색상 상수"
```

**완료 기준:**
- ⬜ `npx tsc --noEmit` 에러 없음
- ⬜ shadcn/ui 컴포넌트 8종 설치 확인
- ⬜ SWR 폴링 훅 타입 정상

---

### Task 4: 프론트엔드 -- 인증 (로그인 페이지 + AuthProvider + 미들웨어)

**skill:** `frontend-design`

**Files:**
- Create: `frontend/lib/auth.tsx` (AuthProvider 컨텍스트 + useAuth 훅)
- Create: `frontend/app/(auth)/login/page.tsx` (로그인 페이지)
- Create: `frontend/app/(auth)/layout.tsx` (인증 레이아웃 -- 센터 정렬)
- Modify: `frontend/app/layout.tsx` (AuthProvider 래핑)
- Create: `frontend/middleware.ts` (미인증 사용자 /login 리다이렉트)

**Step 1: AuthProvider 구현**
- `frontend/lib/auth.tsx` 생성 ('use client'):
  - AuthContext: `{ isAuthenticated, user, login, logout, isLoading }`
  - `user` 타입: `{ username: string; trading_env: "paper" | "live" }`
  - `login(password: string): Promise<boolean>` -- POST /api/v1/auth/login -> 토큰 저장 -> /auth/me 호출
  - `logout()` -- 토큰 제거 + /login 리다이렉트
  - 초기화 시 토큰 존재하면 /auth/me 호출하여 사용자 정보 로드
  - `useAuth()` 훅으로 컨텍스트 소비
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`

**Step 2: 로그인 페이지**
- `frontend/app/(auth)/layout.tsx` -- 심플 센터 레이아웃 (로고 + children)
- `frontend/app/(auth)/login/page.tsx` ('use client'):
  - shadcn/ui Card + Input + Button
  - 비밀번호 입력 필드, 로그인 버튼
  - 에러 메시지 표시 (잘못된 비밀번호, 잠금 상태)
  - 성공 시 / (메인 대시보드)로 리다이렉트
  - 다크 모드 스타일링

**Step 3: Next.js 미들웨어**
- `frontend/middleware.ts` 생성:
  - 쿠키 또는 헤더에서 토큰 존재 여부 확인
  - 토큰 없으면 /login으로 리다이렉트
  - 제외 경로: `/login`, `/_next`, `/favicon.ico`, `/api`
  - 주의: Next.js 16 미들웨어 API 확인 필요 (middleware.ts 또는 proxy.ts 등 변경 가능)

**Step 4: layout.tsx에 AuthProvider 래핑**
- `frontend/app/layout.tsx` 수정:
  - body 안에 `<AuthProvider>{children}</AuthProvider>` 추가
  - AuthProvider는 'use client'이므로 layout.tsx 자체는 서버 컴포넌트 유지 가능
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 타입 에러 없음

**Step 5: 수동 검증**
- 검증: 브라우저에서 `http://localhost:3000` 접속 -> /login 리다이렉트 확인
- 올바른 비밀번호 입력 -> 대시보드 진입 확인
- 검증: `curl -s http://localhost:3000/login -o /dev/null -w "%{http_code}"` -> 200

**Step 6: 커밋**
```
git add frontend/lib/auth.tsx frontend/app/\(auth\)/ frontend/app/layout.tsx frontend/middleware.ts
git commit -m "feat(phase4-sprint1): task4 -- 로그인 페이지 + AuthProvider + 미들웨어"
```

**완료 기준:**
- ⬜ `npx tsc --noEmit` 에러 없음
- ⬜ 미인증 접근 시 /login 리다이렉트
- ⬜ 로그인 성공 시 대시보드 진입
- ⬜ 잘못된 비밀번호 에러 메시지 표시

---

### Task 5: 프론트엔드 -- 대시보드 레이아웃 (사이드바 + 모드배너)

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(dashboard)/layout.tsx` (사이드바 + 모드배너 + 메인영역)
- Create: `frontend/components/layout/sidebar.tsx` (좌측 사이드바 네비게이션)
- Create: `frontend/components/layout/mode-banner.tsx` (실전/모의 모드 고정 배너 40px)

**Step 1: 모드 배너 구현**
- `frontend/components/layout/mode-banner.tsx` ('use client'):
  - useAuth()에서 trading_env 가져오기
  - `live` -> 빨강 배너 (#DC2626) + 흰색 텍스트 "실전 거래 중"
  - `paper` -> 초록 배너 (#16A34A) + 흰색 텍스트 "모의 거래"
  - 고정 높이 40px, 화면 상단 고정 (sticky top-0)
  - colors.ts의 상수 사용

**Step 2: 사이드바 구현**
- `frontend/components/layout/sidebar.tsx` ('use client'):
  - 좌측 사이드바 (접기 가능 -- 아이콘/텍스트 토글)
  - 네비게이션 메뉴 항목 (8개 페이지):
    - 대시보드 `/`
    - 포지션 `/positions`
    - 주문 현황 `/orders`
    - 매매 신호 `/signals` (Sprint 2에서 구현, 링크만 배치)
    - 스크리닝 `/screening` (Sprint 2)
    - 매매 이력 `/history` (Sprint 2)
    - 성과 분석 `/analytics` (Sprint 2)
    - 설정 `/settings` (Sprint 2)
  - 현재 경로 활성 표시 (usePathname)
  - 하단에 모드 배지: `live` -> 빨강 Badge, `paper` -> 초록 Badge
  - 하단에 로그아웃 버튼

**Step 3: 대시보드 레이아웃 조합**
- `frontend/app/(dashboard)/layout.tsx`:
  - 구조: 모드배너(상단 40px) + 사이드바(좌측) + 메인 콘텐츠(우측 스크롤)
  - 인증 필요 (AuthProvider가 이미 래핑됨, 미들웨어가 리다이렉트 처리)
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 타입 에러 없음

**Step 4: 수동 검증**
- 검증: 브라우저에서 로그인 후 대시보드 진입 -> 사이드바 + 모드배너 표시 확인
- 사이드바 접기/펼치기 동작 확인
- 모드배너 색상 (TRADING_ENV=paper -> 초록, live -> 빨강) 확인

**Step 5: 커밋**
```
git add frontend/app/\(dashboard\)/layout.tsx frontend/components/layout/
git commit -m "feat(phase4-sprint1): task5 -- 대시보드 레이아웃 (사이드바 + 모드배너)"
```

**완료 기준:**
- ⬜ `npx tsc --noEmit` 에러 없음
- ⬜ 사이드바 8개 메뉴 항목 표시 + 접기/펼치기
- ⬜ 모드배너 40px 고정, 환경별 색상 정확
- ⬜ 사이드바 하단 모드 배지 + 로그아웃

---

### Task 6: 프론트엔드 -- 메인 대시보드 페이지

**skill:** `frontend-design`

**Files:**
- Modify: `frontend/app/(dashboard)/page.tsx` (메인 대시보드 구현)

**Step 1: 대시보드 페이지 구현**
- `frontend/app/(dashboard)/page.tsx` ('use client'):
  - usePolling("/api/v1/dashboard/summary") 로 5초 폴링
  - 카드 4개 그리드 레이아웃 (2x2 또는 4x1):
    1. **오늘 손익** -- today_pnl 금액 + today_pnl_rate 비율, 색상은 getPnlColor 적용
    2. **보유 종목** -- active_positions 수
    3. **오늘 거래** -- today_trade_count 건수
    4. **미실현 손익** -- unrealized_pnl 금액, 색상 적용
  - 하단 상태 영역:
    - 엔진 상태: 실행 중/중지 Badge
    - 리스크 상태: 일일 한도 사용량 (프로그레스 바)
    - 거래 환경: paper/live 표시
  - Skeleton 로딩 상태 (SWR isLoading 시)
  - 에러 상태 표시
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 타입 에러 없음

**Step 2: 수동 검증**
- 검증: 브라우저에서 메인 대시보드 -> 4개 카드 표시 확인
- 5초 폴링으로 데이터 갱신 확인 (Network 탭에서 5초 간격 요청 확인)
- 탭 비활성화 후 다시 활성화 -> 즉시 갱신 확인

**Step 3: 커밋**
```
git add frontend/app/\(dashboard\)/page.tsx
git commit -m "feat(phase4-sprint1): task6 -- 메인 대시보드 페이지 (손익/포지션/거래/리스크 카드)"
```

**완료 기준:**
- ⬜ `npx tsc --noEmit` 에러 없음
- ⬜ 4개 카드에 데이터 표시
- ⬜ 5초 폴링 동작
- ⬜ 로딩/에러 상태 처리

---

### Task 7: 프론트엔드 -- 포지션 페이지

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(dashboard)/positions/page.tsx` (포지션 페이지)

**Step 1: 포지션 페이지 구현**
- `frontend/app/(dashboard)/positions/page.tsx` ('use client'):
  - usePolling("/api/v1/trading/positions") 로 5초 폴링
  - 기존 API 응답 필드 활용: stock_code, quantity, avg_price, current_price, unrealized_pnl, stop_loss, take_profit, trailing_activated, entry_time, strategy_name
  - shadcn/ui Table 사용:
    - 컬럼: 종목코드, 수량, 평균가, 현재가, 미실현 손익, 손익률, 손절가, 익절가, 트레일링, 진입 시각
    - 미실현 손익 색상: getPnlColor 적용 (양수=빨강, 음수=파랑)
    - 손익률 계산: (current_price - avg_price) / avg_price * 100
  - 상단에 보유 종목 수 + 총 미실현 손익 요약 Card
  - 포지션 없는 경우: "보유 종목이 없습니다" 빈 상태 메시지
  - Skeleton 로딩 상태
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 타입 에러 없음

**Step 2: 수동 검증**
- 검증: 브라우저에서 /positions -> 테이블 표시 확인
- 포지션이 없는 경우 빈 상태 메시지 확인

**Step 3: 커밋**
```
git add frontend/app/\(dashboard\)/positions/
git commit -m "feat(phase4-sprint1): task7 -- 포지션 페이지 (보유 종목 테이블 + 5초 폴링)"
```

**완료 기준:**
- ⬜ `npx tsc --noEmit` 에러 없음
- ⬜ 테이블에 포지션 데이터 표시
- ⬜ 미실현 손익 색상 (빨강/파랑) 정확
- ⬜ 빈 상태 + 로딩 상태 처리

---

### Task 8: 프론트엔드 -- 주문 현황 페이지

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(dashboard)/orders/page.tsx` (주문 현황 페이지)

**Step 1: 주문 현황 페이지 구현**
- `frontend/app/(dashboard)/orders/page.tsx` ('use client'):
  - usePolling("/api/v1/trading/orders") 로 5초 폴링
  - 기존 API 응답 필드: id, signal_id, stock_code, order_type, order_no, quantity, price, order_division, status, submitted_at, filled_at
  - 상태별 필터 탭: 전체 / 대기(pending_approval) / 체결(filled) / 취소(cancelled)
    - 탭 전환 시 쿼리 파라미터 `?status=filled` 사용
  - shadcn/ui Table:
    - 컬럼: 주문번호, 종목코드, 주문유형(매수/매도), 수량, 가격, 주문구분, 상태, 제출시각, 체결시각
    - 상태별 Badge 색상: 대기=노랑, 체결=초록, 취소=회색
  - 주문 없는 경우 빈 상태 메시지
  - Skeleton 로딩 상태
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 타입 에러 없음

**Step 2: 수동 검증**
- 검증: 브라우저에서 /orders -> 테이블 표시 확인
- 상태 필터 탭 전환 동작 확인

**Step 3: 커밋**
```
git add frontend/app/\(dashboard\)/orders/
git commit -m "feat(phase4-sprint1): task8 -- 주문 현황 페이지 (상태별 필터 + 5초 폴링)"
```

**완료 기준:**
- ⬜ `npx tsc --noEmit` 에러 없음
- ⬜ 테이블에 주문 데이터 표시
- ⬜ 상태별 필터 탭 동작
- ⬜ 빈 상태 + 로딩 상태 처리

---

### Task 9: 통합 테스트 + 회귀 검증

**Files:**
- Test: `backend/tests/test_phase4_sprint1_integration.py`

**Step 1: 백엔드 통합 테스트**
- `backend/tests/test_phase4_sprint1_integration.py` 생성:
  - JWT 로그인 -> 토큰 획득 -> 보호된 API 접근 전체 플로우
  - /dashboard/summary 집계 정확성 (DB에 테스트 데이터 삽입 후 검증)
  - 인증 제외 경로 (health) 미인증 접근 가능 확인
  - CORS 헤더 검증 (Origin 헤더 포함 요청 -> Access-Control-Allow-Origin 응답)
- 검증: `docker compose exec backend pytest tests/test_phase4_sprint1_integration.py -v`
- 예상: PASS

**Step 2: 백엔드 전체 회귀 검증**
- 검증: `docker compose exec backend pytest -v`
- 예상: 기존 테스트 + 신규 테스트 전체 PASS (기존 약 500+ tests)

**Step 3: 프론트엔드 타입체크**
- 검증: `cd /Users/choijiseon/Documents/Sources/stockbot/frontend && npx tsc --noEmit`
- 예상: 에러 없음

**Step 4: 수동 검증 체크리스트**
- ⬜ 로그인 -> 대시보드 진입 플로우
- ⬜ 메인 대시보드 4개 카드 데이터 표시
- ⬜ 포지션 페이지 테이블
- ⬜ 주문 현황 페이지 + 필터 탭
- ⬜ 사이드바 네비게이션 + 접기
- ⬜ 모드배너 색상 (TRADING_ENV별)
- ⬜ 5초 폴링 동작 (Network 탭 확인)
- ⬜ 탭 비활성화 시 폴링 중단

**Step 5: 커밋**
```
git add backend/tests/test_phase4_sprint1_integration.py
git commit -m "feat(phase4-sprint1): task9 -- Phase 4 Sprint 1 통합 테스트 + 회귀 검증"
```

**완료 기준:**
- ⬜ pytest 전체 통과
- ⬜ `npx tsc --noEmit` 에러 없음
- ⬜ 수동 검증 체크리스트 전체 통과

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 기존 + 신규 전체 passed |
| 프론트 타입체크 | `cd frontend && npx tsc --noEmit` | 에러 없음 |
| 인증 API | `curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"password":"test"}' \| python -m json.tool` | access_token 반환 |
| 대시보드 집계 | `curl -s -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/dashboard/summary \| python -m json.tool` | today_pnl, active_positions 등 포함 |
| 미인증 차단 | `curl -s http://localhost:8000/api/v1/dashboard/summary -w "\n%{http_code}"` | 401 |
| CORS 헤더 | `curl -s -H "Origin: http://localhost:3000" -I http://localhost:8000/api/v1/health` | Access-Control-Allow-Origin 포함 |
| 프론트엔드 접속 | `curl -s http://localhost:3000 -o /dev/null -w "%{http_code}"` | 200 또는 307 (/login 리다이렉트) |
| 로그인 페이지 | `curl -s http://localhost:3000/login -o /dev/null -w "%{http_code}"` | 200 |
