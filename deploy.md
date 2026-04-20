# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v2.2.0 (2026-04-20)

포함 변경: PR #144 (전략 거부 관측성 개선), PR #143 (역머지), PR #139/#140 (docs/.claude 재편)
PR: https://github.com/frogy95/stockbot/pull/145

- ⬜ Vercel 프론트엔드 자동 배포 (PR #145 머지 후 자동)
- ⬜ Railway 백엔드 자동 배포 (PR #145 머지 후 자동)

#### 자동 검증 (배포 완료 후 실행 예정)

- ⬜ `curl -s https://api.stockbot.choiji.kr/api/v1/health` → `{"status":"healthy"}` 확인
- ⬜ Railway 로그 오류 없음 확인 (`railway logs --lines 30 --since 5m`)
- ⬜ 프론트엔드 메인 페이지 접속 확인 (`curl -s -o /dev/null -w "%{http_code}" https://stockbot.choiji.kr`)

#### 수동 검증 필요 항목

- DB 스키마 변경 없음 — Alembic 마이그레이션 불필요
- 신규 환경변수 없음 — Railway 환경변수 변경 불필요

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
