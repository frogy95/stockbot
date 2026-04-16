# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v2.1.1 (2026-04-16)

포함 스프린트: Phase 7.0.1 Sprint 1 — KIS LIVE WebSocket 연결 복구
PR: https://github.com/frogy95/stockbot/pull/138

- ⬜ Vercel 프론트엔드 자동 배포 (PR #138 머지 후 자동 시작)
- ⬜ Railway 백엔드 자동 배포 (PR #138 머지 후 자동 시작)

#### 자동 검증 (배포 완료 후 실행 필요)

- ⬜ `curl -s https://api.stockbot.choiji.kr/api/v1/health` → `{"status":"healthy"}` 확인
- ⬜ `curl -s https://api.stockbot.choiji.kr/api/v1/kis/status | jq .` → `ws_connected: true` 확인
- ⬜ 내일 08:55 KST 수동 확인: `ws_connected: true` (장 시작 전 자동 연결)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
