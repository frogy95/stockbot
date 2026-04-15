# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: 포지션 사이징 balance_amount=0 하드코딩 결함 수정 (2026-04-15)

PR: https://github.com/frogy95/stockbot/pull/129

- ✅ 자동 검증 완료 항목:
  - 코드 리뷰: Critical/High/Medium 이슈 없음
  - pytest (관련 테스트): 31 passed, 0 failed (test_momentum_breakout, test_phase4_6_integration, test_phase4_8_integration)
  - /api/v1/health: healthy (database: connected, redis: connected)

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - 장중 매매 신호 발생 시 주문 수량 > 0 확인 (Railway 로그: `주문가능 예수금: NNNNN원`)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
