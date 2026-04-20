# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: 2차 스크리닝 ETF tracking_error_factor KeyError 수정 (2026-04-20)

PR: https://github.com/frogy95/stockbot/pull/146

- ✅ 자동 검증 완료 항목:
  - pytest (로컬): `test_realtime_screener + test_scorer + test_screener` **62 passed** (신규 회귀 테스트 포함)
  - 타겟 API 검증: 해당 없음 (스크리닝 내부 로직 수정, API 엔드포인트 변경 없음)
  - Playwright 타겟 검증: 해당 없음 (UI 변경 없음)
  - Railway 헬스체크: `{"status":"healthy","database":"connected","redis":"connected"}` 확인
  - Railway 배포 검증: 04:07 KST부터 2차 스크리닝 30초 주기 6회 이상 `KeyError` 없이 정상 완료 확인
  - 에러 재발 없음: `04:02` 이후 `KeyError: 'tracking_error_factor'` 로그 미발생

- ⬜ 수동 검증 필요 항목:
  - `docker compose up --build` (로컬 코드 반영)
  - 장중 2차 스크리닝 통과 로그(`2차 스크리닝 필터 통과: N종목`) 지속 모니터링 (당일 정상 확인됨)
  - v2.2.0 신규 구조화 로그(`전략 거부 [stage]` / `전략 통과 [strategy]`) 샘플링 재시도 (배치에 ETF 포함 시 재발 가능성 없는지 관찰)

### 프로덕션 배포 - v2.2.0 (2026-04-20)

포함 변경: PR #144 (전략 거부 관측성 개선), PR #143 (역머지), PR #139/#140 (docs/.claude 재편)
PR: https://github.com/frogy95/stockbot/pull/145
Railway 배포 ID: f1b99e97-6435-49b1-9053-ddbae3c7cad9 (SUCCESS, 2026-04-20 11:26:35 KST)

- ✅ Vercel 프론트엔드 자동 배포 (PR #145 머지 후 자동 완료)
- ✅ Railway 백엔드 자동 배포 (컨테이너 기동 확인: 02:27:21 UTC)

#### 자동 검증 결과 (2026-04-20 11:29 KST)

- ✅ `curl -s https://api.stockbot.choiji.kr/api/v1/health` → `{"status":"healthy","database":"connected","redis":"connected"}`
- ✅ 프론트엔드 메인 페이지 접속 확인 → HTTP 200 (리디렉션 후 로그인 페이지 정상 렌더링)
- ✅ Playwright 로그인 페이지 렌더링 확인 — "StockBot" 제목, 비밀번호 입력창, 접속 버튼 정상 출력
- ✅ Railway 컨테이너 기동 시퀀스 정상 — 수집 스케줄러, 매매 엔진, OrderManager 워커, 텔레그램 웹훅 초기화 완료
- ✅ 전략 거부 구조화 로그(`전략 거부 [stage]` / `전략 통과 [strategy]`) — 위 hotfix 적용 후 ETF KeyError 해소되어 샘플링 가능

#### 수동 검증 필요 항목

- DB 스키마 변경 없음 — Alembic 마이그레이션 불필요
- 신규 환경변수 없음 — Railway 환경변수 변경 불필요
- ⬜ Notion 릴리즈 노트 업데이트 (사용자 지시 후 진행)

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
