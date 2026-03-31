# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v0.5.0 (2026-03-31)

포함 스프린트: Phase 4 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/38

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

자동 검증 및 수동 검증 필요 항목은 배포 완료 후 업데이트합니다.

#### 수동 검증 필요 항목 (Railway 배포 후)
- ⬜ Railway 환경변수 추가 확인 (ADMIN_PASSWORD, ALLOWED_ORIGINS, JWT_EXPIRY_HOURS)
- ⬜ 프로덕션 로그인 페이지 접속 확인 (stockbot.choiji.kr)
- ⬜ 프로덕션 JWT 인증 흐름 확인 (로그인 → 대시보드 → API 응답)
- ⬜ CORS 프로덕션 origin 허용 확인 (stockbot.choiji.kr → api.stockbot.choiji.kr)

---

### Phase 4 Sprint 1: 대시보드 기본 구조 + 핵심 페이지 (2026-03-31)

PR: https://github.com/frogy95/stockbot/pull/36

#### 코드 리뷰 결과 (2026-03-31, 재검증)
- ✅ 코드 리뷰 완료 — PR #36 코멘트 작성 (https://github.com/frogy95/stockbot/pull/36#issuecomment-4159611506)
- Critical 이슈: 1건 → ✅ 수정 완료
  - `/login` 페이지에서 401 무한 리다이렉트 루프 (`apiFetch`에서 pathname 체크로 수정, commit ea10f19)
- High 이슈: 없음
- Medium 이슈: 1건 (기록만)
  - JWT HMAC 키 길이 경고: 테스트 환경에서 JWT_SECRET이 26바이트로 RFC 7518 최소 권장(32바이트) 미만. 프로덕션 환경변수 32자 이상 설정 시 해소. Phase 문서 미해결 사항 9번에 기록
- 보안: 하드코딩 시크릿 없음, 로그인 실패 5회 잠금(Redis), CORS 환경변수 기반
- 패턴 준수: App Router Route Groups, shadcn/ui, SWR 폴링 패턴 정상

#### 자동 검증 결과 (2026-03-31, 재검증)
- ✅ pytest -v 전체: 522 passed, 20 warnings
- ✅ npx tsc --noEmit: exit 0 (사용자 확인)
- ✅ npm run build: 성공 (사용자 확인)
- ✅ GET /api/v1/health: {"status":"healthy","database":"connected","redis":"connected"}
- ✅ POST /api/v1/auth/login (비밀번호 미설정): 401 "비밀번호가 설정되지 않았습니다" — 정상
- ✅ GET /api/v1/dashboard/summary (invalid token): 401 — 인증 가드 정상
- ✅ GET /api/v1/trading/positions (invalid token): 401 — trading API 인증 정상
- ✅ 프론트엔드 접속: http://localhost:3000 → 307 리다이렉트 → /login 200 OK
- ✅ Playwright: 로그인 페이지 UI 정상 렌더링 확인 (스크린샷: docs/phase/phase4/sprint1/login-page.png)

#### Phase 문서 반영 (2026-03-31)
- ✅ Phase 4 Sprint 분할 테이블: Sprint 1 ✅ 표시
- ✅ Sprint 1 상세 섹션: ✅ 완료 (PR #36, 2026-03-31) 추가
- ✅ 미해결 사항 1번(CORS), 3번(색상), 7번(shadcn/ui): ✅ 해결 표시
- ✅ 미해결 사항 9번(JWT 키 길이): Medium 이슈 추가 (Sprint 2 개선 권장)
- ✅ 완료 기준 테이블: 인증, CORS, 색상 관례 ✅ 완료로 변경

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
