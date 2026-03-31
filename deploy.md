# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: Railway 장중 재시작 시 market_open 누락 버그 수정 (2026-03-31)

PR: https://github.com/frogy95/stockbot/pull/47

- ✅ 자동 검증 완료 항목:
  - pytest: 539 passed, 38 warnings, 0 failed
  - 신규 테스트 3건 통과 (장중/장전/장후 케이스)
  - 코드 리뷰: Critical/High 이슈 없음 (Medium 1건 — 함수 내 import, 배포 차단 사유 아님)

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - Railway 배포 후 장중 재시작 시 로그에서 "장중 재시작 감지" 메시지 확인
  - Railway 배포 후 ws_subscriptions > 0 확인 (WS 연결 성공)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
