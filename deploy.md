# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 4 Sprint 2: 신호/스크리닝/설정 + 웹 매매 승인 (MVP 완성) (2026-03-31)

PR: https://github.com/frogy95/stockbot/pull/44

#### 코드 리뷰 결과 (2026-03-31)

- ✅ 보안: settings/audit 라우터 인증 의존성 적용 확인
- ✅ 모드 전환 보호: 비밀번호 재확인 + 장중 차단 + 포지션 체크 + 감사 로그 기록
- ✅ 타입 안전성: TypeScript strict 적용, apiPut 함수 추가, usePolling 함수형 intervalMs 지원
- ✅ 컴포넌트 패턴: ApprovalCard 카운트다운 타이머 메모리 누수 없음 (cleanup useEffect)
- ✅ High 이슈 (즉시 수정 완료): 스크리닝 페이지 API 응답 타입 불일치 — `GET /screening/primary`가 `{results, screened_at, total}` 객체 반환인데 프론트엔드가 배열로 기대하여 `results?.map is not a function` 런타임 에러 발생. `ScreeningResponse` 타입 추가 및 `data.results` 접근으로 수정
- ⚠️ Medium 이슈 (Phase 5에서 개선 권장): JWT HMAC 키 길이 경고 — `SECRET_KEY`가 26바이트로 RFC 7518 권장 32바이트 미만. 테스트 환경 경고이며 프로덕션 Railway 환경변수는 32자 이상으로 설정 필요

#### 자동 검증 결과 (2026-03-31)

- ✅ pytest 536 passed, 38 warnings (0 failed)
- ✅ TypeScript tsc --noEmit 오류 없음
- ✅ GET /api/v1/settings (32개 설정 반환)
- ✅ PUT /api/v1/settings/mode 비밀번호 검증 동작 (잘못된 비밀번호 403)
- ✅ GET /api/v1/audit/logs (감사 로그 조회)
- ✅ GET /api/v1/trading/signals/pending (대기 신호 조회)
- ✅ GET /api/v1/trading/signals (신호 목록)
- ✅ GET /api/v1/screening/primary (30건 결과 반환)
- ✅ GET /api/v1/trading/history (매매 이력)
- ✅ Playwright UI 검증: 대시보드, 매매신호, 스크리닝(수정 후), 매매이력, 성과분석, 설정 페이지 정상 렌더링
- ✅ 스크린샷 저장: `docs/phase/phase4/sprint2/settings-page.png`, `docs/phase/phase4/sprint2/screening-fixed.png`

#### Phase 문서 반영

- ✅ `docs/phase/phase4/phase4.md` Sprint 2 완료 표시, 미해결 사항 해결 표시, 완료 기준 업데이트

#### 수동 검증 필요 항목

- ⬜ Railway 프로덕션 환경 확인 (배포 후 `deploy-prod` 에이전트에서 수행)
- ⬜ `SECRET_KEY` Railway 환경변수 32자 이상 설정 확인 (JWT HMAC 경고 해소)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
