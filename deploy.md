# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: market_open 미실행 장애 복구 (2026-03-31)

PR: https://github.com/frogy95/stockbot/pull/40

- ✅ 자동 검증 완료 항목:
  - pytest: 522 passed, 0 failed
  - test_scheduler.py 타겟 테스트: 8 passed (market_open_recovery 잡 포함)
  - GET /api/v1/collector/status: market_open_recovery 잡 09:05 KST 정상 등록 확인
  - MISFIRE_GRACE_TIME 300초 반영 확인

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - Railway 배포 후 다음 장 09:05 KST market_open_recovery 잡 실행 로그 확인
  - Railway 배포 후 ws_subscriptions > 0 확인 (WS 연결 성공)
  - 텔레그램 복구 알림 수신 확인 (장애 재현 시)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
