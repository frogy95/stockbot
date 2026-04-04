# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 4.8 Sprint 2: 재시도 스케줄 + 알림 + 모니터링 (2026-04-05)

PR: (sprint-review 완료 후 업데이트 예정)

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

#### 수동 검증 필요 항목

- ⬜ 프로덕션 배포 후 다음 거래일 08:30 premarket_retry job 동작 확인 (재시도 로그 확인)
- ⬜ 프로덕션 배포 후 포털 실패 시 [정보] 알림, 이중 실패 시 [긴급] 알림 발송 확인

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
