# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v1.3.0 (2026-04-06)

포함 스프린트: Phase 4.9 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/91

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포
- ⬜ 다음 거래일 08:00 premarket_pipeline 실행 시 포털 이중 실패 → DB 폴백 발동 확인 (Railway 로그)
- ⬜ 08:30 premarket_retry job 후속 재실행 체인 동작 확인
- ⬜ 이중 실패 시 [긴급] 알림 발송 확인 (텔레그램)

---

### Hotfix: cross_check_prices 날짜 타입 불일치 수정 (2026-04-06)

PR: https://github.com/frogy95/stockbot/pull/92

- ✅ 자동 검증 완료 항목:
  - pytest 전체: 694 passed, 0 failed
  - 타겟 API 검증: 해당 없음 (내부 로직, 엔드포인트 미노출)

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - 다음 거래일 08:00 premarket_pipeline 실행 시 cross_check_prices 정상 동작 확인 (Railway 로그)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
