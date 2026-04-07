# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: KIS 일봉 수동 수집 API 추가 (2026-04-07)

PR: (PR 생성 후 업데이트)

- ✅ 자동 검증 완료 항목:
  - pytest 타겟(test_scheduler.py + test_kis_daily_collector.py): 22 passed

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - T-2 데이터 보충: `curl -X POST https://api.stockbot.choiji.kr/api/v1/collector/trigger/kis-daily/20260402`
  - pipeline-status에서 premarket.db_validation 날짜 분포 확인
  - 1차 스크리닝 재트리거: `curl -X POST https://api.stockbot.choiji.kr/api/v1/screening/trigger/primary`

---

### Hotfix: ETF/일봉 수집기 UTC 날짜 불일치 수정 (2026-04-07)

PR: (생성 중)

- ✅ 자동 검증 완료 항목:
  - pytest: test_kis_collector.py 7 passed, test_kis_daily_collector.py 5 passed
  - 전체 pytest: 690 passed, 4 failed (기존 실패 포함)

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - ETF 수집 수동 트리거: `curl -X POST https://api.stockbot.choiji.kr/api/v1/collector/trigger/etf`
  - pipeline-status에서 `etf.db_validation.passed = true` 확인

---

### 프로덕션 배포 - v1.3.0 (2026-04-06)

포함 스프린트: Phase 4.9 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/91

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

- ⬜ 다음 거래일 08:00 premarket_pipeline 실행 시 포털 이중 실패 → DB 폴백 발동 확인 (Railway 로그)
- ⬜ 08:30 premarket_retry job 후속 재실행 체인 동작 확인
- ⬜ 이중 실패 시 [긴급] 알림 발송 확인 (텔레그램)

---

### Hotfix: 포털 수집기 날짜 폴백 제거 (2026-04-05)

PR: https://github.com/frogy95/stockbot/pull/82

- ✅ 자동 검증 완료 항목:
  - pytest 타겟(test_data_go_kr.py): 8 passed, 0 failed
  - 헬스체크 API: /api/v1/health — healthy

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - 다음 거래일 08:00 premarket_pipeline 실행 시 포털 0건 → KIS 폴백 발동 확인 (Railway 로그)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
