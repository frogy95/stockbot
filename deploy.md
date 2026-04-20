# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

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
- ⬜ 전략 거부 구조화 로그(`전략 거부 [stage]` / `전략 통과 [strategy]`) 노출 확인 — 2차 스크리닝 KeyError로 신호 생성 단계 미도달, 로그 샘플링 불가 (아래 기존 버그 참고)

#### 기존 버그 (v2.2.0 비관련, 별도 핫픽스 필요)

- **2차 스크리닝 `KeyError: 'tracking_error_factor'` 반복 발생** — `modules/screening/scorer.py`에서 ETF 후보 처리 시 `tracking_error_factor` 필드 누락. v2.2.0 머지 이전(02:25~)부터 이미 발생 중이던 기존 버그로 이번 배포와 무관. 2차 스크리닝이 30초마다 실패하여 ETF 신호 생성 불가 상태. **즉각 핫픽스 검토 권고**.

#### 수동 검증 필요 항목

- DB 스키마 변경 없음 — Alembic 마이그레이션 불필요
- 신규 환경변수 없음 — Railway 환경변수 변경 불필요
- ⬜ Notion 릴리즈 노트 업데이트 (사용자 지시 후 진행)

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
