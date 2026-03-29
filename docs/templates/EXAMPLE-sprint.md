> **이 파일은 예제입니다.** sprint-planner 에이전트가 실제 `docs/phase/phase{N}/sprint{N}/sprint{N}.md`를 자동 생성합니다.
> 사용법: "phase{N}의 sprint 계획 세워줘. phase{N}.md 기준으로"

# Sprint {N}: 사용자 인증 시스템

**Goal:** JWT 기반 인증 시스템 구현 (회원가입, 로그인, 토큰 갱신)

**Architecture:** FastAPI 백엔드에 인증 서비스를 추가하고, Next.js 프론트엔드에 로그인/가입 UI를 구현

**Tech Stack:** FastAPI, SQLAlchemy, bcrypt, JWT, Next.js, shadcn/ui

**Sprint 기간:** YYYY-MM-DD ~ (사용자 검토 후 구현)
**이전 스프린트:** 이전 Sprint (pytest 42 passed, PR #12)

---

## 제외 범위
- OAuth/소셜 로그인 (다음 Sprint에서 구현)
- 이메일 인증 (Phase 문서에 포함되어 있으나 이 Sprint에서는 제외)

## 실행 플랜

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 인증 서비스 모듈 | 백엔드 | `karpathy-guidelines` |

### Phase 2 (병렬 가능)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | 인증 API 엔드포인트 | 백엔드 | — |
| Task 3 | 로그인/가입 UI | 프론트엔드 | `frontend-design` |

### Phase 3 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 4 | 통합 테스트 | 전체 | — |

> **팀 실행**: "Phase 2를 팀으로 실행해줘"

---

### Task 1: 인증 서비스 모듈

**skill:** `karpathy-guidelines`

**Files:**
- Create: `backend/app/services/auth.py`
- Create: `backend/app/models/user.py`
- Test: `backend/tests/services/test_auth.py`

**Step 1: 테스트 작성**

```bash
# 검증 명령
docker compose exec backend pytest backend/tests/services/test_auth.py -v
# 예상: FAILED (아직 구현 전)
```

**Step 2: 핵심 로직 구현**

- `AuthService` 클래스: 회원가입, 로그인, 토큰 발급/검증
- bcrypt를 이용한 비밀번호 해싱
- JWT access/refresh 토큰 생성

```bash
# 검증 명령
docker compose exec backend pytest backend/tests/services/test_auth.py -v
# 예상: 5 passed
```

**Step 3: 커밋**

```
git add backend/app/services/auth.py backend/app/models/user.py backend/tests/services/test_auth.py
git commit -m "feat(phase{P}-sprint{N}): 인증 서비스 모듈 구현"
```

**완료 기준:**
- ⬜ pytest 테스트 통과
- ⬜ 비밀번호 해싱 확인

---

### Task 2: 인증 API 엔드포인트

**skill:** —

**Files:**
- Create: `backend/app/api/v1/auth.py`
- Modify: `backend/app/api/v1/__init__.py`
- Test: `backend/tests/api/test_auth.py`

**Step 1: API 라우터 구현**

- POST `/api/v1/auth/register` — 회원가입
- POST `/api/v1/auth/login` — 로그인 (JWT 반환)
- POST `/api/v1/auth/refresh` — 토큰 갱신

```bash
# 검증 명령
docker compose exec backend pytest backend/tests/api/test_auth.py -v
# 예상: 6 passed
```

**Step 2: 커밋**

```
git add backend/app/api/v1/auth.py backend/app/api/v1/__init__.py backend/tests/api/test_auth.py
git commit -m "feat(phase{P}-sprint{N}): 인증 API 엔드포인트 구현"
```

**완료 기준:**
- ⬜ API 테스트 통과
- ⬜ Swagger 문서 확인

---

### Task 3: 로그인/가입 UI

**skill:** `frontend-design`

**Files:**
- Create: `frontend/app/(auth)/login/page.tsx`
- Create: `frontend/app/(auth)/register/page.tsx`
- Create: `frontend/lib/auth.ts`

**Step 1: 로그인 페이지 구현**

- shadcn/ui 컴포넌트 사용
- 폼 유효성 검사 (zod + react-hook-form)

**Step 2: 회원가입 페이지 구현**

```bash
# 검증 명령
cd frontend && npx tsc --noEmit
# 예상: 에러 없음
```

**Step 3: 커밋**

```
git add frontend/app/\(auth\)/login/page.tsx frontend/app/\(auth\)/register/page.tsx frontend/lib/auth.ts
git commit -m "feat(phase{P}-sprint{N}): 로그인/가입 UI 구현"
```

**완료 기준:**
- ⬜ TypeScript 타입체크 통과
- ⬜ 로그인/가입 폼 렌더링 확인

---

### Task 4: 통합 테스트

**skill:** —

**Files:**
- Create: `backend/tests/integration/test_auth_flow.py`

**Step 1: E2E 인증 흐름 테스트**

- 회원가입 → 로그인 → 토큰 갱신 → 보호된 리소스 접근

```bash
# 검증 명령
docker compose exec backend pytest backend/tests/integration/test_auth_flow.py -v
# 예상: 3 passed
```

**Step 2: 커밋**

```
git add backend/tests/integration/test_auth_flow.py
git commit -m "test(phase{P}-sprint{N}): 인증 통합 테스트 추가"
```

**완료 기준:**
- ⬜ 통합 테스트 통과

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | N passed |
| 프론트 타입체크 | `cd frontend && npx tsc --noEmit` | 에러 없음 |
| 로그인 API | `curl -X POST http://localhost:8000/api/v1/auth/login ...` | JWT 토큰 반환 |
