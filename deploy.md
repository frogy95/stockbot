# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: 포털 수집기 날짜 폴백 제거 (2026-04-05)

PR: https://github.com/frogy95/stockbot/pull/82

- ✅ 자동 검증 완료 항목:
  - pytest 타겟(test_data_go_kr.py): 8 passed, 0 failed
  - 헬스체크 API: /api/v1/health — healthy

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - 다음 거래일 08:00 premarket_pipeline 실행 시 포털 0건 → KIS 폴백 발동 확인 (Railway 로그)

---

### 프로덕션 배포 - v1.2.0 (2026-04-05)

포함 스프린트: Phase 4.8 Sprint 1, Sprint 2, Sprint 3
PR: https://github.com/frogy95/stockbot/pull/81

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 자동 검증 (배포 완료 후 업데이트 예정)

- ⬜ /api/v1/health 헬스체크 확인
- ⬜ 프론트엔드 메인 페이지 접속 확인

#### 수동 검증 필요 항목

- ⬜ 다음 거래일 08:00 premarket_pipeline job 자동 실행 확인 (Railway 로그)
- ⬜ 08:30 premarket_retry job이 체인 파이프라인과 독립적으로 실행되는지 확인
- ⬜ 포털 실패 시 [정보] 알림, 이중 실패 시 [긴급] 알림 발송 확인

---

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
