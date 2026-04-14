# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 6.2 Sprint 1 — 장전 수집 단순화 (PR 생성 완료)

포함 스프린트: Phase 6.2 Sprint 1
PR: (sprint-close 실행 후 기입 예정)

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

#### 수동 검증 항목 (배포 후 확인 필요)

- ⬜ /api/v1/health 헬스체크 확인 (프로덕션)
- ⬜ 주요 페이지 접속 확인
- ⬜ 16:00 포털 보조 수집 cron 동작 확인 (첫 거래일 모니터링)
- ⬜ 08:00 KIS 직접 수집 정상 동작 확인

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
