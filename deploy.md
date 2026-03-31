# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: 2차 스크리닝 → 매매 엔진 연결 누락 수정 (2026-03-31)

PR: https://github.com/frogy95/stockbot/pull/50

- ✅ 자동 검증 완료 항목:
  - pytest: 539 passed, 0 failed
  - 관련 테스트(test_scheduler.py, test_trading_engine.py, test_engine_approval.py): 23 passed
  - 코드 리뷰: Critical/High 이슈 없음

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - Railway 배포 후 장중 2차 스크리닝 로그에서 `process_screening_results` 호출 확인
  - Railway 배포 후 매매 신호 생성 확인 (스크리닝 통과 종목 존재 시)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
