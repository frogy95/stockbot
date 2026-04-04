# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 4.8 Sprint 3: 장전 파이프라인 체인 구조 전환 (2026-04-05)

PR: https://github.com/frogy95/stockbot/pull/80

#### 코드 리뷰 결과 (2026-04-05)

- ✅ 코드 리뷰 완료 — 이슈 없음 (Critical 0건, High 0건, Medium 0건)
- ✅ 락 선점/해제 구조 정상: `_run_scheduled_pipeline` 선점 → `run_premarket_pipeline` finally에서 해제
- ✅ 자동/수동 트리거 충돌 보호 확인 (`PIPELINE_RUNNING_KEY` 락)
- ✅ 개별 CronTrigger 6개 제거 + `premarket_pipeline` 단일 등록 확인

#### 자동 검증 결과 (2026-04-05)

- ✅ pytest 전체: 678 passed, 0 failed (Sprint 3 신규 4건 포함)
- ✅ `test_pipeline_chain.py` 4건 PASS (등록/락 선점/락 충돌/소요 시간 로깅)
- ✅ `test_scheduler.py` 17건 PASS (job 구조 변경 반영)

#### 수동 검증 필요 항목

- ⬜ 다음 거래일 08:00 premarket_pipeline job 자동 실행 확인 (Railway 로그)
- ⬜ 08:30 premarket_retry job이 체인 파이프라인과 독립적으로 실행되는지 확인

#### Phase 문서 반영

- ✅ `docs/phase/phase4.8/phase4.8.md` Sprint 3 완료 표시 추가 (PR #80, 2026-04-05)

---

### 프로덕션 배포 - v1.1.0 (2026-04-05)

포함 스프린트: Phase 4.8 Sprint 1, Sprint 2
PR: https://github.com/frogy95/stockbot/pull/79

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 자동 검증 (배포 완료 후 업데이트 예정)

- ⬜ /api/v1/health 헬스체크 확인
- ⬜ 프론트엔드 메인 페이지 접속 확인

#### 수동 검증 필요 항목

- ⬜ 다음 거래일 08:30 premarket_retry job 동작 확인 (재시도 로그 확인)
- ⬜ 포털 실패 시 [정보] 알림, 이중 실패 시 [긴급] 알림 발송 확인

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
